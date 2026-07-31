from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SkillRegistry:
    def __init__(self, root: Path | str = "skills") -> None:
        self.root = Path(root)

    def load(self) -> dict[str, dict[str, Any]]:
        skills: dict[str, dict[str, Any]] = {}
        if not self.root.exists():
            return skills
        for path in sorted(self.root.rglob("manifest.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            skill_id = data["id"]
            if skill_id in skills:
                raise ValueError(f"Duplicate skill id: {skill_id}")
            data["path"] = str(path.parent)
            skills[skill_id] = data
        return skills
