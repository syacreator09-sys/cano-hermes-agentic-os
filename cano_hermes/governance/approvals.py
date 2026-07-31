from __future__ import annotations

from datetime import datetime, timezone

from cano_hermes.domain.enums import ApprovalStatus
from cano_hermes.domain.models import ApprovalRequest
from cano_hermes.storage.sqlite import SQLiteStore


class ApprovalService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def request(self, approval: ApprovalRequest) -> ApprovalRequest:
        return self.store.save_approval(approval)

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
