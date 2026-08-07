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
    # P0 (plan POTENCIA, 2026-08-07): the 6 previously-orphan teams. Domains
    # are free strings set by callers (`cano_hermes/cli.py --domain`,
    # `POST /api/tasks` TaskCreate.domain -- there is no automatic
    # decomposer stamping domains today), so the convention is
    # domain == team name, plus one alias where the plan/operator language
    # differs from the team name ("trading" is how Cano and the POTENCIA
    # plan refer to the investments work; "personal" is the natural short
    # form of personal-operations).
    "investments": "investments",
    "trading": "investments",
    "revenue": "revenue",
    "documents": "documents",
    "learning": "learning",
    "personal-operations": "personal-operations",
    "personal": "personal-operations",
    "projects": "projects",
}

# Team -> hermes kanban profile name that K6's `bridge/kanban_bridge.py`
# passes to `hermes kanban add --profile <this>`, and that
# `governance/auto_approval.load_office_never()` resolves to
# `offices/<profile>/office.yaml` for the office's `never:` list, and that
# `bridge/office_launcher.ensure_office_for_profile()` uses to start the
# right Docker container (PROFILE_TO_OFFICE).
#
# P0 (plan POTENCIA, 2026-08-07): the K5-era `team-*` placeholders never
# matched any real profile/office, which left 4 of the 5 Docker offices
# unreachable from any task.domain. Every value below is now a real profile
# id == a real `offices/<name>/office.yaml` directory:
#
#   - "research"    -> hermes-research   (kept from K5: "radar viral diario"
#     == the research domain; native folder-isolated worker, no container).
#   - "operations"  -> hermes-monitor    (kept from K5: "Ojos del sistema"
#     == operations; Docker office `analytics`).
#   - "content"     -> hermes-produccion (render reels/largos/carruseles --
#     the content team's executable work (media-render-worker,
#     factory-operator, storyboard-designer) is production; Docker office
#     `content`. hermes-guiones stays native/cron-driven and
#     hermes-distribucion is gate-only publishing, so neither is the
#     content team's default lane -- see the "no entry" notes below).
#   - "forge"       -> hermes-ugc        (Docker office `ugc`: the UGC
#     pipeline scout->plan->generate is the forge team's build-new-capacity
#     work in production today; agent-designer/skill-engineer artifacts
#     stay native but the office is the forge's live workshop).
#   - "finance"     -> hermes-monitor    (finance's routable work today is
#     read-only vigilance: cost-controller reconciles --usage-file vs
#     budget, budget-controller watches quotas -- exactly the analytics
#     office's read-only monitoring lane; no dedicated finance office
#     exists).
#   - "investments" -> hermes-market-intel (Docker office `market-intel`:
#     its mission literally crosses the investment-intelligence offline
#     council signal; makes the 5th Docker office reachable. P3 will grow
#     this into the trading office).
#
# Teams WITHOUT an entry (kanban_profile=None, handled everywhere --
# auto_approval treats None as "no office never-list", kanban_bridge does
# not route by profile at order level, office_launcher no-ops):
#   - "engineering": goes through the claude-code/codex subscription
#     executors directly (router.py gives engineering +3.5 to those
#     profiles) -- a tier-0 Kimi Docker office would be a downgrade.
#   - "governance": governance agents (task-governor, security-guardian,
#     evaluator...) run native next to the API; governance is also the
#     fallback team for unknown domains, and an unknown domain must NOT
#     auto-launch a Docker container.
#   - "revenue", "documents", "learning", "personal-operations",
#     "projects": personal/native hermes agents, read-only by manifest,
#     no Docker office exists for them.
#
# Offices with no team pointing at them, on purpose:
#   - hermes-guiones (native, cron "0 10 * * *" -- driven by its own
#     schedule, not by domain routing).
#   - hermes-distribucion (gate-only publishing: reached explicitly via
#     `hermes kanban add --profile hermes-distribucion` after human
#     approval, never as an automatic destination for a whole domain).
TEAM_TO_KANBAN_PROFILE = {
    "research": "hermes-research",
    "content": "hermes-produccion",
    "operations": "hermes-monitor",
    "forge": "hermes-ugc",
    "finance": "hermes-monitor",
    "investments": "hermes-market-intel",
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
