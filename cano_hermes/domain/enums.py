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


class OrderStatus(StrEnum):
    """Lifecycle of an `OrderRecord` -- one owner request (Telegram/CLI/API)
    that decomposes into one or more `TaskRecord`s (K6) and gets recombined
    into a single delivery (K7). Kept as its own enum rather than reusing
    `TaskStatus` because an order's states are about *fan-out/fan-in*
    (decompose, dispatch N children, aggregate their results), not a single
    unit of work moving through review/approval -- the two lifecycles only
    share DONE/FAILED/BLOCKED in spirit, not in the states that get you
    there.

    RECEIVED    -- order created, not yet decomposed.
    DECOMPOSING -- K6's auto-decompose is turning it into subtasks.
    DISPATCHED  -- subtasks exist and were sent to the Kanban bus.
    AGGREGATING -- all subtasks finished; K7's aggregator is synthesizing
                   the final artifact.
    DONE        -- aggregate_artifact written, delivery notified.
    FAILED      -- unrecoverable failure (decompose error, all subtasks
                   failed, aggregation error).
    BLOCKED     -- waiting on a human gate (e.g. a subtask needs approval
                   that isn't LOW-risk/$0 auto-approved).
    """

    RECEIVED = "received"
    DECOMPOSING = "decomposing"
    DISPATCHED = "dispatched"
    AGGREGATING = "aggregating"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"
