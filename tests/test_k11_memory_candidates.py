"""K11 (plan HERMES-KICKOFF) -- memory_candidates reader + human-gated
resolver.

Covers: (a) store-level add -> list -> get -> resolve round trip (both
decisions), (b) status filtering, (c) `MemoryCandidateService`'s
anti-self-approval rule and its `decision="approved"`-only scope, (d) the
vault-promotion side effect on approval (and its absence on rejection),
(e) HTTP list/get/resolve endpoints end-to-end.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from cano_hermes.governance.memory_candidates import MemoryCandidateService
from cano_hermes.storage.sqlite import SQLiteStore


class MemoryCandidateStoreTests(unittest.TestCase):
    def _store(self, d: str) -> SQLiteStore:
        return SQLiteStore(f"sqlite:///{d}/db.sqlite")

    def test_add_list_get_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.add_memory_candidate("cand-1", "engineering", {"lesson": "always run tests"})
            listed = store.list_memory_candidates()
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["id"], "cand-1")
            self.assertEqual(listed[0]["status"], "candidate")
            self.assertEqual(listed[0]["namespace"], "engineering")
            self.assertEqual(store.get_memory_candidate("cand-1")["payload"]["lesson"], "always run tests")
            self.assertIsNone(store.get_memory_candidate("does-not-exist"))

    def test_list_filters_by_status(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.add_memory_candidate("cand-1", "ns", {"a": 1})
            store.add_memory_candidate("cand-2", "ns", {"a": 2})
            store.resolve_memory_candidate("cand-1", "approved", "cano")
            self.assertEqual([c["id"] for c in store.list_memory_candidates("candidate")], ["cand-2"])
            self.assertEqual([c["id"] for c in store.list_memory_candidates("approved")], ["cand-1"])
            self.assertEqual(len(store.list_memory_candidates()), 2)

    def test_resolve_folds_resolver_into_payload(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.add_memory_candidate("cand-1", "ns", {"lesson": "x"})
            updated = store.resolve_memory_candidate("cand-1", "rejected", "cano")
            self.assertEqual(updated["status"], "rejected")
            self.assertEqual(updated["payload"]["resolved_by"], "cano")
            self.assertIn("resolved_at", updated["payload"])
            self.assertEqual(updated["payload"]["lesson"], "x")

    def test_resolve_unknown_candidate_raises_keyerror(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            with self.assertRaises(KeyError):
                store.resolve_memory_candidate("nope", "approved", "cano")


class MemoryCandidateServiceTests(unittest.TestCase):
    def _service(self, d: str) -> tuple[MemoryCandidateService, SQLiteStore, Path]:
        store = SQLiteStore(f"sqlite:///{d}/db.sqlite")
        vault_root = Path(d) / "vault"
        return MemoryCandidateService(store, vault_root), store, vault_root

    def test_resolve_approved_promotes_to_vault(self):
        with tempfile.TemporaryDirectory() as d:
            service, store, vault_root = self._service(d)
            store.add_memory_candidate("cand-1", "engineering", {"lesson": "durable insight"})
            result = service.resolve("cand-1", "approved", "cano")
            self.assertEqual(result["status"], "approved")
            self.assertIsNotNone(result["promoted_path"])
            promoted = Path(result["promoted_path"])
            self.assertTrue(promoted.exists())
            self.assertTrue(promoted.is_relative_to(vault_root / "00-Candidatos-Aprobados"))
            text = promoted.read_text(encoding="utf-8")
            self.assertIn("durable insight", text)
            self.assertIn("approved_pending_index", text)

    def test_resolve_rejected_does_not_touch_vault(self):
        with tempfile.TemporaryDirectory() as d:
            service, store, vault_root = self._service(d)
            store.add_memory_candidate("cand-1", "engineering", {"lesson": "x"})
            result = service.resolve("cand-1", "rejected", "cano")
            self.assertEqual(result["status"], "rejected")
            self.assertIsNone(result["promoted_path"])
            self.assertFalse((vault_root / "00-Candidatos-Aprobados").exists())

    def test_self_approval_blocked_when_proposed_by_present(self):
        with tempfile.TemporaryDirectory() as d:
            service, store, _ = self._service(d)
            store.add_memory_candidate("cand-1", "ns", {"lesson": "x", "proposed_by": "conductor"})
            with self.assertRaises(PermissionError):
                service.resolve("cand-1", "approved", "conductor")
            # still pending -- the blocked attempt did not mutate status
            self.assertEqual(store.get_memory_candidate("cand-1")["status"], "candidate")

    def test_self_rejection_is_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            service, store, _ = self._service(d)
            store.add_memory_candidate("cand-1", "ns", {"lesson": "x", "proposed_by": "conductor"})
            result = service.resolve("cand-1", "rejected", "conductor")
            self.assertEqual(result["status"], "rejected")

    def test_approval_by_different_actor_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            service, store, _ = self._service(d)
            store.add_memory_candidate("cand-1", "ns", {"lesson": "x", "proposed_by": "conductor"})
            result = service.resolve("cand-1", "approved", "cano")
            self.assertEqual(result["status"], "approved")

    def test_self_approval_allowed_when_no_proposed_by_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            service, store, _ = self._service(d)
            store.add_memory_candidate("cand-1", "ns", {"lesson": "x"})  # no proposed_by
            result = service.resolve("cand-1", "approved", "cano")
            self.assertEqual(result["status"], "approved")

    def test_resolve_already_resolved_candidate_raises_valueerror(self):
        with tempfile.TemporaryDirectory() as d:
            service, store, _ = self._service(d)
            store.add_memory_candidate("cand-1", "ns", {"lesson": "x"})
            service.resolve("cand-1", "approved", "cano")
            with self.assertRaises(ValueError):
                service.resolve("cand-1", "approved", "cano")

    def test_resolve_invalid_decision_raises_valueerror(self):
        with tempfile.TemporaryDirectory() as d:
            service, store, _ = self._service(d)
            store.add_memory_candidate("cand-1", "ns", {"lesson": "x"})
            with self.assertRaises(ValueError):
                service.resolve("cand-1", "maybe", "cano")

    def test_get_unknown_candidate_raises_keyerror(self):
        with tempfile.TemporaryDirectory() as d:
            service, _, _ = self._service(d)
            with self.assertRaises(KeyError):
                service.get("nope")


class MemoryCandidateApiTests(unittest.TestCase):
    def test_list_get_resolve_over_http(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["HERMES_DATABASE_URL"] = f"sqlite:///{d}/api.db"
            os.environ["HERMES_VAULT_PATH"] = f"{d}/vault"

            from cano_hermes.api import dependencies
            from cano_hermes.api.app import app
            from cano_hermes.config import settings

            settings.database_url = os.environ["HERMES_DATABASE_URL"]
            settings.vault_path = Path(os.environ["HERMES_VAULT_PATH"])
            dependencies.store.cache_clear()
            dependencies.memory_candidates.cache_clear()

            dependencies.store().add_memory_candidate("cand-http-1", "engineering", {"lesson": "y", "proposed_by": "agent-x"})

            with TestClient(app) as client:
                listed = client.get("/api/memory/candidates")
                self.assertEqual(listed.status_code, 200)
                self.assertEqual(len(listed.json()), 1)

                pending = client.get("/api/memory/candidates", params={"status": "candidate"})
                self.assertEqual(len(pending.json()), 1)

                got = client.get("/api/memory/candidates/cand-http-1")
                self.assertEqual(got.status_code, 200)
                self.assertEqual(got.json()["id"], "cand-http-1")

                missing = client.get("/api/memory/candidates/does-not-exist")
                self.assertEqual(missing.status_code, 404)

                # same actor as proposed_by -> blocked
                blocked = client.post(
                    "/api/memory/candidates/cand-http-1/resolve",
                    json={"decision": "approved", "actor": "agent-x"},
                )
                self.assertEqual(blocked.status_code, 403)

                resolved = client.post(
                    "/api/memory/candidates/cand-http-1/resolve",
                    json={"decision": "approved", "actor": "cano"},
                )
                self.assertEqual(resolved.status_code, 200)
                body = resolved.json()
                self.assertEqual(body["status"], "approved")
                self.assertIsNotNone(body["promoted_path"])
                self.assertTrue(Path(body["promoted_path"]).exists())

                bad_decision = client.post(
                    "/api/memory/candidates/cand-http-1/resolve",
                    json={"decision": "approved", "actor": "cano"},
                )
                self.assertEqual(bad_decision.status_code, 400)

            dependencies.store.cache_clear()
            dependencies.memory_candidates.cache_clear()
            del os.environ["HERMES_DATABASE_URL"]
            del os.environ["HERMES_VAULT_PATH"]


if __name__ == "__main__":
    unittest.main()
