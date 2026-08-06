"""K9 (plan HERMES-KICKOFF) -- cano_hermes/bridge/office_usage.py.

Covers: mirroring office usage-*.json files into storage/workspaces/office-<x>/
so `BudgetService.ingest_workspace()` (K1, untouched) sees them; idempotency;
missing office directories are skipped, not errors; and an end-to-end check
that a mirrored file is actually ingested by the real BudgetService.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cano_hermes.bridge.office_usage import OFFICE_NAMES, sync_office_usage_to_workspaces
from cano_hermes.governance.budget import BudgetService
from cano_hermes.storage.sqlite import SQLiteStore


class SyncOfficeUsageTests(unittest.TestCase):
    def _dirs(self, tmp: str) -> tuple[Path, Path]:
        offices_data_root = Path(tmp) / "offices-data"
        workspaces_root = Path(tmp) / "workspaces"
        return offices_data_root, workspaces_root

    def test_no_office_directories_yet_mirrors_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            offices_data_root, workspaces_root = self._dirs(tmp)
            count = sync_office_usage_to_workspaces(offices_data_root, workspaces_root)
        self.assertEqual(count, 0)

    def test_mirrors_usage_files_from_one_office(self):
        with tempfile.TemporaryDirectory() as tmp:
            offices_data_root, workspaces_root = self._dirs(tmp)
            out_dir = offices_data_root / "analytics" / "output"
            out_dir.mkdir(parents=True)
            (out_dir / "usage-analytics-t1-123.json").write_text(
                json.dumps({"estimated_cost_usd": 0.05})
            )
            (out_dir / "hermes-report-analytics-t1-123.md").write_text("not a usage file")

            count = sync_office_usage_to_workspaces(offices_data_root, workspaces_root)

            self.assertEqual(count, 1)
            mirrored = workspaces_root / "office-analytics" / "usage-analytics-t1-123.json"
            self.assertTrue(mirrored.exists())
            self.assertNotIn("hermes-report", "\n".join(p.name for p in (workspaces_root / "office-analytics").iterdir()))

    def test_second_call_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            offices_data_root, workspaces_root = self._dirs(tmp)
            out_dir = offices_data_root / "ugc" / "output"
            out_dir.mkdir(parents=True)
            (out_dir / "usage-ugc-t1-1.json").write_text(json.dumps({"estimated_cost_usd": 0.1}))

            first = sync_office_usage_to_workspaces(offices_data_root, workspaces_root)
            second = sync_office_usage_to_workspaces(offices_data_root, workspaces_root)

            self.assertEqual(first, 1)
            self.assertEqual(second, 0)

    def test_covers_all_5_offices(self):
        self.assertEqual(
            set(OFFICE_NAMES), {"analytics", "ugc", "content", "publish", "market-intel"}
        )

    def test_mirrored_file_is_ingestible_by_real_budget_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            offices_data_root, workspaces_root = self._dirs(tmp)
            out_dir = offices_data_root / "publish" / "output"
            out_dir.mkdir(parents=True)
            (out_dir / "usage-publish-t9-1.json").write_text(
                json.dumps({"estimated_cost_usd": 0.25})
            )
            sync_office_usage_to_workspaces(offices_data_root, workspaces_root)

            store = SQLiteStore(f"sqlite:///{tmp}/budget.db")
            budget = BudgetService(store, daily_limit_usd=5.0)
            total = budget.ingest_workspace(workspaces_root)

            self.assertAlmostEqual(total, 0.25)
            ledger = budget.ledger_for()
            self.assertAlmostEqual(ledger.spent_usd, 0.25)


if __name__ == "__main__":
    unittest.main()
