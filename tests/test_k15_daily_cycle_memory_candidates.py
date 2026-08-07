"""K15 (plan HERMES-KICKOFF) -- `scripts/daily_cycle.py`'s new memory
candidates visibility step.

Covers: (a) pending candidates (`status="candidate"`, the real status
string `SQLiteStore.add_memory_candidate` writes) surface in the snapshot,
(b) approved/rejected candidates do NOT count as pending, (c) the step
never raises even against a broken vault path (must not kill the rest of
the cycle), (d) `render_markdown` renders the pending list without
crashing for both the empty and non-empty case.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cano_hermes.storage.sqlite import SQLiteStore
from scripts import daily_cycle


class MemoryCandidatesSnapshotTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.store = SQLiteStore(f"sqlite:///{self._tmpdir.name}/candidates.db")
        self.vault_root = Path(self._tmpdir.name) / "vault"

    def test_no_candidates_is_empty_but_ok(self):
        with patch.object(daily_cycle.settings, "vault_path", self.vault_root):
            result = daily_cycle.memory_candidates_snapshot(self.store)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["pending_count"], 0)
        self.assertEqual(result["pending"], [])

    def test_pending_candidate_surfaces(self):
        self.store.add_memory_candidate("cand-1", "engineering", {"lesson": "always run tests"})
        with patch.object(daily_cycle.settings, "vault_path", self.vault_root):
            result = daily_cycle.memory_candidates_snapshot(self.store)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["pending_count"], 1)
        self.assertEqual(result["pending"][0]["id"], "cand-1")
        self.assertEqual(result["pending"][0]["namespace"], "engineering")

    def test_resolved_candidate_does_not_count_as_pending(self):
        self.store.add_memory_candidate("cand-1", "engineering", {"lesson": "x"})
        self.store.resolve_memory_candidate("cand-1", "approved", "cano")
        with patch.object(daily_cycle.settings, "vault_path", self.vault_root):
            result = daily_cycle.memory_candidates_snapshot(self.store)
        self.assertEqual(result["pending_count"], 0)

    def test_never_raises_even_if_store_is_broken(self):
        class BrokenStore:
            def list_memory_candidates(self, status=None):
                raise RuntimeError("db exploded")

        result = daily_cycle.memory_candidates_snapshot(BrokenStore())  # type: ignore[arg-type]
        self.assertEqual(result["status"], "error")
        self.assertIn("db exploded", result["detail"])

    def test_render_markdown_handles_pending_and_empty(self):
        base_result = {
            "date": "2026-08-06",
            "alerts": [],
            "connections": {"status": "error", "detail": "n/a"},
            "health": {
                "starhome_api": {"status": "ok"},
                "hermes_status": {"status": "ok"},
                "nexus_doctor": {"status": "ok"},
                "docker_stats": {"status": "ok", "containers": []},
                "offices": {},
            },
            "ugc_performance": {"classification": "N/A", "note": "n/a"},
            "costs": {
                "usage_files": {"usage_files_found": 0, "total_cost_usd": 0.0},
                "budget": {"spent_usd": 0.0, "daily_limit_usd": 5.0, "percent_used": 0.0, "remaining_usd": 5.0},
                "higgsfield_credits": {"status": "n/a", "note": "n/a"},
            },
            "audit": {"status": "PASS", "agents": 1, "skills": 1, "notes": 1},
        }
        empty = {**base_result, "memory_candidates": {"status": "ok", "pending_count": 0, "pending": []}}
        rendered_empty = daily_cycle.render_markdown(empty)
        self.assertIn("Nada pendiente.", rendered_empty)

        with_pending = {
            **base_result,
            "memory_candidates": {
                "status": "ok",
                "pending_count": 1,
                "pending": [{"id": "cand-1", "namespace": "engineering", "created_at": "2026-08-06T00:00:00"}],
            },
        }
        rendered_pending = daily_cycle.render_markdown(with_pending)
        self.assertIn("cand-1", rendered_pending)
        self.assertIn("Pendientes de revisión humana: **1**", rendered_pending)


if __name__ == "__main__":
    unittest.main()
