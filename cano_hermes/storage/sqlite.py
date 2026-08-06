from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from cano_hermes.domain.models import ApprovalRequest, TaskEvent, TaskRecord
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

    def add_memory_candidate(self, candidate_id: str, namespace: str, payload: dict) -> None:
        from datetime import datetime, timezone
        with self.connect() as db:
            db.execute(
                "INSERT INTO memory_candidates VALUES(?,?,?,?,?)",
                (candidate_id, namespace, json.dumps(payload), "candidate", datetime.now(timezone.utc).isoformat()),
            )
