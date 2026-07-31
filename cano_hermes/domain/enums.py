from enum import StrEnum


class TaskStatus(StrEnum):
    INBOX = "inbox"
    PLANNED = "planned"
    READY = "ready"
    RUNNING = "running"
    REVIEW = "review"
    APPROVAL = "approval"
    DONE = "done"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentStatus(StrEnum):
    DRAFT = "draft"
    CANDIDATE = "candidate"
    QUARANTINE = "quarantine"
    TESTING = "testing"
    APPROVED = "approved"
    ACTIVE = "active"
    STALE = "stale"
    ARCHIVED = "archived"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
