"""K14 (plan HERMES-KICKOFF) -- `scripts/daily_cycle.py`'s new
`write_finance_and_orders_snapshot` step.

Regression test for a real bug caught during live verification against
production data: `metricas_diarias.valor` and `gastos.monto_usd` (both
Baserow `number` fields, confirmed live via `GET /api/database/fields/
table/136/`) reject more than 2 decimal places -- a first version of this
function passed `orders_dashboard`'s `failure_rate["rate"]` (a 4-decimal
fraction, e.g. 0.5505) straight through and got a real 400
`ERROR_REQUEST_BODY_VALIDATION`/`max_decimal_places` back from the running
Baserow instance. Every value this function writes must be pre-rounded to
<=2 decimals before it reaches `monitoring.write_metric_row`/
`write_expense_row`.
"""
from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from cano_hermes.domain.enums import OrderStatus, RiskLevel, TaskStatus
from cano_hermes.domain.models import ExecutionResult, OrderRecord, TaskCreate, TaskRecord
from cano_hermes.governance.budget import BudgetService
from cano_hermes.storage.sqlite import SQLiteStore
from scripts import daily_cycle


def _decimal_places(value: float) -> int:
    text = f"{value:.10f}".rstrip("0")
    return len(text.split(".")[1]) if "." in text else 0


class DailyCycleFinanceOrdersSnapshotTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.store = SQLiteStore(f"sqlite:///{self._tmpdir.name}/snapshot.db")
        self.budget = BudgetService(self.store, daily_limit_usd=5.0)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _seed(self):
        order = OrderRecord(objective="orden de prueba", source="api")
        order.status = OrderStatus.DONE
        self.store.save_order(order)

        task = TaskRecord(
            **TaskCreate(
                title="subtarea", objective="objetivo de prueba", domain="research",
                risk=RiskLevel.LOW, parent_task_id=order.id,
            ).model_dump(),
        )
        task.status = TaskStatus.DONE
        self.store.save_task(task)
        # A cost with more than 2 decimal places on purpose -- this is
        # exactly the shape (`round(cost, 4)` in dashboards.py) that
        # exposed the bug.
        self.store.save_execution(
            ExecutionResult(task_id=task.id, executor="claude-code", status="completed", summary="ok"),
            usage={"estimated_cost_usd": 1.23456},
        )

    def test_every_written_value_has_at_most_two_decimal_places(self):
        self._seed()
        recorded_values: list[float] = []

        def _capture_metric(fecha, oficina, metrica, valor, nota=""):
            recorded_values.append(valor)
            return {"status": "ok", "row_id": 1}

        def _capture_expense(fecha, oficina, concepto, monto_usd, aprobado_por="", solicitud_id=""):
            recorded_values.append(monto_usd)
            return {"status": "ok", "row_id": 1}

        with patch("cano_hermes.monitoring.write_metric_row", side_effect=_capture_metric), \
             patch("cano_hermes.monitoring.write_expense_row", side_effect=_capture_expense):
            result = daily_cycle.write_finance_and_orders_snapshot(self.store, self.budget)

        self.assertGreater(len(recorded_values), 0)
        for value in recorded_values:
            self.assertLessEqual(
                _decimal_places(value), 2,
                f"{value} has more than 2 decimal places -- Baserow's number fields reject this",
            )
        # The seeded 1.23456 cost must actually have reached an
        # expense_writes entry (not silently skipped) -- proves the
        # rounding happens on the way out, not by coincidentally never
        # exercising a fractional value.
        self.assertTrue(any(w["monto_usd"] > 0 for w in result["expense_writes"]))

    def test_all_writes_succeed_when_baserow_is_unreachable_gracefully(self):
        """Never raises even if every Baserow call fails -- same contract
        as `write_baserow_metrics` above it in this module."""
        self._seed()
        with patch("cano_hermes.monitoring._baserow_token", return_value=None):
            result = daily_cycle.write_finance_and_orders_snapshot(self.store, self.budget)

        for entry in result["metric_writes"]:
            self.assertEqual(entry["result"]["status"], "sin_token")
        for entry in result["expense_writes"]:
            self.assertEqual(entry["result"]["status"], "sin_token")


if __name__ == "__main__":
    unittest.main()
