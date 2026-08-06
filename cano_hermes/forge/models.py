"""Pipeline-tracking models for Plan Prometeo F4.

These are deliberately separate from `AgentManifest`/skill `manifest.json`:
those describe the *capability itself* (what F3's `AgentFactory`/
`SkillFactory` write to disk as the candidate artifact); `ForgeCandidate`
tracks the *pipeline's own state* around that artifact — which stage it has
cleared, what the sandbox/review produced, and which `ApprovalRequest` (if
any) is gating its promotion. One candidate id maps to exactly one artifact
and exactly one `ForgeCandidate` tracking record.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


CandidateKind = Literal["agent", "skill"]


class ForgeStage(StrEnum):
    """Pipeline stage. Distinct from `AgentStatus`/skill `status`, which
    describe the artifact's own lifecycle (quarantine/testing/active/...)."""

    PROPOSED = "proposed"
    REJECTED = "rejected"
    SANDBOXED = "sandboxed"
    SANDBOX_FAILED = "sandbox_failed"
    REVIEWED = "reviewed"
    REVIEW_FAILED = "review_failed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PROMOTED = "promoted"


class StageResult(BaseModel):
    """Outcome of one pipeline stage (sandbox or cross-review)."""

    passed: bool
    checks: dict[str, bool] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class ForgeCandidate(BaseModel):
    id: str
    kind: CandidateKind
    team: str | None = None
    definition: dict[str, Any] = Field(default_factory=dict)
    stage: ForgeStage = ForgeStage.PROPOSED
    requested_by: str = "system"
    candidate_path: str | None = None
    artifact_snapshot: dict[str, Any] = Field(
        default_factory=dict,
        description="Exact content last written to candidate_path (post status-forcing), used to reconstruct the manifest at promotion time without re-parsing disk.",
    )
    sandbox_result: StageResult | None = None
    review_result: StageResult | None = None
    approval_id: str | None = None
    promoted_path: str | None = None
    external_duplicate_warnings: list[str] = Field(default_factory=list)
    rejection_reason: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
