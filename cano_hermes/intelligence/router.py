from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from cano_hermes.domain.enums import RiskLevel
from cano_hermes.domain.models import TaskRecord
from .profiles import DEFAULT_PROFILES, ModelProfile

@dataclass(frozen=True)
class RouteRequest:
    domain: str
    complexity: int=2
    context_need: int=2
    tools_required: bool=False
    vision_required: bool=False
    risk: RiskLevel=RiskLevel.LOW
    prefer_subscription: bool=True
    max_cost_tier: int=5

@dataclass(frozen=True)
class RouteDecision:
    profile: ModelProfile
    score: float
    reasons: list[str]

class ModelRouter:
    def __init__(self, profiles: Iterable[ModelProfile]=DEFAULT_PROFILES) -> None:
        self.profiles=list(profiles)
    def from_task(self, task: TaskRecord) -> RouteRequest:
        return RouteRequest(domain=task.domain, complexity=int(task.metadata.get("complexity",3)), context_need=int(task.metadata.get("context_need",2)), tools_required=task.domain in {"engineering","operations","content","forge"}, vision_required=bool(task.metadata.get("vision_required",False)), risk=RiskLevel(task.risk), prefer_subscription=bool(task.metadata.get("prefer_subscription",True)), max_cost_tier=int(task.metadata.get("max_cost_tier",5)))
    def route_task(self, task: TaskRecord) -> RouteDecision:
        return self.route(self.from_task(task))
    def route(self, request: RouteRequest) -> RouteDecision:
        candidates=[]
        for profile in self.profiles:
            if profile.cost_tier>request.max_cost_tier: continue
            if request.tools_required and not profile.supports_tools: continue
            if request.vision_required and not profile.supports_vision: continue
            score=max(0,6-abs(profile.quality-request.complexity)*1.5)
            score+=min(profile.context,request.context_need)*0.8
            score+=max(0,5-profile.cost_tier)*1.1
            reasons=[]
            if request.prefer_subscription and profile.subscription: score+=3; reasons.append("subscription-first")
            if request.domain=="engineering" and profile.id in {"claude-subscription","codex-subscription"}: score+=3.5; reasons.append("engineering-runtime")
            if request.domain=="research" and profile.id=="kimi-research": score+=3; reasons.append("long-research")
            if request.domain in {"trends","content"} and profile.id=="grok-trends": score+=2; reasons.append("trend-specialist")
            if request.risk in {RiskLevel.HIGH,RiskLevel.CRITICAL} and profile.quality>=5: score+=2.5; reasons.append("high-risk-quality")
            candidates.append(RouteDecision(profile,score,reasons))
        if not candidates: raise RuntimeError("No model profile satisfies routing constraints")
        return max(candidates,key=lambda item:(item.score,-item.profile.cost_tier))
