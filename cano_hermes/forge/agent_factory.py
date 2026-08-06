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

    def create_from_definition(self, definition: dict) -> tuple[AgentManifest, Path]:
        """Plan Prometeo F4 — the pipeline's "candidate" stage for agents.

        Accepts an arbitrary caller-supplied definition (id, name, team,
        objective, and optionally runtime/model_profiles/skills/tools/
        permissions/budget/evaluations/max_concurrency), validates it against
        the full `AgentManifest` schema, and forces `status=QUARANTINE`
        regardless of what the caller asked for — a candidate is never
        allowed to propose itself straight into production. Written to
        `self.root/<id>.yaml`, same as `create_candidate`.
        """
        payload = dict(definition)
        agent_id = payload.get("id")
        if not agent_id or not SAFE_ID.fullmatch(str(agent_id)):
            raise ValueError("definition['id'] must be kebab-case and 3-64 characters")
        payload["status"] = AgentStatus.QUARANTINE
        manifest = AgentManifest.model_validate(payload)
        path = self.root / f"{manifest.id}.yaml"
        if path.exists():
            raise FileExistsError(path)
        path.write_text(yaml.safe_dump(manifest.model_dump(mode="json"), sort_keys=False), encoding="utf-8")
        return manifest, path

    def rewrite_status(self, path: Path, manifest: AgentManifest, status: AgentStatus) -> AgentManifest:
        """Advance the candidate artifact's own lifecycle status in place
        (QUARANTINE -> TESTING as it clears sandbox, docs/ARCHITECTURE.md
        §5's DRAFT→...→ACTIVE cycle) without touching the pipeline-tracking
        `ForgeCandidate` record, which lives separately in `forge/store.py`.
        """
        updated = manifest.model_copy(update={"status": status})
        path.write_text(yaml.safe_dump(updated.model_dump(mode="json"), sort_keys=False), encoding="utf-8")
        return updated

    def promote(self, manifest: AgentManifest, target_root: Path | str = "agents") -> Path:
        """Materialize an approved candidate as a real, active agent file at
        `agents/<team>/<id>.yaml`. Only ever called after `ApprovalService`
        has recorded a human resolution — see `forge/pipeline.py`."""
        target_dir = Path(target_root) / manifest.team
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{manifest.id}.yaml"
        if target_path.exists():
            raise FileExistsError(target_path)
        promoted = manifest.model_copy(update={"status": AgentStatus.ACTIVE})
        target_path.write_text(yaml.safe_dump(promoted.model_dump(mode="json"), sort_keys=False), encoding="utf-8")
        return target_path
