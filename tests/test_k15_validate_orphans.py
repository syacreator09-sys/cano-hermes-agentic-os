"""K15 (plan HERMES-KICKOFF) -- `scripts/validate.py`'s orphan/dangling-
reference sweep over `skills/` and `agents/`.

Covers: (a) the real repo state validates clean (zero orphans, zero
dangling refs -- this is the actual K15 "Verif" clause: "cero skills
huerfanos en scripts/validate.py extendido"), (b) an orphan skill (no
agent references it) is detected and fails validate.run(), (c) an agent
referencing a nonexistent skill id is detected and fails validate.run(),
(d) a skill under `skills/candidates/` (SkillFactory's quarantine area,
`cano_hermes/forge/skill_factory.py`) is correctly excluded from the
orphan check -- it is unreferenced by design until a human promotes it.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts import validate


class ValidateRealRepoTests(unittest.TestCase):
    def test_current_repo_has_zero_orphans_and_zero_dangling_refs(self):
        result = validate.run()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["orphan_skills"], [])


class ValidateOrphanSweepTests(unittest.TestCase):
    """Builds a throwaway skills/+agents/ tree under validate.ROOT so the
    orphan/dangling-ref logic is exercised in isolation from the real repo
    tree (which must stay untouched -- these tests only monkeypatch
    `validate.ROOT` for the duration of each test)."""

    def _write_skill(self, root: Path, skill_id: str, under_candidates: bool = False) -> None:
        base = root / "skills" / ("candidates" if under_candidates else "") / skill_id
        base.mkdir(parents=True, exist_ok=True)
        (base / "manifest.json").write_text(json.dumps({"id": skill_id, "status": "active"}), encoding="utf-8")
        (base / "SKILL.md").write_text(f"# {skill_id}\n\nProcedure.\n", encoding="utf-8")

    def _write_agent(self, root: Path, agent_id: str, skills: list[str]) -> None:
        agents_dir = root / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": agent_id, "name": agent_id, "team": "research", "objective": "test",
            "skills": skills,
        }
        (agents_dir / f"{agent_id}.yaml").write_text(
            "\n".join(f"{k}: {json.dumps(v)}" for k, v in payload.items()), encoding="utf-8"
        )

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "vault").mkdir(parents=True, exist_ok=True)
        self._orig_root = validate.ROOT
        self._orig_prefix = validate._CANDIDATES_PREFIX
        validate.ROOT = self.root
        validate._CANDIDATES_PREFIX = str(self.root / "skills" / "candidates")
        self.addCleanup(self._restore)

    def _restore(self):
        validate.ROOT = self._orig_root
        validate._CANDIDATES_PREFIX = self._orig_prefix

    def test_clean_tree_passes(self):
        self._write_skill(self.root, "skill-a")
        self._write_agent(self.root, "agent-a", ["skill-a"])
        result = validate.run()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["orphan_skills"], [])

    def test_orphan_skill_fails(self):
        self._write_skill(self.root, "skill-a")
        self._write_skill(self.root, "skill-orphan")
        self._write_agent(self.root, "agent-a", ["skill-a"])
        with self.assertRaises(SystemExit) as ctx:
            validate.run()
        self.assertIn("orphan skill", str(ctx.exception))
        self.assertIn("skill-orphan", str(ctx.exception))

    def test_dangling_agent_reference_fails(self):
        self._write_skill(self.root, "skill-a")
        self._write_agent(self.root, "agent-a", ["skill-a", "skill-does-not-exist"])
        with self.assertRaises(SystemExit) as ctx:
            validate.run()
        self.assertIn("unknown skill", str(ctx.exception))
        self.assertIn("skill-does-not-exist", str(ctx.exception))

    def test_candidate_skill_excluded_from_orphan_check(self):
        self._write_skill(self.root, "skill-a")
        self._write_agent(self.root, "agent-a", ["skill-a"])
        self._write_skill(self.root, "skill-in-quarantine", under_candidates=True)
        result = validate.run()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["orphan_skills"], [])
        self.assertIn("skill-in-quarantine", result["candidate_skills"])


if __name__ == "__main__":
    unittest.main()
