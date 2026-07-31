from dataclasses import dataclass


@dataclass(frozen=True)
class Opportunity:
    relevance: float
    novelty: float
    evidence: float
    channel_fit: float
    production_cost: float
    risk: float


def score_opportunity(item: Opportunity) -> float:
    positive = item.relevance * 0.30 + item.novelty * 0.20 + item.evidence * 0.25 + item.channel_fit * 0.25
    penalty = item.production_cost * 0.12 + item.risk * 0.18
    return round(max(0.0, min(1.0, positive - penalty)), 4)
