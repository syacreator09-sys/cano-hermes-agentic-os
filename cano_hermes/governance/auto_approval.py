"""K12 (plan HERMES-KICKOFF) -- "autonomia gobernada": lets a genuinely
safe `ApprovalRequest` resolve itself instead of sitting in Cano's queue,
without touching `ApprovalService.resolve()`'s own anti-self-approval
guard at all.

Why this exists now, not earlier: K12 also flips `Settings.execution_mode`'s
default from `dry_run` to `supervised` (the value this machine's real
`.env` already forces -- see `config.py`). Under `supervised`,
`PermissionEngine.evaluate_action` is called with the coarse action label
`"production_write"` (`ExecutionService.run`), which is itself a member of
`SENSITIVE_ACTIONS` -- so *every* task execution, regardless of its own
risk, now routes through `TaskStatus.APPROVAL` before it can run (this is
the exact regression `tests/test_k7_kanban_events.py::
test_synthesis_needing_approval_blocks_order_not_fails_it` already
documents from a live 2026-08-06 demo run). Without this module, that
would mean Cano has to manually approve every single LOW-risk, zero-cost
task the whole system ever runs -- not "governed autonomy", just
autonomy removed. This module is the narrow, auditable escape hatch: it
only ever fires for requests that are safe by construction on every one
of the axes below, all at once.

Contract (plan HERMES-KICKOFF K12, ALL of the following must hold or the
request is left untouched, exactly as it is today):

1. `approval.risk == RiskLevel.LOW`.
2. `approval.costo_estimado_usd == 0` -- not "small", zero. Not one cent.
3. `approval.action` is not in `policy.SENSITIVE_ACTIONS`, checked here
   independently of whatever validation the request's creator already
   did (K1-K7's two call sites -- `ExecutionService.run`,
   `ForgePipeline.request_approval` -- already only reach the approval
   path when their own `PermissionEngine`/default risk said so; this is
   a second, standalone check, not a delegation to the first one).
4. If the task belongs to a K9 office (`kanban_profile` resolves to a
   real `offices/<profile>/office.yaml`), `approval.action` is not in
   that office's `never:` list -- a hard allowlist-negative, not a
   suggestion. Profiles with no matching manifest (since P0, plan
   POTENCIA, every `conductor.TEAM_TO_KANBAN_PROFILE` value is a real
   office, but an unknown/legacy profile string can still arrive) are
   treated as "no office to check against", not as a failure -- there is
   nothing to violate.
5. If a concrete write target is known for this request, it must resolve
   inside the packet's own `allowed_write_paths` (K1/K2) -- reusing
   `PermissionEngine.validate_path`, the same containment check
   `ExecutionPacket`-scoped writes are already held to. A write target
   given with no `allowed_write_paths` to check it against fails closed
   (cannot prove containment -> not safe to auto-approve), matching the
   "cuando dudes, requiere aprobacion humana" rule the whole phase runs
   under. Callers that genuinely have no write-path concept for this
   action (most read/plan/simulate-shaped work) simply omit both and
   this condition is vacuously satisfied.

One deliberate addition beyond the letter of the K12 task spec, in the
same conservative spirit: `approval.presupuesto_restante >= 0`. A request
can legitimately cost exactly $0 while the *ledger* is already over budget
from unrelated prior spend today (`BudgetLedger.can_spend` -- see
`ExecutionService.run`'s `budget_allows` check, which is a second,
independent reason a request can land here besides `PermissionEngine`
denying it). Auto-approving anything, even a free action, while the
day's budget is already blown is exactly the kind of gray-zone call this
phase's golden rule ("cuando dudes, requiere aprobacion humana") is
about -- so it stays pending for Cano rather than silently proceeding.

The one thing this module will NEVER do is duplicate
`ApprovalService.resolve`'s self-approval check. It calls `resolve()`
with `actor=AUTO_APPROVAL_ACTOR` ("policy-engine") exactly like any other
actor would, and if that ever collides with `approval.requested_by`
(never observed in practice -- every real caller today defaults
`requested_by` to `"system"` or a human/agent id, never the literal
string `"policy-engine"`), `resolve()` raises `PermissionError` exactly
as it would for a human trying to approve their own request, and this
module treats that exactly like "conditions not met": the request stays
pending, nothing crashes.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from cano_hermes.config import settings
from cano_hermes.domain.enums import RiskLevel
from cano_hermes.domain.models import ApprovalRequest
from cano_hermes.governance.approvals import ApprovalService
from cano_hermes.governance.policy import SENSITIVE_ACTIONS, PermissionEngine

logger = logging.getLogger(__name__)

# Never confusable with a human Telegram approval (K4) or an agent id --
# `ApprovalRequest.resolved_by`/`requested_by` values elsewhere in this
# codebase are either "system", a human's own actor string, or an agent
# id from `agents/**/*.yaml`, none of which are "policy-engine".
AUTO_APPROVAL_ACTOR = "policy-engine"


@dataclass(frozen=True)
class AutoApprovalDecision:
    approved: bool
    reason: str


def _offices_root(offices_root: Path | None = None) -> Path:
    return offices_root if offices_root is not None else Path(settings.repository_root) / "offices"


def load_office_never(kanban_profile: str | None, offices_root: Path | None = None) -> frozenset[str]:
    """The `never:` allowlist-negative from a K9 `offices/<profile>/
    office.yaml`, or an empty set when `kanban_profile` is falsy or no
    manifest exists for it. A missing manifest is "nothing to check
    against" -- since P0 (plan POTENCIA) every
    `conductor.TEAM_TO_KANBAN_PROFILE` value is a real office, but an
    unknown or legacy profile string must not silently block every task
    from its domain."""
    if not kanban_profile:
        return frozenset()
    manifest_path = _offices_root(offices_root) / kanban_profile / "office.yaml"
    if not manifest_path.is_file():
        return frozenset()
    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        logger.warning("auto_approval: could not read/parse %s -- treating as no office", manifest_path, exc_info=True)
        return frozenset()
    never = data.get("never") or []
    return frozenset(str(item) for item in never)


def evaluate_auto_approval(
    approval: ApprovalRequest,
    *,
    kanban_profile: str | None = None,
    write_target: Path | None = None,
    allowed_write_paths: Sequence[Path] = (),
    offices_root: Path | None = None,
) -> AutoApprovalDecision:
    """Pure decision function -- no side effects, no call to
    `ApprovalService`. Kept separate from `try_auto_approve` so the
    matrix of conditions can be unit-tested without a store/DB at all."""
    if approval.risk != RiskLevel.LOW:
        return AutoApprovalDecision(False, f"risk={approval.risk.value!r} is not LOW")

    if approval.costo_estimado_usd != 0:
        return AutoApprovalDecision(False, f"costo_estimado_usd={approval.costo_estimado_usd} is not 0")

    if approval.presupuesto_restante < 0:
        return AutoApprovalDecision(False, "presupuesto_restante is already negative (budget over limit)")

    if approval.action in SENSITIVE_ACTIONS:
        return AutoApprovalDecision(False, f"action {approval.action!r} is in SENSITIVE_ACTIONS")

    never = load_office_never(kanban_profile, offices_root=offices_root)
    if approval.action in never:
        return AutoApprovalDecision(
            False, f"action {approval.action!r} is in office {kanban_profile!r}'s never: list"
        )

    if write_target is not None:
        if not allowed_write_paths:
            return AutoApprovalDecision(
                False, "write_target given with no allowed_write_paths to validate it against"
            )
        if not PermissionEngine.validate_path(Path(write_target), [Path(p) for p in allowed_write_paths]):
            return AutoApprovalDecision(
                False, f"write_target {write_target} is outside allowed_write_paths {tuple(allowed_write_paths)}"
            )

    return AutoApprovalDecision(True, "risk=LOW, cost=$0, not sensitive, not in office never:, writes contained")


def try_auto_approve(
    approvals: ApprovalService,
    approval: ApprovalRequest,
    *,
    kanban_profile: str | None = None,
    write_target: Path | None = None,
    allowed_write_paths: Sequence[Path] = (),
    offices_root: Path | None = None,
) -> ApprovalRequest | None:
    """If `approval` clears every `evaluate_auto_approval` condition,
    resolve it now (actor=`AUTO_APPROVAL_ACTOR`) via the real
    `ApprovalService.resolve` -- same code path, same anti-self-approval
    guard, same event trail a human approval would produce -- and return
    the resolved record. Otherwise: no-op, returns `None`, the request
    stays exactly as pending as it was before this call, for Cano."""
    decision = evaluate_auto_approval(
        approval,
        kanban_profile=kanban_profile,
        write_target=write_target,
        allowed_write_paths=allowed_write_paths,
        offices_root=offices_root,
    )
    if not decision.approved:
        logger.debug("auto_approval: leaving %s pending (%s)", approval.id, decision.reason)
        return None
    try:
        resolved = approvals.resolve(approval.id, True, AUTO_APPROVAL_ACTOR)
    except PermissionError:
        # requested_by == AUTO_APPROVAL_ACTOR -- never observed from a real
        # caller, but if it ever happens, fail exactly like any other
        # unmet condition: stay pending, do not crash the caller's
        # execution path over it.
        logger.warning(
            "auto_approval: %s was requested_by=%r, matching AUTO_APPROVAL_ACTOR -- leaving pending",
            approval.id, approval.requested_by,
        )
        return None
    logger.info("auto_approval: resolved %s automatically (%s)", approval.id, decision.reason)
    return resolved
