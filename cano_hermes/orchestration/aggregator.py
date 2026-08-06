"""K7 (plan HERMES-KICKOFF, gap 2 continuation) -- fan-in: order -> synthesis
-> DONE.

Called reactively from `bridge/inbound.py` when a `completed` kanban event
resolves to an `OrderRecord` and either (a) `list_children(order_id)` is
empty -- today's reality, see `inbound.py`'s module docstring for why an
empty child list here still means "the order's kanban work just finished",
not "nothing has happened yet" -- or (b) every tracked child is terminal.
No separate poller: the reactive check happens inline on the event that
plausibly completes the set, exactly as the K7 task asked for.

Swarm detection (planner -> workers -> verifier -> synthesizer): the task
instructions asked this module to distinguish "did a real hermes Swarm run"
from "one plain task ran" and collect the swarm's own synthesizer output
when it did. That is not cleanly observable from here. hermes-agent's kanban
Swarm v1 (`hermes kanban swarm`) is a *separate* code path from the
plain `create --triage` + auto-decompose flow K6 uses -- StarHome never
calls `hermes kanban swarm`, and the three lifecycle hooks this bridge
listens to (`kanban_task_claimed/completed/blocked`) carry no field
indicating whether the completing task was a swarm synthesizer, a fan-out
child, or a plain single task (see the hook kwargs list in
`hermes_cli/plugins.py`'s `VALID_HOOKS` docstring -- there is no
`workflow`/`swarm_id`/`role` kwarg). Reconstructing that would mean shelling
out to `hermes kanban show <id> --json` and inferring role from task_links
topology and title conventions -- heuristic, easy to get wrong silently,
and out of scope for what K7 needs to work correctly today. Per the task's
own guidance, this is documented as a known limitation and the same
simplified path is used for ALL cases: every order's fan-in always runs
StarHome's own single tier-0 synthesis task below, whether the kanban side
happened to run a swarm, a fan-out, or a single task -- the synthesis
objective is built from whatever `summary` the resolving event carried, so
if hermes's own synthesizer already produced a good summary (swarm case),
that text flows straight into StarHome's synthesis prompt as source
material rather than being discarded and redone from scratch.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from cano_hermes.domain.enums import OrderStatus, RiskLevel, TaskStatus
from cano_hermes.domain.models import Budget, OrderRecord, TaskCreate, TaskEvent, TaskRecord
from cano_hermes.orchestration.execution_service import ExecutionService
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.storage.sqlite import SQLiteStore

SYNTHESIS_DOMAIN = "synthesis"
SYNTHESIS_PROJECT = "starhome-orders"


def all_terminal(children: list[TaskRecord]) -> bool:
    """True only when `children` is non-empty and every task in it is DONE
    or FAILED. An empty list is deliberately NOT "all terminal" here --
    "no children tracked yet" and "every tracked child finished" are
    different states; callers that want to treat "no children" as its own
    trigger (today's actual case, see module docstring) check for that
    separately rather than relying on this returning True vacuously."""
    if not children:
        return False
    return all(t.status in (TaskStatus.DONE, TaskStatus.FAILED) for t in children)


def _copy_tree(source: Path, destination: Path) -> list[str]:
    if not source.exists():
        return []
    copied: list[str] = []
    for item in sorted(source.rglob("*")):
        if item.is_dir():
            continue
        target = destination / item.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        copied.append(str(target))
    return copied


async def close_order_with_synthesis(
    *,
    engine: TaskEngine,
    store: SQLiteStore,
    execution_service: ExecutionService,
    notifier,
    artifacts_root: Path,
    order: OrderRecord,
    trigger_summary: str,
) -> OrderRecord:
    """Runs the K7 fan-in for one order: DISPATCHED -> AGGREGATING -> spins
    up ONE synthesis `TaskRecord` through the *existing* `ExecutionService`
    (executor defaults to `hermes-agent` with no model/provider override,
    which resolves to hermes-agent's own configured default profile --
    `kimi-k2.6`/`kimi` in `~/.hermes/config.yaml` on this machine, i.e.
    tier-0 -- see `ExecutionService._resolve_executor_id`: no
    `assigned_agent` + domain not in {research, engineering} always falls
    back to `hermes-agent`) -> folds that task's own artifacts into
    `storage/artifacts/<order_id>/final/` -> DONE.

    Deliberately reuses `ExecutionService`/`TaskEngine.transition` instead
    of a bespoke run-and-notify path: `complete_execution` (K2) already
    copies the synthesis task's own workspace into
    `storage/artifacts/<synthesis_task_id>/` and auto-closes it
    REVIEW -> DONE for LOW risk (every synthesis task is created at LOW
    risk, unconditionally), and that DONE transition already fires K4's
    Telegram notification for the *task* via `TaskEngine`'s `on_transition`
    wiring -- Cano gets one message for the synthesis task completing and a
    second, order-level one below (`notifier.notify_order_done`), since
    `OrderRecord` transitions do NOT go through `TaskEngine.transition` (see
    `inbound.py`'s module docstring: "esto dispara la notificación de K4
    automáticamente" does not hold for orders the way it does for tasks --
    documented difference from the plan's assumption, not an oversight).

    Idempotent: a no-op (returns `order` unchanged) unless
    `order.status == OrderStatus.DISPATCHED` -- the `starhome-bridge`
    plugin's retry queue is at-least-once, so a redelivered `completed`
    event must never re-run synthesis or double-notify.
    """
    if order.status != OrderStatus.DISPATCHED:
        return order

    order.status = OrderStatus.AGGREGATING
    order.updated_at = datetime.now(UTC)
    store.save_order(order)
    store.add_event(TaskEvent(
        task_id=order.id, kind="order.aggregating", actor="aggregator",
        payload={"trigger_summary": trigger_summary[:500]},
    ))

    synthesis_task = engine.create(TaskCreate(
        title=f"Síntesis — {order.objective.strip().splitlines()[0][:80]}",
        objective=(
            "Sintetiza en un informe final, claro y accionable, el resultado de esta orden.\n\n"
            f"Orden original:\n{order.objective}\n\n"
            f"Resultado reportado por el trabajo despachado a kanban:\n{trigger_summary}\n"
        ),
        project=SYNTHESIS_PROJECT,
        domain=SYNTHESIS_DOMAIN,
        risk=RiskLevel.LOW,
        parent_task_id=order.id,
        budget=Budget(),
    ))

    result = await execution_service.run(synthesis_task.id)

    final_dir = artifacts_root / order.id / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    copied = _copy_tree(artifacts_root / synthesis_task.id, final_dir)
    summary_path = final_dir / "synthesis-summary.txt"
    summary_path.write_text(result.summary or "(sin resumen)", encoding="utf-8")
    copied.append(str(summary_path))

    refreshed = engine.require(synthesis_task.id)
    if refreshed.status != TaskStatus.DONE:
        # Shouldn't happen on the LOW-risk-always-auto-closes path -- but an
        # order must never be left silently stuck in AGGREGATING if the run
        # itself failed or somehow needed a human. Two distinct "needed a
        # human" states exist and both map to BLOCKED, never FAILED: REVIEW
        # (`completion.py` only auto-closes LOW risk; a run that somehow
        # produced non-LOW risk lands here) and APPROVAL (K8 live demo,
        # 2026-08-06, `order-c334c655cf60` -- under this machine's real
        # `execution_mode=supervised` default, `PermissionEngine` routes
        # every non-dry-run action through approval_required *before* it
        # runs, regardless of the synthesis task's LOW risk; the original
        # code here only anticipated the post-run REVIEW gate and
        # mis-classified this equally-legitimate pre-run human gate as an
        # unexpected failure). Both are exactly the "genuinely waiting on a
        # human gate" case `api/app.py`'s `dispatch_order` docstring
        # describes BLOCKED as being reserved for -- a pending approval is
        # not a subprocess/infrastructure failure, so FAILED must never be
        # the label for it.
        order.status = (
            OrderStatus.BLOCKED
            if refreshed.status in (TaskStatus.REVIEW, TaskStatus.APPROVAL)
            else OrderStatus.FAILED
        )
        order.updated_at = datetime.now(UTC)
        store.save_order(order)
        store.add_event(TaskEvent(
            task_id=order.id, kind=f"order.{order.status.value}", actor="aggregator",
            payload={"synthesis_task_id": synthesis_task.id, "synthesis_status": refreshed.status.value},
        ))
        return order

    order.status = OrderStatus.DONE
    order.aggregate_artifact = str(final_dir)
    order.updated_at = datetime.now(UTC)
    store.save_order(order)
    store.add_event(TaskEvent(
        task_id=order.id, kind="order.done", actor="aggregator",
        payload={"synthesis_task_id": synthesis_task.id, "artifacts": copied},
    ))
    if notifier is not None:
        notifier.notify_order_done(order, copied)
    return order
