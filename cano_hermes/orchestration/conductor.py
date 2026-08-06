from __future__ import annotations

from dataclasses import dataclass

from cano_hermes.domain.enums import RiskLevel
from cano_hermes.domain.models import TaskRecord
from cano_hermes.intelligence.router import ModelRouter, RouteRequest
from cano_hermes.registry.agents import AgentRegistry


DOMAIN_TEAMS = {
    "engineering": "engineering",
    "research": "research",
    "content": "content",
    "operations": "operations",
    "forge": "forge",
    "security": "governance",
    "finance": "finance",
}


@dataclass(frozen=True)
class Assignment:
    agent_id: str
    route_profile: str
    rationale: list[str]


class Conductor:
    def __init__(self, registry: AgentRegistry, router: ModelRouter) -> None:
        self.registry = registry
        self.router = router

    def assign(self, task: TaskRecord) -> Assignment:
        team = DOMAIN_TEAMS.get(task.domain, "governance")
        agents = self.registry.active_for_team(team)
        if not agents:
            agents = [a for a in self.registry.all() if a.id == "task-governor"]
        if not agents:
            raise RuntimeError(f"No active agent for team {team}")
        agent = agents[0]
        complexity = int(task.metadata.get("complexity", 3))
        context_need = int(task.metadata.get("context_need", 2))
        route = self.router.route(
            RouteRequest(
                domain=task.domain,
                complexity=complexity,
                context_need=context_need,
                tools_required=task.domain in {"engineering", "operations", "content"},
                vision_required=bool(task.metadata.get("vision_required", False)),
                risk=RiskLevel(task.risk),
                max_cost_tier=int(task.metadata.get("max_cost_tier", 5)),
            )
        )
        return Assignment(agent.id, route.profile.id, route.reasons)
