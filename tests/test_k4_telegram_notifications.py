"""K4 (plan HERMES-KICKOFF, gap 6) -- Telegram notifications.

Covers: (a) DONE fires a message with the execution's summary + artifacts,
(b) FAILED fires a message with the failure reason, (c) a pending APPROVAL
fires a message with the full `ApprovalRequest` schema, (d) missing
credentials is best-effort (no crash, no message attempted), plus a
skip-cleanly-without-real-credentials live-send smoke test.

None of (a)-(d) ever touch the network: `httpx.post` is monkeypatched at
`cano_hermes.notifications.telegram.httpx.post` for every one of them.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cano_hermes.domain.enums import RiskLevel, TaskStatus
from cano_hermes.domain.models import ApprovalRequest, ExecutionResult, TaskCreate
from cano_hermes.governance.approvals import ApprovalService
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.notifications.service import NotificationService
from cano_hermes.notifications.telegram import send_telegram_message
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]


class _FakeResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError("boom", request=None, response=self)


def _engine_and_notifier(d: str) -> tuple[TaskEngine, NotificationService, ApprovalService]:
    store = SQLiteStore(f"sqlite:///{d}/db.sqlite")
    notifier = NotificationService(store)
    engine = TaskEngine(
        store,
        Conductor(AgentRegistry(ROOT / "agents"), ModelRouter()),
        on_transition=notifier.on_transition,
    )
    approvals = ApprovalService(store, on_request=notifier.on_approval_requested)
    return engine, notifier, approvals


class TelegramClientTests(unittest.TestCase):
    """telegram.py in isolation, credentials always mocked via settings."""

    def test_missing_credentials_is_best_effort_no_crash_no_send(self):
        with patch("cano_hermes.notifications.telegram.settings") as fake_settings, \
             patch("cano_hermes.notifications.telegram.httpx.post") as fake_post:
            fake_settings.telegram_bot_token = ""
            fake_settings.telegram_chat_id = ""
            ok = send_telegram_message("should never be sent")
            self.assertFalse(ok)
            fake_post.assert_not_called()

    def test_http_failure_is_best_effort_no_crash(self):
        with patch("cano_hermes.notifications.telegram.settings") as fake_settings, \
             patch("cano_hermes.notifications.telegram.httpx.post") as fake_post:
            fake_settings.telegram_bot_token = "fake-token"
            fake_settings.telegram_chat_id = "12345"
            fake_post.return_value = _FakeResponse(status_code=500)
            ok = send_telegram_message("hello")
            self.assertFalse(ok)

    def test_success_posts_chat_id_and_text(self):
        with patch("cano_hermes.notifications.telegram.settings") as fake_settings, \
             patch("cano_hermes.notifications.telegram.httpx.post") as fake_post:
            fake_settings.telegram_bot_token = "fake-token"
            fake_settings.telegram_chat_id = "12345"
            fake_post.return_value = _FakeResponse(status_code=200)
            ok = send_telegram_message("hello world")
            self.assertTrue(ok)
            fake_post.assert_called_once()
            _, kwargs = fake_post.call_args
            self.assertEqual(kwargs["json"]["chat_id"], "12345")
            self.assertEqual(kwargs["json"]["text"], "hello world")
            self.assertIn("fake-token", fake_post.call_args[0][0])


class TransitionTriggerTests(unittest.TestCase):
    """(a)/(b)/(d): DONE and FAILED transitions fire (or don't) a message."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _patched_send(self):
        return patch("cano_hermes.notifications.service.send_telegram_message")

    def test_done_transition_sends_message_with_summary_and_artifacts(self):
        engine, _, _ = _engine_and_notifier(self.tmp.name)
        task = engine.create(
            TaskCreate(title="Ship the report", objective="write it", domain="engineering", risk=RiskLevel.LOW)
        )
        engine.store.save_execution(
            ExecutionResult(
                task_id=task.id,
                executor="claude-code",
                status="completed",
                summary="Wrote the quarterly report",
                artifacts=["storage/artifacts/task-x/claude-code/report.md"],
            )
        )
        with self._patched_send() as fake_send:
            fake_send.return_value = True
            engine.transition(task.id, TaskStatus.DONE, "completion", {"reason": "low-risk-auto-complete"})

        fake_send.assert_called_once()
        text = fake_send.call_args[0][0]
        self.assertIn("DONE", text)
        self.assertIn(task.id, text)
        self.assertIn("Wrote the quarterly report", text)
        self.assertIn("report.md", text)

    def test_done_transition_without_execution_row_still_sends(self):
        """The manual /complete endpoint's payload carries no `artifacts` --
        a DONE with no execution row at all must still notify, just without
        an artifacts section, not silently skip the message."""
        engine, _, _ = _engine_and_notifier(self.tmp.name)
        task = engine.create(
            TaskCreate(title="Manual close", objective="close it", domain="engineering", risk=RiskLevel.MEDIUM)
        )
        with self._patched_send() as fake_send:
            fake_send.return_value = True
            engine.transition(task.id, TaskStatus.DONE, "cano", {"reason": "manual-completion"})

        fake_send.assert_called_once()
        text = fake_send.call_args[0][0]
        self.assertIn("DONE", text)
        self.assertIn("sin resumen", text)

    def test_failed_transition_sends_message_with_reason(self):
        engine, _, _ = _engine_and_notifier(self.tmp.name)
        task = engine.create(
            TaskCreate(title="Broken run", objective="try to run", domain="engineering")
        )
        with self._patched_send() as fake_send:
            fake_send.return_value = True
            engine.transition(task.id, TaskStatus.FAILED, "execution-service", {"summary": "executor crashed"})

        fake_send.assert_called_once()
        text = fake_send.call_args[0][0]
        self.assertIn("FAILED", text)
        self.assertIn(task.id, text)
        self.assertIn("executor crashed", text)

    def test_other_transitions_do_not_notify(self):
        engine, _, _ = _engine_and_notifier(self.tmp.name)
        task = engine.create(
            TaskCreate(title="Just planned", objective="plan it", domain="engineering")
        )
        with self._patched_send() as fake_send:
            engine.transition(task.id, TaskStatus.RUNNING, "worker", {})
        fake_send.assert_not_called()

    def test_notification_failure_never_breaks_the_transition(self):
        """Even if the notifier callback blows up, the task transition
        itself must still land -- best-effort means best-effort."""
        engine, _, _ = _engine_and_notifier(self.tmp.name)
        task = engine.create(
            TaskCreate(title="Must still complete", objective="finish", domain="engineering")
        )
        with patch(
            "cano_hermes.notifications.service.send_telegram_message",
            side_effect=RuntimeError("network exploded"),
        ):
            result = engine.transition(task.id, TaskStatus.DONE, "completion", {"reason": "auto"})
        self.assertEqual(result.status, TaskStatus.DONE)
        self.assertEqual(engine.require(task.id).status, TaskStatus.DONE)


class ApprovalTriggerTests(unittest.TestCase):
    """(c): a pending APPROVAL fires a message with the full schema."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_approval_request_sends_message_with_full_schema(self):
        _, _, approvals = _engine_and_notifier(self.tmp.name)
        with patch("cano_hermes.notifications.service.send_telegram_message") as fake_send:
            fake_send.return_value = True
            approvals.request(
                ApprovalRequest(
                    task_id="task-abc123",
                    action="claude-code",
                    motivo="excede presupuesto diario",
                    risk=RiskLevel.HIGH,
                    requested_by="system",
                    costo_estimado_usd=12.5,
                    presupuesto_restante=2.0,
                    canal="engineering",
                    evidencia="storage/workspaces/task-abc123/approval-evidence-task-abc123.json",
                )
            )

        fake_send.assert_called_once()
        text = fake_send.call_args[0][0]
        self.assertIn("APPROVAL", text)
        self.assertIn("task-abc123", text)
        self.assertIn("excede presupuesto diario", text)
        self.assertIn("engineering", text)
        self.assertIn("12.5", text)
        self.assertIn("approval-evidence-task-abc123.json", text)

    def test_approval_resolve_does_not_notify_again(self):
        """Only the initial request notifies -- resolve() isn't wired to
        the notifier at all in K4 (out of scope: resolution is Cano acting
        on the approval he was already notified about, not a new event he
        needs pushed to him)."""
        _, _, approvals = _engine_and_notifier(self.tmp.name)
        with patch("cano_hermes.notifications.service.send_telegram_message") as fake_send:
            fake_send.return_value = True
            approval = approvals.request(
                ApprovalRequest(
                    task_id="task-xyz",
                    action="claude-code",
                    motivo="riesgo alto",
                    risk=RiskLevel.HIGH,
                    requested_by="system",
                    costo_estimado_usd=1.0,
                    presupuesto_restante=4.0,
                    canal="engineering",
                    evidencia="evidence.json",
                )
            )
            fake_send.reset_mock()
            approvals.resolve(approval.id, approved=True, actor="cano")
            fake_send.assert_not_called()


class LiveTelegramSmokeTest(unittest.TestCase):
    """Optional, real end-to-end send -- gated behind an explicit opt-in
    (`RUN_LIVE_TELEGRAM_TEST=1`), not just "credentials happen to be
    present". This machine's own `cano_hermes` `.env` (loaded by
    `Settings`, see config.py) already carries real
    `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` for the `starhome-os` systemd
    unit -- without the opt-in gate, every plain `pytest`/`unittest
    discover` run in *this* environment would silently ping Cano's real
    Telegram chat, which is not what "the suite stays green" should mean.
    Skips cleanly (never fails) whenever the opt-in isn't set or
    credentials are actually missing."""

    def test_send_real_message_if_explicitly_requested(self):
        if os.environ.get("RUN_LIVE_TELEGRAM_TEST") != "1":
            self.skipTest("set RUN_LIVE_TELEGRAM_TEST=1 to actually send a live Telegram message")
        from cano_hermes.config import settings as live_settings

        if not live_settings.telegram_bot_token or not live_settings.telegram_chat_id:
            self.skipTest("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not configured in this environment")
        ok = send_telegram_message("[test suite] K4 live smoke test -- ignore")
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
