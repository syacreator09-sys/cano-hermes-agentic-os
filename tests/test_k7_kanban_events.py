"""K7 (plan HERMES-KICKOFF, gap 2 continuation) -- Kanban -> StarHome bridge.

Covers:
  (a) `inbound.verify_signature` -- valid/invalid/missing signature, unset
      secret always fails closed.
  (b) The three event types (`claimed`/`completed`/`blocked`) transition the
      resolved `TaskRecord` (forward-compat direct task link) as expected,
      and are idempotent against redelivery (the `starhome-bridge` plugin's
      retry queue is at-least-once).
  (c) The three event types against a resolved `OrderRecord`: `claimed` is
      an audit event only (`OrderStatus` has no RUNNING-equivalent),
      `blocked` moves the order to BLOCKED, `completed` triggers
      `aggregator.close_order_with_synthesis` and lands the order on DONE
      with `aggregate_artifact` set, and fires `notifier.notify_order_done`
      exactly once.
  (d) `aggregator.all_terminal` and the "order with tracked children"
      forward-compat path (empty list is not vacuously "all terminal";
      partial completion does not aggregate; full completion does).
  (e) An unknown `kanban_task_id` is ignored (200, no transition, no
      exception).
  (f) `POST /api/bridge/kanban-events` end-to-end via `TestClient`: valid
      signature does the real thing, invalid/missing signature is a 401
      that touches nothing.

None of these tests shell out to `hermes` or hit the real Telegram API --
`send_telegram_message` is monkeypatched everywhere a DONE/BLOCKED
transition could otherwise attempt a real network call, mirroring K4's own
test style.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from cano_hermes.bridge import inbound
from cano_hermes.domain.enums import OrderStatus, RiskLevel, TaskStatus
from cano_hermes.domain.models import OrderRecord, TaskCreate, TaskRecord
from cano_hermes.governance.budget import BudgetService
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.notifications.service import NotificationService
from cano_hermes.orchestration import aggregator
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.orchestration.execution_service import ExecutionService
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]
SECRET = "test-secret-do-not-use-in-prod"


def _sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _rig(d: str):
    """Isolated engine/store/execution_service/notifier, same shape as K4's
    `_engine_and_notifier` helper -- fresh sqlite db per test, dry_run
    execution (no real subprocess), Telegram sends monkeypatched away by
    the caller wherever needed."""
    store = SQLiteStore(f"sqlite:///{d}/db.sqlite")
    notifier = NotificationService(store)
    engine = TaskEngine(
        store,
        Conductor(AgentRegistry(ROOT / "agents"), ModelRouter()),
        on_transition=notifier.on_transition,
    )
    budget = BudgetService(store, daily_limit_usd=100.0)
    execution_service = ExecutionService(
        engine, mode="dry_run", budget=budget, artifacts_root=Path(d) / "artifacts",
    )
    return engine, store, execution_service, notifier, budget


class VerifySignatureTests(unittest.TestCase):
    def test_valid_signature_accepted(self):
        body = b'{"event":"claimed"}'
        self.assertTrue(inbound.verify_signature(SECRET, body, _sign(body)))

    def test_wrong_signature_rejected(self):
        body = b'{"event":"claimed"}'
        self.assertFalse(inbound.verify_signature(SECRET, body, "0" * 64))

    def test_signature_for_different_body_rejected(self):
        signed_for_other_body = _sign(b'{"event":"other"}')
        self.assertFalse(inbound.verify_signature(SECRET, b'{"event":"claimed"}', signed_for_other_body))

    def test_missing_signature_rejected(self):
        self.assertFalse(inbound.verify_signature(SECRET, b"{}", None))
        self.assertFalse(inbound.verify_signature(SECRET, b"{}", ""))

    def test_unset_secret_always_rejected_even_with_matching_signature(self):
        body = b"{}"
        signature = _sign(body, secret="")
        self.assertFalse(inbound.verify_signature("", body, signature))


class TaskEventHandlingTests(unittest.TestCase):
    """(b): a bridge_links row pointing directly at a TaskRecord (forward
    compat -- not exercised by any current K6 caller, which only ever links
    orders, but the branch exists in inbound.py and must work)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.engine, self.store, self.execution_service, self.notifier, self.budget = _rig(self.tmp.name)

    async def _handle(self, payload):
        return await inbound.handle_kanban_event(
            engine=self.engine, store=self.store, execution_service=self.execution_service,
            notifier=self.notifier, budget=self.budget, artifacts_root=Path(self.tmp.name) / "artifacts",
            payload=payload,
        )

    def _run(self, coro):
        import asyncio
        return asyncio.run(coro)

    def test_claimed_transitions_task_to_running(self):
        task = self.engine.create(TaskCreate(title="task title", objective="do it fully", risk=RiskLevel.LOW))
        self.store.save_bridge_link(task.id, "kt-1", "starhome")

        result = self._run(self._handle({"event": "claimed", "task_id": "kt-1", "assignee": "worker"}))

        self.assertEqual(result["status"], "handled")
        self.assertEqual(result["resolved"], "task")
        self.assertEqual(self.engine.require(task.id).status, TaskStatus.RUNNING)

    def test_completed_low_risk_transitions_to_done(self):
        task = self.engine.create(TaskCreate(title="task title", objective="do it fully", risk=RiskLevel.LOW))
        self.store.save_bridge_link(task.id, "kt-2", "starhome")
        self.engine.transition(task.id, TaskStatus.RUNNING, "test-setup")

        with patch("cano_hermes.notifications.service.send_telegram_message"):
            result = self._run(self._handle({"event": "completed", "task_id": "kt-2", "summary": "all good"}))

        self.assertEqual(result["task_status"], "done")
        self.assertEqual(self.engine.require(task.id).status, TaskStatus.DONE)

    def test_completed_medium_risk_transitions_to_review_not_done(self):
        task = self.engine.create(TaskCreate(title="task title", objective="do it fully", risk=RiskLevel.MEDIUM))
        self.store.save_bridge_link(task.id, "kt-3", "starhome")
        self.engine.transition(task.id, TaskStatus.RUNNING, "test-setup")

        result = self._run(self._handle({"event": "completed", "task_id": "kt-3", "summary": "needs eyes"}))

        self.assertEqual(result["task_status"], "review")
        self.assertEqual(self.engine.require(task.id).status, TaskStatus.REVIEW)

    def test_blocked_transitions_task_to_blocked_with_reason(self):
        task = self.engine.create(TaskCreate(title="task title", objective="do it fully", risk=RiskLevel.LOW))
        self.store.save_bridge_link(task.id, "kt-4", "starhome")

        result = self._run(self._handle({"event": "blocked", "task_id": "kt-4", "reason": "esperando input"}))

        self.assertEqual(result["task_status"], "blocked")
        events = self.store.list_events(task.id)
        blocked_events = [e for e in events if e.kind == "task.blocked"]
        self.assertEqual(blocked_events[-1].payload.get("reason"), "esperando input")

    def test_redelivered_completed_event_is_idempotent(self):
        task = self.engine.create(TaskCreate(title="task title", objective="do it fully", risk=RiskLevel.LOW))
        self.store.save_bridge_link(task.id, "kt-5", "starhome")
        self.engine.transition(task.id, TaskStatus.RUNNING, "test-setup")

        with patch("cano_hermes.notifications.service.send_telegram_message"):
            first = self._run(self._handle({"event": "completed", "task_id": "kt-5", "summary": "ok"}))
            second = self._run(self._handle({"event": "completed", "task_id": "kt-5", "summary": "ok again"}))

        self.assertEqual(first["status"], "handled")
        self.assertEqual(second["status"], "ignored")
        self.assertEqual(self.engine.require(task.id).status, TaskStatus.DONE)

    def test_unknown_kanban_task_id_is_ignored(self):
        result = self._run(self._handle({"event": "claimed", "task_id": "kt-does-not-exist"}))
        self.assertEqual(result["status"], "ignored")

    def test_malformed_payload_is_ignored(self):
        result = self._run(self._handle({"event": "not-a-real-event", "task_id": "kt-1"}))
        self.assertEqual(result["status"], "ignored")
        result2 = self._run(self._handle({"event": "claimed"}))
        self.assertEqual(result2["status"], "ignored")

    def test_writes_event_artifact_to_disk(self):
        task = self.engine.create(TaskCreate(title="task title", objective="do it fully", risk=RiskLevel.LOW))
        self.store.save_bridge_link(task.id, "kt-6", "starhome")

        result = self._run(self._handle({"event": "claimed", "task_id": "kt-6", "assignee": "worker"}))

        artifact_path = Path(result["artifact"])
        self.assertTrue(artifact_path.exists())
        payload = json.loads(artifact_path.read_text())
        self.assertEqual(payload["event"], "claimed")


class OrderEventHandlingTests(unittest.TestCase):
    """(c): the order path -- claimed is audit-only, blocked flips the
    order, completed (with no tracked children, today's actual K6 shape)
    triggers full synthesis via `aggregator.close_order_with_synthesis`."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.engine, self.store, self.execution_service, self.notifier, self.budget = _rig(self.tmp.name)

    async def _handle(self, payload):
        return await inbound.handle_kanban_event(
            engine=self.engine, store=self.store, execution_service=self.execution_service,
            notifier=self.notifier, budget=self.budget, artifacts_root=Path(self.tmp.name) / "artifacts",
            payload=payload,
        )

    def _run(self, coro):
        import asyncio
        return asyncio.run(coro)

    def _dispatched_order(self, objective="investiga X y resume") -> OrderRecord:
        order = OrderRecord(objective=objective, source="telegram")
        order.status = OrderStatus.DISPATCHED
        self.store.save_order(order)
        self.store.save_bridge_link(order.id, f"kt-root-{order.id}", "starhome")
        return order

    def test_claimed_is_audit_only_no_status_change(self):
        order = self._dispatched_order()
        result = self._run(self._handle({
            "event": "claimed", "task_id": f"kt-root-{order.id}", "assignee": "orchestrator",
        }))
        self.assertEqual(result["order_status"], "dispatched")
        self.assertEqual(self.store.get_order(order.id).status, OrderStatus.DISPATCHED)
        events = [e.kind for e in self.store.list_events(order.id)]
        self.assertIn("order.kanban_claimed", events)

    def test_blocked_transitions_order_to_blocked(self):
        order = self._dispatched_order()
        result = self._run(self._handle({
            "event": "blocked", "task_id": f"kt-root-{order.id}", "reason": "esperando aprobación",
        }))
        self.assertEqual(result["order_status"], "blocked")
        self.assertEqual(self.store.get_order(order.id).status, OrderStatus.BLOCKED)

    def test_completed_with_no_tracked_children_triggers_full_synthesis(self):
        order = self._dispatched_order()

        with patch("cano_hermes.notifications.service.send_telegram_message") as fake_send:
            result = self._run(self._handle({
                "event": "completed", "task_id": f"kt-root-{order.id}",
                "summary": "hermes terminó la investigación: hallazgo clave X",
            }))

        self.assertTrue(result["aggregated"])
        self.assertEqual(result["order_status"], "done")
        refreshed = self.store.get_order(order.id)
        self.assertEqual(refreshed.status, OrderStatus.DONE)
        self.assertIsNotNone(refreshed.aggregate_artifact)
        self.assertTrue(Path(refreshed.aggregate_artifact).exists())
        summary_file = Path(refreshed.aggregate_artifact) / "synthesis-summary.txt"
        self.assertTrue(summary_file.exists())

        # Exactly one synthesis TaskRecord was created under the order.
        children = self.store.list_children(order.id)
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].domain, "synthesis")
        self.assertEqual(children[0].status, TaskStatus.DONE)

        # Two Telegram messages: the synthesis TaskRecord's own DONE
        # transition (via TaskEngine.on_transition, K4's existing wiring)
        # and the order-level one aggregator fires explicitly, since
        # OrderRecord transitions don't flow through TaskEngine.transition
        # (see aggregator.close_order_with_synthesis's docstring).
        self.assertEqual(fake_send.call_count, 2)
        texts = [call.args[0] for call in fake_send.call_args_list]
        self.assertTrue(any("DONE" in t for t in texts))
        self.assertTrue(any("ORDEN DONE" in t for t in texts))

    def test_completed_is_idempotent_against_redelivery(self):
        order = self._dispatched_order()
        with patch("cano_hermes.notifications.service.send_telegram_message") as fake_send:
            first = self._run(self._handle({
                "event": "completed", "task_id": f"kt-root-{order.id}", "summary": "listo",
            }))
            second = self._run(self._handle({
                "event": "completed", "task_id": f"kt-root-{order.id}", "summary": "listo (redelivered)",
            }))

        self.assertTrue(first["aggregated"])
        self.assertFalse(second.get("aggregated", False))
        # Only one synthesis task -- the redelivery (order already DONE)
        # must not re-run synthesis. Both Telegram messages (synthesis task
        # DONE + order DONE) come from the first call only.
        self.assertEqual(len(self.store.list_children(order.id)), 1)
        self.assertEqual(fake_send.call_count, 2)

    def test_completed_with_partial_children_does_not_aggregate(self):
        order = self._dispatched_order()
        child_a = self.store.save_task(TaskRecord(title="Subtask A", objective="objective a", parent_task_id=order.id))
        self.store.save_task(TaskRecord(title="Subtask B", objective="objective b", parent_task_id=order.id))
        self.engine.transition(child_a.id, TaskStatus.DONE, "test-setup")
        # child_b left in INBOX -- not terminal.

        result = self._run(self._handle({
            "event": "completed", "task_id": f"kt-root-{order.id}", "summary": "child A done",
        }))

        self.assertFalse(result.get("aggregated", False))
        self.assertEqual(self.store.get_order(order.id).status, OrderStatus.DISPATCHED)

    def test_completed_with_all_children_terminal_aggregates(self):
        order = self._dispatched_order()
        child_a = self.store.save_task(TaskRecord(title="Subtask A", objective="objective a", parent_task_id=order.id))
        child_b = self.store.save_task(TaskRecord(title="Subtask B", objective="objective b", parent_task_id=order.id))
        self.engine.transition(child_a.id, TaskStatus.DONE, "test-setup")
        self.engine.transition(child_b.id, TaskStatus.FAILED, "test-setup")

        with patch("cano_hermes.notifications.service.send_telegram_message"):
            result = self._run(self._handle({
                "event": "completed", "task_id": f"kt-root-{order.id}", "summary": "both children finished",
            }))

        self.assertTrue(result["aggregated"])
        self.assertEqual(self.store.get_order(order.id).status, OrderStatus.DONE)

    def test_unknown_kanban_task_id_ignored_no_order_touched(self):
        order = self._dispatched_order()
        result = self._run(self._handle({"event": "completed", "task_id": "kt-does-not-exist", "summary": "x"}))
        self.assertEqual(result["status"], "ignored")
        self.assertEqual(self.store.get_order(order.id).status, OrderStatus.DISPATCHED)


class AggregatorUnitTests(unittest.TestCase):
    def test_all_terminal_empty_list_is_false(self):
        self.assertFalse(aggregator.all_terminal([]))

    def test_all_terminal_false_when_one_pending(self):
        tasks = [
            TaskRecord(title="task a", objective="objective a", status=TaskStatus.DONE),
            TaskRecord(title="task b", objective="objective b", status=TaskStatus.RUNNING),
        ]
        self.assertFalse(aggregator.all_terminal(tasks))

    def test_all_terminal_true_for_done_and_failed_mix(self):
        tasks = [
            TaskRecord(title="task a", objective="objective a", status=TaskStatus.DONE),
            TaskRecord(title="task b", objective="objective b", status=TaskStatus.FAILED),
        ]
        self.assertTrue(aggregator.all_terminal(tasks))

    def test_close_order_with_synthesis_is_noop_unless_dispatched(self):
        with tempfile.TemporaryDirectory() as d:
            engine, store, execution_service, notifier, _budget = _rig(d)
            order = OrderRecord(objective="orden ya cerrada", source="api")
            order.status = OrderStatus.DONE
            store.save_order(order)

            import asyncio

            with patch("cano_hermes.notifications.service.send_telegram_message") as fake_send:
                result = asyncio.run(aggregator.close_order_with_synthesis(
                    engine=engine, store=store, execution_service=execution_service,
                    notifier=notifier, artifacts_root=Path(d) / "artifacts",
                    order=order, trigger_summary="no debería correr",
                ))

            self.assertEqual(result.status, OrderStatus.DONE)
            self.assertEqual(store.list_children(order.id), [])
            fake_send.assert_not_called()


class KanbanEventsApiTests(unittest.TestCase):
    """(f): the real HTTP route, signature verification included.

    This process's real `.env` sets `HERMES_EXECUTION_MODE=supervised` (the
    production default), under which `PermissionEngine` always routes a
    non-dry-run action to approval_required (see `governance/policy.py`) --
    same fact `test_k3_queue_service.py` and `test_execution_wiring.py`
    already document and work around. Only the one test that needs the
    synthesis task to actually reach DONE (`test_completed_event_drives_
    order_to_done_end_to_end`) forces dry_run on the shared
    `execution_service()` singleton, the same way those two files do --
    every dependency cache is cleared in `tearDown` so the override never
    leaks into another test file's run.
    """

    def setUp(self):
        from cano_hermes.api import dependencies

        self._dependencies = dependencies
        self._dep_fns = (
            dependencies.store,
            dependencies.registry,
            dependencies.engine,
            dependencies.approvals,
            dependencies.budget,
            dependencies.execution_service,
            dependencies.queue_service,
            dependencies.notification_service,
        )
        for dep in self._dep_fns:
            dep.cache_clear()

    def tearDown(self):
        for dep in self._dep_fns:
            dep.cache_clear()

    def _client(self):
        from cano_hermes.api.app import app

        return TestClient(app)

    def _force_dry_run(self):
        es = self._dependencies.execution_service()
        es.mode = "dry_run"
        es.policy.execution_mode = "dry_run"
        es.executors["hermes-agent"].mode = "dry_run"

    def _post_signed(self, client, payload: dict, secret: str = SECRET):
        body = json.dumps(payload).encode("utf-8")
        headers = {"X-StarHome-Signature": _sign(body, secret), "Content-Type": "application/json"}
        return client.post("/api/bridge/kanban-events", content=body, headers=headers)

    def test_valid_signature_claimed_event_returns_200(self):
        with patch("cano_hermes.api.app.settings.starhome_bridge_hmac_secret", SECRET):
            with self._client() as client:
                created = client.post("/api/orders", json={"objective": "orden api test", "source": "api"})
                order_id = created.json()["id"]
                # Derived from `order_id` (uuid-based, unique per test run) --
                # a fixed literal kanban_task_id would collide with
                # `bridge_links` rows left behind by earlier runs of this
                # same test against this process's real, persistent
                # `storage/hermes.db` (every other test in this suite that
                # hits the API shares that same file -- see `test_api.py`/
                # `test_k5_orders_domain.py`, none of which needed a
                # kanban_task_id -> starhome_id reverse lookup, so this
                # collision never surfaced before K7).
                kanban_task_id = f"kt-api-1-{order_id}"
                with patch("cano_hermes.api.app.kanban_bridge.submit_order_to_kanban") as fake_submit:
                    from cano_hermes.bridge.kanban_bridge import BridgeSubmission
                    fake_submit.return_value = BridgeSubmission(
                        kanban_task_id=kanban_task_id, board="starhome", command=["hermes"]
                    )
                    client.post(f"/api/orders/{order_id}/dispatch")

                response = self._post_signed(client, {
                    "event": "claimed", "task_id": kanban_task_id, "assignee": "worker",
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], "handled")

    def test_completed_event_drives_order_to_done_end_to_end(self):
        with patch("cano_hermes.api.app.settings.starhome_bridge_hmac_secret", SECRET), \
             patch("cano_hermes.notifications.service.send_telegram_message"):
            with self._client() as client:
                created = client.post("/api/orders", json={"objective": "orden e2e", "source": "api"})
                order_id = created.json()["id"]
                kanban_task_id = f"kt-api-2-{order_id}"
                with patch("cano_hermes.api.app.kanban_bridge.submit_order_to_kanban") as fake_submit:
                    from cano_hermes.bridge.kanban_bridge import BridgeSubmission
                    fake_submit.return_value = BridgeSubmission(
                        kanban_task_id=kanban_task_id, board="starhome", command=["hermes"]
                    )
                    client.post(f"/api/orders/{order_id}/dispatch")

                self._force_dry_run()
                response = self._post_signed(client, {
                    "event": "completed", "task_id": kanban_task_id, "summary": "orden e2e completada",
                })
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["aggregated"])

                fetched = client.get(f"/api/orders/{order_id}")
                self.assertEqual(fetched.json()["status"], "done")
                self.assertIsNotNone(fetched.json()["aggregate_artifact"])

    def test_invalid_signature_returns_401_and_touches_nothing(self):
        with patch("cano_hermes.api.app.settings.starhome_bridge_hmac_secret", SECRET):
            with self._client() as client:
                created = client.post("/api/orders", json={"objective": "orden protegida", "source": "api"})
                order_id = created.json()["id"]
                with patch("cano_hermes.api.app.kanban_bridge.submit_order_to_kanban") as fake_submit:
                    from cano_hermes.bridge.kanban_bridge import BridgeSubmission
                    fake_submit.return_value = BridgeSubmission(
                        kanban_task_id="kt-api-3", board="starhome", command=["hermes"]
                    )
                    client.post(f"/api/orders/{order_id}/dispatch")

                body = json.dumps({"event": "completed", "task_id": "kt-api-3", "summary": "no debería aplicar"}).encode()
                response = client.post(
                    "/api/bridge/kanban-events", content=body,
                    headers={"X-StarHome-Signature": "0" * 64, "Content-Type": "application/json"},
                )
                self.assertEqual(response.status_code, 401)

                fetched = client.get(f"/api/orders/{order_id}")
                self.assertEqual(fetched.json()["status"], "dispatched")

    def test_missing_signature_header_returns_401(self):
        with patch("cano_hermes.api.app.settings.starhome_bridge_hmac_secret", SECRET):
            with self._client() as client:
                response = client.post(
                    "/api/bridge/kanban-events",
                    content=json.dumps({"event": "claimed", "task_id": "kt-x"}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(response.status_code, 401)

    def test_unset_secret_rejects_even_a_correctly_signed_request(self):
        with patch("cano_hermes.api.app.settings.starhome_bridge_hmac_secret", ""):
            with self._client() as client:
                response = self._post_signed(client, {"event": "claimed", "task_id": "kt-x"}, secret="")
                self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
