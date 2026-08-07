"""K18 (plan HERMES-KICKOFF) -- unified accounting: agent/engine spend
(`BudgetService`, K1/K14) + real business accounting (CASS/Cano Digital/
LUZYA/otro) via Baserow's `contabilidad` table (`finance.accounting`, K18)
finally backing the `expense-capture`/`cash-position`/`finance-close`
skills that merged from Prometeo F5/Personal Runtime v0.3 as manifest-only
contracts (confirmed live before writing any of this: each skill was just
`manifest.json` + `SKILL.md`, zero Python).

Structure:
  - `SkillsAreManifestOnlyRegressionTests` -- pins down the pre-K18 state
    this task started from (no `logic.py`/executable module anywhere
    under `skills/expense-capture|cash-position|finance-close/`), so a
    future skill-forge run that adds code there is a visible diff, not a
    silent assumption.
  - `AccountingPureLogicTests` -- `select_value`/`validate_movement`/
    `find_duplicate_movements`/`find_duplicate_groups`, no I/O.
  - `CaptureExpenseTests` -- the expense-capture skill: draft without
    `confirm`, duplicate flagged without blocking, `confirm=True` writes
    (urlopen mocked, deterministic).
  - `CashPositionTests` -- the cash-position skill: per-negocio balance,
    consolidation reconciles, cuentas-por-cobrar/pagar honestly absent.
  - `FinanceCloseTests` -- the finance-close skill: seeded rows -> a real
    `cierre-<year>-<month>.md` file with coherent totals.
  - `ApprovalObserverTests` -- an approved, costed `ApprovalRequest`
    generates a real `contabilidad` movement (tipo=gasto, origen=agente,
    referencia=approval.id) via `ApprovalService.resolve`'s new
    `on_resolved` hook; rejected/zero-cost approvals do not.
  - `AccountingDashboardAggregationTests` -- `accounting_dashboard()`
    against fixtures, no HTTP.
  - `AccountingDashboardRouteTests` -- `GET /api/dashboard/accounting`
    responds 200 with both ledgers present (real local Baserow GET, same
    "cheap and real beats mocked" precedent K17's own route test uses).
  - `FinanceCloseRouteTests` -- `POST /api/finance/close` writes the
    report file end-to-end through the HTTP route.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from cano_hermes.domain.enums import ApprovalStatus, RiskLevel
from cano_hermes.domain.models import ApprovalRequest
from cano_hermes.finance import accounting
from cano_hermes.governance.approvals import ApprovalService
from cano_hermes.orchestration import dashboards
from cano_hermes.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]


def _row(negocio: str, tipo: str, monto: float, fecha: str, categoria: str = "cat", referencia: str = "") -> dict:
    return {
        "id": 1, "negocio": negocio, "tipo": tipo, "monto": monto,
        "moneda": "USD", "categoria": categoria, "fecha": fecha,
        "origen": "manual", "referencia": referencia, "cierre_mensual": False,
    }


class SkillsAreManifestOnlyRegressionTests(unittest.TestCase):
    """Confirms the K18 starting premise: F5's three finance skills ship
    only `manifest.json` + `SKILL.md`, no executable module of their own
    (the real logic lives in `cano_hermes.finance.accounting` instead,
    referenced from each skill's docstring)."""

    def test_no_executable_python_under_any_of_the_three_skills(self):
        for skill in ("expense-capture", "cash-position", "finance-close"):
            skill_dir = ROOT / "skills" / skill
            self.assertTrue(skill_dir.is_dir())
            py_files = list(skill_dir.glob("*.py"))
            self.assertEqual(py_files, [], f"{skill} unexpectedly has Python files: {py_files}")
            names = {p.name for p in skill_dir.iterdir()}
            self.assertEqual(names, {"manifest.json", "SKILL.md"})


class AccountingPureLogicTests(unittest.TestCase):
    def test_numeric_value_parses_baserow_number_string(self):
        self.assertEqual(accounting.numeric_value("12.5000"), 12.5)
        self.assertEqual(accounting.numeric_value(12.5), 12.5)
        self.assertEqual(accounting.numeric_value(3), 3.0)

    def test_numeric_value_returns_none_on_garbage(self):
        self.assertIsNone(accounting.numeric_value("not-a-number"))
        self.assertIsNone(accounting.numeric_value(None))
        self.assertIsNone(accounting.numeric_value(""))

    def test_select_value_normalizes_baserow_select_object(self):
        self.assertEqual(accounting.select_value({"negocio": {"value": "CASS"}}, "negocio"), "CASS")
        self.assertEqual(accounting.select_value({"negocio": "CASS"}, "negocio"), "CASS")
        self.assertIsNone(accounting.select_value({}, "negocio"))

    def test_validate_movement_rejects_bad_negocio(self):
        with self.assertRaises(accounting.AccountingValidationError):
            accounting.validate_movement({
                "negocio": "not-a-business", "tipo": "gasto", "monto": 1.0,
                "moneda": "USD", "categoria": "x", "fecha": "2026-08-01", "origen": "manual",
            })

    def test_validate_movement_rejects_negative_monto(self):
        with self.assertRaises(accounting.AccountingValidationError):
            accounting.validate_movement({
                "negocio": "CASS", "tipo": "gasto", "monto": -1.0,
                "moneda": "USD", "categoria": "x", "fecha": "2026-08-01", "origen": "manual",
            })

    def test_validate_movement_rejects_bad_tipo_and_origen(self):
        base = {"negocio": "CASS", "monto": 1.0, "moneda": "USD", "categoria": "x", "fecha": "2026-08-01"}
        with self.assertRaises(accounting.AccountingValidationError):
            accounting.validate_movement({**base, "tipo": "no-es-tipo", "origen": "manual"})
        with self.assertRaises(accounting.AccountingValidationError):
            accounting.validate_movement({**base, "tipo": "gasto", "origen": "no-es-origen"})

    def test_validate_movement_passes_on_full_valid_row(self):
        accounting.validate_movement({
            "negocio": "LUZYA", "tipo": "ingreso", "monto": 100.0, "moneda": "USD",
            "categoria": "ventas", "fecha": "2026-08-01T00:00:00Z", "origen": "manual",
        })  # no raise

    def test_find_duplicate_movements_matches_exact_shape(self):
        rows = [_row("CASS", "gasto", 50.0, "2026-08-01T00:00:00Z", "ads")]
        dupes = accounting.find_duplicate_movements(
            negocio="CASS", monto=50.0, fecha="2026-08-01T00:00:00Z", categoria="ads", rows=rows,
        )
        self.assertEqual(len(dupes), 1)
        no_match = accounting.find_duplicate_movements(
            negocio="CASS", monto=51.0, fecha="2026-08-01T00:00:00Z", categoria="ads", rows=rows,
        )
        self.assertEqual(no_match, [])

    def test_find_duplicate_groups_flags_exact_repeats_only(self):
        rows = [
            _row("CASS", "gasto", 10.0, "2026-08-01", "ads"),
            _row("CASS", "gasto", 10.0, "2026-08-01", "ads"),
            _row("CASS", "gasto", 20.0, "2026-08-01", "ads"),
        ]
        groups = accounting.find_duplicate_groups(rows)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["count"], 2)


class CaptureExpenseTests(unittest.TestCase):
    """skills/expense-capture, procedure step 5: never writes without an
    explicit `confirm=True` -- and never even touches the network to get
    there."""

    def test_without_confirm_returns_draft_and_makes_no_network_call(self):
        with patch("cano_hermes.finance.accounting.urllib.request.urlopen") as mock_urlopen:
            result = accounting.capture_expense(
                negocio="CASS", monto=42.0, categoria="publicidad", fecha="2026-08-01T00:00:00Z",
            )
        self.assertEqual(result["status"], "draft")
        self.assertEqual(result["movement"]["negocio"], "CASS")
        mock_urlopen.assert_not_called()

    def test_without_confirm_flags_duplicate_but_does_not_block(self):
        existing = [_row("CASS", "gasto", 42.0, "2026-08-01T00:00:00Z", "publicidad")]
        with patch("cano_hermes.finance.accounting.urllib.request.urlopen") as mock_urlopen:
            result = accounting.capture_expense(
                negocio="CASS", monto=42.0, categoria="publicidad", fecha="2026-08-01T00:00:00Z",
                rows_for_dedup=existing,
            )
        self.assertEqual(result["status"], "duplicate_review_required")
        self.assertEqual(len(result["duplicates"]), 1)
        mock_urlopen.assert_not_called()

    def test_confirm_true_writes_via_insert_movement(self):
        import json

        with patch.object(accounting, "_accounting_token", return_value="fake-token"), \
             patch("cano_hermes.finance.accounting.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps({"id": 99}).encode()
            result = accounting.capture_expense(
                negocio="LUZYA", tipo="gasto", monto=15.0, categoria="hosting",
                fecha="2026-08-01T00:00:00Z", origen="manual", referencia="manual-entry-1",
                confirm=True, rows_for_dedup=[],
            )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["row_id"], 99)
        self.assertEqual(mock_urlopen.call_count, 1)
        sent_body = mock_urlopen.call_args_list[0]
        # First positional arg to urlopen is the Request object built inside insert_movement.
        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode())
        self.assertEqual(sent["negocio"], "LUZYA")
        self.assertEqual(sent["referencia"], "manual-entry-1")

    def test_invalid_fields_raise_before_any_network_call(self):
        with patch("cano_hermes.finance.accounting.urllib.request.urlopen") as mock_urlopen:
            with self.assertRaises(accounting.AccountingValidationError):
                accounting.capture_expense(
                    negocio="not-a-business", monto=1.0, categoria="x", fecha="2026-08-01", confirm=True,
                )
        mock_urlopen.assert_not_called()


class CashPositionTests(unittest.TestCase):
    def test_per_negocio_balance_and_consolidation_reconciles(self):
        rows = [
            _row("CASS", "ingreso", 100.0, "2026-08-01T00:00:00Z"),
            _row("CASS", "gasto", 30.0, "2026-08-02T00:00:00Z"),
            _row("LUZYA", "ingreso", 50.0, "2026-08-01T00:00:00Z"),
        ]
        result = accounting.cash_position(rows)
        self.assertEqual(result["by_negocio"]["CASS"]["saldo_bruto_usd"], 70.0)
        self.assertEqual(result["by_negocio"]["LUZYA"]["saldo_bruto_usd"], 50.0)
        self.assertEqual(result["consolidado"]["saldo_total_usd"], 120.0)
        self.assertTrue(result["consolidado"]["reconciles"])

    def test_disponible_operativo_never_exceeds_saldo_bruto_and_warns(self):
        rows = [_row("CASS", "ingreso", 10.0, "2026-08-01T00:00:00Z")]
        result = accounting.cash_position(rows)
        cass = result["by_negocio"]["CASS"]
        self.assertEqual(cass["disponible_operativo_usd"], cass["saldo_bruto_usd"])
        self.assertIn("cuentas por cobrar", cass["advertencia"])

    def test_rows_without_fecha_are_counted_not_dropped(self):
        rows = [_row("CASS", "gasto", 5.0, "")]
        result = accounting.cash_position(rows)
        self.assertEqual(result["registros_sin_fecha"], 1)
        self.assertEqual(result["total_movimientos"], 1)

    def test_empty_ledger_returns_zeroed_consolidation(self):
        result = accounting.cash_position([])
        self.assertEqual(result["consolidado"]["saldo_total_usd"], 0.0)
        self.assertEqual(result["by_negocio"], {})

    def test_baserow_string_monto_is_still_summed_correctly(self):
        """Regression: Baserow's `number` field type serializes `monto`
        as a JSON STRING on read (confirmed live against table 660 --
        `"monto": "12.5000"`, not a bare 12.5), and `negocio`/`tipo` come
        back as `{"id":, "value":, "color":}` select objects, not bare
        strings -- i.e. this is the REAL shape `fetch_rows()` returns, not
        a fixture convenience. Before `numeric_value` existed, the old
        `isinstance(monto, (int, float))` check silently dropped every
        real fetched row from the balance -- found live while verifying
        this module end-to-end against the running Baserow instance."""
        rows = [
            {
                "negocio": {"id": 1, "value": "CASS", "color": "blue"},
                "tipo": {"id": 2, "value": "gasto", "color": "red"},
                "monto": "12.5000", "moneda": "USD", "categoria": "hosting",
                "fecha": "2026-08-07T00:00:00Z", "origen": {"id": 3, "value": "manual", "color": "gray"},
                "referencia": "",
            },
            {
                "negocio": {"id": 1, "value": "CASS", "color": "blue"},
                "tipo": {"id": 4, "value": "ingreso", "color": "green"},
                "monto": "100.0000", "moneda": "USD", "categoria": "ventas",
                "fecha": "2026-08-07T00:00:00Z", "origen": {"id": 3, "value": "manual", "color": "gray"},
                "referencia": "",
            },
        ]
        result = accounting.cash_position(rows)
        self.assertIn("CASS", result["by_negocio"])
        self.assertEqual(result["by_negocio"]["CASS"]["saldo_bruto_usd"], 87.5)
        self.assertEqual(result["total_movimientos"], 2)


class FinanceCloseTests(unittest.TestCase):
    """skills/finance-close, dry-run: a real `.md` file with coherent
    per-negocio/per-categoria totals, seeded fixture data."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out_dir = Path(self.tmp.name)

    def test_close_writes_file_with_coherent_totals(self):
        rows = [
            _row("CASS", "ingreso", 200.0, "2026-08-05T00:00:00Z", "ventas", referencia="approval-1"),
            _row("CASS", "gasto", 80.0, "2026-08-10T00:00:00Z", "ads"),
            _row("CASS", "gasto", 20.0, "2026-08-15T00:00:00Z", "hosting"),
            _row("LUZYA", "ingreso", 50.0, "2026-08-03T00:00:00Z", "ventas"),
            # different month -- must not be counted in the August close.
            _row("CASS", "gasto", 999.0, "2026-07-01T00:00:00Z", "ads"),
        ]
        result = accounting.finance_close(rows, 2026, 8, out_dir=self.out_dir)

        self.assertEqual(result["periodo"], "2026-08")
        self.assertEqual(result["movimientos_totales"], 4)  # excludes the July row
        cass = result["por_negocio"]["CASS"]
        self.assertEqual(cass["ingresos_usd"], 200.0)
        self.assertEqual(cass["gastos_usd"], 100.0)
        self.assertEqual(cass["flujo_neto_usd"], 100.0)
        self.assertEqual(cass["movimientos_con_referencia"], 1)
        self.assertEqual(cass["movimientos_sin_referencia"], 2)
        self.assertEqual(result["por_negocio"]["LUZYA"]["ingresos_usd"], 50.0)

        report_path = Path(result["report_path"])
        self.assertTrue(report_path.is_file())
        content = report_path.read_text(encoding="utf-8")
        self.assertIn("2026-08", content)
        self.assertIn("CASS", content)
        self.assertIn("LUZYA", content)
        self.assertIn("no es contabilidad formal certificada", content)

    def test_close_with_no_movements_still_writes_a_coherent_file(self):
        result = accounting.finance_close([], 2099, 1, out_dir=self.out_dir)
        self.assertEqual(result["movimientos_totales"], 0)
        self.assertTrue(Path(result["report_path"]).is_file())

    def test_duplicate_movements_flagged_not_netted_away(self):
        rows = [
            _row("CASS", "gasto", 10.0, "2026-08-01T00:00:00Z", "ads"),
            _row("CASS", "gasto", 10.0, "2026-08-01T00:00:00Z", "ads"),
        ]
        result = accounting.finance_close(rows, 2026, 8, out_dir=self.out_dir)
        self.assertEqual(len(result["posibles_duplicados"]), 1)
        self.assertEqual(result["posibles_duplicados"][0]["count"], 2)


def _full_approval_kwargs(**overrides):
    kwargs = {
        "task_id": "task-k18-1",
        "action": "hermes-agent-run",
        "motivo": "K18 accounting observer test",
        "risk": RiskLevel.MEDIUM,
        "requested_by": "conductor",
        "costo_estimado_usd": 3.25,
        "presupuesto_restante": 1.75,
        "canal": "office-content",
        "evidencia": "storage/workspaces/task-k18-1/evidence.json",
    }
    kwargs.update(overrides)
    return kwargs


class ApprovalObserverTests(unittest.TestCase):
    """K18 task 4: `ApprovalService.resolve()` now accepts `on_resolved`;
    `finance.accounting.on_approval_resolved` is the real observer wired
    at `api.dependencies.approvals()`. Exercised here against a
    standalone `ApprovalService` (not the FastAPI-wired singleton) so the
    assertions stay deterministic and don't depend on process-wide
    dependency state."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteStore(f"sqlite:///{self.tmp.name}/db.sqlite")

    def test_approved_costed_request_captures_a_gasto_movement(self):
        captured = {}

        def fake_capture_expense(**kwargs):
            captured.update(kwargs)
            return {"status": "ok"}

        with patch.object(accounting, "capture_expense", side_effect=fake_capture_expense):
            service = ApprovalService(self.store, on_resolved=accounting.on_approval_resolved)
            approval = service.request(ApprovalRequest(**_full_approval_kwargs()))
            resolved = service.resolve(approval.id, True, actor="cano")

        self.assertEqual(resolved.status, ApprovalStatus.APPROVED)
        self.assertEqual(captured["tipo"], "gasto")
        self.assertEqual(captured["origen"], "agente")
        self.assertEqual(captured["referencia"], approval.id)
        self.assertEqual(captured["monto"], 3.25)
        self.assertTrue(captured["confirm"])

    def test_rejected_request_does_not_capture(self):
        with patch.object(accounting, "capture_expense") as fake_capture:
            service = ApprovalService(self.store, on_resolved=accounting.on_approval_resolved)
            approval = service.request(ApprovalRequest(**_full_approval_kwargs(task_id="task-k18-2")))
            service.resolve(approval.id, False, actor="cano")
        fake_capture.assert_not_called()

    def test_zero_cost_approval_does_not_capture(self):
        with patch.object(accounting, "capture_expense") as fake_capture:
            service = ApprovalService(self.store, on_resolved=accounting.on_approval_resolved)
            approval = service.request(ApprovalRequest(**_full_approval_kwargs(
                task_id="task-k18-3", costo_estimado_usd=0.0,
            )))
            service.resolve(approval.id, True, actor="cano")
        fake_capture.assert_not_called()

    def test_on_resolved_failure_does_not_break_resolve(self):
        """Mirrors K4's `on_request` safety net: a bookkeeping bug must
        never take the approval resolution itself down."""
        with patch.object(accounting, "on_approval_resolved", side_effect=RuntimeError("boom")):
            service = ApprovalService(self.store, on_resolved=accounting.on_approval_resolved)
            approval = service.request(ApprovalRequest(**_full_approval_kwargs(task_id="task-k18-4")))
            resolved = service.resolve(approval.id, True, actor="cano")
        self.assertEqual(resolved.status, ApprovalStatus.APPROVED)


class AccountingDashboardAggregationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteStore(f"sqlite:///{self.tmp.name}/db.sqlite")
        from cano_hermes.governance.budget import BudgetService

        self.budget = BudgetService(self.store, daily_limit_usd=10.0)

    def test_both_ledgers_present_with_fixture_business_rows(self):
        rows = [
            _row("CASS", "ingreso", 100.0, "2026-08-01T00:00:00Z"),
            _row("CASS", "gasto", 40.0, "2026-08-02T00:00:00Z"),
        ]
        data = dashboards.accounting_dashboard(self.store, self.budget, business_rows=rows)
        self.assertIn("agent_ledger", data)
        self.assertIn("today", data["agent_ledger"])
        self.assertIn("business_ledger", data)
        self.assertEqual(data["business_ledger"]["movements_total"], 2)
        self.assertEqual(data["business_ledger"]["cash_position"]["by_negocio"]["CASS"]["saldo_bruto_usd"], 60.0)
        self.assertEqual(len(data["business_ledger"]["by_negocio_and_month"]), 1)
        self.assertEqual(data["business_ledger"]["by_negocio_and_month"][0]["negocio"], "CASS")


class AccountingDashboardRouteTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        from cano_hermes.config import settings

        self._original_database_url = settings.database_url
        settings.database_url = f"sqlite:///{self._tmpdir.name}/k18_route.db"

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

    def test_accounting_route_responds_200_with_both_ledgers(self):
        response = self.client.get("/api/dashboard/accounting")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("agent_ledger", data)
        self.assertIn("business_ledger", data)
        self.assertIn("cash_position", data["business_ledger"])
        self.assertIn("baserow_status", data["business_ledger"])

    def test_accounting_html_route_responds_200(self):
        response = self.client.get("/dashboard/accounting")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("Contabilidad", response.text)


class FinanceCloseRouteTests(unittest.TestCase):
    def test_close_route_writes_report_with_fixture_rows(self):
        fixture_rows = [_row("CASS", "ingreso", 77.0, "2099-02-05T00:00:00Z", "ventas")]
        with patch.object(accounting, "fetch_rows", return_value={"status": "ok", "rows": fixture_rows}):
            with TestClient(__import__("cano_hermes.api.app", fromlist=["app"]).app) as client:
                response = client.post("/api/finance/close", params={"year": 2099, "month": 2})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["periodo"], "2099-02")
        self.assertEqual(data["movimientos_totales"], 1)
        report_path = Path(data["report_path"])
        self.assertTrue(report_path.is_file())
        self.addCleanup(report_path.unlink, missing_ok=True)


if __name__ == "__main__":
    unittest.main()
