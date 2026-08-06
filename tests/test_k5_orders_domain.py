"""K5 (plan HERMES-KICKOFF, gap 1) -- order/task hierarchy domain model.

Covers: (a) `OrderRecord`/`OrderStatus` validate correctly, including
rejecting an unknown `source`; (b) `TaskRecord.parent_task_id` is written
and read back through `SQLiteStore` with no schema migration (payload is a
full JSON blob); (c) `SQLiteStore.list_children` returns exactly the tasks
whose `parent_task_id` matches, Python-filtered over `list_tasks()`;
(d) `Conductor.assign(...).kanban_profile` is populated for several teams,
including the two offices mapped for real (research/operations) and one
provisional placeholder; (e) `POST /api/orders` -> `GET /api/orders/{id}`
end-to-end via `TestClient`, including that a decomposed child task shows
up under `tasks`.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError

from cano_hermes.domain.enums import OrderStatus
from cano_hermes.domain.models import OrderRecord, TaskCreate, TaskRecord
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]


class OrderRecordModelTests(unittest.TestCase):
    def test_defaults(self):
        order = OrderRecord(objective="investiga X y resume", source="telegram")
        self.assertTrue(order.id.startswith("order-"))
        self.assertEqual(order.status, OrderStatus.RECEIVED)
        self.assertEqual(order.subtask_ids, [])
        self.assertIsNone(order.aggregate_artifact)
        self.assertEqual(order.budget.max_cost_usd, 0.0)

    def test_rejects_unknown_source(self):
        with self.assertRaises(ValidationError):
            OrderRecord(objective="algo", source="whatsapp")

    def test_all_order_statuses_constructible(self):
        for status in OrderStatus:
            order = OrderRecord(objective="algo valido", source="cli", status=status)
            self.assertEqual(order.status, status)


class ParentTaskIdPersistenceTests(unittest.TestCase):
    def test_parent_task_id_round_trips_without_migration(self):
        with tempfile.TemporaryDirectory() as d:
            store = SQLiteStore(f"sqlite:///{d}/db.sqlite")
            parent = store.save_task(TaskRecord(title="Parent task", objective="Parent objective"))
            child = store.save_task(
                TaskRecord(title="Child task", objective="Child objective", parent_task_id=parent.id)
            )
            reloaded = store.get_task(child.id)
            self.assertEqual(reloaded.parent_task_id, parent.id)

            # A task created before this field existed still reads back fine
            # (default None) -- simulated by a TaskCreate with no parent_task_id.
            orphan = store.save_task(TaskRecord(**TaskCreate(title="Orphan", objective="No parent").model_dump()))
            self.assertIsNone(store.get_task(orphan.id).parent_task_id)


class ListChildrenTests(unittest.TestCase):
    def test_returns_only_matching_children(self):
        with tempfile.TemporaryDirectory() as d:
            store = SQLiteStore(f"sqlite:///{d}/db.sqlite")
            parent = store.save_task(TaskRecord(title="Parent", objective="Parent objective"))
            other_parent = store.save_task(TaskRecord(title="Other parent", objective="Other objective"))
            child_a = store.save_task(TaskRecord(title="Child A", objective="obj A", parent_task_id=parent.id))
            child_b = store.save_task(TaskRecord(title="Child B", objective="obj B", parent_task_id=parent.id))
            store.save_task(TaskRecord(title="Unrelated", objective="obj C", parent_task_id=other_parent.id))
            store.save_task(TaskRecord(title="No parent", objective="obj D"))

            children = store.list_children(parent.id)
            self.assertEqual({t.id for t in children}, {child_a.id, child_b.id})

    def test_empty_when_no_children(self):
        with tempfile.TemporaryDirectory() as d:
            store = SQLiteStore(f"sqlite:///{d}/db.sqlite")
            self.assertEqual(store.list_children("order-nonexistent"), [])

    def test_order_as_parent(self):
        """K6 will stamp TaskRecord.parent_task_id with an order id -- confirm
        list_children works the same way regardless of whether the parent is
        another task or an order (no "parent kind" field exists)."""
        with tempfile.TemporaryDirectory() as d:
            store = SQLiteStore(f"sqlite:///{d}/db.sqlite")
            order = store.save_order(OrderRecord(objective="orden compuesta", source="api"))
            child = store.save_task(TaskRecord(title="Subtask", objective="Sub", parent_task_id=order.id))
            self.assertEqual([t.id for t in store.list_children(order.id)], [child.id])


class OrderStorePersistenceTests(unittest.TestCase):
    def test_save_get_list_orders(self):
        with tempfile.TemporaryDirectory() as d:
            store = SQLiteStore(f"sqlite:///{d}/db.sqlite")
            order = store.save_order(OrderRecord(objective="algo", source="telegram"))
            self.assertEqual(store.get_order(order.id).id, order.id)
            self.assertEqual(store.get_order("order-missing"), None)
            self.assertIn(order.id, {o.id for o in store.list_orders()})


class KanbanProfileMappingTests(unittest.TestCase):
    def setUp(self):
        self.conductor = Conductor(AgentRegistry(ROOT / "agents"), ModelRouter())

    def _assign(self, domain: str):
        task = TaskRecord(title="Probe task", objective="Probe objective", domain=domain)
        return self.conductor.assign(task)

    def test_kanban_profile_populated_for_known_teams(self):
        cases = {
            "research": "hermes-research",
            "operations": "hermes-monitor",
            "engineering": "team-engineering",
        }
        for domain, expected_profile in cases.items():
            with self.subTest(domain=domain):
                assignment = self._assign(domain)
                self.assertEqual(assignment.kanban_profile, expected_profile)

    def test_kanban_profile_falls_back_to_governance_for_unknown_domain(self):
        assignment = self._assign("some-unmapped-domain")
        self.assertEqual(assignment.kanban_profile, "team-governance")


class OrdersApiTests(unittest.TestCase):
    def test_create_and_get_order_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HERMES_DATABASE_URL"] = f"sqlite:///{d}/api.db"
            from cano_hermes.api.app import app
            from cano_hermes.api.dependencies import store

            store.cache_clear()
            with TestClient(app) as client:
                response = client.post(
                    "/api/orders",
                    json={"objective": "investiga X, resume, genera informe", "source": "telegram"},
                )
                self.assertEqual(response.status_code, 201)
                body = response.json()
                self.assertTrue(body["id"].startswith("order-"))
                self.assertEqual(body["status"], "received")
                order_id = body["id"]

                # Simulate a K6 decomposition dropping a child task under this order.
                store().save_task(
                    TaskRecord(title="Subtask", objective="Subtask objective", parent_task_id=order_id)
                )

                fetched = client.get(f"/api/orders/{order_id}")
                self.assertEqual(fetched.status_code, 200)
                fetched_body = fetched.json()
                self.assertEqual(fetched_body["id"], order_id)
                self.assertEqual(len(fetched_body["tasks"]), 1)
                self.assertEqual(fetched_body["tasks"][0]["parent_task_id"], order_id)

                missing = client.get("/api/orders/order-does-not-exist")
                self.assertEqual(missing.status_code, 404)
            store.cache_clear()


if __name__ == "__main__":
    unittest.main()
