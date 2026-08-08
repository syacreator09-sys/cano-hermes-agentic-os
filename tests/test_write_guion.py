"""A4 (plan AUTONOMÍA TOTAL, 2026-08-08) -- scripts/write_guion.py's
--formato branching. Only the deterministic parts (prompt selection,
output file naming, dry-run) are unit-tested here -- the real hermes
--oneshot invocation is verified live (see plan file), never mocked into
a fake "it works" the way scripts/write_guion.py's own module docstring
already establishes as the convention for this file (T9, plan POTENCIA).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import write_guion as wg  # noqa: E402

BRIEF = {"viral_ranking": [{"title": "algo viral", "platform": "youtube", "opportunity_score": 0.8}]}


class BuildPromptFormatoTests(unittest.TestCase):
    def test_default_formato_uses_short_template(self):
        prompt = wg.build_prompt(BRIEF, "cano-digital-ia", "tema")
        self.assertIn("hook, beats y payoff", prompt)
        self.assertIn("25-45s", prompt)

    def test_formato_largo_uses_long_template_with_six_named_beats(self):
        prompt = wg.build_prompt(BRIEF, "cano-digital-ia", "tema", formato="largo")
        self.assertIn("6 beats fijos", prompt)
        for beat in wg.BEATS_LARGO:
            self.assertIn(f"{beat}:", prompt)
        self.assertNotIn("beats:\n  - keyword", prompt)  # no es el shape short


class WriteGuionDryRunTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        import json
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.brief_path = Path(self.tmp.name) / "2026-08-08" / "cano-digital-ia.json"
        self.brief_path.parent.mkdir(parents=True)
        self.brief_path.write_text(json.dumps(BRIEF), encoding="utf-8")

    def test_dry_run_never_invokes_hermes(self):
        from unittest.mock import patch
        with patch("write_guion.invoke_hermes") as fake_invoke:
            result = wg.write_guion("cano-digital-ia", self.brief_path, "tema", apply=False)
        fake_invoke.assert_not_called()
        self.assertEqual(result["status"], "dry_run")

    def test_dry_run_formato_largo_previews_long_prompt(self):
        result = wg.write_guion("cano-digital-ia", self.brief_path, "tema", apply=False, formato="largo")
        self.assertEqual(result["status"], "dry_run")
        self.assertIn("would_write", result)


if __name__ == "__main__":
    unittest.main()
