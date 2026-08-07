"""K12 (plan HERMES-KICKOFF) -- governance/auto_approval.py and its wiring.

Structure:
  - `AutoApprovalMatrixTests` -- the 4-case matrix the K12 task spec asks
    for, exercised directly against `evaluate_auto_approval`/
    `try_auto_approve` (no HTTP, no ExecutionService) so each condition is
    isolated.
  - `SensitiveActionsAlwaysApprovalTests` -- the single most important
    guarantee of this whole phase: `publish`/any real spend NEVER
    auto-resolves, no exceptions, checked against every member of
    `SENSITIVE_ACTIONS` individually.
  - `ExecutionModeDefaultTests` -- `Settings`'s own field default changed
    dry_run -> supervised (K12 task 2), checked independently of this
    repo's own `.env` (which already overrode it before K12 -- asserting
    on `settings.execution_mode` alone would not prove the *code* default
    changed).
  - `ExecutionServiceAutoApprovalWiringTests` -- end-to-end: a LOW-risk,
    $0 task under `execution_mode="supervised"` used to dead-end at
    `approval_required` for every single run (see
    `tests/test_k7_kanban_events.py`'s
    `test_synthesis_needing_approval_blocks_order_not_fails_it` regression
    note); K12 wires the engine in so it now runs to completion instead,
    exactly as if Cano had already clicked approve.
  - `KanbanSubprocessCredentialIsolationTests` -- Seguridad v2, "aislamiento
    por tier extendido a spawns kanban": `bridge/kanban_bridge.py`'s
    `_run_hermes` used to pass no `env=` at all to `subprocess.run`,
    silently inheriting this process's full credential set into a plain
    board-state CLI call that never needs any of it.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cano_hermes.config import Settings
from cano_hermes.domain.enums import ApprovalStatus, RiskLevel, TaskStatus
from cano_hermes.domain.models import ApprovalRequest, TaskCreate
from cano_hermes.governance.approvals import ApprovalService
from cano_hermes.governance.auto_approval import (
    AUTO_APPROVAL_ACTOR,
    evaluate_auto_approval,
    load_office_never,
    try_auto_approve,
)
from cano_hermes.governance.policy import SENSITIVE_ACTIONS
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.orchestration.execution_service import ExecutionService
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]
OFFICES_ROOT = ROOT / "offices"


def _approval(**overrides) -> ApprovalRequest:
    kwargs = {
        "task_id": "task-1",
        "action": "claude-code",
        "motivo": "sensitive action requires human approval",
        "risk": RiskLevel.LOW,
        "requested_by": "system",
        "costo_estimado_usd": 0.0,
        "presupuesto_restante": 5.0,
        "canal": "engineering",
        "evidencia": "storage/workspaces/task-1/approval-evidence-task-1.json",
    }
    kwargs.update(overrides)
    return ApprovalRequest(**kwargs)


def _engine(d: str) -> TaskEngine:
    return TaskEngine(SQLiteStore(f"sqlite:///{d}/db.sqlite"), Conductor(AgentRegistry(ROOT / "agents"), ModelRouter()))


# ---------------------------------------------------------------------------
# 1. The 4-case matrix
# ---------------------------------------------------------------------------
class AutoApprovalMatrixTests(unittest.TestCase):
    def _rig(self, d: str) -> tuple[SQLiteStore, ApprovalService]:
        store = SQLiteStore(f"sqlite:///{d}/db.sqlite")
        return store, ApprovalService(store)

    def test_case_a_low_risk_zero_cost_non_sensitive_outside_never_auto_resolves(self):
        """LOW / $0 / accion no sensible / fuera de `never:` -> auto-resuelto,
        actor=policy-engine, con evidencia en la fila de approvals."""
        with tempfile.TemporaryDirectory() as d:
            store, approvals = self._rig(d)
            approval = approvals.request(_approval(requested_by="conductor"))
            resolved = try_auto_approve(approvals, approval, kanban_profile=None)

            self.assertIsNotNone(resolved)
            self.assertEqual(resolved.status, ApprovalStatus.APPROVED)
            self.assertEqual(resolved.resolved_by, AUTO_APPROVAL_ACTOR)
            self.assertIsNotNone(resolved.resolved_at)
            # Persisted, not just returned in memory.
            row = next(a for a in store.list_approvals() if a.id == approval.id)
            self.assertEqual(row.status, ApprovalStatus.APPROVED)
            self.assertEqual(row.resolved_by, AUTO_APPROVAL_ACTOR)
            # "evidencia en la fila de approvals" -- the field was mandatory
            # at creation (Prometeo F3 schema) and survives resolution
            # untouched, still pointing at something real.
            self.assertTrue(row.evidencia)

    def test_case_b_low_risk_nonzero_cost_not_auto_resolved(self):
        """LOW / $0.01 -> NO auto-resuelto (ni un centavo)."""
        with tempfile.TemporaryDirectory() as d:
            store, approvals = self._rig(d)
            approval = approvals.request(_approval(requested_by="conductor", costo_estimado_usd=0.01))
            resolved = try_auto_approve(approvals, approval, kanban_profile=None)

            self.assertIsNone(resolved)
            row = next(a for a in store.list_approvals() if a.id == approval.id)
            self.assertEqual(row.status, ApprovalStatus.PENDING)

    def test_case_c_low_risk_zero_cost_sensitive_action_not_auto_resolved(self):
        """LOW / $0 / accion en SENSITIVE_ACTIONS -> NO auto-resuelto."""
        with tempfile.TemporaryDirectory() as d:
            store, approvals = self._rig(d)
            approval = approvals.request(_approval(requested_by="conductor", action="publish"))
            resolved = try_auto_approve(approvals, approval, kanban_profile=None)

            self.assertIsNone(resolved)
            row = next(a for a in store.list_approvals() if a.id == approval.id)
            self.assertEqual(row.status, ApprovalStatus.PENDING)

    def test_case_d_action_in_office_never_not_auto_resolved_even_if_rest_qualifies(self):
        """Accion en el `never:` de su oficina -> NO auto-resuelto aunque
        risk/costo/SENSITIVE_ACTIONS de por si calificarian."""
        never = load_office_never("hermes-research", offices_root=OFFICES_ROOT)
        self.assertIn("pagar", never)  # sanity: real manifest, real list

        with tempfile.TemporaryDirectory() as d:
            store, approvals = self._rig(d)
            approval = approvals.request(
                _approval(requested_by="conductor", action="pagar", canal="hermes-research")
            )
            resolved = try_auto_approve(
                approvals, approval, kanban_profile="hermes-research", offices_root=OFFICES_ROOT
            )

            self.assertIsNone(resolved)
            row = next(a for a in store.list_approvals() if a.id == approval.id)
            self.assertEqual(row.status, ApprovalStatus.PENDING)

    def test_office_with_no_manifest_does_not_block(self):
        """A K5 placeholder profile (e.g. 'team-content') has no
        offices/<profile>/office.yaml -- that must read as 'nothing to
        check against', not as a block."""
        never = load_office_never("team-content", offices_root=OFFICES_ROOT)
        self.assertEqual(never, frozenset())

        with tempfile.TemporaryDirectory() as d:
            _store, approvals = self._rig(d)
            approval = approvals.request(_approval(requested_by="conductor"))
            resolved = try_auto_approve(
                approvals, approval, kanban_profile="team-content", offices_root=OFFICES_ROOT
            )
            self.assertIsNotNone(resolved)
            self.assertEqual(resolved.status, ApprovalStatus.APPROVED)

    def test_write_target_outside_allowed_write_paths_not_auto_resolved(self):
        with tempfile.TemporaryDirectory() as d:
            _store, approvals = self._rig(d)
            approval = approvals.request(_approval(requested_by="conductor"))
            resolved = try_auto_approve(
                approvals,
                approval,
                kanban_profile=None,
                write_target=Path(d) / "somewhere-else" / "file.txt",
                allowed_write_paths=(Path(d) / "workspace",),
            )
            self.assertIsNone(resolved)

    def test_write_target_inside_allowed_write_paths_auto_resolves(self):
        with tempfile.TemporaryDirectory() as d:
            _store, approvals = self._rig(d)
            approval = approvals.request(_approval(requested_by="conductor"))
            workspace = Path(d) / "workspace"
            resolved = try_auto_approve(
                approvals,
                approval,
                kanban_profile=None,
                write_target=workspace / "output.txt",
                allowed_write_paths=(workspace,),
            )
            self.assertIsNotNone(resolved)
            self.assertEqual(resolved.status, ApprovalStatus.APPROVED)

    def test_write_target_with_no_allowed_paths_fails_closed(self):
        """A write target given with nothing to validate it against must
        NOT auto-approve -- 'cuando dudes, requiere aprobacion humana'."""
        with tempfile.TemporaryDirectory() as d:
            _store, approvals = self._rig(d)
            approval = approvals.request(_approval(requested_by="conductor"))
            resolved = try_auto_approve(
                approvals, approval, kanban_profile=None, write_target=Path(d) / "x.txt", allowed_write_paths=()
            )
            self.assertIsNone(resolved)

    def test_negative_remaining_budget_not_auto_resolved_even_at_zero_cost(self):
        """Deliberate K12 addition beyond the literal spec: a $0 request
        must not sail through while the day's ledger is already over
        budget from unrelated prior spend."""
        with tempfile.TemporaryDirectory() as d:
            _store, approvals = self._rig(d)
            approval = approvals.request(_approval(requested_by="conductor", presupuesto_restante=-1.0))
            resolved = try_auto_approve(approvals, approval, kanban_profile=None)
            self.assertIsNone(resolved)

    def test_never_duplicates_self_approval_guard(self):
        """requested_by == AUTO_APPROVAL_ACTOR must never resolve -- and
        must not crash the caller either, it just stays pending, exactly
        like any other failed condition."""
        with tempfile.TemporaryDirectory() as d:
            store, approvals = self._rig(d)
            approval = approvals.request(_approval(requested_by=AUTO_APPROVAL_ACTOR))
            resolved = try_auto_approve(approvals, approval, kanban_profile=None)
            self.assertIsNone(resolved)
            row = next(a for a in store.list_approvals() if a.id == approval.id)
            self.assertEqual(row.status, ApprovalStatus.PENDING)


# ---------------------------------------------------------------------------
# 2. The central guarantee: publish / any real spend ALWAYS needs Cano
# ---------------------------------------------------------------------------
class SensitiveActionsAlwaysApprovalTests(unittest.TestCase):
    def test_every_sensitive_action_never_auto_resolves_even_at_zero_cost_low_risk(self):
        for action in sorted(SENSITIVE_ACTIONS):
            with self.subTest(action=action):
                decision = evaluate_auto_approval(
                    _approval(action=action, costo_estimado_usd=0.0, risk=RiskLevel.LOW)
                )
                self.assertFalse(decision.approved, f"{action!r} must never auto-approve")

    def test_publish_specifically_never_auto_resolves(self):
        self.assertIn("publish", SENSITIVE_ACTIONS)
        decision = evaluate_auto_approval(_approval(action="publish", costo_estimado_usd=0.0, risk=RiskLevel.LOW))
        self.assertFalse(decision.approved)

    def test_any_nonzero_cost_never_auto_resolves_regardless_of_how_small(self):
        for cost in (0.01, 0.5, 1.0, 100.0):
            with self.subTest(cost=cost):
                decision = evaluate_auto_approval(
                    _approval(action="claude-code", costo_estimado_usd=cost, risk=RiskLevel.LOW)
                )
                self.assertFalse(decision.approved)

    def test_medium_high_critical_risk_never_auto_resolve_even_at_zero_cost_safe_action(self):
        for risk in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL):
            with self.subTest(risk=risk):
                decision = evaluate_auto_approval(
                    _approval(action="claude-code", costo_estimado_usd=0.0, risk=risk)
                )
                self.assertFalse(decision.approved)


# ---------------------------------------------------------------------------
# 3. config.py default
# ---------------------------------------------------------------------------
class ExecutionModeDefaultTests(unittest.TestCase):
    def test_settings_field_default_is_supervised(self):
        """Checked against the pydantic field default itself, not a live
        `settings.execution_mode` read -- this repo's own `.env` already
        set HERMES_EXECUTION_MODE=supervised before K12, so reading the
        live singleton would pass even if the *code* default were still
        stale at 'dry_run'."""
        self.assertEqual(Settings.model_fields["execution_mode"].default, "supervised")


# ---------------------------------------------------------------------------
# 4. Wired end-to-end through ExecutionService
# ---------------------------------------------------------------------------
class ExecutionServiceAutoApprovalWiringTests(unittest.TestCase):
    def test_low_risk_zero_cost_task_runs_to_completion_under_supervised_mode(self):
        """Regression guard for the exact bug K12 exists to fix (see
        tests/test_k7_kanban_events.py's
        test_synthesis_needing_approval_blocks_order_not_fails_it):
        execution_mode='supervised' means PermissionEngine always denies
        the coarse 'production_write' action, so every task -- including
        trivial LOW-risk/$0 ones -- used to dead-end at approval_required.
        K12's auto_approval engine must let this one run to completion
        exactly as if a human had approved it."""
        with tempfile.TemporaryDirectory() as d:
            engine = _engine(d)
            task = engine.create(
                TaskCreate(title="Read repo", objective="Read architecture docs", domain="engineering")
            )
            engine.plan(task.id)
            service = ExecutionService(engine, "supervised", Path(d) / "ws", artifacts_root=Path(d) / "artifacts")
            # Force the underlying executor to stay simulated (no real
            # `claude` binary needed in this sandbox) while still routing
            # through the real, non-dry_run PermissionEngine -- same
            # override pattern test_k7_kanban_events.py's `_force_dry_run`
            # uses in reverse.
            service.executors["claude-code"].mode = "dry_run"

            import asyncio

            result = asyncio.run(service.run(task.id, "claude-code"))

            self.assertEqual(result.status, "simulated")
            self.assertNotEqual(result.status, "approval_required")
            refreshed = engine.require(task.id)
            self.assertEqual(refreshed.status, TaskStatus.DONE)

            approvals_rows = engine.store.list_approvals()
            self.assertEqual(len(approvals_rows), 1)
            self.assertEqual(approvals_rows[0].status, ApprovalStatus.APPROVED)
            self.assertEqual(approvals_rows[0].resolved_by, AUTO_APPROVAL_ACTOR)

    def test_high_risk_task_still_blocks_under_supervised_mode(self):
        """The same wiring must NOT auto-approve a HIGH-risk task -- it
        stays exactly as blocked as it is today."""
        with tempfile.TemporaryDirectory() as d:
            engine = _engine(d)
            task = engine.create(
                TaskCreate(
                    title="Risky change",
                    objective="Touch production config",
                    domain="engineering",
                    risk=RiskLevel.HIGH,
                )
            )
            engine.plan(task.id)
            service = ExecutionService(engine, "supervised", Path(d) / "ws", artifacts_root=Path(d) / "artifacts")
            service.executors["claude-code"].mode = "dry_run"

            import asyncio

            result = asyncio.run(service.run(task.id, "claude-code"))

            self.assertEqual(result.status, "approval_required")
            refreshed = engine.require(task.id)
            self.assertEqual(refreshed.status, TaskStatus.APPROVAL)
            approvals_rows = engine.store.list_approvals()
            self.assertEqual(len(approvals_rows), 1)
            self.assertEqual(approvals_rows[0].status, ApprovalStatus.PENDING)


# ---------------------------------------------------------------------------
# 5. Seguridad v2 -- credential isolation extended to kanban CLI spawns
# ---------------------------------------------------------------------------
class KanbanSubprocessCredentialIsolationTests(unittest.TestCase):
    def test_kanban_subprocess_env_strips_every_secret_shaped_variable(self):
        import os
        from unittest.mock import patch

        from cano_hermes.bridge.kanban_bridge import _kanban_subprocess_env

        fake_environ = {
            "PATH": "/usr/bin",
            "HOME": "/home/cano",
            "HERMES_HOME": "/office/hermes-home",
            "ANTHROPIC_API_KEY": "sk-ant-should-not-leak",
            "OPENAI_API_KEY": "sk-should-not-leak",
            "KIMI_API_KEY": "should-not-leak",
            "TELEGRAM_BOT_TOKEN": "should-not-leak",
            "STARHOME_BRIDGE_HMAC_SECRET": "should-not-leak",
            "SOME_ACCESS_TOKEN": "should-not-leak",
        }
        with patch.dict(os.environ, fake_environ, clear=True):
            env = _kanban_subprocess_env()

        self.assertEqual(env.get("PATH"), "/usr/bin")
        self.assertEqual(env.get("HOME"), "/home/cano")
        self.assertEqual(env.get("HERMES_HOME"), "/office/hermes-home")
        for secret_var in (
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "KIMI_API_KEY",
            "TELEGRAM_BOT_TOKEN",
            "STARHOME_BRIDGE_HMAC_SECRET",
            "SOME_ACCESS_TOKEN",
        ):
            self.assertNotIn(secret_var, env)

    def test_run_hermes_passes_the_stripped_env_to_subprocess_run(self):
        from unittest.mock import patch

        from cano_hermes.bridge.kanban_bridge import _run_hermes

        with patch("cano_hermes.bridge.kanban_bridge.subprocess.run") as fake_run:
            fake_run.return_value = __import__("subprocess").CompletedProcess(
                args=["hermes"], returncode=0, stdout="{}", stderr=""
            )
            _run_hermes(["hermes", "kanban", "boards", "create", "starhome"], timeout=5.0)

        self.assertIn("env", fake_run.call_args.kwargs)
        self.assertNotIn("ANTHROPIC_API_KEY", fake_run.call_args.kwargs["env"])


if __name__ == "__main__":
    unittest.main()
