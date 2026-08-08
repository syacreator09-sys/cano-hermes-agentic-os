"""Wires `telegram.send_telegram_message` to the three transitions Cano
actually needs pulled to him instead of having to poll the dashboard for:
DONE, FAILED, and a pending APPROVAL -- K4 (plan HERMES-KICKOFF, gap 6).

Design: `NotificationService` is not a hard dependency anything imports and
calls explicitly. Instead `TaskEngine.transition()` and
`ApprovalService.request()` each accept an optional observer callback
(`on_transition` / `on_request`) invoked, best-effort, after the state
change is durably persisted. `api/dependencies.py` wires
`notification_service()` into both `engine()` and `approvals()`; every call
site that already goes through those two methods -- the K2 low-risk
auto-complete, the manual `POST /api/tasks/{id}/complete`, `ExecutionService`
failing a run, the K0 reaper failing an orphaned task, `ExecutionService`
raising an approval -- is covered for free, with zero new call sites to
remember. Anything that constructs `TaskEngine`/`ApprovalService` directly
(most of the test suite) simply doesn't pass the callback and behaves
exactly as before K4.

Every method here must never raise: `send_telegram_message` itself already
swallows every failure (see `telegram.py`), and `TaskEngine.transition`/
`ApprovalService.request` additionally wrap the callback in a try/except as
a second safety net, so a bug in this module can't take a state transition
down with it either.
"""

from __future__ import annotations

from pathlib import Path

from cano_hermes.domain.enums import TaskStatus
from cano_hermes.domain.models import ApprovalRequest, OrderRecord, TaskRecord
from cano_hermes.storage.sqlite import SQLiteStore

from .telegram import TELEGRAM_MAX_DOCUMENT_BYTES, send_telegram_document, send_telegram_message

_ARTIFACTS_PREVIEW_LIMIT = 10

# A2 (plan AUTONOMÍA TOTAL, 2026-08-08): only these are worth Cano actually
# opening on his phone as a document -- the rest of an order's artifacts
# (workspace scratch files, raw JSON, etc.) stay text-only in the summary
# message above, same as before A2. .txt added in A7 after a real master
# order (order-8f945ff6915e) proved K7's aggregator always writes its
# synthesis report as synthesis-summary.txt -- a genuinely rich final
# report Cano would want pushed as a document, not just listed by path.
_DELIVERABLE_SUFFIXES = {".md", ".png", ".mp4", ".pdf", ".txt"}


class NotificationService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    # -- TaskEngine.transition hook -----------------------------------
    def on_transition(self, task: TaskRecord, status: TaskStatus, payload: dict) -> None:
        if status == TaskStatus.DONE:
            self._notify_done(task)
        elif status == TaskStatus.FAILED:
            self._notify_failed(task, payload)

    def _latest_execution(self, task_id: str) -> dict | None:
        """The execution row backing this task's DONE, not the transition
        payload -- payload shape differs by caller (K2 auto-complete carries
        `artifacts`, the manual `/complete` endpoint carries only a free-text
        `reason`), while the execution row is the one place `summary` and
        `artifacts` always live together, regardless of which path closed
        the task."""
        rows = self.store.get_executions_for_task(task_id)
        return rows[-1] if rows else None

    def _notify_done(self, task: TaskRecord) -> None:
        execution = self._latest_execution(task.id) or {}
        summary = execution.get("summary") or "(sin resumen de ejecución)"
        artifacts = execution.get("artifacts") or []

        lines = [
            f"✅ DONE — {task.title}",
            f"task_id: {task.id}",
            f"resumen: {summary}",
        ]
        if artifacts:
            lines.append(f"artifacts ({len(artifacts)}):")
            lines.extend(f"  - {path}" for path in artifacts[:_ARTIFACTS_PREVIEW_LIMIT])
            remaining = len(artifacts) - _ARTIFACTS_PREVIEW_LIMIT
            if remaining > 0:
                lines.append(f"  ... y {remaining} más")
        send_telegram_message("\n".join(lines))

    def _notify_failed(self, task: TaskRecord, payload: dict) -> None:
        # ExecutionService's FAILED transition carries {"summary": ...};
        # the K0 reaper's carries {"reason": "orphaned-on-restart"} instead
        # -- read whichever is present.
        reason = payload.get("summary") or payload.get("reason") or "motivo no especificado"
        lines = [
            f"❌ FAILED — {task.title}",
            f"task_id: {task.id}",
            f"motivo: {reason}",
        ]
        send_telegram_message("\n".join(lines))

    # -- aggregator.close_order_with_synthesis hook (K7) -----------------
    def notify_order_done(self, order: OrderRecord, artifacts: list[str]) -> None:
        """`OrderRecord` transitions do NOT flow through
        `TaskEngine.transition` (only `TaskRecord` does) -- `save_order` is
        called directly wherever an order changes state (K5/K6/K7's
        `aggregator.py`) -- so unlike `on_transition` above, this is not an
        observer wired into a generic hook; `aggregator.close_order_with_
        synthesis` calls it explicitly, once, right after the order lands
        on DONE. Kept in this module (not inlined in aggregator.py) so
        every Telegram message StarHome ever sends has one owner and one
        format convention."""
        lines = [
            f"✅ ORDEN DONE — {order.objective.strip().splitlines()[0][:120]}",
            f"order_id: {order.id}",
        ]
        if artifacts:
            lines.append(f"artifacts ({len(artifacts)}):")
            lines.extend(f"  - {path}" for path in artifacts[:_ARTIFACTS_PREVIEW_LIMIT])
            remaining = len(artifacts) - _ARTIFACTS_PREVIEW_LIMIT
            if remaining > 0:
                lines.append(f"  ... y {remaining} más")
        send_telegram_message("\n".join(lines))
        self._deliver_documents(order, artifacts)

    def _deliver_documents(self, order: OrderRecord, artifacts: list[str]) -> None:
        """A2 (plan AUTONOMÍA TOTAL, 2026-08-08): the summary message above
        only ever listed artifact paths as text -- Cano had to already be
        on this machine to open one. Send the real deliverable files
        (md/png/mp4/pdf, within Telegram's own size limit -- checked here
        too, not just inside send_telegram_document, so an oversized file
        never even attempts an upload for every artifact in a big batch)
        as actual Telegram documents. Best-effort per file: one failing
        upload must never block the rest of the batch."""
        caption_prefix = order.objective.strip().splitlines()[0][:80]
        for path_str in artifacts:
            path = Path(path_str)
            if path.suffix.lower() not in _DELIVERABLE_SUFFIXES:
                continue
            if not path.is_file() or path.stat().st_size > TELEGRAM_MAX_DOCUMENT_BYTES:
                continue
            send_telegram_document(path_str, f"{caption_prefix} — {path.name}")

    # -- ApprovalService.request hook ----------------------------------
    def on_approval_requested(self, approval: ApprovalRequest) -> None:
        lines = [
            "⏳ APPROVAL pendiente",
            f"approval_id: {approval.id}",
            f"task_id: {approval.task_id}",
            f"canal: {approval.canal}",
            f"motivo: {approval.motivo}",
            f"riesgo: {approval.risk.value}",
            f"costo_estimado_usd: {approval.costo_estimado_usd:.4f}",
            f"presupuesto_restante_usd: {approval.presupuesto_restante:.4f}",
            f"evidencia: {approval.evidencia}",
        ]
        send_telegram_message("\n".join(lines))
