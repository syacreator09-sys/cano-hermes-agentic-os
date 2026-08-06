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

    def create_from_definition(self, definition: dict) -> tuple[dict, Path]:
        """Plan Prometeo F4 — the pipeline's "candidate" stage for skills.

        Accepts an arbitrary caller-supplied definition (id, objective,
        steps, and optionally version/risk/tests), validates the minimal
        required shape, and forces `status="quarantine"` regardless of what
        the caller asked for. Written to `self.root/<id>/` exactly like
        `create_candidate` (manifest.json + SKILL.md).
        """
        skill_id = definition.get("id")
        objective = definition.get("objective")
        if not skill_id or not SAFE_ID.fullmatch(str(skill_id)):
            raise ValueError("definition['id'] must be kebab-case and 3-64 characters")
        if not objective or not str(objective).strip():
            raise ValueError("definition['objective'] is required")
        steps = definition.get("steps") or ["Confirmar objetivo, entradas y restricciones."]
        target = self.root / skill_id
        if target.exists():
            raise FileExistsError(target)
        target.mkdir(parents=True)
        manifest = {
            "id": skill_id,
            "version": definition.get("version", "0.1.0"),
            "status": "quarantine",
            "objective": objective,
            "risk": definition.get("risk", "unknown"),
            "tests": definition.get("tests") or ["manifest", "procedure-review"],
            "progressive_disclosure": definition.get("progressive_disclosure", True),
        }
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        procedure = "\n".join(f"{i}. {step}" for i, step in enumerate(steps, 1))
        (target / "SKILL.md").write_text(f"# {skill_id}\n\n{objective}\n\n## Procedure\n\n{procedure}\n", encoding="utf-8")
        return manifest, target

    def rewrite_status(self, target: Path, manifest: dict, status: str) -> dict:
        """Advance the candidate artifact's own lifecycle status in place
        (quarantine -> testing as it clears sandbox)."""
        updated = dict(manifest)
        updated["status"] = status
        (target / "manifest.json").write_text(json.dumps(updated, indent=2), encoding="utf-8")
        return updated

    def promote(self, manifest: dict, target_root: Path | str = "skills", candidate_dir: Path | str | None = None) -> Path:
        """Materialize an approved candidate as a real, active skill at
        `skills/<id>/`. Only ever called after `ApprovalService` has
        recorded a human resolution — see `forge/pipeline.py`. When
        `candidate_dir` is given, its `SKILL.md` (with the full procedure)
        is carried over verbatim instead of being regenerated from scratch.
        """
        skill_id = manifest["id"]
        target_dir = Path(target_root) / skill_id
        if target_dir.exists():
            raise FileExistsError(target_dir)
        target_dir.mkdir(parents=True)
        promoted = dict(manifest)
        promoted["status"] = "active"
        (target_dir / "manifest.json").write_text(json.dumps(promoted, indent=2), encoding="utf-8")
        candidate_skill_md = Path(candidate_dir) / "SKILL.md" if candidate_dir else None
        if candidate_skill_md and candidate_skill_md.exists():
            (target_dir / "SKILL.md").write_text(candidate_skill_md.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            objective = manifest.get("objective", "")
            (target_dir / "SKILL.md").write_text(f"# {skill_id}\n\n{objective}\n", encoding="utf-8")
        return target_dir
