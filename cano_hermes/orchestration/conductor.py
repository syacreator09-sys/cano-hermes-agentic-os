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

# K5 (plan HERMES-KICKOFF, gap 1): team -> hermes kanban profile name that
# K6's `bridge/kanban_bridge.py` will pass to `hermes kanban add --profile
# <this>`. Checked before inventing anything: `~/.hermes/profiles/` does not
# exist on this machine (no named profiles registered yet), and
# `~/.hermes/kanban.db`'s `tasks.profile` column has no rows to crib real
# names from either -- so there is nothing "real" to look up for most teams.
#
# Where a StarHome team maps unambiguously to one of the 6 Docker offices
# merged in PR #7 (`offices/*/office.yaml`, this repo) by name/mission, we
# use that office's name directly -- those ARE real ids, and K9 registering
# their kanban workers will make them live profiles without touching this
# map:
#   - "research"   -> hermes-research  (mission: "radar viral diario ...
#     transcripts ... para alimentar guiones" == StarHome's research domain)
#   - "operations" -> hermes-monitor   (mission: "Ojos del sistema: ...
#     vigilancia" == StarHome's operations domain)
#
# Every other team gets a provisional `team-<team>` placeholder: "content"
# is deliberately NOT pointed at any single office because four of the six
# (guiones/produccion/distribucion/ugc) all touch content and none is a
# clean 1:1 match; "engineering", "forge", "governance" and "finance" have
# no corresponding Docker office at all yet. K6 can use these placeholders
# as-is (they are valid, stable strings); K9 should replace each with the
# real `office.yaml` profile id once that team gets its own office.
TEAM_TO_KANBAN_PROFILE = {
    "engineering": "team-engineering",
    "research": "hermes-research",
    "content": "team-content",
    "operations": "hermes-monitor",
    "forge": "team-forge",
    "governance": "team-governance",
    "finance": "team-finance",
}


@dataclass(frozen=True)
class Assignment:
    agent_id: str
    route_profile: str
    rationale: list[str]
    kanban_profile: str | None = None


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
        kanban_profile = TEAM_TO_KANBAN_PROFILE.get(team)
        return Assignment(agent.id, route.profile.id, route.reasons, kanban_profile)


def kanban_profile_for_domain(domain: str) -> str | None:
    """Same `domain -> team -> kanban_profile` lookup `Conductor.assign`
    does internally, exposed standalone so callers that already have a
    `task.domain` (K12's auto-approval wiring in `ExecutionService.run`)
    can resolve the K9 office profile a task belongs to without
    re-running the whole assignment/routing pipeline a second time."""
    team = DOMAIN_TEAMS.get(domain, "governance")
    return TEAM_TO_KANBAN_PROFILE.get(team)
