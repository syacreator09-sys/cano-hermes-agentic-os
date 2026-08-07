from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from .enums import AgentStatus, ApprovalStatus, OrderStatus, RiskLevel, TaskStatus


def utcnow() -> datetime:
    return datetime.now(UTC)


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
    # K5 (plan HERMES-KICKOFF, gap 1): when set, this task is a subtask of
    # another task OR of an `OrderRecord` (K6 decomposes one order into many
    # tasks with parent_task_id=order.id -- orders and tasks share the same
    # id-string namespace convention, so no separate "parent kind" field is
    # needed). Settable at creation so K6's decompose step can stamp it in
    # one write instead of create-then-patch.
    parent_task_id: str | None = None


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
    def validate_action_groups(self) -> AgentActions:
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
    """A human-in-the-loop gate raised by PermissionEngine/BudgetLedger.

    Every field below is mandatory by design (Plan Prometeo F3): an approval
    that Cano can't fully evaluate — what it costs, what's left in the
    budget, which office asked, and what evidence backs it — is not a real
    approval. Pydantic rejects construction with a clear per-field message
    when any of them is missing, instead of silently defaulting.
    """

    id: str = Field(default_factory=lambda: f"approval-{uuid4().hex[:12]}")
    task_id: str
    action: str
    motivo: str = Field(min_length=1, description="Por qué se requiere aprobación humana")
    risk: RiskLevel
    requested_by: str
    costo_estimado_usd: float = Field(ge=0, description="Costo estimado en USD de la acción solicitada")
    presupuesto_restante: float = Field(description="Presupuesto restante en el BudgetLedger del día, al momento de la solicitud")
    canal: str = Field(min_length=1, description="Oficina o canal que origina la solicitud")
    evidencia: str = Field(min_length=1, description="Ruta a un draft/dry-run que respalda la solicitud")
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = Field(default_factory=utcnow)
    resolved_at: datetime | None = None
    resolved_by: str | None = None

    @property
    def reason(self) -> str:
        """Backward-compatible alias for `motivo` (pre-F3 field name)."""
        return self.motivo


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


class OrderCreate(BaseModel):
    """Request shape for `POST /api/orders` -- mirrors the TaskCreate/
    TaskRecord split so the API never lets a caller set `status`,
    `subtask_ids` or `aggregate_artifact` directly; those are owned by the
    engine (K5 forces RECEIVED at creation; K6/K7 own the rest)."""

    objective: str = Field(min_length=3, max_length=10_000)
    source: Literal["telegram", "cli", "api"]
    budget: Budget = Field(default_factory=Budget)
    # T10 (plan POTENCIA, 2026-08-07): optional hint so the K6 kanban
    # bridge can route straight to a K9 office instead of always landing
    # in unassigned triage (see kanban_bridge.submit_order_to_kanban).
    # Same domain strings Conductor.assign already accepts
    # (cano_hermes/orchestration/conductor.py:DOMAIN_TEAMS) -- an unknown
    # or omitted domain is not an error, it just keeps the old triage
    # behavior.
    domain: str | None = None


class OrderRecord(OrderCreate):
    """One owner request -- "yo mando UNA orden" (plan HERMES-KICKOFF) --
    that K6 decomposes into `subtask_ids` (TaskRecord.parent_task_id ==
    this id) and K7 recombines into `aggregate_artifact`. Deliberately
    thin at K5: no decompose/aggregate logic lives here, only the shape
    those phases will fill in.
    """

    id: str = Field(default_factory=lambda: f"order-{uuid4().hex[:12]}")
    status: OrderStatus = OrderStatus.RECEIVED
    subtask_ids: list[str] = Field(default_factory=list)
    aggregate_artifact: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
