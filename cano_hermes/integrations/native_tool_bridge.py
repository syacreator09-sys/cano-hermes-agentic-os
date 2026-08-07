"""K19 (plan HERMES-KICKOFF) -- the `PENDING_NATIVE_TOOL` handoff
mechanism `docs/OPERATIONS.md` (K15) designed but deliberately left
unwired ("esta fase documenta el patrón, no lo cablea... queda para
cuando K19 lo necesite en firme"). This module IS that wiring, built
generic on purpose so `business/cass.py` and every future business view
(Cano Digital, LUZYA) share one file-backed job/result protocol instead
of each re-inventing it.

Steps 1-2 and 4 of OPERATIONS.md's design, concretely:
  1. A StarHome job that needs an MCP only a Claude.ai session can call
     (Shopify, Meta/Facebook, Canva, ...) is marked `PENDING_NATIVE_TOOL`
     instead of hanging or failing -- `request_job` writes that request
     as a real artifact on disk (`storage/pending_native_tool/<job_id>.
     request.json`), never a synchronous call the caller waits on.
  2. The request carries exactly what OPERATIONS.md's step 2 asks for:
     which MCP tool(s), the already-resolved params, and where the result
     must be written back (`storage/pending_native_tool/<job_id>.
     result.json`) for a *future* Claude session to pick up (resolved by
     explicit human/operator instruction -- "resuelve los jobs
     PENDING_NATIVE_TOOL de StarHome" -- never automatically).
  4. `request_job` never trusts a result file just because it exists --
     it is only accepted (status flips to `RESOLVED_NATIVE_TOOL`) once it
     has the minimal expected shape (`job_id` matches, a `data` key is
     present). Anything else (missing fields, wrong job_id, invalid JSON)
     is reported back as still-pending with a `detail` explaining why,
     mirroring the "never declare DONE without validating the result's
     shape" rule Factory V5's ImageGen bridge already enforces.

Nothing in this module ever calls an `mcp__claude_ai_*` tool, an HTTP
client, or writes/publishes/spends anything on an external platform --
its only I/O is reading/writing small JSON files under `storage/
pending_native_tool/`. Resolving a job (step 3, actually invoking the
MCP) can only ever happen from a real Claude.ai session with that MCP
connected -- structurally impossible from this module or from the
StarHome/hermes-agent background processes that call it.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PENDING_NATIVE_TOOL_DIR = ROOT / "storage" / "pending_native_tool"


def request_job(
    job_id: str, *, mcp_tools: list[str], params: dict[str, Any], purpose: str,
    jobs_dir: Path | None = None,
) -> dict[str, Any]:
    """Idempotently ensures a `PENDING_NATIVE_TOOL` request file exists
    for `job_id` (writes it once; a second call for the same job_id never
    overwrites an already-queued request or its `created_at`), then
    reports the job's current state:
      - `PENDING_NATIVE_TOOL` -- no result file yet, or an existing one
        failed shape validation (detail explains which).
      - `RESOLVED_NATIVE_TOOL` -- a validated result file was found;
        `data` carries whatever the resolving Claude session wrote.

    Read-mostly for the common case (an already-queued job with no result
    yet costs one `Path.is_file()` + one read of the request file); the
    only write is the one-time initial request file.
    """
    dir_path = jobs_dir or PENDING_NATIVE_TOOL_DIR
    dir_path.mkdir(parents=True, exist_ok=True)
    request_path = dir_path / f"{job_id}.request.json"
    result_path = dir_path / f"{job_id}.result.json"

    if request_path.is_file():
        try:
            request_payload = json.loads(request_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            request_payload = None
    else:
        request_payload = None

    if request_payload is None:
        request_payload = {
            "job_id": job_id,
            "created_at": dt.datetime.now(dt.UTC).isoformat(),
            "mcp_tools": mcp_tools,
            "params": params,
            "purpose": purpose,
            "resolve_by_writing": str(result_path),
        }
        request_path.write_text(json.dumps(request_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    if not result_path.is_file():
        return {
            **request_payload, "status": "PENDING_NATIVE_TOOL",
            "detail": "esperando que una sesion Claude futura invoque el MCP y escriba el resultado en resolve_by_writing",
        }

    try:
        result_payload = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            **request_payload, "status": "PENDING_NATIVE_TOOL",
            "detail": f"result file existe pero es invalido ({exc.__class__.__name__}) -- se ignora, sigue pendiente",
        }

    if not isinstance(result_payload, dict) or result_payload.get("job_id") != job_id or "data" not in result_payload:
        return {
            **request_payload, "status": "PENDING_NATIVE_TOOL",
            "detail": "result file no tiene la forma esperada (job_id coincidente + campo data) -- se ignora, sigue pendiente",
        }

    return {
        **request_payload, "status": "RESOLVED_NATIVE_TOOL",
        "resolved_at": result_payload.get("resolved_at"), "data": result_payload["data"],
    }
