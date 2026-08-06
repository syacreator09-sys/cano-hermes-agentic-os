"""K8 (plan HERMES-KICKOFF) -- unified intake: CLI `order submit/status/list`
and the new `GET /api/orders` list endpoint they rely on.

The Telegram half of K8 (`~/.hermes/skills/starhome-orders/`) is a markdown
skill for the gateway agent, not Python in this repo -- nothing to unit
test here for it (see the K8 demo report for how it was verified
manually). What *is* Python in this repo, and covered below:

(a) `GET /api/orders` -- newest-first list of every order, added alongside
    the CLI so `order list` has an endpoint to call at all.
(b) `cano_hermes.cli.order_submit/order_status/order_list` -- thin `httpx`
    wrappers around the running StarHome API. Tests mock `httpx.post`/
    `httpx.get` (never touch the network or a real server), and check both
    the request shape sent out and the response handed back.
(c) `build_parser()` parses the three `order` subcommands into the
    `args.order_command`/`args.objective`/`args.budget`/etc. shape
    `_run_order` expects.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from cano_hermes import cli as cli_module

ROOT = Path(__file__).resolve().parents[1]


class ListOrdersEndpointTests(unittest.TestCase):
    """Same reset pattern as `test_k7_kanban_events.py`'s
    `KanbanEventsApiTests`: every `lru_cache`d dependency is cleared before
    *and* after each test so a database_url override never leaks into
    another test file's run."""

    def setUp(self):
        from cano_hermes.api import dependencies

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

    def _client(self, tmp_dir: str) -> TestClient:
        from cano_hermes.config import settings

        settings.database_url = f"sqlite:///{tmp_dir}/db.sqlite"
        settings.vault_path = Path(tmp_dir) / "vault"
        settings.agent_path = ROOT / "agents"
        settings.skill_path = ROOT / "skills"
        settings.artifact_path = Path(tmp_dir) / "artifacts"
        settings.worktree_path = Path(tmp_dir) / "worktrees"
        settings.forge_candidates_path = Path(tmp_dir) / "forge" / "candidates"
        settings.forge_sandbox_path = Path(tmp_dir) / "forge" / "sandbox"

        from cano_hermes.api.app import app

        return TestClient(app)

    def test_empty_list_is_empty_array(self):
        with tempfile.TemporaryDirectory() as d:
            client = self._client(d)
            response = client.get("/api/orders")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), [])

    def test_created_orders_appear_newest_first(self):
        with tempfile.TemporaryDirectory() as d:
            client = self._client(d)
            first = client.post("/api/orders", json={"objective": "primera orden real", "source": "cli"})
            second = client.post("/api/orders", json={"objective": "segunda orden real", "source": "telegram"})
            self.assertEqual(first.status_code, 201)
            self.assertEqual(second.status_code, 201)

            listed = client.get("/api/orders").json()
            ids = [o["id"] for o in listed]
            self.assertEqual(ids[0], second.json()["id"])
            self.assertIn(first.json()["id"], ids)


class CliOrderHttpWrapperTests(unittest.TestCase):
    """Mocks `httpx.post`/`httpx.get` -- confirms the CLI functions build
    the right request and unwrap the right response, without a live
    server."""

    def _fake_response(self, payload):
        response = MagicMock()
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        return response

    def test_order_submit_without_budget_omits_budget_key(self):
        with patch.object(cli_module.httpx, "post") as mock_post:
            mock_post.return_value = self._fake_response({"id": "order-abc", "status": "received"})
            result = cli_module.order_submit("dime la hora", source="cli")

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "http://127.0.0.1:8787/api/orders")
        self.assertEqual(kwargs["json"], {"objective": "dime la hora", "source": "cli"})
        self.assertEqual(result, {"id": "order-abc", "status": "received"})

    def test_order_submit_with_budget_sends_max_cost_usd(self):
        with patch.object(cli_module.httpx, "post") as mock_post:
            mock_post.return_value = self._fake_response({"id": "order-xyz"})
            cli_module.order_submit("investiga algo", source="telegram", budget_usd=2.5)

        _, kwargs = mock_post.call_args
        self.assertEqual(
            kwargs["json"],
            {"objective": "investiga algo", "source": "telegram", "budget": {"max_cost_usd": 2.5}},
        )

    def test_order_status_hits_the_right_url(self):
        with patch.object(cli_module.httpx, "get") as mock_get:
            mock_get.return_value = self._fake_response({"id": "order-abc", "status": "dispatched"})
            result = cli_module.order_status("order-abc")

        mock_get.assert_called_once_with("http://127.0.0.1:8787/api/orders/order-abc", timeout=30.0)
        self.assertEqual(result["status"], "dispatched")

    def test_order_list_hits_the_collection_url(self):
        with patch.object(cli_module.httpx, "get") as mock_get:
            mock_get.return_value = self._fake_response([{"id": "order-1"}, {"id": "order-2"}])
            result = cli_module.order_list()

        mock_get.assert_called_once_with("http://127.0.0.1:8787/api/orders", timeout=30.0)
        self.assertEqual(len(result), 2)

    def test_base_url_respects_env_override(self):
        with patch.dict("os.environ", {"STARHOME_API_BASE": "http://example.internal:9000"}):
            with patch.object(cli_module.httpx, "get") as mock_get:
                mock_get.return_value = self._fake_response({"id": "order-1"})
                cli_module.order_status("order-1")
        mock_get.assert_called_once_with("http://example.internal:9000/api/orders/order-1", timeout=30.0)

    def test_http_error_propagates(self):
        import httpx as real_httpx

        with patch.object(cli_module.httpx, "get") as mock_get:
            response = MagicMock()
            response.raise_for_status.side_effect = real_httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock(status_code=404)
            )
            mock_get.return_value = response
            with self.assertRaises(real_httpx.HTTPStatusError):
                cli_module.order_status("order-missing")


class CliOrderArgparseTests(unittest.TestCase):
    def test_submit_parses_objective_source_and_budget(self):
        args = cli_module.build_parser().parse_args(
            ["order", "submit", "dime la hora", "--source", "telegram", "--budget", "3.5"]
        )
        self.assertEqual(args.command, "order")
        self.assertEqual(args.order_command, "submit")
        self.assertEqual(args.objective, "dime la hora")
        self.assertEqual(args.source, "telegram")
        self.assertEqual(args.budget, 3.5)

    def test_submit_defaults_source_cli_and_budget_none(self):
        args = cli_module.build_parser().parse_args(["order", "submit", "algo"])
        self.assertEqual(args.source, "cli")
        self.assertIsNone(args.budget)

    def test_status_parses_order_id(self):
        args = cli_module.build_parser().parse_args(["order", "status", "order-abc"])
        self.assertEqual(args.order_command, "status")
        self.assertEqual(args.order_id, "order-abc")

    def test_list_has_no_extra_args(self):
        args = cli_module.build_parser().parse_args(["order", "list"])
        self.assertEqual(args.order_command, "list")

    def test_missing_order_subcommand_errors(self):
        with self.assertRaises(SystemExit):
            cli_module.build_parser().parse_args(["order"])

    def test_run_order_dispatches_submit_and_prints_json(self):
        args = cli_module.build_parser().parse_args(["order", "submit", "algo barato"])
        with patch.object(cli_module, "order_submit", return_value={"id": "order-1"}) as mock_submit:
            with patch("builtins.print") as mock_print:
                cli_module._run_order(args)
        mock_submit.assert_called_once_with("algo barato", source="cli", budget_usd=None)
        mock_print.assert_called_once()
        self.assertIn("order-1", mock_print.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
