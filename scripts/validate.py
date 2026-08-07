from pathlib import Path
import json
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cano_hermes.domain.models import AgentManifest
from cano_hermes.registry.skills import SkillRegistry
from cano_hermes.nexus.markdown import MarkdownVault

# K15 (plan HERMES-KICKOFF) -- `skills/candidates/<id>/manifest.json` is
# `SkillFactory`'s quarantine area (`cano_hermes/forge/skill_factory.py`):
# a candidate lands there DRAFT/QUARANTINE, unreferenced by any agent by
# design, until a human promotes it into `skills/<id>/` and wires it into an
# agent's `skills:` list. `SkillRegistry.load()` (`rglob("manifest.json")`)
# sweeps candidates into the same registry as promoted skills, so the orphan
# check below must exclude anything still living under this prefix -- it is
# not a bug, it is the pipeline working as designed.
_CANDIDATES_PREFIX = str(ROOT / "skills" / "candidates")


def run() -> dict:
    errors: list[str] = []
    ids: set[str] = set()
    agent_skill_refs: dict[str, list[str]] = {}
    for path in sorted((ROOT / "agents").rglob("*.yaml")):
        try:
            agent = AgentManifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
            if agent.id in ids:
                errors.append(f"duplicate agent: {agent.id}")
            ids.add(agent.id)
            agent_skill_refs[agent.id] = list(agent.skills)
        except Exception as exc:
            errors.append(f"{path}: {exc}")

    skills = SkillRegistry(ROOT / "skills").load()
    for skill_id, data in skills.items():
        if not Path(data["path"], "SKILL.md").exists():
            errors.append(f"missing SKILL.md: {skill_id}")

    # K15 -- orphan/dangling-reference sweep (root CLAUDE.md rule: skills
    # must be wired to at least one agent, never left dangling either way).
    promoted_skill_ids = {
        skill_id for skill_id, data in skills.items()
        if not str(data["path"]).startswith(_CANDIDATES_PREFIX)
    }
    candidate_skill_ids = set(skills) - promoted_skill_ids
    referenced_skill_ids: set[str] = set()
    for agent_id, refs in agent_skill_refs.items():
        for skill_id in refs:
            referenced_skill_ids.add(skill_id)
            if skill_id not in skills:
                errors.append(f"agent '{agent_id}' references unknown skill: {skill_id}")

    orphan_skills = sorted(promoted_skill_ids - referenced_skill_ids)
    for skill_id in orphan_skills:
        errors.append(f"orphan skill (no agent references it): {skill_id}")

    notes = MarkdownVault(ROOT / "vault").index()
    if errors:
        raise SystemExit("\n".join(errors))
    return {
        "status": "ok",
        "agents": len(ids),
        "skills": len(skills),
        "notes": len(notes),
        "orphan_skills": orphan_skills,
        "candidate_skills": sorted(candidate_skill_ids),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
