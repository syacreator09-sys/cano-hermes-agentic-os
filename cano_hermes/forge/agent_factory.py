from __future__ import annotations

import re
from pathlib import Path

import yaml

from cano_hermes.domain.enums import AgentStatus
from cano_hermes.domain.models import AgentManifest, Budget


SAFE_ID = re.compile(r"^[a-z][a-z0-9-]{2,63}$")


class AgentFactory:
    def __init__(self, root: Path | str = "agents/candidates") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create_candidate(
        self,
        agent_id: str,
        name: str,
        team: str,
        objective: str,
        skills: list[str] | None = None,
        tools: list[str] | None = None,
    ) -> Path:
        if not SAFE_ID.fullmatch(agent_id):
            raise ValueError("agent_id must be kebab-case and 3-64 characters")
        path = self.root / f"{agent_id}.yaml"
        if path.exists():
            raise FileExistsError(path)
        manifest = AgentManifest(
            id=agent_id,
            name=name,
            team=team,
            objective=objective,
            status=AgentStatus.QUARANTINE,
            model_profiles=["deepseek-daily"],
            skills=skills or [],
            tools=tools or [],
            permissions={"filesystem": "none", "network": "denied", "production": "denied"},
            budget=Budget(max_cost_usd=0.25, max_turns=10, timeout_seconds=600),
            evaluations=["schema", "safety", "task-contract"],
        )
        path.write_text(yaml.safe_dump(manifest.model_dump(mode="json"), sort_keys=False), encoding="utf-8")
        return path
