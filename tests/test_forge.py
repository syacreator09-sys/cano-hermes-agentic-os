"""Plan Prometeo F4 — the candidate -> sandbox -> cross-review -> approval ->
promotion pipeline (`cano_hermes/forge/pipeline.py`).

Every test builds its own isolated `agents/`, `skills/`, candidate-store and
sandbox-workspace directories under a `TemporaryDirectory` so nothing here
touches this repo's real `agents/`/`skills/` trees (those are exercised
separately, for real, by the three F4 seed candidates committed under
`agents/candidates/` and `skills/candidates/`).
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from cano_hermes.domain.enums import ApprovalStatus
from cano_hermes.forge.duplication import DuplicateCandidateError
from cano_hermes.forge.models import ForgeStage
from cano_hermes.forge.pipeline import ForgePipeline
from cano_hermes.forge.store import ForgeCandidateStore
from cano_hermes.governance.approvals import ApprovalService
from cano_hermes.storage.sqlite import SQLiteStore


def _agent_definition(**overrides) -> dict:
    definition = {
        "id": "test-forge-agent",
        "name": "Test Forge Agent",
        "team": "operations",
        "objective": "A well-formed candidate objective, long enough to pass the task-contract check.",
        "runtime": "hermes",
        "model_profiles": ["kimi-office"],
        "skills": [],
        "tools": ["task_events"],
        "permissions": {"filesystem": "workspace-only", "network": "allowlist", "production": "approval-required"},
        "budget": {"max_cost_usd": 0.2, "max_turns": 6, "timeout_seconds": 300},
        "evaluations": ["schema", "safety", "task-contract"],
    }
    definition.update(overrides)
    return definition


def _skill_definition(**overrides) -> dict:
    definition = {
        "id": "test-forge-skill",
        "objective": "A well-formed skill objective, long enough to pass the task-contract check.",
        "steps": ["Do the first thing.", "Do the second thing."],
    }
    definition.update(overrides)
    return definition


class ForgePipelineTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        (d / "agents").mkdir()
        (d / "skills").mkdir()
        self.store = SQLiteStore(f"sqlite:///{d}/db.sqlite")
        self.approvals = ApprovalService(self.store)
        self.pipeline = ForgePipeline(
            agents_root=d / "agents",
            skills_root=d / "skills",
            agent_candidates_root=d / "agents/candidates",
            skill_candidates_root=d / "skills/candidates",
            candidate_store=ForgeCandidateStore(d / "forge-candidates"),
            sandbox_workspace_root=d / "sandbox",
            approvals=self.approvals,
            command_center_matrix=None,
        )

    def tearDown(self):
        self.tmp.cleanup()


class HappyPathTests(ForgePipelineTestCase):
    def test_valid_candidate_reaches_pending_approval(self):
        candidate = self.pipeline.submit(
            "agent", _agent_definition(), requested_by="forge-lead", canal="operations", costo_estimado_usd=0.1
        )
        self.assertEqual(candidate.stage, ForgeStage.PENDING_APPROVAL)
        self.assertIsNotNone(candidate.approval_id)
        self.assertTrue(candidate.sandbox_result.passed)
        self.assertTrue(candidate.review_result.passed)

        approvals_list = self.approvals.store.list_approvals()
        self.assertEqual(len(approvals_list), 1)
        approval = approvals_list[0]
        self.assertEqual(approval.status, ApprovalStatus.PENDING)
        self.assertEqual(approval.canal, "operations")
        self.assertTrue(Path(approval.evidencia).exists())

    def test_valid_skill_candidate_reaches_pending_approval(self):
        candidate = self.pipeline.submit(
            "skill", _skill_definition(), requested_by="skill-engineer", canal="engineering", costo_estimado_usd=0.0
        )
        self.assertEqual(candidate.stage, ForgeStage.PENDING_APPROVAL)

    def test_promotion_requires_a_resolved_approval_and_then_writes_the_real_file(self):
        candidate = self.pipeline.submit(
            "agent", _agent_definition(), requested_by="forge-lead", canal="operations", costo_estimado_usd=0.1
        )

        with self.assertRaises(PermissionError):
            self.pipeline.promote(candidate.id)

        self.approvals.resolve(candidate.approval_id, True, "cano")
        promoted = self.pipeline.promote(candidate.id)

        self.assertEqual(promoted.stage, ForgeStage.PROMOTED)
        target = Path(promoted.promoted_path)
        self.assertTrue(target.exists())
        self.assertIn("status: active", target.read_text())

    def test_nobody_approves_their_own_forge_request(self):
        candidate = self.pipeline.submit(
            "agent", _agent_definition(), requested_by="office-content", canal="content", costo_estimado_usd=0.1
        )
        with self.assertRaises(PermissionError):
            self.approvals.resolve(candidate.approval_id, True, "office-content")


class DuplicateRejectionTests(ForgePipelineTestCase):
    def test_id_colliding_with_an_existing_production_agent_is_rejected(self):
        # Seed a "production" agent directly, as if it already shipped.
        agents_dir = self.pipeline.agents_root / "operations"
        agents_dir.mkdir(parents=True)
        (agents_dir / "already-live.yaml").write_text(
            "id: already-live\nname: Already Live\nteam: operations\nobjective: exists\nstatus: active\n"
        )

        with self.assertRaises(DuplicateCandidateError):
            self.pipeline.propose("agent", _agent_definition(id="already-live"), requested_by="tester")

    def test_id_colliding_with_an_existing_production_skill_is_rejected(self):
        skill_dir = self.pipeline.skills_root / "already-live-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "manifest.json").write_text(json.dumps({"id": "already-live-skill", "status": "active"}))

        with self.assertRaises(DuplicateCandidateError):
            self.pipeline.propose("skill", _skill_definition(id="already-live-skill"), requested_by="tester")

    def test_proposing_the_same_candidate_id_twice_is_rejected(self):
        self.pipeline.propose("agent", _agent_definition(), requested_by="tester")
        with self.assertRaises(DuplicateCandidateError):
            self.pipeline.propose("agent", _agent_definition(), requested_by="tester")


class MalformedCandidateTests(ForgePipelineTestCase):
    def test_malformed_agent_definition_passes_propose_but_fails_cross_review(self):
        malformed = {"id": "broken-agent", "objective": "x"}  # missing required name/team
        candidate = self.pipeline.propose("agent", malformed, requested_by="tester")
        self.assertEqual(candidate.stage, ForgeStage.PROPOSED)

        candidate = self.pipeline.run_sandbox(candidate.id)
        candidate = self.pipeline.cross_review(candidate.id)

        self.assertEqual(candidate.stage, ForgeStage.REVIEW_FAILED)
        self.assertFalse(candidate.review_result.passed)
        self.assertIsNotNone(candidate.rejection_reason)

    def test_unsafe_permissions_fail_the_safety_check(self):
        unsafe = _agent_definition(
            id="unsafe-agent",
            permissions={"filesystem": "workspace-only", "network": "open", "production": "granted"},
        )
        candidate = self.pipeline.propose("agent", unsafe, requested_by="tester")
        candidate = self.pipeline.run_sandbox(candidate.id)
        candidate = self.pipeline.cross_review(candidate.id)
        self.assertEqual(candidate.stage, ForgeStage.REVIEW_FAILED)
        self.assertFalse(candidate.review_result.checks["safety"])


class PromotionWithoutApprovalTests(ForgePipelineTestCase):
    def test_promoting_a_candidate_stuck_before_pending_approval_fails(self):
        candidate = self.pipeline.propose("agent", _agent_definition(), requested_by="tester")
        with self.assertRaises(ValueError):
            self.pipeline.promote(candidate.id)

    def test_promoting_an_unknown_candidate_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.pipeline.promote("does-not-exist")


class ForgeApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        os.environ["HERMES_DATABASE_URL"] = f"sqlite:///{d}/api.db"
        os.environ["HERMES_AGENT_PATH"] = str(d / "agents")
        os.environ["HERMES_SKILL_PATH"] = str(d / "skills")
        os.environ["HERMES_FORGE_CANDIDATES_PATH"] = str(d / "forge-candidates")
        os.environ["HERMES_FORGE_SANDBOX_PATH"] = str(d / "forge-sandbox")
        os.environ["HERMES_EXECUTION_MODE"] = "dry_run"
        (d / "agents").mkdir(parents=True, exist_ok=True)
        (d / "skills").mkdir(parents=True, exist_ok=True)

        # settings is a module-level singleton read at import time; rebuild it
        # against the env vars just set, mirroring how the other API tests
        # reset dependencies.* lru_caches per test.
        import cano_hermes.config as config_module
        from cano_hermes.api import dependencies

        config_module.settings = config_module.Settings()
        dependencies.settings = config_module.settings
        dependencies.store.cache_clear()
        dependencies.registry.cache_clear()
        dependencies.engine.cache_clear()
        dependencies.approvals.cache_clear()
        dependencies.budget.cache_clear()
        dependencies.execution_service.cache_clear()
        dependencies.forge_pipeline.cache_clear()

        import cano_hermes.api.app as app_module

        app_module.settings = config_module.settings
        self.client = TestClient(app_module.app)

    def tearDown(self):
        self.tmp.cleanup()
        for var in (
            "HERMES_DATABASE_URL",
            "HERMES_AGENT_PATH",
            "HERMES_SKILL_PATH",
            "HERMES_FORGE_CANDIDATES_PATH",
            "HERMES_FORGE_SANDBOX_PATH",
            "HERMES_EXECUTION_MODE",
        ):
            os.environ.pop(var, None)

    def test_propose_agent_endpoint_reaches_pending_approval(self):
        response = self.client.post(
            "/api/forge/agents",
            json={
                "definition": _agent_definition(id="api-forge-agent"),
                "requested_by": "forge-lead",
                "canal": "operations",
                "costo_estimado_usd": 0.1,
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["stage"], "pending_approval")

        status_response = self.client.get(f"/api/forge/candidates/{body['id']}")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["stage"], "pending_approval")

    def test_propose_skill_endpoint_reaches_pending_approval(self):
        response = self.client.post(
            "/api/forge/skills",
            json={
                "definition": _skill_definition(id="api-forge-skill"),
                "requested_by": "skill-engineer",
                "canal": "engineering",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stage"], "pending_approval")

    def test_duplicate_id_via_api_is_409(self):
        payload = {"definition": _agent_definition(id="api-dup-agent"), "requested_by": "x", "canal": "operations"}
        first = self.client.post("/api/forge/agents", json=payload)
        self.assertEqual(first.status_code, 200)
        second = self.client.post("/api/forge/agents", json=payload)
        self.assertEqual(second.status_code, 409)

    def test_unknown_candidate_status_is_404(self):
        response = self.client.get("/api/forge/candidates/does-not-exist")
        self.assertEqual(response.status_code, 404)

    def test_promote_without_resolved_approval_is_403(self):
        proposed = self.client.post(
            "/api/forge/agents",
            json={"definition": _agent_definition(id="api-unresolved-agent"), "requested_by": "x", "canal": "operations"},
        )
        candidate_id = proposed.json()["id"]
        promote_response = self.client.post(f"/api/forge/candidates/{candidate_id}/promote")
        self.assertEqual(promote_response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
