from functools import lru_cache

from cano_hermes.config import settings
from cano_hermes.forge.pipeline import ForgePipeline
from cano_hermes.governance.approvals import ApprovalService
from cano_hermes.governance.budget import BudgetService
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.orchestration.execution_service import ExecutionService
from cano_hermes.orchestration.queue_service import QueueService
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.storage.sqlite import SQLiteStore


@lru_cache
def store() -> SQLiteStore:
    return SQLiteStore(settings.database_url)


@lru_cache
def registry() -> AgentRegistry:
    item = AgentRegistry(settings.agent_path)
    item.load()
    return item


@lru_cache
def engine() -> TaskEngine:
    return TaskEngine(store(), Conductor(registry(), ModelRouter()))


@lru_cache
def approvals() -> ApprovalService:
    return ApprovalService(store())


@lru_cache
def budget() -> BudgetService:
    return BudgetService(store())


@lru_cache
def execution_service() -> ExecutionService:
    return ExecutionService(
        engine(),
        mode=settings.execution_mode,
        approvals=approvals(),
        budget=budget(),
        artifacts_root=settings.artifact_path,
        repository=settings.repository_root,
    )


@lru_cache
def queue_service() -> QueueService:
    """K3 -- `max_concurrent_workers` (Settings, config.py) is read here for
    the first time anywhere in the codebase. It already defaulted to 3
    before K3 (set that way in an earlier phase, not touched by this one) --
    left as-is rather than forced down to a hardcoded 2, since an explicit
    existing default is a deliberate prior choice, not an unset gap. Tests
    that need to observe the semaphore actually bounding concurrency
    construct their own `QueueService(..., max_concurrent_workers=2)`
    directly instead of overriding this global."""
    return QueueService(
        execution_service(),
        engine(),
        max_concurrent_workers=settings.max_concurrent_workers,
    )


@lru_cache
def forge_pipeline() -> ForgePipeline:
    return ForgePipeline(
        agents_root=settings.agent_path,
        skills_root=settings.skill_path,
        candidates_root=settings.forge_candidates_path,
        sandbox_workspace_root=settings.forge_sandbox_path,
        approvals=approvals(),
        budget=budget(),
    )
