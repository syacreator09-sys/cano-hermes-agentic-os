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

import datetime as dt
import json
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
        for path in ("/dashboard/finance", "/dashboard/orders", "/dashboard/offices", "/dashboard/connections", "/dashboard/ads", "/dashboard/trading"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn("text/html", response.headers["content-type"])

    def test_html_views_link_to_each_other(self):
        """K14's nav bar (`_dashboard_nav`) -- every dashboard page links to
        the other views, not just its own content."""
        response = self.client.get("/dashboard/finance")
        for href in (
            "/dashboard", "/dashboard/finance", "/dashboard/orders",
            "/dashboard/offices", "/dashboard/connections", "/dashboard/ads",
            "/dashboard/trading",
        ):
            self.assertIn(f'href="{href}"', response.text)

    def test_ads_route_shape(self):
        response = self.client.get("/api/dashboard/ads")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in ("meta_accounts", "draft_campaigns", "draft_campaigns_count", "published_count", "total_spend_usd"):
            self.assertIn(key, data)
        self.assertEqual(data["published_count"], 0)
        self.assertEqual(data["total_spend_usd"], 0)

    def test_trading_route_shape(self):
        """Hermetic regardless of whether cano-invest-api happens to be
        running on this machine -- points at a port nothing listens on so
        the real network path (urllib timeout/connection-refused) is what
        gets exercised, same as every other 'schema only' test here."""
        with patch("cano_hermes.orchestration.dashboards.INVEST_API_BASE_URL", "http://127.0.0.1:1"):
            response = self.client.get("/api/dashboard/trading")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in ("api", "crypto_spot", "market_intel_synthesis", "live_trading_status"):
            self.assertIn(key, data)
        self.assertEqual(data["live_trading_status"], "disabled_by_design")
        self.assertIn(data["api"]["status"], ("sin_datos", "error"))


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

        # P5 -- no provider in this fixture's usage dict, so it must be
        # honestly bucketed under "desconocido", never guessed from
        # executor="claude-code".
        by_provider = {row["provider"]: row["cost_usd"] for row in data["cost_by_provider"]}
        self.assertAlmostEqual(by_provider.get("desconocido", 0.0), 1.5)
        self.assertNotIn("claude-code", by_provider)

    def test_finance_dashboard_cost_by_provider_uses_real_usage_field(self):
        """P5 -- a run that actually wrote a --usage-file with a real
        provider string (confirmed live content:
        {"model": "kimi-k2.6", "provider": "kimi-coding", ...}) surfaces
        under its real provider name, not under 'hermes-agent'."""
        order = OrderRecord(objective="Escribe un guion", source="api")
        self.store.save_order(order)
        task = TaskRecord(**TaskCreate(
            title="Guion", objective="Escribe un guion corto", domain="content",
            risk=RiskLevel.LOW, parent_task_id=order.id,
        ).model_dump())
        self.store.save_task(task)
        execution = ExecutionResult(task_id=task.id, executor="hermes-agent", status="completed", summary="listo")
        self.store.save_execution(execution, usage={"estimated_cost_usd": 0.0, "provider": "kimi-coding", "model": "kimi-k2.6"})

        # estimated_cost_usd=0 (subscription, not metered) would be
        # filtered out by `cost > 0` upstream -- seed a second, metered
        # execution on the same provider to prove the aggregation path
        # for real instead of asserting on an all-zero fixture.
        execution2 = ExecutionResult(task_id=task.id, executor="hermes-agent", status="completed", summary="listo2")
        self.store.save_execution(execution2, usage={"estimated_cost_usd": 0.02, "provider": "kimi-coding", "model": "kimi-k2.6"})

        data = dashboards.finance_dashboard(self.store, self.budget)
        by_provider = {row["provider"]: row["cost_usd"] for row in data["cost_by_provider"]}
        self.assertAlmostEqual(by_provider.get("kimi-coding", 0.0), 0.02)

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


class CostFromGastosAggregationTests(unittest.TestCase):
    """C4 -- `finance_dashboard`'s new `cost_from_gastos` section, the
    read side of K14's write-only `gastos` Baserow table. No real
    network: `monitoring.fetch_expense_rows` is mocked directly (same
    convention `ConnectionsAggregationTests` below uses for
    `latest_connection_matrix_summary`), never `urllib.request.urlopen`
    at this layer since `finance_dashboard` doesn't touch it directly."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteStore(f"sqlite:///{self._tmpdir.name}/gastos.db")
        from cano_hermes.governance.budget import BudgetService

        self.budget = BudgetService(self.store, daily_limit_usd=10.0)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_aggregates_by_oficina_and_concepto_and_totals(self):
        today = dt.datetime.now(dt.UTC).date()
        fixture_rows = [
            {"fecha": today.isoformat(), "oficina": "publish", "concepto": "elevenlabs", "monto_usd": "10.5"},
            {"fecha": today.isoformat(), "oficina": "publish", "concepto": "gemini", "monto_usd": "4.5"},
            {"fecha": (today - dt.timedelta(days=1)).isoformat(), "oficina": "content", "concepto": "elevenlabs", "monto_usd": "2.0"},
        ]
        with patch.object(monitoring, "fetch_expense_rows", return_value={"status": "ok", "rows": fixture_rows}):
            data = dashboards.finance_dashboard(self.store, self.budget)

        gastos = data["cost_from_gastos"]
        self.assertEqual(gastos["status"], "ok")
        self.assertEqual(gastos["rows_total"], 3)
        self.assertAlmostEqual(gastos["total_usd"], 17.0)

        by_oficina = {row["oficina"]: row["monto_usd"] for row in gastos["by_oficina"]}
        self.assertAlmostEqual(by_oficina["publish"], 15.0)
        self.assertAlmostEqual(by_oficina["content"], 2.0)

        by_concepto = {row["concepto"]: row["monto_usd"] for row in gastos["by_concepto"]}
        self.assertAlmostEqual(by_concepto["elevenlabs"], 12.5)
        self.assertAlmostEqual(by_concepto["gemini"], 4.5)

        # Trend covers both distinct days seen in the fixture.
        trend_dates = {row["date"] for row in gastos["trend_daily"]}
        self.assertEqual(trend_dates, {today.isoformat(), (today - dt.timedelta(days=1)).isoformat()})

    def test_degrades_to_sin_token_without_raising(self):
        with patch.object(monitoring, "fetch_expense_rows", return_value={"status": "sin_token", "detail": "no vault"}):
            data = dashboards.finance_dashboard(self.store, self.budget)

        gastos = data["cost_from_gastos"]
        self.assertEqual(gastos["status"], "sin_token")
        self.assertEqual(gastos["by_oficina"], [])
        self.assertEqual(gastos["by_concepto"], [])
        self.assertEqual(gastos["trend_daily"], [])
        self.assertEqual(gastos["rows_total"], 0)
        # The rest of finance_dashboard must still be a real, non-empty shape.
        self.assertIn("cost_by_executor", data)
        self.assertIn("totals", data)

    def test_degrades_to_error_without_raising(self):
        with patch.object(monitoring, "fetch_expense_rows", return_value={"status": "error", "detail": "HTTP 500"}):
            data = dashboards.finance_dashboard(self.store, self.budget)

        self.assertEqual(data["cost_from_gastos"]["status"], "error")
        self.assertEqual(data["cost_from_gastos"]["detail"], "HTTP 500")

    def test_executor_granularity_note_reflects_real_distinct_executors(self):
        """The plan's honesty requirement: `executions` today distinguishes
        only by `executor`, never fabricate a provider from it."""
        with patch.object(monitoring, "fetch_expense_rows", return_value={"status": "sin_token", "detail": None}):
            data = dashboards.finance_dashboard(self.store, self.budget)

        note = data["cost_by_executor_note"]
        self.assertIn("executor", note)
        self.assertIn("proveedor", note)


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

    def _write_idle_registry(self) -> Path:
        """Separate fixture from `_write_registry` above -- distinct
        `proveedor` per claimed key so the substring match in
        `idle_provider_keys` can tell them apart deterministically."""
        registry_path = self.tmp_path / "idle_registry.yaml"
        registry_path.write_text(
            yaml.safe_dump({
                "_meta": {"nota": "fixture de test, nunca el vault real"},
                "llaves": [
                    {
                        "nombre": "ACTIVE_KEY", "proveedor": "ActiveProv", "dominio": "starhome",
                        "uso": "fixture", "consumidores": ["repo/a.py:1"],
                        "validacion": "live-free", "riesgo": "bajo",
                        "rotacion_pendiente": False, "rotacion_motivo": "",
                    },
                    {
                        "nombre": "IDLE_KEY", "proveedor": "IdleProv", "dominio": "starhome",
                        "uso": "fixture", "consumidores": ["repo/b.py:1"],
                        "validacion": "live-free", "riesgo": "medio",
                        "rotacion_pendiente": False, "rotacion_motivo": "",
                    },
                    {
                        "nombre": "UNCLAIMED_NEVER_IDLE", "proveedor": "NoSignalProv", "dominio": "starhome",
                        "uso": "fixture", "consumidores": [],
                        "validacion": "presence-only", "riesgo": "bajo",
                        "rotacion_pendiente": False, "rotacion_motivo": "",
                    },
                ],
            }),
            encoding="utf-8",
        )
        return registry_path

    def test_idle_provider_keys_flags_claimed_key_with_no_recent_signal(self):
        """C4 -- a key with a code consumer but zero recent gastos/
        executions signal must appear; a key WITH a recent gastos signal
        must not; a key with no consumer at all (C3's own unclaimed_keys
        territory) must never appear here regardless of signal."""
        registry_path = self._write_idle_registry()
        today = dt.datetime.now(dt.UTC).date()
        gastos_rows = [
            {"fecha": today.isoformat(), "oficina": "publish", "concepto": "gasto activeprov mensual", "monto_usd": "5.0"},
        ]

        with patch.object(monitoring, "fetch_expense_rows", return_value={"status": "ok", "rows": gastos_rows}):
            idle = dashboards.idle_provider_keys(None, registry_path=registry_path)

        names = {row["nombre"] for row in idle}
        self.assertIn("IDLE_KEY", names)
        self.assertNotIn("ACTIVE_KEY", names)
        self.assertNotIn("UNCLAIMED_NEVER_IDLE", names)

    def test_idle_provider_keys_recent_execution_counts_as_signal(self):
        """The `executions.executor` cross-check (pata b of the plan) --
        seeded directly through `SQLiteStore`, no HTTP."""
        registry_path = self._write_idle_registry()
        store = SQLiteStore(f"sqlite:///{self.tmp_path}/idle.db")

        order = OrderRecord(objective="fixture order", source="api")
        store.save_order(order)
        task = TaskRecord(
            **TaskCreate(
                title="fixture task", objective="fixture", domain="research",
                risk=RiskLevel.LOW, parent_task_id=order.id,
            ).model_dump(),
        )
        store.save_task(task)
        execution = ExecutionResult(
            task_id=task.id, executor="activeprov-agent", status="completed", summary="ok", exit_code=0,
        )
        store.save_execution(execution, usage={})

        with patch.object(monitoring, "fetch_expense_rows", return_value={"status": "sin_token", "detail": None}):
            idle = dashboards.idle_provider_keys(store, registry_path=registry_path)

        names = {row["nombre"] for row in idle}
        self.assertIn("IDLE_KEY", names)
        # "ActiveProv" is a substring (case-insensitive) of the seeded
        # executor "activeprov-agent" -> must be cleared by signal (b).
        self.assertNotIn("ACTIVE_KEY", names)

    def test_idle_provider_keys_store_none_skips_execution_signal_without_raising(self):
        registry_path = self._write_idle_registry()
        with patch.object(monitoring, "fetch_expense_rows", return_value={"status": "sin_token", "detail": None}):
            idle = dashboards.idle_provider_keys(None, registry_path=registry_path)
        names = {row["nombre"] for row in idle}
        # No gastos signal (sin_token) and no store -> both claimed keys idle.
        self.assertIn("IDLE_KEY", names)
        self.assertIn("ACTIVE_KEY", names)

    def test_connections_dashboard_includes_idle_keys_section(self):
        registry_path = self._write_idle_registry()
        with patch(
            "cano_hermes.orchestration.dashboards.monitoring.latest_connection_matrix_summary",
            return_value=None,
        ), patch.object(monitoring, "fetch_expense_rows", return_value={"status": "sin_token", "detail": None}):
            data = dashboards.connections_dashboard(None, registry_path=registry_path)

        self.assertIn("idle_keys", data)
        self.assertIn("idle_keys_count", data)
        self.assertIn("idle_keys_window_days", data)
        self.assertIn("idle_keys_gastos_status", data)
        self.assertEqual(data["idle_keys_gastos_status"], "sin_token")
        names = {row["nombre"] for row in data["idle_keys"]}
        self.assertEqual(data["idle_keys_count"], len(data["idle_keys"]))
        self.assertIn("IDLE_KEY", names)
        self.assertIn("ACTIVE_KEY", names)  # no gastos signal AND store=None -> both idle here.

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


class AdsAggregationTests(unittest.TestCase):
    """P2 -- seeds a tmp_path snapshot + a tmp_path draft-campaign tree
    (never storage/pending_native_tool or storage/workspaces/ads for real)
    to confirm `ads_dashboard()` genuinely aggregates instead of returning
    an always-empty shape."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_no_snapshot_degrades_honestly(self):
        result = dashboards.ads_dashboard(
            snapshot_path=self.tmp_path / "nope.json", workspace_root=self.tmp_path / "nope",
        )
        self.assertEqual(result["meta_accounts"]["status"], "sin_snapshot")
        self.assertEqual(result["draft_campaigns_count"], 0)

    def test_seeded_snapshot_and_campaign_aggregate(self):
        snapshot_path = self.tmp_path / "snapshot.json"
        snapshot_path.write_text(json.dumps({
            "job_id": "ads-meta-status",
            "data": {
                "ad_accounts": [{"business_name": "Test Biz", "account_status": "ACTIVE", "currency": "MXN", "has_payment_method": True}],
                "warning": "fixture warning",
            },
        }), encoding="utf-8")

        workspace_root = self.tmp_path / "ads"
        campaign_dir = workspace_root / "cano-digital" / "meta" / "[TEST] fixture -- 2026-08-07"
        campaign_dir.mkdir(parents=True)
        (campaign_dir / "campaign.json").write_text(json.dumps({
            "canal": "cano-digital", "plataforma": "meta", "slug": "[TEST] fixture -- 2026-08-07",
            "status": "DRAFT", "authorized": False, "published": False, "spend": 0.0,
        }), encoding="utf-8")

        result = dashboards.ads_dashboard(snapshot_path=snapshot_path, workspace_root=workspace_root)

        self.assertEqual(result["meta_accounts"]["status"], "ok")
        self.assertEqual(len(result["meta_accounts"]["ad_accounts"]), 1)
        self.assertEqual(result["draft_campaigns_count"], 1)
        self.assertEqual(result["draft_campaigns"][0]["canal"], "cano-digital")
        self.assertEqual(result["published_count"], 0)
        self.assertEqual(result["total_spend_usd"], 0)


class TradingAggregationTests(unittest.TestCase):
    """P3-B -- mocks urlopen (never real network) to confirm
    trading_dashboard() genuinely aggregates the API response + a seeded
    market-intel synthesis file instead of returning an always-empty
    shape."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_api_down_degrades_honestly(self):
        result = dashboards.trading_dashboard(invest_api_base_url="http://127.0.0.1:1", market_intel_output_dir=self.tmp_path)
        self.assertIn(result["api"]["status"], ("sin_datos", "error"))
        self.assertEqual(result["market_intel_synthesis"]["status"], "sin_datos")

    def test_seeded_api_response_and_synthesis_aggregate(self):
        output_dir = self.tmp_path
        (output_dir / "market-intel-daily-1.md").write_text("# old", encoding="utf-8")
        (output_dir / "market-intel-daily-2.md").write_text("# nueva sintesis real", encoding="utf-8")

        class _FakeResponse:
            def __init__(self, payload):
                self._payload = json.dumps(payload).encode()
            def read(self):
                return self._payload
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        responses = {
            "/health": {"status": "ok", "mode": "offline", "version": "0.3.0"},
            "/v1/crypto/spot": {"as_of": "2026-08-07T00:00:00Z", "items": [{"venue": "BINANCE", "symbol": "BTCUSDT", "status": "ok", "price": 64000.0, "currency": "USDT"}]},
        }

        def fake_urlopen(url, timeout=None):
            for path, payload in responses.items():
                if url.endswith(path):
                    return _FakeResponse(payload)
            raise AssertionError(f"unexpected url {url}")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = dashboards.trading_dashboard(invest_api_base_url="http://fake", market_intel_output_dir=output_dir)

        self.assertEqual(result["api"]["status"], "ok")
        self.assertEqual(result["crypto_spot"]["items"][0]["price"], 64000.0)
        self.assertEqual(result["market_intel_synthesis"]["status"], "ok")
        self.assertEqual(result["market_intel_synthesis"]["file"], "market-intel-daily-2.md")
        self.assertIn("nueva sintesis real", result["market_intel_synthesis"]["content"])


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
