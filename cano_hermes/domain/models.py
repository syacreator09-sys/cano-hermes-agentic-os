from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

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


class AgentManifest(BaseModel):
    id: str
    name: str
    team: str
    objective: str
    status: AgentStatus = AgentStatus.CANDIDATE
    runtime: str = "hermes"
    model_profiles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
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
