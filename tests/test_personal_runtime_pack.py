from pathlib import Path

import yaml

from cano_hermes.domain.enums import AgentStatus
from cano_hermes.domain.models import AgentManifest
from cano_hermes.registry.skills import SkillRegistry

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_AGENTS = {
    "chief-of-staff": "agents/personal-operations/chief-of-staff.yaml",
    "finance-controller": "agents/finance/finance-controller.yaml",
    "revenue-operator": "agents/revenue/revenue-operator.yaml",
    "project-operator": "agents/projects/project-operator.yaml",
    "content-intelligence-director": "agents/content/content-intelligence-director.yaml",
    "investment-intelligence": "agents/investments/investment-intelligence.yaml",
    "document-auditor": "agents/documents/document-auditor.yaml",
    "learning-coach": "agents/learning/learning-coach.yaml",
}

EXPECTED_SKILLS = {
    "daily-brief",
    "capture-anything",
    "weekly-review",
    "expense-capture",
    "cash-position",
    "finance-close",
    "lead-next-action",
    "pipeline-review",
    "project-status",
    "blocker-review",
    "content-opportunity-brief",
    "investment-thesis-review",
    "document-consistency-audit",
    "learning-session",
}


def test_personal_runtime_agents_are_safe_candidates() -> None:
    for expected_id, relative_path in EXPECTED_AGENTS.items():
        path = ROOT / relative_path
        assert path.exists(), f"missing agent manifest: {relative_path}"

        manifest = AgentManifest.model_validate(
            yaml.safe_load(path.read_text(encoding="utf-8"))
        )

        assert manifest.id == expected_id
        assert manifest.description.strip()
        assert manifest.status is AgentStatus.CANDIDATE
        assert manifest.runtime == "hermes"
        assert manifest.actions.allowed
        assert manifest.actions.approval_required
        assert manifest.actions.prohibited
        assert manifest.permissions["filesystem"] == "workspace-only"
        assert manifest.permissions["network"] == "allowlist"
        assert manifest.permissions["production"] == "approval-required"
        assert manifest.budget.max_cost_usd <= 0.5
        assert manifest.budget.max_turns <= 20
        assert manifest.budget.timeout_seconds <= 1800
        assert manifest.max_concurrency == 1


def test_personal_runtime_skills_are_registered_candidates() -> None:
    registry = SkillRegistry(ROOT / "skills").load()

    assert EXPECTED_SKILLS <= registry.keys()
    for skill_id in EXPECTED_SKILLS:
        manifest = registry[skill_id]
        assert manifest["status"] == "candidate"
        assert manifest["version"] == "0.3.0"
        assert manifest["progressive_disclosure"] is True


def test_personal_runtime_skills_have_procedure_and_verification() -> None:
    for skill_id in EXPECTED_SKILLS:
        path = ROOT / "skills" / skill_id / "SKILL.md"
        assert path.exists(), f"missing skill: {skill_id}"

        content = path.read_text(encoding="utf-8")
        assert content.startswith(f"# {skill_id}\n")
        assert "## Procedure" in content
        assert "## Verification" in content
        assert "approval" in content.lower() or "aprobación" in content.lower()
