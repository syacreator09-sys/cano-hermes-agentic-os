from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SkillRegistry:
    def __init__(self, root: Path | str = "skills") -> None:
        self.root = Path(root)

    def load(self) -> dict[str, dict[str, Any]]:
        skills: dict[str, dict[str, Any]] = {}
        if not self.root.exists():
            return skills
        for path in sorted(self.root.rglob("manifest.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Skipping unreadable/invalid skill manifest %s: %s", path, exc)
                continue
            skill_id = data.get("id")
            if not skill_id:
                logger.warning("Skipping skill manifest without an 'id': %s", path)
                continue
            # Duplicate IDs stay fatal (pre-existing contract); a broken
            # SKILL.md is only a warning so the rest of the registry still loads.
            if skill_id in skills:
                raise ValueError(f"Duplicate skill id: {skill_id}")
            if not (path.parent / "SKILL.md").exists():
                logger.warning("Skill '%s' has a manifest.json but no SKILL.md at %s", skill_id, path.parent)
            data["path"] = str(path.parent)
            skills[skill_id] = data
        return skills
