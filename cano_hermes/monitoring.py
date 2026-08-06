"""Plan Prometeo F13 — shared read-only monitoring helpers.

Both `scripts/daily_cycle.py` (the cron-triggered batch job) and
`cano_hermes.api.app`'s `GET /api/dashboard` need the same snapshots:
connection health, F11 office container status, F9's UGC performance
(honestly reported as "no hay datos suficientes" -- F9 was a fixture
dry-run, not live), usage-file cost ingestion, and `validate.py`'s
PASS/FLAG audit. Centralizing them here means:

  - the dashboard endpoint never re-runs a network-touching audit (Apify
    GET) on every browser refresh -- it reads the on-disk JSON mirror
    `daily_cycle.py`/`connection_matrix.py` already wrote;
  - the two callers can't drift on what "healthy" or "sin datos" means.

Everything here is read-only and free -- no paid API calls, no writes
outside `reports/` and (for `write_metric_row`) the Baserow instance this
machine already runs locally (F11).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VAULT_ENV_PATH = Path.home() / ".secrets/credenciales/credenciales/.env"
BASEROW_BASE_URL = "http://localhost:8085"
# Table IDs for the 4 F11 tables (database 34, workspace "StarHome
# Prometeo"). Baserow assigns these once at table creation and they are
# not sequential (other trashed workspaces consumed intermediate ids) --
# confirmed live against the running instance, not guessed:
#   solicitudes=130  gastos=136  productos_ugc=140  metricas_diarias=141
BASEROW_METRICAS_TABLE_ID = 141

OFFICE_CONTAINER_NAMES = ["office-analytics", "office-ugc", "office-content", "office-publish"]


# --------------------------------------------------------------------------
# Connections (F2/F13) -- read the on-disk JSON mirror, never re-run live.
# --------------------------------------------------------------------------
def latest_connection_matrix_summary() -> dict[str, Any] | None:
    """Most recent JSON summary written by `scripts/connection_matrix.py`
    (`compute_and_render`). Returns None if the audit has never run in
    this environment -- callers must treat that as "sin datos", not as a
    failure."""
    reports_dir = ROOT / "reports"
    candidates = sorted(reports_dir.glob("connection-matrix-*.json"))
    if not candidates:
        return None
    try:
        return json.loads(candidates[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def run_connection_matrix() -> dict[str, Any]:
    """Actually runs the F2 audit (writes the .md + .json report). Used by
    `daily_cycle.py`'s step 1 -- the dashboard endpoint should use
    `latest_connection_matrix_summary()` instead so a GET stays instant."""
    from scripts import connection_matrix

    return connection_matrix.compute_and_render()


# --------------------------------------------------------------------------
# Health (StarHome API, hermes status, nexus doctor, docker stats)
# --------------------------------------------------------------------------
def check_starhome_health(base_url: str = "http://localhost:8787") -> dict[str, Any]:
    try:
        req = urllib.request.Request(f"{base_url}/api/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            return {"status": "ok", "http_status": resp.getcode(), "body": body}
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError) as exc:
        return {"status": "error", "detail": f"{exc.__class__.__name__}: {exc}"}


def _run_cli(binary: str, args: list[str], timeout: int = 30) -> dict[str, Any]:
    if shutil.which(binary) is None:
        return {"status": "sin_binario", "detail": f"'{binary}' no está en PATH"}
    try:
        result = subprocess.run(
            [binary, *args], capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "error", "detail": str(exc)}
    return {
        "status": "ok" if result.returncode == 0 else "error",
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
    }


def check_hermes_status() -> dict[str, Any]:
    return _run_cli("hermes", ["status"])


def check_nexus_doctor() -> dict[str, Any]:
    return _run_cli("nexus", ["doctor"])


def check_docker_stats() -> dict[str, Any]:
    """`docker stats --no-stream` for whatever F11 containers are up right
    now. Empty `containers` is the expected steady state -- offices are
    on-demand (F11: no restart policy), not daemons."""
    if shutil.which("docker") is None:
        return {"status": "sin_binario", "detail": "'docker' no está en PATH"}
    try:
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format",
             "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "error", "detail": str(exc)}
    if result.returncode != 0:
        return {"status": "error", "detail": result.stderr[-1000:]}
    containers = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) == 4:
            containers.append(dict(zip(("name", "cpu", "mem_usage", "mem_percent"), parts)))
    return {"status": "ok", "containers": containers}


def office_container_status() -> dict[str, str]:
    """`docker ps` snapshot for the 4 F11 offices: 'up' | 'down' | 'unknown'.
    'down' is the expected steady state (on-demand containers, F11)."""
    if shutil.which("docker") is None:
        return {name: "unknown" for name in OFFICE_CONTAINER_NAMES}
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {name: "unknown" for name in OFFICE_CONTAINER_NAMES}
    if result.returncode != 0:
        return {name: "unknown" for name in OFFICE_CONTAINER_NAMES}
    running = set(result.stdout.split())
    return {name: ("up" if name in running else "down") for name in OFFICE_CONTAINER_NAMES}


# --------------------------------------------------------------------------
# UGC performance (F9) -- honest "sin datos suficientes", never invented.
# --------------------------------------------------------------------------
def ugc_performance_summary() -> dict[str, Any]:
    """F9's UGC-Affiliate pipeline was an explicit $0 dry-run against
    fixtures (reports/ugc-affiliate-dry-run-2026-08-06.md) -- there is no
    live CPV/CTR/conversion feed in this environment. Report that
    honestly instead of classifying ESCALAR/MANTENER/MATAR off synthetic
    numbers."""
    dry_run_report = ROOT / "reports" / "ugc-affiliate-dry-run-2026-08-06.md"
    return {
        "classification": "sin_datos_suficientes",
        "note": (
            "F9 fue un dry-run gratuito contra fixtures de "
            "cano-ai-command-center/01-offices/ugc-affiliate (139 registros, "
            "19 con comision>0); no hay CPV/CTR/conversion en vivo en este "
            "entorno para clasificar ESCALAR/MANTENER/MATAR con datos reales."
        ),
        "source_report": str(dry_run_report) if dry_run_report.exists() else None,
    }


# --------------------------------------------------------------------------
# Costs -- usage-*.json (F3's BudgetService input) + Higgsfield credits.
# --------------------------------------------------------------------------
def usage_files_summary(workspace_root: Path | None = None) -> dict[str, Any]:
    root = workspace_root or (ROOT / "storage" / "workspaces")
    files = sorted(root.glob("**/usage-*.json")) if root.exists() else []
    entries = []
    total_cost = 0.0
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        cost = None
        for field in ("estimated_cost_usd", "cost_usd", "total_cost_usd"):
            value = data.get(field)
            if isinstance(value, (int, float)):
                cost = float(value)
                break
        entries.append({"file": str(f.relative_to(ROOT)), "cost_usd": cost})
        if cost:
            total_cost += cost
    return {
        "usage_files_found": len(files),
        "total_cost_usd": round(total_cost, 4),
        "entries": entries,
    }


def higgsfield_credits_summary() -> dict[str, Any]:
    """No versioned Higgsfield credit tracker exists in any contract repo
    audited (factory-ia-channel-v5, ugc-commerce-studio) -- both mention
    Higgsfield as the paid provider in their CLAUDE.md but neither ships a
    script that reads/writes a credits ledger. Documented as absent, not
    invented."""
    return {
        "status": "sin_tracker",
        "note": (
            "No se encontró ningún tracker de créditos Higgsfield versionado "
            "en los repos de contrato revisados (factory-ia-channel-v5, "
            "ugc-commerce-studio). AUDIT_GAPS.md de ugc-affiliate (F9) ya "
            "documentó por separado: plan FREE, 8 créditos, cuenta "
            "insuficiente para producir."
        ),
    }


# --------------------------------------------------------------------------
# Audit proxy -- scripts/validate.py PASS/FLAG.
# --------------------------------------------------------------------------
def run_validate() -> dict[str, Any]:
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate.py")],
            capture_output=True, text=True, timeout=60, check=False, cwd=str(ROOT),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "FLAG", "detail": str(exc)}
    if result.returncode == 0:
        payload: dict[str, Any] = {}
        lines = [line for line in result.stdout.strip().splitlines() if line]
        if lines:
            try:
                payload = json.loads("\n".join(lines))
            except json.JSONDecodeError:
                payload = {"raw_stdout": result.stdout[-2000:]}
        # validate.py's own JSON payload also has a "status" key (its
        # value is always "ok" when returncode==0) -- pop it before
        # merging so it can't silently shadow our PASS/FLAG classification
        # via dict-literal key precedence.
        payload.pop("status", None)
        return {"status": "PASS", **payload}
    return {"status": "FLAG", "stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:]}


# --------------------------------------------------------------------------
# Baserow (F11) -- write-only helper for `metricas_diarias`. Never prints
# BASEROW_TOKEN; reads it from the vault .env this machine already uses
# for every other credential (F2's VAULT_PATH), not from this repo's own
# .env (Settings/pydantic never sees it either).
# --------------------------------------------------------------------------
def _baserow_token() -> str | None:
    if not VAULT_ENV_PATH.exists():
        return None
    for line in VAULT_ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("BASEROW_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def baserow_configured() -> bool:
    return _baserow_token() is not None


def write_metric_row(fecha: str, oficina: str, metrica: str, valor: float, nota: str = "") -> dict[str, Any]:
    """POSTs one row to the `metricas_diarias` Baserow table (F11). Never
    raises -- a Baserow outage or a missing/under-scoped token must not
    take down the rest of the daily cycle; the caller records the result
    dict in the report instead."""
    token = _baserow_token()
    if not token:
        return {"status": "sin_token", "detail": "BASEROW_TOKEN no encontrado en el vault"}

    body = json.dumps({
        "fecha": f"{fecha}T00:00:00Z",
        "oficina": oficina,
        "metrica": metrica,
        "valor": valor,
        "nota": nota,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{BASEROW_BASE_URL}/api/database/rows/table/{BASEROW_METRICAS_TABLE_ID}/?user_field_names=true",
        data=body, method="POST",
        headers={"Authorization": f"Token {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"status": "ok", "row_id": json.loads(resp.read()).get("id")}
    except urllib.error.HTTPError as exc:
        return {"status": "error", "http_status": exc.code, "detail": exc.read().decode(errors="replace")[:300]}
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return {"status": "error", "detail": f"{exc.__class__.__name__}: {exc}"}
