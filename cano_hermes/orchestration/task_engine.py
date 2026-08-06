from __future__ import annotations

from datetime import datetime, timezone

from cano_hermes.domain.enums import TaskStatus
from cano_hermes.domain.models import TaskCreate, TaskEvent, TaskRecord
from cano_hermes.storage.sqlite import SQLiteStore
from .conductor import Conductor


class TaskEngine:
    def __init__(self, store: SQLiteStore, conductor: Conductor) -> None:
        self.store = store
        self.conductor = conductor

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
        return task

    def require(self, task_id: str) -> TaskRecord:
        task = self.store.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return task
