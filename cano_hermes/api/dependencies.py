from functools import lru_cache

from cano_hermes.config import settings
from cano_hermes.forge.pipeline import ForgePipeline
from cano_hermes.governance.approvals import ApprovalService
from cano_hermes.governance.budget import BudgetService
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.orchestration.execution_service import ExecutionService
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
