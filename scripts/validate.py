from pathlib import Path
import json
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cano_hermes.domain.models import AgentManifest
from cano_hermes.registry.skills import SkillRegistry
from cano_hermes.nexus.markdown import MarkdownVault

errors: list[str] = []
ids: set[str] = set()
for path in sorted((ROOT / "agents").rglob("*.yaml")):
    try:
        agent = AgentManifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        if agent.id in ids:
            errors.append(f"duplicate agent: {agent.id}")
        ids.add(agent.id)
    except Exception as exc:
        errors.append(f"{path}: {exc}")
skills = SkillRegistry(ROOT / "skills").load()
for skill_id, data in skills.items():
    if not Path(data["path"], "SKILL.md").exists():
        errors.append(f"missing SKILL.md: {skill_id}")
notes = MarkdownVault(ROOT / "vault").index()
if errors:
    raise SystemExit("\n".join(errors))
print(json.dumps({"status": "ok", "agents": len(ids), "skills": len(skills), "notes": len(notes)}, indent=2))
