"""K7 (plan HERMES-KICKOFF, gap 2 continuation) -- Kanban -> StarHome bridge,
inbound half.

Companion to `bridge/kanban_bridge.py` (K6, the outbound half: StarHome ->
Kanban). This module is the target of the `starhome-bridge` user plugin
living outside this repo at `~/.hermes/plugins/starhome-bridge/` -- CERO
changes to hermes-agent itself, per the task's hard constraint. See that
plugin's `__init__.py` docstring for the wire contract (payload shape,
`X-StarHome-Signature` HMAC-SHA256 header) and for confirmation that the
underlying `kanban_task_claimed`/`kanban_task_completed`/`kanban_task_blocked`
hooks are real, wired, best-effort hooks (`hermes_cli/kanban_db.py`'s
`_fire_kanban_lifecycle_hook`, confirmed live against hermes-agent
v0.20.0's own test suite, `tests/hermes_cli/test_kanban_lifecycle_hooks.py`)
-- not something this phase had to invent or assume.

The load-bearing design decision here, adapting the plan to what K6 actually
built (documented because the plan's K7 section assumed something K6 didn't
do): `kanban_bridge.submit_order_to_kanban` (K6) registers exactly ONE
`bridge_links` row per order -- `order.id` -> the root triage task's own
kanban_task_id. hermes-agent's own decomposer (`kanban_decompose.py`) may
fan that root out into child kanban tasks entirely *inside* its own board
DB, but StarHome was never told about those children (no `TaskRecord` rows
with `parent_task_id=order.id` get created by K6) and their kanban_task_ids
were never registered in `bridge_links` either. So:

- Lifecycle events for a fanned-out CHILD kanban task resolve to no
  `bridge_links` row at all here -- they are logged and ignored (200, no-op,
  never a 401/500), exactly like an event for a kanban_task_id from Cano's
  personal board or any other work this bridge doesn't own.
- The root task's OWN `kanban_task_claimed`/`completed`/`blocked` events are
  the only ones that resolve, and per `kanban_decompose.py`'s own docstring
  ("The root task stays alive and becomes the parent of every leaf child,
  so when the whole graph completes the root wakes back up") the root's
  `completed` event only fires once every internal child has already
  finished -- whether hermes fanned the order out or ran it as one task.
  That makes the root's `completed` event exactly the fan-in signal K7
  needs, with zero extra plumbing: this bridge does not need to poll or
  reconstruct hermes's internal task graph to know "is this order's kanban
  work done".
- `list_children(order_id)` (K5) is still consulted first (`_order_children_status`
  below) so that if a *future* phase starts creating real StarHome
  `TaskRecord` subtasks under an order (K8+), the "all children terminal"
  path activates automatically without another rewrite of this module --
  today it is simply always empty, so the root-completed signal above is
  what actually fires in practice.

`bridge_links` can also resolve directly to a plain `TaskRecord` (not an
`OrderRecord`) -- not exercised by any current caller (K6 only ever links
orders), but handled here for forward compatibility with a future direct
task-level dispatch, reusing `TaskEngine.transition` (and, transitively,
K4's notification wiring) instead of a parallel state machine.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cano_hermes.domain.enums import OrderStatus, TaskStatus
from cano_hermes.domain.models import TaskEvent
from cano_hermes.orchestration import aggregator
from cano_hermes.orchestration.execution_service import ExecutionService
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.storage.sqlite import SQLiteStore

logger = logging.getLogger(__name__)

VALID_EVENTS = {"claimed", "completed", "blocked"}

# TaskRecord statuses from which each event is accepted -- guards against a
# redelivered event (the starhome-bridge plugin's retry queue is
# at-least-once by design) re-running a transition that already happened.
_TASK_CLAIMABLE_FROM = {TaskStatus.INBOX, TaskStatus.PLANNED, TaskStatus.READY}
_TASK_COMPLETABLE_FROM = {TaskStatus.RUNNING}
_TASK_BLOCKABLE_FROM = {
    TaskStatus.INBOX,
    TaskStatus.PLANNED,
    TaskStatus.READY,
    TaskStatus.RUNNING,
}


def verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    """Constant-time HMAC-SHA256 check. Fails closed: an unset `secret`
    (never configured on this side) or a missing/empty `signature` header
    always returns False -- there is no "skip verification" mode."""
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _write_event_artifact(artifacts_root: Path, starhome_id: str, payload: dict[str, Any]) -> str:
    """Persist the raw kanban event payload StarHome received -- the closest
    thing to "an artifact/result the hook reported" a lifecycle hook (as
    opposed to a file attachment) actually carries. Lands under
    `storage/artifacts/<starhome_id>/kanban-events/` so it shows up
    alongside whatever `complete_execution` (K2) or the synthesis task
    (K7's aggregator) already writes for the same id."""
    event = str(payload.get("event", "event"))
    kanban_task_id = str(payload.get("task_id", "unknown"))
    ts = payload.get("ts")
    suffix = f"{ts:.6f}" if isinstance(ts, (int, float)) else datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    destination = artifacts_root / starhome_id / "kanban-events" / f"{event}-{kanban_task_id}-{suffix}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(destination)


def _ingest_cost_if_present(budget, payload: dict[str, Any]) -> None:
    """Forward-compatible only: none of the three kanban lifecycle hooks
    (`hermes_cli/plugins.py`'s `VALID_HOOKS` docstring: `task_id`, `board`,
    `assignee`, `run_id`, `profile_name`, plus `summary`/`reason`) carry a
    cost figure today -- `kanban_db.py`'s `tasks`/`task_runs` tables have no
    `cost_usd`/`estimated_cost_usd` column to source one from either. This
    is therefore a documented no-op in practice, wired against
    `BudgetService`'s real API (`record_spend(amount, force=True)`,
    confirmed in `governance/budget.py`) so ingestion activates for free
    the moment a future hermes-agent version -- or a future revision of the
    starhome-bridge plugin that shells out to `hermes kanban show --json`
    for run cost -- starts populating `cost_usd` on the payload."""
    if budget is None:
        return
    amount = payload.get("cost_usd")
    if isinstance(amount, (int, float)) and amount > 0:
        budget.record_spend(float(amount), force=True)


async def handle_kanban_event(
    *,
    engine: TaskEngine,
    store: SQLiteStore,
    execution_service: ExecutionService,
    notifier: Any,
    budget: Any,
    artifacts_root: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Core handler behind `POST /api/bridge/kanban-events`, called only
    AFTER `verify_signature` has already passed (the route owns the 401).

    Never raises for a malformed-but-signed payload or an unresolvable
    kanban_task_id -- those are legitimate "nothing to do here" outcomes
    (see module docstring), not errors; the endpoint always answers 200 for
    a validly-signed request. Returns a small dict describing what
    happened, useful for tests and for the route's own JSON response.
    """
    event = payload.get("event")
    kanban_task_id = payload.get("task_id")
    if event not in VALID_EVENTS or not kanban_task_id:
        logger.warning("kanban-events: malformed payload ignored: %r", payload)
        return {"status": "ignored", "reason": "malformed payload"}

    link = store.get_bridge_link_by_kanban_task_id(str(kanban_task_id))
    if link is None:
        logger.debug("kanban-events: no bridge_links row for kanban_task_id=%s -- ignored", kanban_task_id)
        return {"status": "ignored", "reason": "unknown kanban_task_id"}

    _ingest_cost_if_present(budget, payload)
    starhome_id = link["starhome_id"]

    order = store.get_order(starhome_id)
    if order is not None:
        artifact_path = _write_event_artifact(artifacts_root, starhome_id, payload)
        result = await _handle_order_event(
            engine=engine,
            store=store,
            execution_service=execution_service,
            notifier=notifier,
            artifacts_root=artifacts_root,
            order=order,
            event=event,
            payload=payload,
        )
        result["artifact"] = artifact_path
        return result

    task = store.get_task(starhome_id)
    if task is not None:
        artifact_path = _write_event_artifact(artifacts_root, starhome_id, payload)
        result = _handle_task_event(engine=engine, task_id=task.id, event=event, payload=payload)
        result["artifact"] = artifact_path
        return result

    logger.warning(
        "kanban-events: bridge_links row for %s points at neither an order nor a task (starhome_id=%s)",
        kanban_task_id,
        starhome_id,
    )
    return {"status": "ignored", "reason": "dangling bridge_links row"}


async def _handle_order_event(
    *,
    engine: TaskEngine,
    store: SQLiteStore,
    execution_service: ExecutionService,
    notifier: Any,
    artifacts_root: Path,
    order,
    event: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if event == "claimed":
        # OrderStatus (domain/enums.py) has no distinct "in-flight" state
        # between DISPATCHED and AGGREGATING -- unlike TaskStatus, which has
        # RUNNING. DISPATCHED already means "sent to kanban, work under
        # way", so a claim is recorded as an audit event only; see module
        # docstring for why this is a deliberate reading of the plan's
        # "claimed -> RUNNING" line, not an oversight.
        store.add_event(TaskEvent(
            task_id=order.id, kind="order.kanban_claimed", actor="kanban-bridge",
            payload={"kanban_task_id": payload.get("task_id"), "assignee": payload.get("assignee")},
        ))
        return {"status": "handled", "resolved": "order", "order_status": order.status.value}

    if event == "blocked":
        if order.status != OrderStatus.DISPATCHED:
            return {"status": "ignored", "reason": f"order already {order.status.value}"}
        order.status = OrderStatus.BLOCKED
        order.updated_at = datetime.now(UTC)
        store.save_order(order)
        store.add_event(TaskEvent(
            task_id=order.id, kind="order.blocked", actor="kanban-bridge",
            payload={"kanban_task_id": payload.get("task_id"), "reason": payload.get("reason")},
        ))
        return {"status": "handled", "resolved": "order", "order_status": order.status.value}

    # event == "completed"
    if order.status != OrderStatus.DISPATCHED:
        # Already AGGREGATING/DONE/FAILED/BLOCKED -- a redelivered event
        # (the starhome-bridge plugin's retry queue is at-least-once) must
        # not re-run synthesis or double-notify. Checked here, before ever
        # calling into `aggregator`, so "aggregated" below always means
        # "this call is the one that just did it", not "the order happens
        # to already be DONE from an earlier call".
        return {
            "status": "ignored", "reason": f"order already {order.status.value}",
            "resolved": "order", "order_status": order.status.value, "aggregated": False,
        }

    children = store.list_children(order.id)
    if children:
        if not aggregator.all_terminal(children):
            store.add_event(TaskEvent(
                task_id=order.id, kind="order.kanban_child_completed", actor="kanban-bridge",
                payload={"kanban_task_id": payload.get("task_id")},
            ))
            return {"status": "handled", "resolved": "order", "order_status": order.status.value, "aggregated": False}

    trigger_summary = str(payload.get("summary") or "(sin resumen)")
    updated = await aggregator.close_order_with_synthesis(
        engine=engine,
        store=store,
        execution_service=execution_service,
        notifier=notifier,
        artifacts_root=artifacts_root,
        order=order,
        trigger_summary=trigger_summary,
    )
    return {
        "status": "handled",
        "resolved": "order",
        "order_status": updated.status.value,
        "aggregated": updated.status == OrderStatus.DONE,
    }


def _handle_task_event(*, engine: TaskEngine, task_id: str, event: str, payload: dict[str, Any]) -> dict[str, Any]:
    task = engine.require(task_id)

    if event == "claimed":
        if task.status not in _TASK_CLAIMABLE_FROM:
            return {"status": "ignored", "reason": f"task already {task.status.value}"}
        engine.transition(task_id, TaskStatus.RUNNING, "kanban-bridge", {"kanban_task_id": payload.get("task_id")})
        return {"status": "handled", "resolved": "task", "task_status": TaskStatus.RUNNING.value}

    if event == "blocked":
        if task.status not in _TASK_BLOCKABLE_FROM:
            return {"status": "ignored", "reason": f"task already {task.status.value}"}
        engine.transition(
            task_id, TaskStatus.BLOCKED, "kanban-bridge",
            {"kanban_task_id": payload.get("task_id"), "reason": payload.get("reason")},
        )
        return {"status": "handled", "resolved": "task", "task_status": TaskStatus.BLOCKED.value}

    # event == "completed"
    if task.status not in _TASK_COMPLETABLE_FROM:
        return {"status": "ignored", "reason": f"task already {task.status.value}"}
    summary = str(payload.get("summary") or "(sin resumen)")
    next_status = TaskStatus.DONE if task.risk.value == "low" else TaskStatus.REVIEW
    engine.transition(
        task_id, next_status, "kanban-bridge",
        {"kanban_task_id": payload.get("task_id"), "summary": summary[:500]},
    )
    return {"status": "handled", "resolved": "task", "task_status": next_status.value}
