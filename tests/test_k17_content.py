"""K17 (plan HERMES-KICKOFF) -- content control matrix.

Structure:
  - `DedupPureLogicTests` -- `find_conflicting_rows`/`estado_value`
    against fixture rows, both plain-string and Baserow's
    `{"value": ...}` select shape, no I/O at all.
  - `DedupSecondAttemptRejectedTests` -- the task spec's explicit
    requirement: two attempts with the same `dedup_key`, the second
    rejected, using a local fixture (no live Baserow -- deterministic).
  - `PublishRequiresVideoIdTests` -- the task spec's other explicit hard
    rule: a row with estado="publicado" cannot be inserted without a real
    video_id, proven via `insert_content_row` never even attempting the
    network call (urlopen patched and asserted un-called).
  - `DedupCliTests` -- the CLI `office-publish/task.sh` (K9) actually
    shells out to (`check-key`), exit codes only.
  - `ContentDashboardAggregationTests` -- seeds real fixtures for every
    K17 source (factory.db, ugc discovered json, upload_log_ugc.db, a
    content-routed task) and calls `content_dashboard` directly, no HTTP
    -- confirms it actually aggregates, not just an always-empty shape.
  - `ContentDashboardRouteTests` -- `GET /api/dashboard/content` and
    `/dashboard/content` respond 200 with the documented shape.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from cano_hermes.content import dedup
from cano_hermes.domain.enums import RiskLevel
from cano_hermes.domain.models import TaskCreate, TaskRecord
from cano_hermes.orchestration import dashboards
from cano_hermes.storage.sqlite import SQLiteStore


def _row(dedup_key: str, estado: str, *, as_select_object: bool = False) -> dict:
    estado_field = {"id": 1, "value": estado, "color": "blue"} if as_select_object else estado
    return {"id": 1, "canal": "cano-digital", "oficina_productora": "office-ugc",
            "estado": estado_field, "video_id": None, "dedup_key": dedup_key}


class DedupPureLogicTests(unittest.TestCase):
    def test_draft_state_blocks(self):
        rows = [_row("k1", "draft")]
        self.assertEqual(dedup.find_conflicting_rows("k1", rows), rows)

    def test_baserow_select_object_shape_normalizes(self):
        """Baserow's row-read API returns single_select as {"value": ...},
        not a bare string -- confirmed live against table 659. Both shapes
        must be recognized identically."""
        rows = [_row("k1", "draft", as_select_object=True)]
        self.assertEqual(dedup.estado_value(rows[0]), "draft")
        self.assertEqual(dedup.find_conflicting_rows("k1", rows), rows)

    def test_idea_and_brief_never_block(self):
        rows = [_row("k1", "idea"), _row("k1", "brief"), _row("k1", "producido")]
        self.assertEqual(dedup.find_conflicting_rows("k1", rows), [])

    def test_different_dedup_key_never_conflicts(self):
        rows = [_row("other-key", "publicado")]
        self.assertEqual(dedup.find_conflicting_rows("k1", rows), [])

    def test_compute_dedup_key_is_deterministic_and_case_insensitive(self):
        a = dedup.compute_dedup_key(canal="Cano-Digital", angulo="Hook A", fecha="2026-08-06")
        b = dedup.compute_dedup_key(canal="cano-digital", angulo="hook a", fecha="2026-08-06")
        self.assertEqual(a, b)
        c = dedup.compute_dedup_key(canal="cano-digital", angulo="hook b", fecha="2026-08-06")
        self.assertNotEqual(a, c)


class DedupSecondAttemptRejectedTests(unittest.TestCase):
    """The task spec's own phrasing: 'dos intentos con el mismo
    dedup_key -- el segundo rechazado, con test real'. Uses a local
    fixture standing in for Baserow's row list (no live network, fully
    deterministic) -- this is `check_dedup`'s documented `rows=` escape
    hatch, built exactly for this."""

    def test_check_dedup_clear_then_duplicate_after_first_insert(self):
        key = "test-two-attempts-key"

        # Attempt 1: matrix is empty -- clear.
        empty_matrix: list[dict] = []
        first = dedup.check_dedup(key, rows=empty_matrix)
        self.assertEqual(first["status"], "clear")

        # Simulate the real effect of a successful first insert: the row
        # now exists in the matrix at estado=draft.
        matrix_after_first_insert = [_row(key, "draft")]

        # Attempt 2: same key, matrix now carries a draft-or-later row --
        # rejected.
        second = dedup.check_dedup(key, rows=matrix_after_first_insert)
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(len(second["conflicts"]), 1)

        with self.assertRaises(dedup.ContentDedupError):
            dedup.reject_if_duplicate(key, rows=matrix_after_first_insert)

    def test_insert_content_row_second_call_rejected_via_mocked_fetch(self):
        """Same scenario, but through `insert_content_row`'s real
        control flow (the function office-publish's dedup gate and
        `content_dashboard`'s writers would actually call), with Baserow
        itself mocked out (`_content_token`/urlopen) so this stays a fast,
        deterministic unit test, not a live-network one."""
        key = "test-two-attempts-key-2"

        with patch.object(dedup, "_content_token", return_value="fake-token"), \
             patch("cano_hermes.content.dedup.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps({"id": 42}).encode()

            first = dedup.insert_content_row(
                {"canal": "cano-digital", "oficina_productora": "office-ugc", "estado": "draft", "dedup_key": key},
                rows_for_dedup=[],
            )
            self.assertEqual(first["status"], "ok")
            self.assertEqual(mock_urlopen.call_count, 1)

            # Second attempt: the matrix (fixture standing in for what
            # Baserow would now really contain) already has that key at
            # draft -- must raise BEFORE a second network call.
            with self.assertRaises(dedup.ContentDedupError):
                dedup.insert_content_row(
                    {
                        "canal": "cano-digital", "oficina_productora": "office-ugc",
                        "estado": "draft", "dedup_key": key,
                    },
                    rows_for_dedup=[_row(key, "draft")],
                )
            # Rejected before any second POST was attempted.
            self.assertEqual(mock_urlopen.call_count, 1)

    def test_check_dedup_unknown_when_baserow_unreachable(self):
        with patch.object(dedup, "fetch_rows", return_value={"status": "error", "detail": "boom"}):
            result = dedup.check_dedup("some-key")
        self.assertEqual(result["status"], "unknown")
        # unknown never raises via reject_if_duplicate -- only "duplicate" does.
        with patch.object(dedup, "fetch_rows", return_value={"status": "error", "detail": "boom"}):
            returned = dedup.reject_if_duplicate("some-key")
        self.assertEqual(returned["status"], "unknown")


class PublishRequiresVideoIdTests(unittest.TestCase):
    """The task spec's other explicit hard rule: 'no se puede insertar
    una fila con estado=publicado sin video_id'."""

    def test_validate_raises_on_empty_video_id(self):
        with self.assertRaises(dedup.ContentValidationError):
            dedup.validate_publish_requires_video_id({"estado": "publicado", "video_id": ""})

    def test_validate_raises_on_missing_video_id_key(self):
        with self.assertRaises(dedup.ContentValidationError):
            dedup.validate_publish_requires_video_id({"estado": "publicado"})

    def test_validate_passes_with_real_video_id(self):
        dedup.validate_publish_requires_video_id({"estado": "publicado", "video_id": "yt-abc123"})  # no raise

    def test_validate_does_not_apply_to_other_estados(self):
        dedup.validate_publish_requires_video_id({"estado": "draft", "video_id": ""})  # no raise

    def test_insert_content_row_rejects_before_any_network_call(self):
        """Never even attempts the POST -- the hard rule is checked
        first, with zero I/O, matching the module's own documented
        contract ('no network call' for either hard-rule check)."""
        with patch("cano_hermes.content.dedup.urllib.request.urlopen") as mock_urlopen:
            with self.assertRaises(dedup.ContentValidationError):
                dedup.insert_content_row({
                    "canal": "cano-digital", "oficina_productora": "office-ugc",
                    "estado": "publicado", "video_id": "",
                })
        mock_urlopen.assert_not_called()


class DedupCliTests(unittest.TestCase):
    def test_cli_exit_1_on_duplicate(self):
        with patch.object(dedup, "check_dedup", return_value={"status": "duplicate", "dedup_key": "k", "conflicts": [{}], "detail": None}):
            exit_code = dedup._cli(["check-key", "k"])
        self.assertEqual(exit_code, 1)

    def test_cli_exit_0_on_clear(self):
        with patch.object(dedup, "check_dedup", return_value={"status": "clear", "dedup_key": "k", "conflicts": [], "detail": None}):
            exit_code = dedup._cli(["check-key", "k"])
        self.assertEqual(exit_code, 0)

    def test_cli_exit_0_on_unknown(self):
        """Deliberately not a hard block at the CLI layer -- see the
        CLI's own docstring: a Baserow hiccup must not turn into a
        production stoppage by itself; task.sh reads the JSON status."""
        with patch.object(dedup, "check_dedup", return_value={"status": "unknown", "dedup_key": "k", "conflicts": [], "detail": "boom"}):
            exit_code = dedup._cli(["check-key", "k"])
        self.assertEqual(exit_code, 0)


class ContentDashboardAggregationTests(unittest.TestCase):
    """Seeds real fixtures for every K17 source and calls
    `content_dashboard` directly (no HTTP) -- the task spec's "confirm the
    dashboard really aggregates" requirement, mirrored from K14's own test
    style."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.store = SQLiteStore(f"sqlite:///{self.root}/k17.db")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_factory_db(self) -> Path:
        path = self.root / "factory.db"
        conn = sqlite3.connect(path)
        conn.execute(
            "CREATE TABLE distribution_campaigns (id INTEGER PRIMARY KEY, name TEXT, scope TEXT, "
            "status TEXT, publish_mode TEXT, start_date TEXT, end_date TEXT, created_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE publications (id INTEGER PRIMARY KEY, channel_id TEXT, platform TEXT, status TEXT, "
            "scheduled_at TEXT, published_at TEXT, external_id TEXT, created_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE plan_items (id INTEGER PRIMARY KEY, plan_id INTEGER, channel_id TEXT, title TEXT, "
            "format TEXT, status TEXT, planned_at TEXT, budget_usd REAL, created_at TEXT)"
        )
        conn.execute(
            "INSERT INTO distribution_campaigns VALUES (1,'10-day sprint','multi','active','manual',"
            "'2026-08-01','2026-08-10','2026-08-01T00:00:00')"
        )
        conn.execute(
            "INSERT INTO publications VALUES (1,'cosmic-lens','youtube','scheduled',"
            "'2026-08-06T18:00:00',NULL,'','2026-08-05T18:00:00')"
        )
        conn.execute(
            "INSERT INTO plan_items VALUES (1,1,'cosmic-lens','Rogue Planets','short','planned',"
            "'2026-08-07T00:00:00',5.0,'2026-08-05T00:00:00')"
        )
        conn.commit()
        conn.close()
        return path

    def _make_ugc_discovered_dir(self) -> Path:
        directory = self.root / "discovered"
        directory.mkdir()
        (directory / "2026-08-01.json").write_text(json.dumps([
            {"nombre": "Test gadget", "categoria": "cano-digital", "plataforma": "tiktok_video", "video_id": "src-1"},
            {"nombre": "Test gadget 2", "categoria": "cano-digital", "plataforma": "tiktok_video", "video_id": "src-2"},
        ]), encoding="utf-8")
        return directory

    def _make_upload_log_db(self) -> Path:
        path = self.root / "upload_log_ugc.db"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE uploads (canal TEXT, slug TEXT, fecha TEXT, status TEXT, req_id TEXT)")
        conn.execute("INSERT INTO uploads VALUES ('cano-digital','test-slug','2026-08-01','success','real-req-1')")
        conn.commit()
        conn.close()
        return path

    def test_aggregates_every_real_source(self):
        factory_db = self._make_factory_db()
        ugc_dir = self._make_ugc_discovered_dir()
        upload_log = self._make_upload_log_db()

        task = TaskRecord(
            **TaskCreate(
                title="Producir video afiliado", objective="Producir un short para cano-digital",
                domain="ugc", risk=RiskLevel.LOW,
            ).model_dump(),
            route_profile="hermes-ugc",
        )
        self.store.save_task(task)

        with patch.object(dedup, "fetch_rows", return_value={
            "status": "ok",
            "rows": [{"id": 1, "canal": "cano-digital", "oficina_productora": "office-ugc",
                       "estado": {"value": "draft"}, "video_id": None, "dedup_key": "seed-key"}],
        }):
            data = dashboards.content_dashboard(
                self.store, factory_db_path=factory_db,
                campaign_packages_dir=self.root / "no-such-campaign-packages-dir",
                ugc_discovered_dir=ugc_dir, upload_log_path=upload_log,
            )

        self.assertEqual(data["baserow_contenido"]["status"], "ok")
        self.assertEqual(len(data["baserow_contenido"]["rows"]), 1)
        self.assertEqual(data["baserow_contenido"]["rows"][0]["estado"], "draft")

        self.assertEqual(data["factory_v5"]["status"], "ok")
        self.assertEqual(data["factory_v5"]["totals"], {"campaigns": 1, "publications": 1, "plan_items": 1})

        self.assertEqual(data["factory_v5_campaign_packages"]["status"], "ausente")

        self.assertEqual(data["ugc_discovered"]["totals"], {"files": 1, "products": 2})

        self.assertEqual(data["upload_log_ugc"]["status"], "ok")
        self.assertEqual(len(data["upload_log_ugc"]["rows"]), 1)
        self.assertEqual(data["upload_log_ugc"]["rows"][0]["req_id"], "real-req-1")

        self.assertEqual(len(data["content_tasks"]), 1)
        self.assertEqual(data["content_tasks"][0]["route_profile"], "hermes-ugc")

        summary = data["sources_summary"]
        for key in (
            "baserow_contenido", "factory_v5_ledger_db", "factory_v5_campaign_packages_dir",
            "ugc_discovered_json", "upload_log_ugc_db", "orders_tasks_k5_k7",
        ):
            self.assertIn(key, summary)
        self.assertTrue(summary["factory_v5_ledger_db"]["has_data"])
        self.assertFalse(summary["factory_v5_campaign_packages_dir"]["has_data"])
        self.assertTrue(summary["ugc_discovered_json"]["has_data"])
        self.assertTrue(summary["upload_log_ugc_db"]["has_data"])
        self.assertTrue(summary["orders_tasks_k5_k7"]["has_data"])

    def test_missing_sources_degrade_to_explicit_status_not_crash(self):
        data = dashboards.content_dashboard(
            self.store,
            factory_db_path=self.root / "no-factory.db",
            campaign_packages_dir=self.root / "no-campaign-packages",
            ugc_discovered_dir=self.root / "no-discovered",
            # parent dir also missing -- exercises "ledger_dir_not_mounted"
            # (distinct from "ledger_absent", where the dir exists but the
            # db file itself hasn't been written yet).
            upload_log_path=self.root / "not-mounted" / "no-upload-log.db",
        )
        self.assertEqual(data["factory_v5"]["status"], "ausente")
        self.assertEqual(data["ugc_discovered"]["status"], "ausente")
        self.assertEqual(data["upload_log_ugc"]["status"], "ledger_dir_not_mounted")
        self.assertEqual(data["content_tasks"], [])

    def test_upload_log_dir_present_but_db_not_written_yet(self):
        """The real, expected state on this machine today (confirmed
        live): the ugc-affiliate dir IS mounted/present, but
        upload_log_ugc.db itself was never created (uploader.py writes it
        at runtime, on first real upload)."""
        data = dashboards.content_dashboard(
            self.store,
            factory_db_path=self.root / "no-factory.db",
            campaign_packages_dir=self.root / "no-campaign-packages",
            ugc_discovered_dir=self.root / "no-discovered",
            upload_log_path=self.root / "no-upload-log.db",  # self.root exists, file doesn't
        )
        self.assertEqual(data["upload_log_ugc"]["status"], "ledger_absent")


class ContentDashboardRouteTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        from cano_hermes.config import settings

        self._original_database_url = settings.database_url
        settings.database_url = f"sqlite:///{self._tmpdir.name}/k17_route.db"

        from cano_hermes.api import dependencies

        self._dependencies = dependencies
        for cached in (
            dependencies.store, dependencies.registry, dependencies.engine,
            dependencies.approvals, dependencies.budget,
            dependencies.execution_service, dependencies.forge_pipeline,
        ):
            cached.cache_clear()

        from cano_hermes.api.app import app

        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self._tmpdir.cleanup()
        from cano_hermes.config import settings

        settings.database_url = self._original_database_url
        for cached in (
            self._dependencies.store, self._dependencies.registry, self._dependencies.engine,
            self._dependencies.approvals, self._dependencies.budget,
            self._dependencies.execution_service, self._dependencies.forge_pipeline,
        ):
            cached.cache_clear()

    def test_content_route_responds_200_with_expected_shape(self):
        response = self.client.get("/api/dashboard/content")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in (
            "generated_at", "baserow_contenido", "factory_v5", "factory_v5_campaign_packages",
            "ugc_discovered", "upload_log_ugc", "content_tasks", "sources_summary",
        ):
            self.assertIn(key, data)
        self.assertIn("rows", data["baserow_contenido"])
        self.assertIn("totals", data["factory_v5"])

    def test_html_view_responds_200_and_links_other_dashboards(self):
        response = self.client.get("/dashboard/content")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        for href in ("/dashboard", "/dashboard/finance", "/dashboard/orders", "/dashboard/offices", "/dashboard/content"):
            self.assertIn(f'href="{href}"', response.text)


if __name__ == "__main__":
    unittest.main()
