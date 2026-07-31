from __future__ import annotations

from pathlib import Path
import yaml

from cano_hermes.domain.models import AgentManifest


class AgentRegistry:
    def __init__(self, root: Path | str = "agents") -> None:
        self.root = Path(root)
        self._agents: dict[str, AgentManifest] = {}

    def load(self) -> dict[str, AgentManifest]:
        agents: dict[str, AgentManifest] = {}
        if not self.root.exists():
            return agents
        for path in sorted(self.root.rglob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            manifest = AgentManifest.model_validate(data)
            if manifest.id in agents:
                raise ValueError(f"Duplicate agent id: {manifest.id}")
            agents[manifest.id] = manifest
        self._agents = agents
        return agents

    def all(self) -> list[AgentManifest]:
        if not self._agents:
            self.load()
        return list(self._agents.values())

    def get(self, agent_id: str) -> AgentManifest | None:
        if not self._agents:
            self.load()
        return self._agents.get(agent_id)

    def active_for_team(self, team: str) -> list[AgentManifest]:
        return [a for a in self.all() if a.team == team and a.status.value in {"approved", "active"}]
