"""K6 (plan HERMES-KICKOFF, gap 2) -- StarHome -> Kanban bridge.

Covers: (a) `submit_order_to_kanban` builds the correct `hermes kanban
--board starhome create ...` command, including `--idempotency-key
<order.id>`; (b) `SQLiteStore.save_bridge_link`/`get_bridge_link_by_*`
round-trip in both directions; (c) a subprocess failure (non-zero exit,
timeout, missing binary, unparseable JSON) raises `KanbanBridgeError`, and
`POST /api/orders/{id}/dispatch` turns that into the order landing on
`FAILED` with the error message captured on an event -- never limbo; (d)
title/priority derivation from `OrderRecord`; (e) the dispatch endpoint's
happy path (DISPATCHED + bridge_links row) and its 404/409 guards.

Every unit test here mocks `cano_hermes.bridge.kanban_bridge.subprocess.run`
(or, at the API layer, `cano_hermes.api.app.kanban_bridge.submit_order_to_kanban`
directly) -- none of them shell out to a real `hermes` process. The one
test that does is `LiveKanbanIntegrationTest`, gated behind
`RUN_LIVE_KANBAN_TEST=1`, same pattern as K4's `LiveTelegramSmokeTest`.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cano_hermes.bridge import kanban_bridge
from cano_hermes.bridge.kanban_bridge import BridgeSubmission, KanbanBridgeError
from cano_hermes.domain.models import Budget, OrderRecord
from cano_hermes.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["hermes"], returncode=returncode, stdout=stdout, stderr=stderr)


class TitleAndPriorityTests(unittest.TestCase):
    def test_title_uses_first_line_verbatim_when_short(self):
        order = OrderRecord(objective="investiga X y resume", source="cli")
        self.assertEqual(kanban_bridge._order_title(order), "investiga X y resume")

    def test_title_truncates_long_objective_with_ellipsis(self):
        order = OrderRecord(objective="a" * 200, source="api")
        title = kanban_bridge._order_title(order)
        self.assertTrue(title.endswith("…"))
        self.assertLessEqual(len(title), kanban_bridge.TITLE_MAX_CHARS)

    def test_title_uses_only_first_line_of_multiline_objective(self):
        order = OrderRecord(objective="linea uno\nlinea dos con mas detalle", source="api")
        self.assertEqual(kanban_bridge._order_title(order), "linea uno")

    def test_priority_defaults_to_zero_with_default_budget(self):
        order = OrderRecord(objective="algo simple", source="api")
        self.assertEqual(kanban_bridge._order_priority(order), 0)

    def test_priority_rounds_budget_to_nearest_int(self):
        order = OrderRecord(objective="algo", source="api", budget=Budget(max_cost_usd=4.6))
        self.assertEqual(kanban_bridge._order_priority(order), 5)

    def test_priority_clamped_to_max(self):
        order = OrderRecord(objective="orden cara", source="api", budget=Budget(max_cost_usd=999))
        self.assertEqual(kanban_bridge._order_priority(order), kanban_bridge.PRIORITY_MAX)


class EnsureBoardTests(unittest.TestCase):
    def test_calls_boards_create_with_slug(self):
        with patch("cano_hermes.bridge.kanban_bridge.subprocess.run") as fake_run:
            fake_run.return_value = _completed(returncode=0, stdout="Board 'starhome' created.\n")
            kanban_bridge.ensure_board("starhome", command="hermes")
        args = fake_run.call_args[0][0]
        self.assertEqual(args[:5], ["hermes", "kanban", "boards", "create", "starhome"])

    def test_nonzero_exit_raises_kanban_bridge_error(self):
        with patch("cano_hermes.bridge.kanban_bridge.subprocess.run") as fake_run:
            fake_run.return_value = _completed(returncode=1, stderr="boom")
            with self.assertRaises(KanbanBridgeError):
                kanban_bridge.ensure_board("starhome", command="hermes")


class SubmitOrderToKanbanTests(unittest.TestCase):
    def setUp(self):
        self.order = OrderRecord(objective="investiga X, resume, genera informe", source="telegram")

    def _patched_run(self, *results):
        return patch("cano_hermes.bridge.kanban_bridge.subprocess.run", side_effect=list(results))

    def test_builds_correct_command_with_idempotency_key(self):
        board_ok = _completed(returncode=0, stdout="ok")
        create_ok = _completed(returncode=0, stdout=json.dumps({"id": "t_abc123"}))
        with self._patched_run(board_ok, create_ok) as fake_run:
            submission = kanban_bridge.submit_order_to_kanban(self.order, command="hermes")

        self.assertIsInstance(submission, BridgeSubmission)
        self.assertEqual(submission.kanban_task_id, "t_abc123")
        self.assertEqual(submission.board, "starhome")
        self.assertEqual(fake_run.call_count, 2)

        create_args = fake_run.call_args_list[1][0][0]
        self.assertEqual(create_args[:5], ["hermes", "kanban", "--board", "starhome", "create"])
        self.assertIn("--idempotency-key", create_args)
        self.assertEqual(
            create_args[create_args.index("--idempotency-key") + 1], self.order.id
        )
        self.assertIn("--triage", create_args)
        self.assertIn("--json", create_args)
        self.assertIn("--body", create_args)
        self.assertEqual(
            create_args[create_args.index("--body") + 1], self.order.objective
        )

    def test_nonzero_exit_raises_with_stderr_in_message(self):
        board_ok = _completed(returncode=0)
        create_fail = _completed(returncode=1, stderr="hermes: something broke")
        with self._patched_run(board_ok, create_fail):
            with self.assertRaises(KanbanBridgeError) as ctx:
                kanban_bridge.submit_order_to_kanban(self.order, command="hermes")
        self.assertIn("something broke", str(ctx.exception))

    def test_unparseable_json_raises(self):
        board_ok = _completed(returncode=0)
        create_bad_json = _completed(returncode=0, stdout="not json at all")
        with self._patched_run(board_ok, create_bad_json):
            with self.assertRaises(KanbanBridgeError):
                kanban_bridge.submit_order_to_kanban(self.order, command="hermes")

    def test_missing_id_field_raises(self):
        board_ok = _completed(returncode=0)
        create_no_id = _completed(returncode=0, stdout=json.dumps({"title": "no id here"}))
        with self._patched_run(board_ok, create_no_id):
            with self.assertRaises(KanbanBridgeError):
                kanban_bridge.submit_order_to_kanban(self.order, command="hermes")

    def test_command_not_found_raises(self):
        with patch(
            "cano_hermes.bridge.kanban_bridge.subprocess.run", side_effect=FileNotFoundError()
        ), self.assertRaises(KanbanBridgeError):
            kanban_bridge.submit_order_to_kanban(self.order, command="hermes-does-not-exist")

    def test_timeout_raises(self):
        with patch(
            "cano_hermes.bridge.kanban_bridge.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="hermes", timeout=30),
        ), self.assertRaises(KanbanBridgeError):
            kanban_bridge.submit_order_to_kanban(self.order, command="hermes")


class DomainToAssigneeTests(unittest.TestCase):
    """T10 (plan POTENCIA): OrderCreate.domain -> --assignee <profile>,
    resolved via the same conductor.kanban_profile_for_domain table P0
    fixed. Without a domain (or one with no office), behavior is
    byte-identical to before -- SubmitOrderToKanbanTests above."""

    def _patched_run(self, *results):
        return patch("cano_hermes.bridge.kanban_bridge.subprocess.run", side_effect=list(results))

    def test_known_office_domain_uses_assignee_not_triage(self):
        order = OrderRecord(objective="produce contenido para el canal", source="cli", domain="content")
        board_ok = _completed(returncode=0, stdout="ok")
        create_ok = _completed(returncode=0, stdout=json.dumps({"id": "t_x"}))
        with self._patched_run(board_ok, create_ok) as fake_run:
            kanban_bridge.submit_order_to_kanban(order, command="hermes")

        create_args = fake_run.call_args_list[1][0][0]
        self.assertIn("--assignee", create_args)
        self.assertEqual(create_args[create_args.index("--assignee") + 1], "hermes-produccion")
        self.assertNotIn("--triage", create_args)

    def test_domain_with_no_office_falls_back_to_triage(self):
        order = OrderRecord(objective="revisar codigo", source="cli", domain="engineering")
        board_ok = _completed(returncode=0, stdout="ok")
        create_ok = _completed(returncode=0, stdout=json.dumps({"id": "t_x"}))
        with self._patched_run(board_ok, create_ok) as fake_run:
            kanban_bridge.submit_order_to_kanban(order, command="hermes")

        create_args = fake_run.call_args_list[1][0][0]
        self.assertIn("--triage", create_args)
        self.assertNotIn("--assignee", create_args)

    def test_unknown_domain_falls_back_to_triage(self):
        order = OrderRecord(objective="algo raro", source="cli", domain="no-existe-este-dominio")
        board_ok = _completed(returncode=0, stdout="ok")
        create_ok = _completed(returncode=0, stdout=json.dumps({"id": "t_x"}))
        with self._patched_run(board_ok, create_ok) as fake_run:
            kanban_bridge.submit_order_to_kanban(order, command="hermes")

        create_args = fake_run.call_args_list[1][0][0]
        self.assertIn("--triage", create_args)

    def test_no_domain_is_unchanged_from_before(self):
        order = OrderRecord(objective="sin dominio explicito", source="cli")
        board_ok = _completed(returncode=0, stdout="ok")
        create_ok = _completed(returncode=0, stdout=json.dumps({"id": "t_x"}))
        with self._patched_run(board_ok, create_ok) as fake_run:
            kanban_bridge.submit_order_to_kanban(order, command="hermes")

        create_args = fake_run.call_args_list[1][0][0]
        self.assertIn("--triage", create_args)
        self.assertNotIn("--assignee", create_args)


class BridgeLinksStorageTests(unittest.TestCase):
    def test_save_and_resolve_both_directions(self):
        with tempfile.TemporaryDirectory() as d:
            store = SQLiteStore(f"sqlite:///{d}/db.sqlite")
            link = store.save_bridge_link("order-abc", "t_xyz789", "starhome")
            self.assertEqual(link["starhome_id"], "order-abc")
            self.assertEqual(link["kanban_task_id"], "t_xyz789")
            self.assertEqual(link["board"], "starhome")

            by_starhome = store.get_bridge_link_by_starhome_id("order-abc")
            self.assertEqual(by_starhome["kanban_task_id"], "t_xyz789")

            by_kanban = store.get_bridge_link_by_kanban_task_id("t_xyz789")
            self.assertEqual(by_kanban["starhome_id"], "order-abc")

            self.assertIsNone(store.get_bridge_link_by_starhome_id("order-missing"))
            self.assertIsNone(store.get_bridge_link_by_kanban_task_id("t-missing"))

    def test_upsert_overwrites_existing_link_for_same_starhome_id(self):
        with tempfile.TemporaryDirectory() as d:
            store = SQLiteStore(f"sqlite:///{d}/db.sqlite")
            store.save_bridge_link("order-abc", "t_first", "starhome")
            store.save_bridge_link("order-abc", "t_second", "starhome")
            link = store.get_bridge_link_by_starhome_id("order-abc")
            self.assertEqual(link["kanban_task_id"], "t_second")
            self.assertIsNone(store.get_bridge_link_by_kanban_task_id("t_first"))


class DispatchEndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["HERMES_DATABASE_URL"] = f"sqlite:///{self.tmp.name}/api.db"

    def _client(self):
        from fastapi.testclient import TestClient

        from cano_hermes.api.app import app
        from cano_hermes.api.dependencies import store

        store.cache_clear()
        return TestClient(app), store

    def test_dispatch_success_transitions_to_dispatched_and_saves_link(self):
        client, store = self._client()
        with client:
            created = client.post(
                "/api/orders", json={"objective": "investiga X", "source": "telegram"}
            )
            order_id = created.json()["id"]

            with patch("cano_hermes.api.app.kanban_bridge.submit_order_to_kanban") as fake_submit:
                fake_submit.return_value = BridgeSubmission(
                    kanban_task_id="t_dispatched1", board="starhome", command=["hermes"]
                )
                response = client.post(f"/api/orders/{order_id}/dispatch")

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["status"], "dispatched")
            self.assertEqual(body["bridge_link"]["kanban_task_id"], "t_dispatched1")
            self.assertEqual(body["bridge_link"]["board"], "starhome")

            link = store().get_bridge_link_by_starhome_id(order_id)
            self.assertEqual(link["kanban_task_id"], "t_dispatched1")

            fetched = client.get(f"/api/orders/{order_id}")
            self.assertEqual(fetched.json()["status"], "dispatched")
        store.cache_clear()

    def test_dispatch_failure_transitions_order_to_failed_not_limbo(self):
        client, store = self._client()
        with client:
            created = client.post(
                "/api/orders", json={"objective": "orden que va a fallar", "source": "api"}
            )
            order_id = created.json()["id"]

            with patch(
                "cano_hermes.api.app.kanban_bridge.submit_order_to_kanban",
                side_effect=KanbanBridgeError("hermes: board no existe"),
            ):
                response = client.post(f"/api/orders/{order_id}/dispatch")

            self.assertEqual(response.status_code, 502)
            self.assertIn("board no existe", response.json()["detail"])

            fetched = client.get(f"/api/orders/{order_id}")
            self.assertEqual(fetched.json()["status"], "failed")

            self.assertIsNone(store().get_bridge_link_by_starhome_id(order_id))

            events = store().list_events(order_id)
            failure_events = [e for e in events if e.kind == "order.dispatch_failed"]
            self.assertEqual(len(failure_events), 1)
            self.assertIn("board no existe", failure_events[0].payload["error"])
        store.cache_clear()

    def test_dispatch_missing_order_404(self):
        client, store = self._client()
        with client:
            response = client.post("/api/orders/order-does-not-exist/dispatch")
            self.assertEqual(response.status_code, 404)
        store.cache_clear()

    def test_dispatch_already_dispatched_is_refused_with_409(self):
        client, store = self._client()
        with client:
            created = client.post(
                "/api/orders", json={"objective": "doble dispatch", "source": "api"}
            )
            order_id = created.json()["id"]
            with patch("cano_hermes.api.app.kanban_bridge.submit_order_to_kanban") as fake_submit:
                fake_submit.return_value = BridgeSubmission(
                    kanban_task_id="t_once", board="starhome", command=["hermes"]
                )
                first = client.post(f"/api/orders/{order_id}/dispatch")
                self.assertEqual(first.status_code, 200)
                second = client.post(f"/api/orders/{order_id}/dispatch")
                self.assertEqual(second.status_code, 409)
                fake_submit.assert_called_once()
        store.cache_clear()


class LiveKanbanIntegrationTest(unittest.TestCase):
    """Optional, real end-to-end submission against this machine's actual
    hermes-agent install -- gated behind an explicit opt-in
    (`RUN_LIVE_KANBAN_TEST=1`), same pattern as K4's `LiveTelegramSmokeTest`
    in `tests/test_k4_telegram_notifications.py`. Without the opt-in this
    would otherwise create a real row on the real `starhome` kanban board on
    every plain `pytest`/`unittest discover` run in this environment, which
    is not what "the suite stays green" should mean. Archives the task it
    creates so repeated manual runs don't clutter the board. Skips cleanly
    (never fails) whenever the opt-in isn't set or the `hermes` CLI isn't on
    PATH."""

    def test_real_submit_and_list_round_trip(self):
        if os.environ.get("RUN_LIVE_KANBAN_TEST") != "1":
            self.skipTest(
                "set RUN_LIVE_KANBAN_TEST=1 to actually submit to the real hermes kanban board"
            )
        import shutil

        if shutil.which("hermes") is None:
            self.skipTest("hermes CLI not found on PATH")

        order = OrderRecord(
            objective="[K6 live test] verificacion end-to-end del bridge -- ignorar",
            source="api",
        )
        submission = kanban_bridge.submit_order_to_kanban(order)
        self.assertTrue(submission.kanban_task_id)
        self.assertEqual(submission.board, "starhome")

        try:
            listing = subprocess.run(
                ["hermes", "kanban", "--board", "starhome", "list", "--json"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(listing.returncode, 0)
            tasks = json.loads(listing.stdout)
            self.assertIn(submission.kanban_task_id, {t["id"] for t in tasks})
        finally:
            subprocess.run(
                ["hermes", "kanban", "--board", "starhome", "archive", submission.kanban_task_id],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )


if __name__ == "__main__":
    unittest.main()
