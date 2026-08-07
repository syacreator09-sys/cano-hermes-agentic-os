"""K17 (plan HERMES-KICKOFF) -- content control matrix: single point of
truth for "what content exists and in what state, on any channel or
campaign", backed by Baserow's `contenido` table (table id 659, database
171, workspace 126 "StarHome K17 Content" -- created live by
`infrastructure/baserow/setup_content_table.py`, confirmed against the
running local Baserow instance, not guessed).

Two callers, both read-only against this module's public API:
  - `orchestration/dashboards.py`'s `content_dashboard()` -- aggregates
    this table (+ the other K17 sources) for `GET /api/dashboard/content`.
  - `infrastructure/offices/publish/task.sh` (K9, office-publish) -- calls
    this module's CLI (`python3 -m cano_hermes.content.dedup check-key
    <key>`) before producing a draft, per the K17 mandate ("office-publish
    la consulta ANTES de cualquier draft").

Two hard rules enforced here in Python, not in Baserow (Baserow's
single_select/text fields have no cross-field conditional-required
constraint):
  1. `validate_publish_requires_video_id` -- a row with
     estado="publicado" MUST carry a non-empty video_id. Raises
     `ContentValidationError` before any network call; never silently
     written.
  2. `reject_if_duplicate` -- a dedup_key already present at
     draft-or-later state (draft, aprobado, publicado; idea/brief/
     producido are pre-commitment and never block) raises
     `ContentDedupError`.

Same "never raise on Baserow being unreachable" discipline as
`monitoring.write_metric_row`/`write_expense_row` for the read/write
helpers -- EXCEPT the two validation functions above, which are
deliberate hard stops with no network involved at all. A Baserow outage
degrades `check_dedup`'s `status` to "unknown", not to a false "clear";
callers (the CLI, `insert_content_row`) that need a conservative default
must decide what "unknown" means for them (see the CLI's own docstring),
mirroring `office-publish/task.sh`'s existing rule for its OTHER dedup
check (`upload_log_ugc.db` absent -> reported as a block, never as "no
duplicates found").
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

from cano_hermes.monitoring import BASEROW_BASE_URL, VAULT_ENV_PATH, baserow_headers

BASEROW_CONTENIDO_TABLE_ID = 659

# Lifecycle order from the K17 mandate. States at or after "draft" are
# real production commitment (a draft occupies a content slot even before
# it's approved/published) -- those are what dedup blocks against. "idea"
# and "brief" are pre-commitment: two independent ideas about the same
# angle are not yet a duplicate of real work.
ESTADO_ORDER = ["idea", "brief", "producido", "draft", "aprobado", "publicado"]
_BLOCKING_STATES = frozenset({"draft", "aprobado", "publicado"})
_MAX_PAGES = 20  # 20 * 100 rows/page = 2000 rows -- generous for this table's real size.


class ContentDedupError(RuntimeError):
    """A dedup_key already exists at draft-or-later state."""


class ContentValidationError(ValueError):
    """A content row violates a hard rule (e.g. published without a real video_id)."""


def compute_dedup_key(*, canal: str, angulo: str, fecha: str) -> str:
    """K17's suggested default: hash of canal+angulo+fecha. Callers with a
    more specific natural key (e.g. a source video_id already known to be
    unique) may pass that directly to `check_dedup`/`insert_content_row`
    instead -- this helper exists for the common case, it is not the only
    valid way to build a dedup_key."""
    raw = f"{canal.strip().lower()}|{angulo.strip().lower()}|{fecha.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _content_token() -> str | None:
    """BASEROW_CONTENT_TOKEN -- a DIFFERENT key than `monitoring.py`'s
    BASEROW_TOKEN, because the `contenido` table lives in its own Baserow
    workspace (see this module's docstring for why: BASEROW_TOKEN's
    workspace only grants management-API access via JWT, which was never
    persisted).

    Checks the environment first, the vault .env second: office-publish's
    container (K9/K17) gets the token injected as a real env var via
    docker-compose's allowlist pattern (it is never handed the host's
    vault file at all, by design -- see docker-compose.yml's comment on
    this service) while every host-side caller (tests, this repo's own
    CLI/API run natively) keeps reading the vault the same way
    `monitoring._baserow_token` does."""
    env_token = os.environ.get("BASEROW_CONTENT_TOKEN")
    if env_token:
        return env_token
    if not VAULT_ENV_PATH.exists():
        return None
    for line in VAULT_ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("BASEROW_CONTENT_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def content_configured() -> bool:
    return _content_token() is not None


def fetch_rows(*, timeout: float = 10.0) -> dict[str, Any]:
    """GETs every row of the `contenido` table (paginated, Baserow's
    default page size), never raises. Returns one of:
      {"status": "sin_token", "detail": ...}
      {"status": "error", "detail": ...}
      {"status": "ok", "rows": [ {...}, ... ]}
    """
    token = _content_token()
    if not token:
        return {"status": "sin_token", "detail": "BASEROW_CONTENT_TOKEN no encontrado en el vault"}

    rows: list[dict[str, Any]] = []
    url = (
        f"{BASEROW_BASE_URL}/api/database/rows/table/{BASEROW_CONTENIDO_TABLE_ID}/"
        "?user_field_names=true&size=100"
    )
    for _ in range(_MAX_PAGES):
        req = urllib.request.Request(url, headers=baserow_headers(token))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            return {"status": "error", "http_status": exc.code, "detail": exc.read().decode(errors="replace")[:300]}
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            return {"status": "error", "detail": f"{exc.__class__.__name__}: {exc}"}

        rows.extend(payload.get("results", []))
        url = payload.get("next")
        if not url:
            break

    return {"status": "ok", "rows": rows}


def estado_value(row: dict[str, Any]) -> str | None:
    """Baserow's row-read API (`?user_field_names=true`) returns a
    single_select field as `{"id":, "value":, "color":}`, not the bare
    string -- confirmed live against table 659 -- while row-WRITE bodies
    take the bare string (Baserow resolves it to the matching option by
    value). Normalize both shapes here so callers (including test
    fixtures, which may use either) don't have to know the difference."""
    estado = row.get("estado")
    if isinstance(estado, dict):
        return estado.get("value")
    return estado


def find_conflicting_rows(dedup_key: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pure function (no I/O) -- the part of dedup logic the test suite
    exercises directly against a fixture, without touching Baserow."""
    return [
        row for row in rows
        if row.get("dedup_key") == dedup_key and estado_value(row) in _BLOCKING_STATES
    ]


def check_dedup(dedup_key: str, *, rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Returns {"status": "clear"|"duplicate"|"unknown", "dedup_key":,
    "conflicts": [...], "detail": ...}. Pass `rows` (e.g. a fixture list)
    to skip the live Baserow fetch entirely -- this is what the test suite
    does; the real CLI/insert path leaves it None."""
    if rows is None:
        fetched = fetch_rows()
        if fetched["status"] != "ok":
            return {
                "status": "unknown", "dedup_key": dedup_key, "conflicts": [],
                "detail": fetched.get("detail", fetched["status"]),
            }
        rows = fetched["rows"]

    conflicts = find_conflicting_rows(dedup_key, rows)
    return {
        "status": "duplicate" if conflicts else "clear",
        "dedup_key": dedup_key,
        "conflicts": conflicts,
        "detail": None,
    }


def reject_if_duplicate(dedup_key: str, *, rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Raises `ContentDedupError` when `check_dedup` reports "duplicate".
    Returns the check_dedup result unchanged for "clear"/"unknown" -- the
    caller decides what "unknown" (Baserow unreachable/unconfigured)
    means for it; this function's only hard opinion is "duplicate"."""
    result = check_dedup(dedup_key, rows=rows)
    if result["status"] == "duplicate":
        raise ContentDedupError(
            f"dedup_key {dedup_key!r} ya existe en estado draft-o-posterior "
            f"({len(result['conflicts'])} fila(s) en conflicto) -- rechazado."
        )
    return result


def validate_publish_requires_video_id(fields: dict[str, Any]) -> None:
    """Hard rule (K17 mandate, mirrors F9's rule for the old UGC ledger):
    a row with estado="publicado" must carry a real, non-empty video_id.
    Raises `ContentValidationError` -- never a silent pass-through."""
    if fields.get("estado") == "publicado" and not (fields.get("video_id") or "").strip():
        raise ContentValidationError(
            "estado='publicado' requiere video_id real y no vacio -- fila rechazada."
        )


def insert_content_row(
    fields: dict[str, Any], *, rows_for_dedup: list[dict[str, Any]] | None = None, timeout: float = 10.0,
) -> dict[str, Any]:
    """Validates both hard rules, then POSTs one row to the `contenido`
    table. Raises `ContentValidationError`/`ContentDedupError` on the two
    hard rules (deliberate, no network involved for either check); once
    past those, degrades to a result dict on any Baserow error (same
    "never raise on infra flakiness" contract as
    `monitoring.write_metric_row`)."""
    validate_publish_requires_video_id(fields)
    dedup_key = fields.get("dedup_key")
    if dedup_key:
        reject_if_duplicate(dedup_key, rows=rows_for_dedup)

    token = _content_token()
    if not token:
        return {"status": "sin_token", "detail": "BASEROW_CONTENT_TOKEN no encontrado en el vault"}

    body = json.dumps(fields).encode("utf-8")
    req = urllib.request.Request(
        f"{BASEROW_BASE_URL}/api/database/rows/table/{BASEROW_CONTENIDO_TABLE_ID}/?user_field_names=true",
        data=body, method="POST",
        headers=baserow_headers(token, json_body=True),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"status": "ok", "row_id": json.loads(resp.read()).get("id")}
    except urllib.error.HTTPError as exc:
        return {"status": "error", "http_status": exc.code, "detail": exc.read().decode(errors="replace")[:300]}
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return {"status": "error", "detail": f"{exc.__class__.__name__}: {exc}"}


def _cli(argv: list[str] | None = None) -> int:
    """`python3 -m cano_hermes.content.dedup check-key <dedup_key>` --
    prints the `check_dedup` result as JSON, exit code 1 on "duplicate",
    0 on "clear" or "unknown". This is what
    `infrastructure/offices/publish/task.sh` shells out to.

    Exit 0 on "unknown" (not 1) is deliberate here, distinct from
    `reject_if_duplicate`'s Python behaviour: a CLI caller that treats a
    non-zero exit as "hard block" would otherwise turn every Baserow
    hiccup into a production stoppage. task.sh instead greps this
    command's JSON `status` field itself and decides (matching its
    existing `upload_log_ugc.db`-absent handling: report the uncertainty
    explicitly, don't silently treat it as either clear or blocked)."""
    parser = argparse.ArgumentParser(prog="python -m cano_hermes.content.dedup")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_check = sub.add_parser("check-key", help="check one dedup_key against the content matrix")
    p_check.add_argument("dedup_key")
    args = parser.parse_args(argv)

    if args.cmd == "check-key":
        result = check_dedup(args.dedup_key)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if result["status"] == "duplicate" else 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
