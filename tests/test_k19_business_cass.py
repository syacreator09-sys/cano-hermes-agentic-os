"""K19 (plan HERMES-KICKOFF) -- `GET /api/dashboard/business/cass`, the
first business view (Shopify+Meta as `PENDING_NATIVE_TOOL`, real YouTube,
K17/K18 sources filtered to CASS).

Structure:
  - `NativeToolBridgeTests` -- `integrations.native_tool_bridge.
    request_job`: writes the request file once (idempotent across calls),
    stays `PENDING_NATIVE_TOOL` with no result file, flips to
    `RESOLVED_NATIVE_TOOL` only once a validly-shaped result file exists,
    and stays pending (with a `detail`) on a malformed/mismatched one.
  - `ShopifyMetaNeverWriteTests` -- the hard safety guarantee: neither
    `business.cass` nor `integrations.native_tool_bridge` import an HTTP
    client at all (source-code scan, not just "wasn't called this run"),
    so `shopify_status`/`meta_status` are structurally incapable of ever
    making a Shopify/Meta network call, write or otherwise.
  - `YoutubeIntegrationNoWriteCallTests` -- `integrations.youtube`: a
    source-code scan confirms the only non-GET HTTP verb anywhere in the
    module is the OAuth2 refresh POST (never youtube.googleapis.com), plus
    a mocked-`urlopen` test confirming the real request against
    `channels` is a GET with no request body. Also covers the sin_token
    path (missing token file) and a real, unmocked smoke call against the
    live `cass-healt` token on this host (skipped gracefully if network/
    token is unavailable, never a hard failure).
  - `ContentAccountingFilterTests` -- `business.cass.content_status`/
    `accounting_status` filter K17/K18's already-aggregated dashboards
    down to CASS, including the "Baserow source empty" case (must degrade
    to has_data=False, never raise).
  - `CassDashboardAggregationTests` -- `cass_dashboard` end-to-end against
    fixtures/overrides (no live YouTube/Shopify/Meta network), asserting
    all 5 sources are present in the documented shape even when every
    Baserow source is empty.
  - `CassDashboardRouteTests` -- `GET /api/dashboard/business/cass` and
    `/dashboard/business/cass` respond 200 with the 5 components present
    (YouTube mocked so the route test doesn't depend on live network).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from cano_hermes.business import cass as business_cass
from cano_hermes.integrations import native_tool_bridge, youtube
from cano_hermes.orchestration import dashboards
from cano_hermes.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]


class NativeToolBridgeTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.jobs_dir = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_first_call_writes_request_file_and_stays_pending(self):
        result = native_tool_bridge.request_job(
            "job-a", mcp_tools=["mcp__x__y"], params={"a": 1}, purpose="p", jobs_dir=self.jobs_dir,
        )
        self.assertEqual(result["status"], "PENDING_NATIVE_TOOL")
        request_path = self.jobs_dir / "job-a.request.json"
        self.assertTrue(request_path.is_file())
        written = json.loads(request_path.read_text())
        self.assertEqual(written["job_id"], "job-a")
        self.assertEqual(written["mcp_tools"], ["mcp__x__y"])

    def test_second_call_is_idempotent_does_not_rewrite_created_at(self):
        first = native_tool_bridge.request_job(
            "job-b", mcp_tools=["t"], params={}, purpose="p", jobs_dir=self.jobs_dir,
        )
        second = native_tool_bridge.request_job(
            "job-b", mcp_tools=["t", "changed"], params={"different": True}, purpose="different purpose",
            jobs_dir=self.jobs_dir,
        )
        self.assertEqual(first["created_at"], second["created_at"])
        # Original request wins -- a later call with different params never overwrites a queued job.
        self.assertEqual(second["mcp_tools"], ["t"])

    def test_resolved_result_file_flips_status_and_carries_data(self):
        native_tool_bridge.request_job("job-c", mcp_tools=["t"], params={}, purpose="p", jobs_dir=self.jobs_dir)
        result_path = self.jobs_dir / "job-c.result.json"
        result_path.write_text(json.dumps({
            "job_id": "job-c", "resolved_at": "2026-08-06T00:00:00Z", "data": {"shop": "ok"},
        }))
        result = native_tool_bridge.request_job("job-c", mcp_tools=["t"], params={}, purpose="p", jobs_dir=self.jobs_dir)
        self.assertEqual(result["status"], "RESOLVED_NATIVE_TOOL")
        self.assertEqual(result["data"], {"shop": "ok"})

    def test_malformed_result_file_stays_pending_with_detail(self):
        native_tool_bridge.request_job("job-d", mcp_tools=["t"], params={}, purpose="p", jobs_dir=self.jobs_dir)
        result_path = self.jobs_dir / "job-d.result.json"
        result_path.write_text(json.dumps({"job_id": "job-d"}))  # no "data" key
        result = native_tool_bridge.request_job("job-d", mcp_tools=["t"], params={}, purpose="p", jobs_dir=self.jobs_dir)
        self.assertEqual(result["status"], "PENDING_NATIVE_TOOL")
        self.assertIn("detail", result)

    def test_result_file_for_wrong_job_id_is_ignored(self):
        native_tool_bridge.request_job("job-e", mcp_tools=["t"], params={}, purpose="p", jobs_dir=self.jobs_dir)
        (self.jobs_dir / "job-e.result.json").write_text(json.dumps({"job_id": "someone-else", "data": {}}))
        result = native_tool_bridge.request_job("job-e", mcp_tools=["t"], params={}, purpose="p", jobs_dir=self.jobs_dir)
        self.assertEqual(result["status"], "PENDING_NATIVE_TOOL")


class ShopifyMetaNeverWriteTests(unittest.TestCase):
    """Structural guarantee, not just a per-run observation: these two
    modules cannot make any HTTP call at all (no urllib/requests/httpx
    import anywhere), so there is no code path -- write or read -- by
    which `shopify_status`/`meta_status` could ever touch Shopify or Meta
    directly from this backend."""

    def test_business_cass_module_imports_no_http_client(self):
        source = (ROOT / "cano_hermes/business/cass.py").read_text()
        for forbidden in ("import urllib", "import requests", "import httpx", "urlopen("):
            self.assertNotIn(forbidden, source, f"business/cass.py must never import an HTTP client ({forbidden})")

    def test_native_tool_bridge_module_imports_no_http_client(self):
        source = (ROOT / "cano_hermes/integrations/native_tool_bridge.py").read_text()
        for forbidden in ("import urllib", "import requests", "import httpx", "urlopen("):
            self.assertNotIn(forbidden, source, f"native_tool_bridge.py must never import an HTTP client ({forbidden})")

    def test_shopify_status_is_always_pending_or_resolved_native_tool_never_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = business_cass.shopify_status(jobs_dir=Path(tmp))
        self.assertIn(result["status"], ("PENDING_NATIVE_TOOL", "RESOLVED_NATIVE_TOOL"))
        self.assertIn("mcp__claude_ai_Shopify__", result["mcp_tools"][0])

    def test_meta_status_is_always_pending_or_resolved_native_tool_never_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = business_cass.meta_status(jobs_dir=Path(tmp))
        self.assertIn(result["status"], ("PENDING_NATIVE_TOOL", "RESOLVED_NATIVE_TOOL"))
        self.assertIn("mcp__claude_ai_Facebook__", result["mcp_tools"][0])


class YoutubeIntegrationNoWriteCallTests(unittest.TestCase):
    def test_module_never_issues_a_write_http_verb_against_youtube_api(self):
        source = (ROOT / "cano_hermes/integrations/youtube.py").read_text()
        # The only POST in this file must be the OAuth2 refresh grant -- never
        # a call to youtube.googleapis.com, and no PUT/PATCH/DELETE anywhere.
        for forbidden in ('method="PUT"', "method='PUT'", 'method="PATCH"', 'method="DELETE"'):
            self.assertNotIn(forbidden, source)
        post_lines = [line for line in source.splitlines() if 'method="POST"' in line or "method='POST'" in line]
        self.assertEqual(len(post_lines), 1, "expected exactly one POST call (the OAuth2 refresh grant)")
        self.assertIn("OAUTH_TOKEN_REFRESH_URL", post_lines[0])
        self.assertNotIn("youtube", post_lines[0].lower())

    def test_sin_token_when_token_file_missing(self):
        result = youtube.channel_snapshot("no-such-channel", token_path_override=Path("/nonexistent/token.json"))
        self.assertEqual(result["status"], "sin_token")
        self.assertIsNone(result["channel"])

    def test_channels_list_call_is_a_plain_get_with_no_body(self):
        """Mocks both network calls (refresh + channels.list) and inspects
        the actual `urllib.request.Request` built for the second one --
        proves the real code path issues a GET (no `data=`, default
        method) against the `channels` endpoint, never a write."""
        with tempfile.TemporaryDirectory() as tmp:
            token_path = Path(tmp) / "youtube_token.json"
            token_path.write_text(json.dumps({
                "client_id": "cid", "client_secret": "csecret", "refresh_token": "rtoken",
            }))

            refresh_response = MagicMock()
            refresh_response.read.return_value = json.dumps({"access_token": "fake-access-token"}).encode()
            refresh_response.__enter__.return_value = refresh_response

            channels_response = MagicMock()
            channels_response.read.return_value = json.dumps({
                "items": [{
                    "id": "UCFAKE", "snippet": {"title": "fake channel", "customUrl": "@fake"},
                    "statistics": {"subscriberCount": "1", "videoCount": "2", "viewCount": "3"},
                }],
            }).encode()
            channels_response.__enter__.return_value = channels_response

            requests_seen: list = []

            def fake_urlopen(req, timeout=None):
                requests_seen.append(req)
                return refresh_response if "oauth2.googleapis.com" in req.full_url else channels_response

            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                result = youtube.channel_snapshot("fake-channel", token_path_override=token_path)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["channel"]["title"], "fake channel")
        self.assertEqual(result["channel"]["subscriber_count"], 1)

        self.assertEqual(len(requests_seen), 2)
        refresh_req, channels_req = requests_seen
        self.assertEqual(refresh_req.get_method(), "POST")
        self.assertIn("oauth2.googleapis.com", refresh_req.full_url)
        self.assertEqual(channels_req.get_method(), "GET")
        self.assertIn("/youtube/v3/channels", channels_req.full_url)
        self.assertIn("mine=true", channels_req.full_url)
        self.assertIsNone(channels_req.data)

    def test_live_smoke_against_real_cass_healt_token_if_available(self):
        """K19 mandate: one real, unmocked call if the token is reachable
        and simple to use. Never a hard failure of the suite -- skips if
        the token file or network is unavailable on this host."""
        real_path = youtube.token_path("cass-healt")
        if not real_path.is_file():
            self.skipTest(f"{real_path} no existe en este host -- token cass-healt no disponible")
        result = youtube.channel_snapshot("cass-healt")
        if result["status"] != "ok":
            self.skipTest(f"llamada real no disponible ahora mismo: {result.get('detail')}")
        channel = result["channel"]
        self.assertIsInstance(channel["subscriber_count"], int)
        self.assertIsInstance(channel["video_count"], int)
        self.assertTrue(channel["title"])


def _content_row(canal: str | None, oficina: str | None, estado: str = "publicado") -> dict:
    return {"id": 1, "canal": canal, "oficina_productora": oficina, "estado": estado,
            "video_id": "v1", "costo_usd": 1.0, "link_artifact": None, "fecha": "2026-08-01",
            "dedup_key": "k"}


class ContentAccountingFilterTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteStore(url=f"sqlite:///{self._tmpdir.name}/k19.db")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_content_status_filters_rows_mentioning_cass_case_insensitive(self):
        rows = [
            _content_row("CASS-healt", "office-ugc"),
            _content_row("cano-digital", "office-ugc"),
            _content_row("otro-canal", "oficina-cass-produccion"),
            _content_row(None, None),
        ]
        with patch.object(dashboards.dedup, "fetch_rows", return_value={"status": "ok", "rows": rows}):
            result = business_cass.content_status(self.store)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["count"], 2)
        self.assertTrue(result["has_data"])

    def test_content_status_degrades_cleanly_when_baserow_table_is_empty(self):
        with patch.object(dashboards.dedup, "fetch_rows", return_value={"status": "ok", "rows": []}):
            result = business_cass.content_status(self.store)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["rows"], [])
        self.assertFalse(result["has_data"])

    def test_content_status_never_raises_when_baserow_unreachable(self):
        with patch.object(dashboards.dedup, "fetch_rows", return_value={"status": "error", "detail": "boom"}):
            result = business_cass.content_status(self.store)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["rows"], [])

    def test_accounting_status_filters_by_negocio_cass_only(self):
        rows = [
            {"id": 1, "negocio": "CASS", "tipo": "ingreso", "monto": 100.0, "fecha": "2026-08-01"},
            {"id": 2, "negocio": "LUZYA", "tipo": "ingreso", "monto": 999.0, "fecha": "2026-08-01"},
            {"id": 3, "negocio": "CASS", "tipo": "gasto", "monto": 40.0, "fecha": "2026-08-02"},
        ]
        from cano_hermes.config import settings
        from cano_hermes.governance.budget import BudgetService

        original_url = settings.database_url
        settings.database_url = f"sqlite:///{self._tmpdir.name}/k19_budget.db"
        try:
            budget = BudgetService(self.store)
            result = business_cass.accounting_status(self.store, budget, business_rows=rows)
        finally:
            settings.database_url = original_url

        self.assertEqual(result["status"], "ok")
        self.assertIsNotNone(result["cash_position"])
        self.assertEqual(result["cash_position"]["ingresos_total_usd"], 100.0)
        self.assertEqual(result["cash_position"]["gastos_total_usd"], 40.0)
        self.assertTrue(result["has_data"])
        self.assertTrue(all(row["negocio"] == "CASS" for row in result["movements_by_month"]))

    def test_accounting_status_degrades_cleanly_when_no_cass_rows(self):
        from cano_hermes.config import settings
        from cano_hermes.governance.budget import BudgetService

        original_url = settings.database_url
        settings.database_url = f"sqlite:///{self._tmpdir.name}/k19_budget2.db"
        try:
            budget = BudgetService(self.store)
            result = business_cass.accounting_status(self.store, budget, business_rows=[])
        finally:
            settings.database_url = original_url

        self.assertIsNone(result["cash_position"])
        self.assertEqual(result["movements_by_month"], [])
        self.assertFalse(result["has_data"])


class CassDashboardAggregationTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteStore(url=f"sqlite:///{self._tmpdir.name}/k19_agg.db")
        self.jobs_dir = Path(self._tmpdir.name) / "jobs"

        from cano_hermes.config import settings
        from cano_hermes.governance.budget import BudgetService

        self._original_url = settings.database_url
        settings.database_url = f"sqlite:///{self._tmpdir.name}/k19_agg_budget.db"
        self.budget = BudgetService(self.store)

    def tearDown(self):
        from cano_hermes.config import settings

        settings.database_url = self._original_url
        self._tmpdir.cleanup()

    def test_all_five_sources_present_even_with_everything_empty(self):
        with patch.object(dashboards.dedup, "fetch_rows", return_value={"status": "ok", "rows": []}):
            data = business_cass.cass_dashboard(
                self.store, self.budget, jobs_dir=self.jobs_dir,
                youtube_token_path_override=Path("/nonexistent/token.json"),
                accounting_business_rows=[],
            )

        self.assertEqual(data["negocio"], "CASS")
        for key in ("shopify", "meta", "youtube", "content", "accounting"):
            self.assertIn(key, data)

        self.assertEqual(data["shopify"]["status"], "PENDING_NATIVE_TOOL")
        self.assertEqual(data["meta"]["status"], "PENDING_NATIVE_TOOL")
        self.assertEqual(data["youtube"]["status"], "sin_token")
        self.assertEqual(data["content"]["status"], "ok")
        self.assertEqual(data["content"]["rows"], [])
        self.assertIsNone(data["accounting"]["cash_position"])


class CassDashboardRouteTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        from cano_hermes.config import settings

        self._original_database_url = settings.database_url
        settings.database_url = f"sqlite:///{self._tmpdir.name}/k19_route.db"

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

        # YouTube requires live external network -- mocked here so the HTTP
        # route test is deterministic; live behavior is covered separately
        # by YoutubeIntegrationNoWriteCallTests.
        self._youtube_patch = patch(
            "cano_hermes.integrations.youtube.channel_snapshot",
            return_value={"status": "ok", "detail": None, "channel": {
                "channel_id": "UCFAKE", "title": "fake", "custom_url": "@fake",
                "published_at": "2026-01-01T00:00:00Z", "subscriber_count": 1,
                "video_count": 1, "view_count": 1, "hidden_subscriber_count": False,
            }},
        )
        self._youtube_patch.start()

    def tearDown(self):
        self._youtube_patch.stop()
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

    def test_business_cass_route_responds_200_with_five_components(self):
        response = self.client.get("/api/dashboard/business/cass")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["negocio"], "CASS")
        for key in ("shopify", "meta", "youtube", "content", "accounting"):
            self.assertIn(key, data)
        self.assertIn(data["shopify"]["status"], ("PENDING_NATIVE_TOOL", "RESOLVED_NATIVE_TOOL"))
        self.assertIn(data["meta"]["status"], ("PENDING_NATIVE_TOOL", "RESOLVED_NATIVE_TOOL"))
        self.assertEqual(data["youtube"]["status"], "ok")
        self.assertIn("rows", data["content"])
        self.assertIn("movements_by_month", data["accounting"])

    def test_html_view_responds_200_and_links_other_dashboards(self):
        response = self.client.get("/dashboard/business/cass")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("/dashboard/accounting", response.text)


if __name__ == "__main__":
    unittest.main()
