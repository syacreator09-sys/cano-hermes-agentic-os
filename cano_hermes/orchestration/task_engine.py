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
