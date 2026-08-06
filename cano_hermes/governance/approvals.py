from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from cano_hermes.domain.enums import ApprovalStatus
from cano_hermes.domain.models import ApprovalRequest
from cano_hermes.storage.sqlite import SQLiteStore

logger = logging.getLogger(__name__)


class ApprovalService:
    def __init__(
        self,
        store: SQLiteStore,
        on_request: Callable[[ApprovalRequest], None] | None = None,
    ) -> None:
        """`on_request`, when given, is called with the freshly persisted
        `ApprovalRequest` every time `request()` raises one -- K4's
        `NotificationService.on_approval_requested` hooks in here so Cano
        gets the full schema (motivo, costo, canal, evidencia) over
        Telegram the moment a task needs his sign-off, not only when he
        happens to check the dashboard. Wrapped in try/except for the same
        reason as `TaskEngine.on_transition`: a notification failure must
        never take the approval-request flow down with it."""
        self.store = store
        self.on_request = on_request

    def request(self, approval: ApprovalRequest) -> ApprovalRequest:
        saved = self.store.save_approval(approval)
        if self.on_request is not None:
            try:
                self.on_request(saved)
            except Exception:
                logger.warning("on_request callback failed for approval %s", saved.id, exc_info=True)
        return saved

    def resolve(self, approval_id: str, approved: bool, actor: str) -> ApprovalRequest:
        approval = next((a for a in self.store.list_approvals() if a.id == approval_id), None)
        if approval is None:
            raise KeyError(approval_id)
        if approval.requested_by == actor:
            raise PermissionError("An actor cannot approve its own request")
        approval.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        approval.resolved_at = datetime.now(timezone.utc)
        approval.resolved_by = actor
        return self.store.save_approval(approval)
