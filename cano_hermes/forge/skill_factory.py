from __future__ import annotations

import json
import re
from pathlib import Path


SAFE_ID = re.compile(r"^[a-z][a-z0-9-]{2,63}$")


class SkillFactory:
    def __init__(self, root: Path | str = "skills/candidates") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create_candidate(self, skill_id: str, objective: str, steps: list[str]) -> Path:
        if not SAFE_ID.fullmatch(skill_id):
            raise ValueError("skill_id must be kebab-case and 3-64 characters")
        target = self.root / skill_id
        if target.exists():
            raise FileExistsError(target)
        target.mkdir(parents=True)
        manifest = {
            "id": skill_id,
            "version": "0.1.0",
            "status": "quarantine",
            "objective": objective,
            "risk": "unknown",
            "tests": ["manifest", "procedure-review"],
        }
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        procedure = "\n".join(f"{i}. {step}" for i, step in enumerate(steps, 1))
        (target / "SKILL.md").write_text(f"# {skill_id}\n\n{objective}\n\n## Procedure\n\n{procedure}\n", encoding="utf-8")
        return target
