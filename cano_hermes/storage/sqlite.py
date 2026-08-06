from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from cano_hermes.domain.models import (
    ApprovalRequest,
    ExecutionResult,
    OrderRecord,
    TaskEvent,
    TaskRecord,
)
from cano_hermes.governance.budget import BudgetLedger


class SQLiteStore:
    def __init__(self, url: str = "sqlite:///storage/hermes.db") -> None:
        if not url.startswith("sqlite:///"):
            raise ValueError("Foundation store supports sqlite:/// URLs only")
        raw = url.removeprefix("sqlite:///")
        self.path = Path(raw).expanduser()
        if str(self.path) == ":memory:":
            self.path = Path("storage/hermes-memory.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL;")
        connection.execute("PRAGMA busy_timeout=5000;")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id, created_at);
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory_candidates (
                    id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS budget_ledger (
                    day TEXT PRIMARY KEY,
                    daily_limit_usd REAL NOT NULL,
                    spent_usd REAL NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS executions (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    executor TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    artifacts_json TEXT NOT NULL,
                    usage_json TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_executions_task ON executions(task_id, started_at);
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bridge_links (
                    starhome_id TEXT PRIMARY KEY,
                    kanban_task_id TEXT NOT NULL,
                    board TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_bridge_links_kanban_task
                    ON bridge_links(kanban_task_id);
                """
            )

    def save_task(self, task: TaskRecord) -> TaskRecord:
        payload = task.model_dump_json()
        with self.connect() as db:
            db.execute(
                """INSERT INTO tasks(id,payload,created_at,updated_at) VALUES(?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at""",
                (task.id, payload, task.created_at.isoformat(), task.updated_at.isoformat()),
            )
        return task

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM tasks WHERE id=?", (task_id,)).fetchone()
        return TaskRecord.model_validate_json(row["payload"]) if row else None

    def list_tasks(self) -> list[TaskRecord]:
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM tasks ORDER BY created_at DESC").fetchall()
        return [TaskRecord.model_validate_json(row["payload"]) for row in rows]

    def list_children(self, parent_task_id: str) -> list[TaskRecord]:
        """K5 -- filters in Python over `list_tasks()` rather than adding a
        `parent_task_id` column (+ index) to the `tasks` table. Trade-off:
        an O(n) scan of every task per call instead of an indexed lookup,
        which is the right call at this volume (this store is sized for
        dozens/hundreds of tasks, not the row counts where that scan would
        show up) and it avoids a schema migration on a table whose payload
        is already the single source of truth -- `save_task`/`get_task`
        round-trip the full `TaskRecord` JSON blob, so a new field like
        `parent_task_id` is already readable/writable with zero DDL change.
        Revisit (add the column + `CREATE INDEX`) if task volume ever grows
        enough for the scan to matter.
        """
        return [t for t in self.list_tasks() if t.parent_task_id == parent_task_id]

    def add_event(self, event: TaskEvent) -> TaskEvent:
        with self.connect() as db:
            db.execute(
                "INSERT INTO events(id,task_id,payload,created_at) VALUES(?,?,?,?)",
                (event.id, event.task_id, event.model_dump_json(), event.created_at.isoformat()),
            )
        return event

    def list_events(self, task_id: str) -> list[TaskEvent]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM events WHERE task_id=? ORDER BY created_at", (task_id,)
            ).fetchall()
        return [TaskEvent.model_validate_json(row["payload"]) for row in rows]

    def save_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        with self.connect() as db:
            db.execute(
                """INSERT INTO approvals(id,task_id,payload,created_at) VALUES(?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET payload=excluded.payload""",
                (approval.id, approval.task_id, approval.model_dump_json(), approval.created_at.isoformat()),
            )
        return approval

    def list_approvals(self) -> list[ApprovalRequest]:
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM approvals ORDER BY created_at DESC").fetchall()
        return [ApprovalRequest.model_validate_json(row["payload"]) for row in rows]

    def save_order(self, order: OrderRecord) -> OrderRecord:
        """Same pattern as `save_task`: `orders.payload` is the full
        `OrderRecord` JSON blob, so every field (including ones K6/K7 add
        later) round-trips with zero DDL change."""
        payload = order.model_dump_json()
        with self.connect() as db:
            db.execute(
                """INSERT INTO orders(id,payload,created_at,updated_at) VALUES(?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at""",
                (order.id, payload, order.created_at.isoformat(), order.updated_at.isoformat()),
            )
        return order

    def get_order(self, order_id: str) -> OrderRecord | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM orders WHERE id=?", (order_id,)).fetchone()
        return OrderRecord.model_validate_json(row["payload"]) if row else None

    def list_orders(self) -> list[OrderRecord]:
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM orders ORDER BY created_at DESC").fetchall()
        return [OrderRecord.model_validate_json(row["payload"]) for row in rows]

    def save_budget_state(self, day: str, ledger: BudgetLedger) -> BudgetLedger:
        from datetime import datetime, timezone

        with self.connect() as db:
            db.execute(
                """INSERT INTO budget_ledger(day,daily_limit_usd,spent_usd,updated_at) VALUES(?,?,?,?)
                ON CONFLICT(day) DO UPDATE SET daily_limit_usd=excluded.daily_limit_usd,
                    spent_usd=excluded.spent_usd, updated_at=excluded.updated_at""",
                (day, ledger.daily_limit_usd, ledger.spent_usd, datetime.now(timezone.utc).isoformat()),
            )
        return ledger

    def get_budget_state(self, day: str) -> BudgetLedger | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT daily_limit_usd, spent_usd FROM budget_ledger WHERE day=?", (day,)
            ).fetchone()
        if row is None:
            return None
        return BudgetLedger(daily_limit_usd=row["daily_limit_usd"], spent_usd=row["spent_usd"])

    def save_execution(self, execution: ExecutionResult, usage: dict | None = None) -> ExecutionResult:
        """Structured, queryable record of one executor run — the durable
        counterpart to the truncated `task.execution_id`/`summary` event
        TaskEngine already writes. `usage` is stored separately from
        `execution.metrics` because it can be sourced differently per
        executor (hermes-agent's --usage-file JSON vs. claude-code's parsed
        stream-json `usage`/`total_cost_usd`), so callers pass it explicitly
        rather than ExecutionService guessing which metrics keys count."""
        with self.connect() as db:
            db.execute(
                """INSERT INTO executions(
                    id,task_id,executor,status,summary,metrics_json,artifacts_json,usage_json,started_at,finished_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status, summary=excluded.summary,
                    metrics_json=excluded.metrics_json, artifacts_json=excluded.artifacts_json,
                    usage_json=excluded.usage_json, finished_at=excluded.finished_at""",
                (
                    execution.execution_id,
                    execution.task_id,
                    execution.executor,
                    execution.status,
                    execution.summary,
                    json.dumps(execution.metrics),
                    json.dumps(execution.artifacts),
                    json.dumps(usage or {}),
                    execution.started_at.isoformat(),
                    execution.finished_at.isoformat(),
                ),
            )
        return execution

    @staticmethod
    def _execution_row_to_dict(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "task_id": row["task_id"],
            "executor": row["executor"],
            "status": row["status"],
            "summary": row["summary"],
            "metrics": json.loads(row["metrics_json"]),
            "artifacts": json.loads(row["artifacts_json"]),
            "usage": json.loads(row["usage_json"]),
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
        }

    def get_executions_for_task(self, task_id: str) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM executions WHERE task_id=? ORDER BY started_at", (task_id,)
            ).fetchall()
        return [self._execution_row_to_dict(row) for row in rows]

    def get_execution(self, execution_id: str) -> dict | None:
        """K3 -- single-row lookup backing `GET /api/executions/{id}`, so a
        caller that enqueued a run through `QueueService` can poll it by the
        id it got back at enqueue time instead of scanning by task."""
        with self.connect() as db:
            row = db.execute("SELECT * FROM executions WHERE id=?", (execution_id,)).fetchone()
        return self._execution_row_to_dict(row) if row is not None else None

    def add_memory_candidate(self, candidate_id: str, namespace: str, payload: dict) -> None:
        from datetime import datetime, timezone
        with self.connect() as db:
            db.execute(
                "INSERT INTO memory_candidates VALUES(?,?,?,?,?)",
                (candidate_id, namespace, json.dumps(payload), "candidate", datetime.now(timezone.utc).isoformat()),
            )

    def save_bridge_link(self, starhome_id: str, kanban_task_id: str, board: str) -> dict:
        """K6 -- one row per StarHome id (order or task) that has been
        dispatched to Kanban, resolvable in both directions:
        `get_bridge_link_by_starhome_id` (StarHome already knows the id it
        dispatched) and `get_bridge_link_by_kanban_task_id` (K7's inbound
        webhook only knows the Kanban task id and needs to find the
        StarHome side). Upserts on `starhome_id`: a retried dispatch for the
        same order overwrites its own link rather than erroring, matching
        the idempotency `kanban_bridge.submit_order_to_kanban` already
        gets from the CLI's own `--idempotency-key` dedup."""
        from datetime import datetime, timezone

        created_at = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute(
                """INSERT INTO bridge_links(starhome_id,kanban_task_id,board,created_at) VALUES(?,?,?,?)
                ON CONFLICT(starhome_id) DO UPDATE SET
                    kanban_task_id=excluded.kanban_task_id, board=excluded.board""",
                (starhome_id, kanban_task_id, board, created_at),
            )
        return {
            "starhome_id": starhome_id,
            "kanban_task_id": kanban_task_id,
            "board": board,
            "created_at": created_at,
        }

    @staticmethod
    def _bridge_link_row_to_dict(row: sqlite3.Row) -> dict:
        return {
            "starhome_id": row["starhome_id"],
            "kanban_task_id": row["kanban_task_id"],
            "board": row["board"],
            "created_at": row["created_at"],
        }

    def get_bridge_link_by_starhome_id(self, starhome_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM bridge_links WHERE starhome_id=?", (starhome_id,)
            ).fetchone()
        return self._bridge_link_row_to_dict(row) if row is not None else None

    def get_bridge_link_by_kanban_task_id(self, kanban_task_id: str) -> dict | None:
        """K7 will call this from the inbound webhook handler to resolve a
        Kanban task lifecycle event back to the StarHome order/task that
        dispatched it. `kanban_task_id` is not unique-constrained (no
        current caller writes more than one row per kanban task, but
        nothing here assumes that either) -- returns the first match by
        `created_at`."""
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM bridge_links WHERE kanban_task_id=? ORDER BY created_at LIMIT 1",
                (kanban_task_id,),
            ).fetchone()
        return self._bridge_link_row_to_dict(row) if row is not None else None
