"""K9 (plan HERMES-KICKOFF, gaps 12/13) -- start/stop the Docker "offices"
(infrastructure/offices/docker-compose.yml) on demand, so StarHome can bring
an office up only when work actually needs it instead of leaving all 5
running all the time.

Hard cap: at most `settings.offices_max_active` (default 2) offices active
simultaneously -- this machine's whole Docker budget (16GB/3CPU, HERMES-
KICKOFF ceiling) assumes at most 2 offices running at once alongside
Baserow (2g/1cpu) and the F3 sandbox (512m/1cpu, counted separately). A 3rd
`start()` call while 2 are already up is REJECTED with a clear
`OfficeLauncherError`, not queued or blocked -- an office worker can take
an unbounded amount of wall-clock time (kanban tasks, not one-shot cycles,
since K9), so silently blocking the caller until "room" appears could hang
indefinitely. The caller (K16's autonomous loop, eventually) decides
whether to retry, wait, or pick a different office.

Each office maps 1:1 onto exactly one Docker Compose `profiles:` entry in
infrastructure/offices/docker-compose.yml (`analytics`, `ugc`, `content`,
`publish`, `market-intel`) and, per K9's office.yaml <-> Docker reconciliation
(see K9 report), onto one kanban profile. `ensure_office_for_profile()` is
the wiring point K16 (or any future auto-dispatch code) can call with a
task's `kanban_profile` string to make sure the right container is up
before a task assigned to it can be claimed -- optional per the K9 mandate,
included because the mapping table already had to exist for K9's own
report, so exposing it programmatically costs little.

This module only shells out to `docker compose` (the same programmatic
boundary K6's `bridge/kanban_bridge.py` uses for `hermes kanban`) -- it
never imports docker-py or talks to the Docker socket directly, and it
never runs with elevated privileges itself.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from cano_hermes.config import settings

logger = logging.getLogger(__name__)

COMPOSE_SUBPROCESS_TIMEOUT_SECONDS = 60.0

# K9 office.yaml <-> Docker office mapping (see K9 report for the full
# rationale table). Only profiles with a real Docker office (isolation:
# docker in their office.yaml) appear here -- hermes-research and
# hermes-guiones stay native (isolation: folder) and have no entry, on
# purpose: ensure_office_for_profile() returns None for them rather than
# inventing a container that doesn't exist.
PROFILE_TO_OFFICE: dict[str, str] = {
    "hermes-monitor": "analytics",
    "hermes-ugc": "ugc",
    "hermes-produccion": "content",
    "hermes-distribucion": "publish",
    "hermes-market-intel": "market-intel",
}

KNOWN_OFFICES = frozenset(PROFILE_TO_OFFICE.values())


class OfficeLauncherError(RuntimeError):
    """`docker compose` failed, timed out, or the 2-office cap was hit."""


@dataclass(frozen=True)
class OfficeLaunchResult:
    office: str
    action: str  # "started" | "already_running" | "stopped" | "not_running"
    active_offices: frozenset[str]


def _compose_dir() -> Path:
    return Path(settings.repository_root) / "infrastructure" / "offices"


def _run_compose(args: list[str], *, timeout: float = COMPOSE_SUBPROCESS_TIMEOUT_SECONDS) -> subprocess.CompletedProcess[str]:
    compose_dir = _compose_dir()
    try:
        return subprocess.run(
            ["docker", "compose", *args],
            cwd=compose_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise OfficeLauncherError("comando 'docker' no encontrado en esta maquina") from exc
    except subprocess.TimeoutExpired as exc:
        raise OfficeLauncherError(f"'docker compose {' '.join(args)}' excedio el timeout de {timeout}s") from exc
    except OSError as exc:
        raise OfficeLauncherError(f"'docker compose {' '.join(args)}' fallo al lanzarse: {exc}") from exc


class OfficeLauncher:
    """Start/stop offices under the `offices_max_active` cap.

    Stateless by design (no in-process bookkeeping of "what's running") --
    `active()` always asks Docker directly via `docker compose ps`, so this
    class is safe to construct fresh per request and stays correct across
    StarHome restarts, manual `docker compose` calls from a terminal, etc.
    """

    def __init__(self, max_active: int | None = None) -> None:
        self.max_active = max_active if max_active is not None else settings.offices_max_active

    def active(self) -> frozenset[str]:
        """Offices with at least one running container right now, queried
        live from Docker (never cached) -- `docker compose ps --format
        json` lists every service with a running container in this
        project, regardless of which `profiles:` name it was started
        under; we intersect with `KNOWN_OFFICES` so an unrelated service
        someone adds to this compose file later can't accidentally count
        against the cap."""
        result = _run_compose(["ps", "--format", "json", "--status", "running"])
        if result.returncode != 0:
            stderr = (result.stderr or "").strip() or "(sin stderr)"
            raise OfficeLauncherError(f"'docker compose ps' fallo (codigo {result.returncode}): {stderr}")
        running: set[str] = set()
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            import json

            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            service = row.get("Service")
            office = service.removeprefix("office-") if isinstance(service, str) else None
            if office in KNOWN_OFFICES:
                running.add(office)
        return frozenset(running)

    def start(self, office: str) -> OfficeLaunchResult:
        if office not in KNOWN_OFFICES:
            raise OfficeLauncherError(
                f"'{office}' no es una oficina Docker conocida (opciones: {sorted(KNOWN_OFFICES)})"
            )
        current = self.active()
        if office in current:
            return OfficeLaunchResult(office=office, action="already_running", active_offices=current)
        if len(current) >= self.max_active:
            raise OfficeLauncherError(
                f"no se puede levantar '{office}': ya hay {len(current)} oficinas activas "
                f"({sorted(current)}), techo = {self.max_active}. Baja una oficina primero "
                f"(OfficeLauncher.stop) o espera a que termine su ciclo."
            )
        result = _run_compose(["--profile", office, "up", "-d"], timeout=180.0)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip() or "(sin stderr)"
            raise OfficeLauncherError(f"no se pudo levantar office-{office} (codigo {result.returncode}): {stderr}")
        logger.info("office-%s levantada bajo demanda", office)
        return OfficeLaunchResult(office=office, action="started", active_offices=self.active())

    def stop(self, office: str) -> OfficeLaunchResult:
        if office not in KNOWN_OFFICES:
            raise OfficeLauncherError(
                f"'{office}' no es una oficina Docker conocida (opciones: {sorted(KNOWN_OFFICES)})"
            )
        current = self.active()
        if office not in current:
            return OfficeLaunchResult(office=office, action="not_running", active_offices=current)
        result = _run_compose(["--profile", office, "down"], timeout=60.0)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip() or "(sin stderr)"
            raise OfficeLauncherError(f"no se pudo bajar office-{office} (codigo {result.returncode}): {stderr}")
        logger.info("office-%s bajada", office)
        return OfficeLaunchResult(office=office, action="stopped", active_offices=self.active())


def ensure_office_for_profile(kanban_profile: str, launcher: OfficeLauncher | None = None) -> OfficeLaunchResult | None:
    """K9 optional wiring point for K16: given a task's `kanban_profile`
    (e.g. "hermes-ugc"), start the Docker office that serves it if it
    isn't already running. Returns None (no-op) for profiles that don't
    map to a Docker office (native folder/none-isolation profiles like
    hermes-research/hermes-guiones, or an unrecognized profile) -- callers
    must not treat None as an error, it means "nothing to launch"."""
    office = PROFILE_TO_OFFICE.get(kanban_profile)
    if office is None:
        return None
    return (launcher or OfficeLauncher()).start(office)
