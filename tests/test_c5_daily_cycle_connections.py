"""C5 (plan de conexiones) -- `scripts/daily_cycle.py`'s connection-alert
work: the new "## 1. Conexiones (F2)" detail (validators_totals + failed
providers + key-registry counts), the ✓->✗ regression alert, and the new
`metricas_diarias` rows.

Follows the mocking style already established by `test_k14_daily_cycle_
snapshot.py`/`test_k15_daily_cycle_memory_candidates.py`: patch
`cano_hermes.monitoring.write_metric_row` (never hit real Baserow), build
minimal `result`-shaped fixtures for `render_markdown`, and exercise the
new pure helpers (`_load_previous_connection_matrix`,
`_detect_connection_regressions`) directly with tmp-dir fixtures instead of
running the full `run_cycle()`.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import daily_cycle


def _base_result(**overrides):
    base = {
        "date": "2026-08-07",
        "alerts": [],
        "connections": {
            "status": "ok",
            "report_path": "reports/connection-matrix-2026-08-07.md",
            "totals": {"✓": 10, "✗": 2, "—": 3},
            "apify": {"status": "✓", "detail": "ok"},
            "rapidapi": {"status": "✓", "detail": "ok"},
            "validators": {
                "openai": {"status": "✓", "detail": "200 -- lista de modelos obtenida", "latency_ms": 120, "quota": None},
                "github": {"status": "✗", "detail": "token invalido (HTTP 401)", "latency_ms": 80, "quota": None},
                "kie": {"status": "policy-skip", "detail": "balance facturable, se usa readiness sin red", "latency_ms": None, "quota": None},
            },
            "validators_totals": {"✓": 1, "✗": 1, "—": 0, "policy-skip": 1},
        },
        "key_registry": {"status": "ok", "detail": None, "unclaimed_count": 42, "rotation_pending_count": 2},
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
        "memory_candidates": {"status": "ok", "pending_count": 0, "pending": []},
    }
    base.update(overrides)
    return base


class RenderMarkdownConnectionsSectionTests(unittest.TestCase):
    def test_shows_validators_totals_and_failed_providers(self):
        rendered = daily_cycle.render_markdown(_base_result())
        self.assertIn("Validadores en vivo: ✓1 ✗1 —0 policy-skip1", rendered)
        self.assertIn("Proveedores en ✗ (validador en vivo):", rendered)
        self.assertIn("`github`: token invalido (HTTP 401)", rendered)
        # openai is ✓ -- must not show up in the failed-providers list.
        self.assertNotIn("`openai`: 200", rendered)

    def test_shows_no_failed_providers_when_all_ok(self):
        result = _base_result()
        result["connections"]["validators"] = {
            "openai": {"status": "✓", "detail": "ok", "latency_ms": 1, "quota": None},
        }
        result["connections"]["validators_totals"] = {"✓": 1, "✗": 0, "—": 0, "policy-skip": 0}
        rendered = daily_cycle.render_markdown(result)
        self.assertIn("Proveedores en ✗ (validador en vivo): ninguno.", rendered)

    def test_shows_key_registry_counts(self):
        rendered = daily_cycle.render_markdown(_base_result())
        self.assertIn("Llaves sin consumidor (`config/key_registry.yaml`): **42**", rendered)
        self.assertIn("Llaves con rotación pendiente (`config/key_registry.yaml`): **2**", rendered)

    def test_never_prints_a_key_value(self):
        """Guard against the one thing this whole plan forbids: no key
        VALUE (as opposed to variable name) should ever reach the report.
        `detail` in this repo's validators only ever carries env var names
        (e.g. "`GITHUB_TOKEN`") and descriptive text -- assert none of the
        obviously secret-shaped tokens sneak in."""
        rendered = daily_cycle.render_markdown(_base_result())
        self.assertNotIn("sk-", rendered)
        self.assertNotIn("ghp_", rendered)

    def test_connections_error_status_still_renders_key_registry_line(self):
        result = _base_result(connections={"status": "error", "detail": "boom"})
        rendered = daily_cycle.render_markdown(result)
        self.assertIn("**error**: boom", rendered)
        self.assertIn("Llaves sin consumidor", rendered)

    def test_missing_key_registry_defaults_to_zero(self):
        result = _base_result()
        del result["key_registry"]
        rendered = daily_cycle.render_markdown(result)
        self.assertIn("Llaves sin consumidor (`config/key_registry.yaml`): **0**", rendered)


class DetectConnectionRegressionsTests(unittest.TestCase):
    def test_provider_ok_yesterday_failed_today_is_flagged(self):
        previous = {"validators": {"github": {"status": "✓"}, "openai": {"status": "✓"}}}
        today = {"validators": {"github": {"status": "✗"}, "openai": {"status": "✓"}}}
        self.assertEqual(daily_cycle._detect_connection_regressions(today, previous), ["github"])

    def test_no_change_flags_nothing(self):
        previous = {"validators": {"github": {"status": "✓"}}}
        today = {"validators": {"github": {"status": "✓"}}}
        self.assertEqual(daily_cycle._detect_connection_regressions(today, previous), [])

    def test_no_previous_report_flags_nothing_and_does_not_raise(self):
        today = {"validators": {"github": {"status": "✗"}}}
        self.assertEqual(daily_cycle._detect_connection_regressions(today, None), [])

    def test_provider_that_was_already_failing_is_not_a_regression(self):
        previous = {"validators": {"mistral": {"status": "✗"}}}
        today = {"validators": {"mistral": {"status": "✗"}}}
        self.assertEqual(daily_cycle._detect_connection_regressions(today, previous), [])

    def test_provider_missing_from_previous_report_is_not_a_regression(self):
        previous = {"validators": {}}
        today = {"validators": {"newprovider": {"status": "✗"}}}
        self.assertEqual(daily_cycle._detect_connection_regressions(today, previous), [])

    def test_multiple_regressions_sorted(self):
        previous = {"validators": {"github": {"status": "✓"}, "openai": {"status": "✓"}, "cohere": {"status": "✓"}}}
        today = {"validators": {"github": {"status": "✗"}, "openai": {"status": "✗"}, "cohere": {"status": "✓"}}}
        self.assertEqual(daily_cycle._detect_connection_regressions(today, previous), ["github", "openai"])

    def test_malformed_today_connections_does_not_raise(self):
        previous = {"validators": {"github": {"status": "✓"}}}
        self.assertEqual(daily_cycle._detect_connection_regressions({"status": "error"}, previous), [])
        self.assertEqual(daily_cycle._detect_connection_regressions(None, previous), [])

    def test_old_format_previous_report_with_no_validators_key(self):
        """Real-world edge case: `reports/connection-matrix-2026-08-06.json`
        in this repo predates the validators field and has no `validators`
        key at all. Must degrade to "nothing to compare", not raise."""
        previous = {"date": "2026-08-06", "totals": {"✓": 5}}
        today = {"validators": {"github": {"status": "✗"}}}
        self.assertEqual(daily_cycle._detect_connection_regressions(today, previous), [])


class LoadPreviousConnectionMatrixTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.reports_dir = Path(self._tmpdir.name)

    def _write(self, date: str, payload: dict):
        (self.reports_dir / f"connection-matrix-{date}.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def test_no_history_returns_none_without_raising(self):
        result = daily_cycle._load_previous_connection_matrix("2026-08-07", self.reports_dir)
        self.assertIsNone(result)

    def test_missing_reports_dir_returns_none_without_raising(self):
        missing = self.reports_dir / "does-not-exist"
        result = daily_cycle._load_previous_connection_matrix("2026-08-07", missing)
        self.assertIsNone(result)

    def test_prefers_exact_yesterday_file(self):
        self._write("2026-08-05", {"date": "2026-08-05", "marker": "too-old"})
        self._write("2026-08-06", {"date": "2026-08-06", "marker": "yesterday"})
        result = daily_cycle._load_previous_connection_matrix("2026-08-07", self.reports_dir)
        self.assertEqual(result["marker"], "yesterday")

    def test_falls_back_to_next_most_recent_when_yesterday_missing(self):
        self._write("2026-08-03", {"date": "2026-08-03", "marker": "older"})
        self._write("2026-08-05", {"date": "2026-08-05", "marker": "most-recent-available"})
        # No 2026-08-06.json on purpose.
        result = daily_cycle._load_previous_connection_matrix("2026-08-07", self.reports_dir)
        self.assertEqual(result["marker"], "most-recent-available")

    def test_never_picks_todays_own_file(self):
        self._write("2026-08-07", {"date": "2026-08-07", "marker": "today"})
        result = daily_cycle._load_previous_connection_matrix("2026-08-07", self.reports_dir)
        self.assertIsNone(result)

    def test_corrupt_json_returns_none_without_raising(self):
        (self.reports_dir / "connection-matrix-2026-08-06.json").write_text("{not valid json", encoding="utf-8")
        result = daily_cycle._load_previous_connection_matrix("2026-08-07", self.reports_dir)
        self.assertIsNone(result)


class WriteBaserowMetricsNewRowsTests(unittest.TestCase):
    def test_new_rows_written_with_rounded_values(self):
        result = _base_result()
        captured: list[tuple] = []

        def _capture(fecha, oficina, metrica, valor, nota=""):
            captured.append((metrica, valor))
            return {"status": "ok", "row_id": 1}

        with patch("cano_hermes.monitoring.write_metric_row", side_effect=_capture):
            written = daily_cycle.write_baserow_metrics(result)

        by_metric = {row["metrica"]: row["valor"] for row in written}
        self.assertIn("validators_ok_pct", by_metric)
        self.assertIn("validators_policy_skip_count", by_metric)
        self.assertIn("unclaimed_keys_count", by_metric)
        self.assertIn("rotation_pending_count", by_metric)

        # validators_totals = {"✓": 1, "✗": 1, "—": 0, "policy-skip": 1} -> 3 checks, 1 ok.
        self.assertAlmostEqual(by_metric["validators_ok_pct"], round(1 / 3 * 100.0, 2))
        self.assertEqual(by_metric["validators_policy_skip_count"], 1.0)
        self.assertEqual(by_metric["unclaimed_keys_count"], 42.0)
        self.assertEqual(by_metric["rotation_pending_count"], 2.0)

        for metrica, valor in captured:
            if isinstance(valor, float):
                text = f"{valor:.10f}".rstrip("0")
                decimals = len(text.split(".")[1]) if "." in text else 0
                self.assertLessEqual(decimals, 2, f"{metrica}={valor} has more than 2 decimal places")

    def test_missing_connections_and_key_registry_default_to_zero(self):
        result = _base_result(connections={"status": "error", "detail": "boom"})
        del result["key_registry"]
        with patch("cano_hermes.monitoring.write_metric_row", return_value={"status": "ok", "row_id": 1}):
            written = daily_cycle.write_baserow_metrics(result)
        by_metric = {row["metrica"]: row["valor"] for row in written}
        self.assertEqual(by_metric["validators_ok_pct"], 0.0)
        self.assertEqual(by_metric["validators_policy_skip_count"], 0.0)
        self.assertEqual(by_metric["unclaimed_keys_count"], 0.0)
        self.assertEqual(by_metric["rotation_pending_count"], 0.0)

    def test_never_raises_when_baserow_is_unreachable(self):
        result = _base_result()
        with patch("cano_hermes.monitoring.write_metric_row", return_value={"status": "sin_token"}):
            written = daily_cycle.write_baserow_metrics(result)
        for row in written:
            self.assertEqual(row["result"]["status"], "sin_token")


class KeyRegistrySummaryTests(unittest.TestCase):
    def test_counts_unclaimed_and_rotation_pending(self):
        fake_registry = {
            "status": "ok",
            "detail": None,
            "llaves": [
                {"nombre": "A", "consumidores": [], "rotacion_pendiente": False},
                {"nombre": "B", "consumidores": ["scripts/x.py:1"], "rotacion_pendiente": False},
                {"nombre": "C", "consumidores": [], "rotacion_pendiente": True},
            ],
        }
        with patch.object(daily_cycle.dashboards, "_load_key_registry", return_value=fake_registry):
            summary = daily_cycle._key_registry_summary()
        self.assertEqual(summary["unclaimed_count"], 2)
        self.assertEqual(summary["rotation_pending_count"], 1)

    def test_missing_registry_file_degrades_to_zero_counts(self):
        with patch.object(
            daily_cycle.dashboards, "_load_key_registry",
            return_value={"status": "ausente", "detail": "no existe", "llaves": []},
        ):
            summary = daily_cycle._key_registry_summary()
        self.assertEqual(summary["unclaimed_count"], 0)
        self.assertEqual(summary["rotation_pending_count"], 0)

    def test_never_raises_if_loader_blows_up(self):
        with patch.object(daily_cycle.dashboards, "_load_key_registry", side_effect=RuntimeError("boom")):
            summary = daily_cycle._key_registry_summary()
        self.assertEqual(summary["status"], "error")
        self.assertEqual(summary["unclaimed_count"], 0)


if __name__ == "__main__":
    unittest.main()
