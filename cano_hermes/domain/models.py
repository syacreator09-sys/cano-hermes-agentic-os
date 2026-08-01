from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from .enums import AgentStatus, ApprovalStatus, RiskLevel, TaskStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Budget(BaseModel):
    max_cost_usd: float = Field(default=0.0, ge=0)
    max_turns: int = Field(default=12, ge=1, le=200)
    timeout_seconds: int = Field(default=900, ge=5, le=86_400)


class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    objective: str = Field(min_length=3, max_length=10_000)
    project: str = "general"
    domain: str = "general"
    risk: RiskLevel = RiskLevel.LOW
    requested_runtime: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    budget: Budget = Field(default_factory=Budget)


class TaskRecord(TaskCreate):
    id: str = Field(default_factory=lambda: f"task-{uuid4().hex[:12]}")
    status: TaskStatus = TaskStatus.INBOX
    assigned_agent: str | None = None
    route_profile: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class TaskEvent(BaseModel):
    id: str = Field(default_factory=lambda: f"evt-{uuid4().hex[:12]}")
    task_id: str
    kind: str
    actor: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class AgentActions(BaseModel):
    allowed: list[str] = Field(default_factory=list)
    approval_required: list[str] = Field(default_factory=list)
    prohibited: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_action_groups(self) -> "AgentActions":
        groups = {
            "allowed": self.allowed,
            "approval_required": self.approval_required,
            "prohibited": self.prohibited,
        }

        normalized_groups: dict[str, set[str]] = {}
        for group_name, values in groups.items():
            normalized = [value.strip() for value in values]
            if any(not value for value in normalized):
                raise ValueError(f"empty action in {group_name}")
            if len(normalized) != len(set(normalized)):
                raise ValueError(f"duplicate action in {group_name}")
            normalized_groups[group_name] = set(normalized)

        group_names = list(normalized_groups)
        for index, left_name in enumerate(group_names):
            for right_name in group_names[index + 1 :]:
                overlap = normalized_groups[left_name] & normalized_groups[right_name]
                if overlap:
                    joined = ", ".join(sorted(overlap))
                    raise ValueError(
                        f"actions cannot appear in both {left_name} and {right_name}: {joined}"
                    )
        return self


class AgentManifest(BaseModel):
    id: str
    name: str
    team: str
    objective: str
    description: str = ""
    status: AgentStatus = AgentStatus.CANDIDATE
    runtime: str = "hermes"
    model_profiles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    actions: AgentActions = Field(default_factory=AgentActions)
    permissions: dict[str, Any] = Field(default_factory=dict)
    budget: Budget = Field(default_factory=Budget)
    evaluations: list[str] = Field(default_factory=list)
    max_concurrency: int = Field(default=1, ge=1, le=8)


class ApprovalRequest(BaseModel):
    id: str = Field(default_factory=lambda: f"approval-{uuid4().hex[:12]}")
    task_id: str
    action: str
    reason: str
    risk: RiskLevel
    requested_by: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = Field(default_factory=utcnow)
    resolved_at: datetime | None = None
    resolved_by: str | None = None


class ExecutionResult(BaseModel):
    execution_id: str = Field(default_factory=lambda: f"exec-{uuid4().hex[:12]}")
    task_id: str
    executor: str
    status: str
    summary: str
    exit_code: int | None = None
    artifacts: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime = Field(default_factory=utcnow)
