"""K14 (plan HERMES-KICKOFF) -- `GET /api/dashboard/{finance,orders,offices}`
and the aggregation behind them (`orchestration/dashboards.py`).

Structure:
  - `DashboardRoutesShapeTests` -- the 3 new HTTP routes (+ their HTML
    twins) respond 200 with the documented top-level shape, against an
    empty store. Schema, not values -- real data is exercised separately.
  - `FinanceAndOrdersAggregationTests` -- seeds a real order, a real child
    task, and a real `executions` row carrying non-zero `usage_json`
    directly through `SQLiteStore` (no HTTP, no ExecutionService), then
    calls `dashboards.finance_dashboard`/`orders_dashboard` directly and
    asserts the seeded cost/throughput actually surfaces -- the task spec's
    explicit "confirm the dashboard really aggregates and doesn't return
    empty structure" requirement.
  - `OfficeContainerStatusMatchingTests` -- the K14 fix to
    `monitoring.office_container_status()` (it used to compare against the
    bare "office-<name>" string, which `docker compose`-assigned container
    names like "offices-office-analytics-1" never equal -- confirmed live
    before this fix, every office silently read 'down' forever).
  - `CachedSubprocessChecksTests` -- `docker_stats_cached`/
    `kanban_board_stats_cached` never raise when the underlying binary is
    unavailable, and the offices dashboard route stays 200 in that case.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from fastapi.testclient import TestClient

from cano_hermes import monitoring
from cano_hermes.config import settings
from cano_hermes.domain.enums import OrderStatus, RiskLevel, TaskStatus
from cano_hermes.domain.models import (
    ExecutionResult,
    OrderRecord,
    TaskCreate,
    TaskEvent,
    TaskRecord,
)
from cano_hermes.orchestration import dashboards
from cano_hermes.storage.sqlite import SQLiteStore


class DashboardRoutesShapeTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_database_url = settings.database_url
        settings.database_url = f"sqlite:///{self._tmpdir.name}/k14.db"

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
        settings.database_url = self._original_database_url
        for cached in (
            self._dependencies.store, self._dependencies.registry, self._dependencies.engine,
            self._dependencies.approvals, self._dependencies.budget,
            self._dependencies.execution_service, self._dependencies.forge_pipeline,
        ):
            cached.cache_clear()

    def test_finance_route_shape(self):
        response = self.client.get("/api/dashboard/finance")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in (
            "generated_at", "ledger_daily", "today", "cost_by_executor",
            "cost_by_office", "cost_by_order", "cost_by_task_top", "totals",
        ):
            self.assertIn(key, data)
        for key in ("day", "daily_limit_usd", "spent_usd", "remaining_usd", "percent_used",
                    "projected_spend_usd", "projected_percent_used"):
            self.assertIn(key, data["today"])
        # 5 K9 offices always present, even with zero usage files.
        self.assertEqual({row["office"] for row in data["cost_by_office"]},
                          set(monitoring.OFFICE_NAMES))

    def test_orders_route_shape(self):
        response = self.client.get("/api/dashboard/orders")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in (
            "generated_at", "active_orders", "active_orders_count", "orders_total_count",
            "throughput", "failure_rate", "queue",
        ):
            self.assertIn(key, data)
        for key in ("orders_per_day", "avg_seconds_to_done", "avg_hours_to_done", "sample_size"):
            self.assertIn(key, data["throughput"])
        for key in ("pending_executions", "running_executions", "tasks_ready", "tasks_running"):
            self.assertIn(key, data["queue"])
        self.assertEqual(data["active_orders"], [])
        self.assertEqual(data["active_orders_count"], 0)

    def test_offices_route_shape(self):
        response = self.client.get("/api/dashboard/offices")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("offices", data)
        self.assertEqual(len(data["offices"]), 5)
        names = {o["office"] for o in data["offices"]}
        self.assertEqual(names, set(monitoring.OFFICE_NAMES))
        for office in data["offices"]:
            for key in ("status", "last_run", "budget_daily_usd", "actual_spent_usd", "over_budget"):
                self.assertIn(key, office)
            self.assertIn(office["status"], ("up", "down", "unknown"))

    def test_connections_route_shape(self):
        """C3 -- schema only, against whatever the real registry/matrix on
        this host happen to hold right now (same convention
        `test_offices_route_shape` already uses for docker/kanban: no
        mocking, just assert the documented top-level shape holds)."""
        response = self.client.get("/api/dashboard/connections")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in (
            "generated_at", "registry", "unclaimed_keys", "unclaimed_keys_count",
            "rotation_pending", "rotation_pending_count", "matrix",
        ):
            self.assertIn(key, data)
        for key in ("status", "detail", "total_keys", "by_domain"):
            self.assertIn(key, data["registry"])
        for key in (
            "status", "date", "report_path", "validators",
            "validators_totals", "totals", "apify", "rapidapi",
        ):
            self.assertIn(key, data["matrix"])
        self.assertIn(data["matrix"]["status"], ("ok", "sin_datos"))

    def test_html_views_respond_200(self):
        for path in ("/dashboard/finance", "/dashboard/orders", "/dashboard/offices", "/dashboard/connections"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn("text/html", response.headers["content-type"])

    def test_html_views_link_to_each_other(self):
        """K14's nav bar (`_dashboard_nav`) -- every dashboard page links to
        the other views, not just its own content."""
        response = self.client.get("/dashboard/finance")
        for href in (
            "/dashboard", "/dashboard/finance", "/dashboard/orders",
            "/dashboard/offices", "/dashboard/connections",
        ):
            self.assertIn(f'href="{href}"', response.text)


class FinanceAndOrdersAggregationTests(unittest.TestCase):
    """No HTTP, no ExecutionService -- seeds `SQLiteStore` directly with one
    order, one child task, and one execution carrying real usage cost, then
    calls the aggregation functions directly. This is the task spec's
    "at least one test with real seeded data" requirement."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteStore(f"sqlite:///{self._tmpdir.name}/seeded.db")
        from cano_hermes.governance.budget import BudgetService

        self.budget = BudgetService(self.store, daily_limit_usd=10.0)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _seed_order_with_costed_task(self) -> tuple[OrderRecord, TaskRecord]:
        order = OrderRecord(objective="Investiga el mercado de semiconductores", source="api")
        self.store.save_order(order)

        task = TaskRecord(
            **TaskCreate(
                title="Subtarea de investigación",
                objective="Recolecta 5 fuentes primarias",
                domain="research",
                risk=RiskLevel.LOW,
                parent_task_id=order.id,
            ).model_dump(),
        )
        task.status = TaskStatus.DONE
        self.store.save_task(task)

        execution = ExecutionResult(
            task_id=task.id, executor="claude-code", status="completed",
            summary="listo", exit_code=0,
        )
        self.store.save_execution(execution, usage={"estimated_cost_usd": 1.5})
        return order, task

    def test_finance_dashboard_aggregates_seeded_cost(self):
        order, task = self._seed_order_with_costed_task()

        data = dashboards.finance_dashboard(self.store, self.budget)

        self.assertGreater(data["totals"]["all_time_recorded_cost_usd"], 0.0)
        self.assertEqual(data["totals"]["executions_priced"], 1)

        by_executor = {row["executor"]: row["cost_usd"] for row in data["cost_by_executor"]}
        self.assertAlmostEqual(by_executor.get("claude-code", 0.0), 1.5)

        by_order = {row["order_id"]: row["cost_usd"] for row in data["cost_by_order"]}
        self.assertAlmostEqual(by_order.get(order.id, 0.0), 1.5)

        by_task = {row["task_id"]: row["cost_usd"] for row in data["cost_by_task_top"]}
        self.assertAlmostEqual(by_task.get(task.id, 0.0), 1.5)

    def test_orders_dashboard_resolves_child_task_tree_and_throughput(self):
        order, _task = self._seed_order_with_costed_task()
        order.status = OrderStatus.DONE
        order.updated_at = order.created_at
        self.store.save_order(order)
        self.store.add_event(TaskEvent(task_id=order.id, kind="order.done", actor="test"))

        data = dashboards.orders_dashboard(self.store)

        self.assertEqual(data["orders_total_count"], 1)
        # order.status is DONE, not one of the "active" statuses -- it must
        # not appear in active_orders (that's the whole point of the
        # active/terminal split), but it must still count toward
        # throughput/failure_rate below.
        self.assertEqual(data["active_orders_count"], 0)
        self.assertEqual(data["failure_rate"]["done_count"], 1)
        self.assertEqual(data["throughput"]["sample_size"], 1)
        self.assertIsNotNone(data["throughput"]["avg_seconds_to_done"])

    def test_orders_dashboard_active_order_resolves_children(self):
        order, task = self._seed_order_with_costed_task()  # order stays RECEIVED (active)

        data = dashboards.orders_dashboard(self.store)

        self.assertEqual(data["active_orders_count"], 1)
        row = data["active_orders"][0]
        self.assertEqual(row["id"], order.id)
        self.assertEqual(len(row["tasks"]), 1)
        self.assertEqual(row["tasks"][0]["id"], task.id)
        self.assertEqual(row["tasks"][0]["executor"], "claude-code")

    def test_finance_dashboard_never_empty_structure_with_seeded_data(self):
        """The task spec's own phrasing: confirm this is not just an
        always-empty shape regardless of what's in the store."""
        empty = dashboards.finance_dashboard(self.store, self.budget)
        self.assertEqual(empty["cost_by_order"], [])
        self.assertEqual(empty["cost_by_executor"], [])

        self._seed_order_with_costed_task()
        seeded = dashboards.finance_dashboard(self.store, self.budget)
        self.assertNotEqual(seeded["cost_by_order"], [])
        self.assertNotEqual(seeded["cost_by_executor"], [])


class ConnectionsAggregationTests(unittest.TestCase):
    """C3 -- seeds a tmp_path `key_registry.yaml` (never the real vault
    mirror) and mocks `monitoring.latest_connection_matrix_summary()`
    (never a real report file, never network) to confirm
    `connections_dashboard()` genuinely aggregates both sources instead of
    returning an always-empty shape -- same criterion
    `FinanceAndOrdersAggregationTests`/`content_dashboard`'s own tests use
    for the other views."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_registry(self) -> Path:
        registry_path = self.tmp_path / "key_registry.yaml"
        registry_path.write_text(
            yaml.safe_dump({
                "_meta": {"nota": "fixture de test, nunca el vault real"},
                "llaves": [
                    {
                        "nombre": "TEST_KEY_CLAIMED", "proveedor": "TestProv", "dominio": "starhome",
                        "uso": "fixture", "consumidores": ["repo/file.py:1"],
                        "validacion": "live-free", "riesgo": "bajo",
                        "rotacion_pendiente": False, "rotacion_motivo": "",
                    },
                    {
                        "nombre": "TEST_KEY_UNCLAIMED", "proveedor": "TestProv", "dominio": "otro-proyecto",
                        "uso": "fixture", "consumidores": [],
                        "validacion": "presence-only", "riesgo": "alto",
                        "rotacion_pendiente": False, "rotacion_motivo": "",
                    },
                    {
                        "nombre": "TEST_KEY_ROTATE", "proveedor": "TestProv", "dominio": "factory-v5",
                        "uso": "fixture", "consumidores": ["repo/other.py:5"],
                        "validacion": "live-free", "riesgo": "alto",
                        "rotacion_pendiente": True, "rotacion_motivo": "expuesta en logs",
                    },
                ],
            }),
            encoding="utf-8",
        )
        return registry_path

    def test_connections_dashboard_aggregates_registry_and_matrix(self):
        registry_path = self._write_registry()
        fake_matrix = {
            "date": "2026-01-01",
            "report_path": "reports/connection-matrix-2026-01-01.md",
            "totals": {"✓": 1, "✗": 0, "—": 0},
            "validators": {
                "testprov": {"status": "✓", "detail": "200 ok", "latency_ms": 123, "quota": None},
            },
            "validators_totals": {"✓": 1, "✗": 0, "—": 0, "policy-skip": 0},
            "apify": {"status": "—", "detail": "n/a"},
            "rapidapi": {"status": "—", "detail": "n/a"},
        }

        with patch(
            "cano_hermes.orchestration.dashboards.monitoring.latest_connection_matrix_summary",
            return_value=fake_matrix,
        ):
            data = dashboards.connections_dashboard(registry_path=registry_path)

        self.assertEqual(data["registry"]["status"], "ok")
        self.assertEqual(data["registry"]["total_keys"], 3)
        self.assertEqual(data["registry"]["by_domain"], {"factory-v5": 1, "otro-proyecto": 1, "starhome": 1})

        self.assertEqual(data["unclaimed_keys_count"], 1)
        self.assertEqual(data["unclaimed_keys"][0]["nombre"], "TEST_KEY_UNCLAIMED")

        self.assertEqual(data["rotation_pending_count"], 1)
        self.assertEqual(data["rotation_pending"][0]["nombre"], "TEST_KEY_ROTATE")
        self.assertEqual(data["rotation_pending"][0]["rotacion_motivo"], "expuesta en logs")

        self.assertEqual(data["matrix"]["status"], "ok")
        self.assertEqual(data["matrix"]["date"], "2026-01-01")
        self.assertEqual(len(data["matrix"]["validators"]), 1)
        self.assertEqual(data["matrix"]["validators"][0]["provider"], "testprov")
        self.assertEqual(data["matrix"]["validators"][0]["latency_ms"], 123)
        self.assertEqual(data["matrix"]["validators_totals"]["✓"], 1)

    def test_connections_dashboard_handles_missing_matrix_without_raising(self):
        """`latest_connection_matrix_summary()` returning None (audit never
        ran in this environment) must not raise -- the endpoint still
        responds 200 with an explicit 'sin_datos' section."""
        registry_path = self._write_registry()

        with patch(
            "cano_hermes.orchestration.dashboards.monitoring.latest_connection_matrix_summary",
            return_value=None,
        ):
            data = dashboards.connections_dashboard(registry_path=registry_path)

        self.assertEqual(data["matrix"]["status"], "sin_datos")
        self.assertEqual(data["matrix"]["validators"], [])
        self.assertEqual(data["matrix"]["validators_totals"], {})
        # Registry aggregation must still work even with no matrix data.
        self.assertEqual(data["registry"]["total_keys"], 3)

    def test_connections_route_survives_missing_matrix(self):
        """HTTP-level guard for the same contract: the FastAPI route
        itself must stay 200, not just the aggregation function."""
        from cano_hermes.api import dependencies
        from cano_hermes.api.app import app

        for cached in (
            dependencies.store, dependencies.registry, dependencies.engine,
            dependencies.approvals, dependencies.budget,
            dependencies.execution_service, dependencies.forge_pipeline,
        ):
            cached.cache_clear()

        with patch(
            "cano_hermes.orchestration.dashboards.monitoring.latest_connection_matrix_summary",
            return_value=None,
        ), TestClient(app) as client:
            response = client.get("/api/dashboard/connections")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["matrix"]["status"], "sin_datos")


class OfficeContainerStatusMatchingTests(unittest.TestCase):
    """K14 fix: `docker compose` names containers "<project>-office-<name>-
    <n>" (confirmed live: "offices-office-analytics-1"), never the bare
    "office-<name>" the pre-K14 exact-match check compared against -- so
    every office silently read 'down' forever, even while running."""

    def test_substring_match_recognizes_compose_named_container(self):
        import subprocess
        from unittest.mock import patch

        fake_ps = subprocess.CompletedProcess(
            args=["docker", "ps"], returncode=0,
            stdout="offices-office-analytics-1\nsome-unrelated-container\n", stderr="",
        )
        with patch("cano_hermes.monitoring.shutil.which", return_value="/usr/bin/docker"), \
             patch("cano_hermes.monitoring.subprocess.run", return_value=fake_ps):
            statuses = monitoring.office_container_status()

        self.assertEqual(statuses["office-analytics"], "up")
        self.assertEqual(statuses["office-ugc"], "down")
        # K9 added market-intel as the 5th office; it must be checked too.
        self.assertIn("office-market-intel", statuses)

    def test_exact_bare_name_would_not_have_matched(self):
        """Regression guard for the exact bug: the OLD exact-equality
        check against "office-analytics" fails against the real container
        name below, proving the fix (substring match) is what actually
        makes `test_substring_match_recognizes_compose_named_container`
        pass, not an unrelated change."""
        real_name = "offices-office-analytics-1"
        self.assertNotEqual(real_name, "office-analytics")
        self.assertIn("office-analytics", real_name)


class CachedSubprocessChecksTests(unittest.TestCase):
    """`docker_stats_cached`/`kanban_board_stats_cached` (K14's caching
    decision for the offices dashboard) must degrade gracefully -- never
    raise -- when Docker/hermes aren't on PATH, and the offices dashboard
    route must stay 200 in that case."""

    def setUp(self):
        monitoring._CACHE.clear()

    def tearDown(self):
        monitoring._CACHE.clear()

    def test_docker_stats_cached_missing_binary_does_not_raise(self):
        from unittest.mock import patch

        with patch("cano_hermes.monitoring.shutil.which", return_value=None):
            result = monitoring.docker_stats_cached(ttl_seconds=30.0)

        self.assertEqual(result["status"], "sin_binario")

    def test_docker_stats_cached_reuses_value_within_ttl(self):
        from unittest.mock import patch

        calls = {"n": 0}

        def fake_check():
            calls["n"] += 1
            return {"status": "ok", "containers": []}

        with patch("cano_hermes.monitoring.check_docker_stats", side_effect=fake_check):
            monitoring.docker_stats_cached(ttl_seconds=60.0)
            monitoring.docker_stats_cached(ttl_seconds=60.0)

        self.assertEqual(calls["n"], 1)

    def test_offices_dashboard_survives_docker_and_hermes_unavailable(self):
        from unittest.mock import patch

        with patch("cano_hermes.monitoring.shutil.which", return_value=None):
            data = dashboards.offices_dashboard(docker_stats_ttl=0.0, kanban_stats_ttl=0.0)

        self.assertEqual(data["docker_stats_status"], "sin_binario")
        self.assertEqual(data["kanban_board_stats_status"], "sin_binario")
        self.assertEqual(len(data["offices"]), 5)
        for office in data["offices"]:
            self.assertIsNone(office["docker_usage"])
            self.assertIsNone(office["kanban_tasks_in_profile"])


if __name__ == "__main__":
    unittest.main()
