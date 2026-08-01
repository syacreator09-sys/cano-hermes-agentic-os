import pytest
from pydantic import ValidationError

from cano_hermes.domain.models import AgentActions, AgentManifest


def test_legacy_manifest_remains_valid_without_action_metadata() -> None:
    manifest = AgentManifest.model_validate(
        {
            "id": "legacy-agent",
            "name": "Legacy Agent",
            "team": "legacy",
            "objective": "Mantener compatibilidad con manifiestos existentes.",
        }
    )

    assert manifest.description == ""
    assert manifest.actions.allowed == []
    assert manifest.actions.approval_required == []
    assert manifest.actions.prohibited == []


def test_action_contract_rejects_overlapping_actions() -> None:
    with pytest.raises(ValidationError):
        AgentActions.model_validate(
            {
                "allowed": ["prepare_report"],
                "approval_required": ["prepare_report"],
                "prohibited": [],
            }
        )
