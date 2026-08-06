"""Plan Prometeo F13 — GET /api/dashboard and GET /dashboard.

Covers: the endpoint responds 200 with the expected aggregated shape, a
pending ApprovalRequest surfaces with its full F3 schema intact, and the
incomplete-request rejection the dashboard relies on (reusing
ApprovalRequest's own Pydantic validation, not a reimplementation) still
holds.
"""
from __future__ import annotations

import tempfile
import unittest

from fastapi.testclient import TestClient
from pydantic import ValidationError

from cano_hermes.config import settings
from cano_hermes.domain.enums import RiskLevel
from cano_hermes.domain.models import ApprovalRequest


def _full_approval_kwargs(**overrides):
    kwargs = {
        "task_id": "task-dashboard-1",
        "action": "production_write",
        "motivo": "dashboard smoke test approval",
        "risk": RiskLevel.HIGH,
        "requested_by": "conductor",
        "costo_estimado_usd": 2.0,
        "presupuesto_restante": 3.0,
        "canal": "engineering",
        "evidencia": "storage/workspaces/task-dashboard-1/evidence.json",
    }
    kwargs.update(overrides)
    return kwargs


class DashboardApiTests(unittest.TestCase):
    def setUp(self):
        # `settings` is a module-level singleton built once at first import
        # of cano_hermes.config -- pydantic BaseSettings only reads env vars
        # at *construction* time, so setting HERMES_DATABASE_URL per test
        # after that first import is a no-op and every test would silently
        # share the first test's sqlite file. Mutate the already-built
        # singleton's attribute directly instead; store()/budget()/etc. all
        # read settings.database_url fresh on each call once their
        # lru_cache is cleared, so this actually takes effect per test.
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_database_url = settings.database_url
        settings.database_url = f"sqlite:///{self._tmpdir.name}/dashboard.db"

        from cano_hermes.api import dependencies

        for cached in (
            dependencies.store, dependencies.registry, dependencies.engine,
            dependencies.approvals, dependencies.budget,
            dependencies.execution_service, dependencies.forge_pipeline,
        ):
            cached.cache_clear()

        from cano_hermes.api.app import app

        self.app = app
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self._tmpdir.cleanup()
        settings.database_url = self._original_database_url
        from cano_hermes.api import dependencies

        for cached in (
            dependencies.store, dependencies.registry, dependencies.engine,
            dependencies.approvals, dependencies.budget,
            dependencies.execution_service, dependencies.forge_pipeline,
        ):
            cached.cache_clear()

    def test_dashboard_json_has_expected_shape(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in (
            "generated_at", "approvals_pending", "approvals_pending_count",
            "budget", "connections", "ugc_performance", "offices", "baserow",
        ):
            self.assertIn(key, data)
        for key in ("day", "daily_limit_usd", "spent_usd", "remaining_usd", "percent_used"):
            self.assertIn(key, data["budget"])

    def test_pending_approval_surfaces_with_full_schema(self):
        from cano_hermes.api.dependencies import approvals

        approval = approvals().request(ApprovalRequest(**_full_approval_kwargs()))

        data = self.client.get("/api/dashboard").json()
        self.assertEqual(data["approvals_pending_count"], 1)
        row = data["approvals_pending"][0]
        self.assertEqual(row["id"], approval.id)
        # every F3-mandatory field must be present, not just a subset
        for key in (
            "motivo", "costo_estimado_usd", "presupuesto_restante",
            "canal", "evidencia", "requested_by",
        ):
            self.assertIn(key, row)
            self.assertNotEqual(row[key], "")

    def test_resolved_approval_is_excluded_from_pending(self):
        from cano_hermes.api.dependencies import approvals

        approval = approvals().request(ApprovalRequest(**_full_approval_kwargs(task_id="task-dashboard-2")))
        approvals().resolve(approval.id, True, actor="cano")

        data = self.client.get("/api/dashboard").json()
        self.assertEqual(data["approvals_pending_count"], 0)

    def test_html_dashboard_responds_200(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("Dashboard", response.text)

    def test_incomplete_approval_request_rejected_with_clear_message(self):
        """The dashboard never hand-builds a 'solicitud' — it reads whatever
        ApprovalService/SQLiteStore already validated on the way in. An
        incomplete request must fail right here, at construction, with a
        clear per-field message (F3's contract), not reach the dashboard as
        partial JSON."""
        kwargs = _full_approval_kwargs()
        del kwargs["costo_estimado_usd"]
        with self.assertRaises(ValidationError) as ctx:
            ApprovalRequest(**kwargs)
        self.assertIn("costo_estimado_usd", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
