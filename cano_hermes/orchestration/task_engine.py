from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from cano_hermes.domain.enums import TaskStatus
from cano_hermes.domain.models import TaskCreate, TaskEvent, TaskRecord
from cano_hermes.storage.sqlite import SQLiteStore

from .conductor import Conductor

logger = logging.getLogger(__name__)


class TaskEngine:
    def __init__(
        self,
        store: SQLiteStore,
        conductor: Conductor,
        on_transition: Callable[[TaskRecord, TaskStatus, dict], None] | None = None,
    ) -> None:
        """`on_transition`, when given, is called after every `transition()`
        with the up-to-date task, its new status and the transition payload
        -- K4's `NotificationService.on_transition` hooks in here so DONE/
        FAILED get a Telegram message regardless of which call site (K2
        auto-complete, the manual `/complete` endpoint, `ExecutionService`
        failing a run, the K0 reaper) triggered it. Wrapped in try/except:
        a notification failure must never take a state transition down with
        it (see notifications/telegram.py, which itself already never
        raises -- this is a second, defensive layer)."""
        self.store = store
        self.conductor = conductor
        self.on_transition = on_transition

    def create(self, request: TaskCreate) -> TaskRecord:
        task = TaskRecord.model_validate(request.model_dump())
        self.store.save_task(task)
        self.store.add_event(TaskEvent(task_id=task.id, kind="task.created", actor="cano", payload={"title": task.title}))
        return task

    def plan(self, task_id: str) -> TaskRecord:
        task = self.require(task_id)
        assignment = self.conductor.assign(task)
        task.assigned_agent = assignment.agent_id
        task.route_profile = assignment.route_profile
        task.status = TaskStatus.PLANNED
        task.updated_at = datetime.now(timezone.utc)
        self.store.save_task(task)
        self.store.add_event(
            TaskEvent(
                task_id=task.id,
                kind="task.planned",
                actor="conductor",
                payload={
                    "agent": assignment.agent_id,
                    "route_profile": assignment.route_profile,
                    "rationale": assignment.rationale,
                },
            )
        )
        return task

    def reap_orphaned(self, actor: str = "system") -> list[TaskRecord]:
        """Fail any task left in RUNNING state by an unclean restart.

        A task can only be RUNNING while a live process is executing it. If the
        process died (crash, restart, kill -9), the record is orphaned: nothing
        will ever transition it again. Call this once at startup, before any new
        work is dispatched, so orphaned tasks don't block downstream logic that
        assumes RUNNING means "actively being worked".
        """
        reaped: list[TaskRecord] = []
        for task in self.store.list_tasks():
            if task.status == TaskStatus.RUNNING:
                reaped.append(
                    self.transition(
                        task.id,
                        TaskStatus.FAILED,
                        actor,
                        {"reason": "orphaned-on-restart"},
                    )
                )
        return reaped

    def transition(self, task_id: str, status: TaskStatus, actor: str, payload: dict | None = None) -> TaskRecord:
        task = self.require(task_id)
        task.status = status
        task.updated_at = datetime.now(timezone.utc)
        self.store.save_task(task)
        self.store.add_event(TaskEvent(task_id=task.id, kind=f"task.{status.value}", actor=actor, payload=payload or {}))
        if self.on_transition is not None:
            try:
                self.on_transition(task, status, payload or {})
            except Exception:
                logger.warning("on_transition callback failed for task %s -> %s", task.id, status.value, exc_info=True)
        return task

    def require(self, task_id: str) -> TaskRecord:
        task = self.store.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return task
