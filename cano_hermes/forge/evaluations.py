"""Cross-review checks for Plan Prometeo F4.

These give real teeth to the `evaluations: [schema, safety, task-contract]`
every `agents/forge/*.yaml` manifest already declares (forge-lead,
agent-designer, capability-auditor, ...) — up to now that list was metadata
nobody read. `ForgePipeline.cross_review` runs exactly these three checks
against the sandboxed candidate and treats a fail on any of them as a
rejection, standing in for the "another agent (or a rules function)
evaluates the sandbox result" step in the F4 brief. A dedicated function per
check (not a monolithic validator) so each can be unit-tested and reasoned
about on its own, matching how `capability-auditor` would explain a
rejection to Cano.
"""
from __future__ import annotations

from typing import Any

from .models import StageResult

MAX_CANDIDATE_COST_USD = 5.0
SAFE_PRODUCTION_VALUES = {"denied", "approval-required"}
SAFE_NETWORK_VALUES = {"denied", "none", "allowlist"}
UNSAFE_FILESYSTEM_VALUES = {"unrestricted", "all", "*", "/"}
DANGEROUS_TOOL_HINTS = ("credential", "secret", "docker_socket", "prod_write", "delete_all")


def evaluate_schema(kind: str, definition: dict[str, Any]) -> StageResult:
    notes: list[str] = []
    checks: dict[str, bool] = {}

    if kind == "agent":
        from cano_hermes.domain.models import AgentManifest

        try:
            AgentManifest.model_validate(definition)
            checks["agent_manifest_schema"] = True
        except Exception as exc:  # noqa: BLE001 — surfaced as a review note, not raised
            checks["agent_manifest_schema"] = False
            notes.append(f"AgentManifest schema invalid: {exc}")
    elif kind == "skill":
        required = {"id", "objective"}
        missing = required - definition.keys()
        checks["skill_manifest_required_fields"] = not missing
        if missing:
            notes.append(f"skill definition missing required fields: {sorted(missing)}")
    else:
        checks["known_kind"] = False
        notes.append(f"unknown candidate kind: {kind}")

    return StageResult(passed=all(checks.values()) if checks else False, checks=checks, notes=notes)


def evaluate_safety(kind: str, definition: dict[str, Any]) -> StageResult:
    notes: list[str] = []
    checks: dict[str, bool] = {}

    permissions = definition.get("permissions", {}) if isinstance(definition.get("permissions"), dict) else {}
    production = str(permissions.get("production", "denied")).lower()
    network = str(permissions.get("network", "denied")).lower()
    filesystem = str(permissions.get("filesystem", "workspace-only")).lower()

    checks["production_requires_approval_or_denied"] = kind != "agent" or production in SAFE_PRODUCTION_VALUES
    if not checks["production_requires_approval_or_denied"]:
        notes.append(f"permissions.production='{production}' is not allowed for a new candidate (must be denied/approval-required)")

    checks["network_not_open"] = kind != "agent" or network in SAFE_NETWORK_VALUES
    if not checks["network_not_open"]:
        notes.append(f"permissions.network='{network}' is too broad for a new candidate")

    checks["filesystem_scoped"] = kind != "agent" or filesystem not in UNSAFE_FILESYSTEM_VALUES
    if not checks["filesystem_scoped"]:
        notes.append(f"permissions.filesystem='{filesystem}' is not scoped to a workspace")

    tools = definition.get("tools") or []
    dangerous = [t for t in tools if any(hint in str(t).lower() for hint in DANGEROUS_TOOL_HINTS)]
    checks["no_dangerous_tools_outside_allowlist"] = not dangerous
    if dangerous:
        notes.append(f"tools request capabilities outside the candidate allowlist: {dangerous}")

    return StageResult(passed=all(checks.values()), checks=checks, notes=notes)


def evaluate_task_contract(kind: str, definition: dict[str, Any]) -> StageResult:
    notes: list[str] = []
    checks: dict[str, bool] = {}

    objective = str(definition.get("objective", "")).strip()
    checks["objective_is_descriptive"] = len(objective) >= 10
    if not checks["objective_is_descriptive"]:
        notes.append("objective is missing or too short to be a real contract")

    budget = definition.get("budget") or {}
    max_cost = budget.get("max_cost_usd", 0) if isinstance(budget, dict) else 0
    try:
        max_cost = float(max_cost)
    except (TypeError, ValueError):
        max_cost = float("inf")
    checks["budget_within_candidate_ceiling"] = max_cost <= MAX_CANDIDATE_COST_USD
    if not checks["budget_within_candidate_ceiling"]:
        notes.append(f"budget.max_cost_usd={max_cost} exceeds the {MAX_CANDIDATE_COST_USD} ceiling for an unproven candidate")

    if kind == "agent":
        evaluations = definition.get("evaluations") or []
        checks["declares_schema_and_safety_gates"] = {"schema", "safety"} <= set(evaluations)
        if not checks["declares_schema_and_safety_gates"]:
            notes.append("agent definition must declare at least 'schema' and 'safety' in its own evaluations list")

    return StageResult(passed=all(checks.values()), checks=checks, notes=notes)


def cross_review(kind: str, definition: dict[str, Any]) -> StageResult:
    """Combine schema + safety + task-contract into the single verdict
    `ForgePipeline.cross_review` records against the candidate."""
    results = {
        "schema": evaluate_schema(kind, definition),
        "safety": evaluate_safety(kind, definition),
        "task-contract": evaluate_task_contract(kind, definition),
    }
    checks = {name: result.passed for name, result in results.items()}
    notes = [note for result in results.values() for note in result.notes]
    raw = {name: result.model_dump(mode="json") for name, result in results.items()}
    return StageResult(passed=all(checks.values()), checks=checks, notes=notes, raw=raw)
