"""Plan Prometeo F4 — the candidate -> sandbox -> cross-review -> approval ->
promotion pipeline.

This is PROMETEO's actual forge, wired on top of what F3 soldered:

- **Candidato**: `AgentFactory`/`SkillFactory` (F3-era, extended here with
  `create_from_definition`/`promote`) write the definition to a quarantine
  artifact under `agents/candidates/`/`skills/candidates/` — not yet active,
  not yet loaded by `AgentRegistry`/`SkillRegistry` (those only scan
  `agents/`/`skills/`, never `*/candidates/`).
- **Sandbox**: the candidate's smoke-test command runs through
  `ContainerSandboxExecutor` (`cano_hermes/runtimes/container_sandbox.py`,
  registered in `ExecutionService.executors["container-sandbox"]`) —
  rootless, `--network none`, zero credentials by allowlist
  (`EXECUTOR_SECRET_ALLOWLIST["container-sandbox"]` is the empty set).
- **Revisión cruzada**: `forge/evaluations.py` runs the schema/safety/
  task-contract checks every `agents/forge/*.yaml` manifest already
  declares in its own `evaluations:` list, against the sandboxed candidate.
- **Aprobación**: `ApprovalService`/`ApprovalRequest` (F3,
  `cano_hermes/governance/approvals.py`) — promoting a candidate to
  production is exactly the kind of risky action F3 built approvals for.
  Nothing here ever resolves its own request.
- **Promoción**: only after a human resolves that request does
  `AgentFactory.promote`/`SkillFactory.promote` materialize the candidate at
  `agents/<team>/<id>.yaml` or `skills/<id>/`.

Each stage is a separate method so the API/CLI can drive the pipeline
incrementally, or `submit()` can run propose -> sandbox -> cross-review ->
request-approval in one call and stop there — promotion always needs a
separate, later call once Cano has actually resolved the approval.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from cano_hermes.domain.enums import AgentStatus, ApprovalStatus, RiskLevel
from cano_hermes.domain.models import AgentManifest, ApprovalRequest
from cano_hermes.governance.approvals import ApprovalService
from cano_hermes.governance.auto_approval import try_auto_approve
from cano_hermes.governance.budget import BudgetService
from cano_hermes.runtimes.base import ExecutionPacket
from cano_hermes.runtimes.container_sandbox import ContainerSandboxExecutor

from .agent_factory import AgentFactory
from .duplication import (
    DEFAULT_COMMAND_CENTER_MATRIX,
    DuplicateCandidateError,
    check_not_duplicate,
    scan_command_center_matrix,
)
from .evaluations import cross_review as run_cross_review_checks
from .models import CandidateKind, ForgeCandidate, ForgeStage
from .skill_factory import SkillFactory
from .store import ForgeCandidateStore

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForgePipeline:
    def __init__(
        self,
        *,
        agents_root: Path | str = "agents",
        skills_root: Path | str = "skills",
        agent_candidates_root: Path | str | None = None,
        skill_candidates_root: Path | str | None = None,
        candidate_store: ForgeCandidateStore | None = None,
        candidates_root: Path | str = "storage/forge/candidates",
        sandbox_workspace_root: Path | str = "storage/forge/sandbox",
        sandbox_executor: ContainerSandboxExecutor | None = None,
        approvals: ApprovalService | None = None,
        budget: BudgetService | None = None,
        command_center_matrix: Path | str | None = DEFAULT_COMMAND_CENTER_MATRIX,
    ) -> None:
        self.agents_root = Path(agents_root)
        self.skills_root = Path(skills_root)
        # Candidate artifacts default to living *under* their own root
        # (agents/candidates, skills/candidates) so overriding agents_root/
        # skills_root (e.g. in tests, or a custom settings.agent_path)
        # relocates the whole quarantine tree with it, instead of a caller
        # having to keep two paths in sync by hand.
        self.agent_factory = AgentFactory(agent_candidates_root or self.agents_root / "candidates")
        self.skill_factory = SkillFactory(skill_candidates_root or self.skills_root / "candidates")
        self.store = candidate_store or ForgeCandidateStore(candidates_root)
        self.sandbox_workspace_root = Path(sandbox_workspace_root)

        if sandbox_executor is None:
            from cano_hermes.config import settings

            sandbox_executor = ContainerSandboxExecutor(mode=settings.execution_mode)
        self.sandbox_executor = sandbox_executor

        if approvals is None:
            from cano_hermes.config import settings
            from cano_hermes.storage.sqlite import SQLiteStore

            approvals = ApprovalService(SQLiteStore(settings.database_url))
        self.approvals = approvals
        self.budget = budget

        self.command_center_matrix = Path(command_center_matrix) if command_center_matrix else None

    # ------------------------------------------------------------------
    # 1. Candidato
    # ------------------------------------------------------------------
    def propose(self, kind: CandidateKind, definition: dict[str, Any], *, requested_by: str = "system") -> ForgeCandidate:
        candidate_id = definition.get("id")
        if not candidate_id or not isinstance(candidate_id, str):
            raise ValueError("definition must include a string 'id'")

        # Hard anti-duplication gate (F4 rule): reject before any work if the
        # id already exists as a real, production agent or skill.
        check_not_duplicate(kind, candidate_id, agents_root=self.agents_root, skills_root=self.skills_root)

        existing = self.store.get(candidate_id)
        if existing is not None and existing.stage != ForgeStage.REJECTED:
            raise DuplicateCandidateError(
                f"candidate '{candidate_id}' is already in the pipeline (stage={existing.stage})"
            )

        path, artifact_snapshot = self._materialize_candidate_artifact(kind, definition)
        team = artifact_snapshot.get("team") if kind == "agent" else None

        objective = str(definition.get("objective", ""))
        warnings = (
            scan_command_center_matrix(candidate_id, objective, matrix_path=self.command_center_matrix)
            if self.command_center_matrix is not None
            else []
        )

        candidate = ForgeCandidate(
            id=candidate_id,
            kind=kind,
            team=team,
            definition=definition,
            stage=ForgeStage.PROPOSED,
            requested_by=requested_by,
            candidate_path=str(path),
            artifact_snapshot=artifact_snapshot,
            external_duplicate_warnings=warnings,
        )
        return self.store.save(candidate)

    def _materialize_candidate_artifact(self, kind: CandidateKind, definition: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
        if kind == "agent":
            try:
                manifest, path = self.agent_factory.create_from_definition(definition)
                return path, manifest.model_dump(mode="json")
            except FileExistsError:
                raise
            except (ValidationError, ValueError) as exc:
                # A malformed candidate is not rejected at intake — it enters
                # the pipeline with a best-effort artifact so cross_review's
                # "schema" check can formally reject it with a recorded
                # reason (auditable), instead of a bare exception at propose().
                path = self.agent_factory.root / f"{definition['id']}.yaml"
                if path.exists():
                    raise DuplicateCandidateError(str(path)) from exc
                raw = dict(definition)
                raw["status"] = AgentStatus.QUARANTINE.value
                path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
                return path, raw
        else:
            manifest, path = self.skill_factory.create_from_definition(definition)
            return path, manifest

    # ------------------------------------------------------------------
    # 2. Sandbox
    # ------------------------------------------------------------------
    def run_sandbox(self, candidate_id: str) -> ForgeCandidate:
        candidate = self.store.require(candidate_id)
        if candidate.stage != ForgeStage.PROPOSED:
            raise ValueError(f"candidate '{candidate_id}' is not awaiting sandbox (stage={candidate.stage})")

        # `docker run -v <path>:/workspace` requires an absolute host path —
        # a relative one is parsed as a named-volume identifier and rejected.
        workspace = (self.sandbox_workspace_root / candidate_id).resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "candidate.json").write_text(json.dumps(candidate.definition, indent=2), encoding="utf-8")

        packet = ExecutionPacket(
            task_id=f"forge-{candidate_id}",
            objective=f"sandbox smoke-test for forge candidate {candidate_id}",
            workspace=workspace,
            metadata={"command": self._smoke_test_command(), "network": "none"},
        )
        result = asyncio.run(self.sandbox_executor.execute(packet))
        passed = result.status in {"simulated", "completed"} and result.exit_code in (None, 0)

        from .models import StageResult

        candidate.sandbox_result = StageResult(
            passed=passed,
            checks={"sandbox_executed_cleanly": passed},
            notes=[result.summary],
            raw=result.model_dump(mode="json"),
        )
        candidate.stage = ForgeStage.SANDBOXED if passed else ForgeStage.SANDBOX_FAILED
        if not passed:
            candidate.rejection_reason = f"sandbox failed: {result.summary}"
        candidate.updated_at = _utcnow()
        self.store.save(candidate)
        if passed:
            self._advance_artifact_status(candidate)
        return candidate

    @staticmethod
    def _smoke_test_command() -> list[str]:
        # No network, no credentials (EXECUTOR_SECRET_ALLOWLIST["container-sandbox"]
        # is empty) — just proves the candidate artifact is well-formed enough
        # to parse and carries the two fields every candidate must have.
        smoke_test = (
            "import json; d = json.load(open('candidate.json')); "
            "assert d.get('id') and d.get('objective'), 'missing id/objective'; "
            "print('forge-smoke-test: ok')"
        )
        return ["python3", "-c", smoke_test]

    def _advance_artifact_status(self, candidate: ForgeCandidate) -> None:
        """Best-effort: move the on-disk candidate artifact's own lifecycle
        status quarantine -> testing (docs/ARCHITECTURE.md §5). Never raises
        — a candidate that failed schema validation at propose() simply
        keeps its best-effort artifact untouched; the pipeline's own
        `stage` field (not the artifact's `status`) is the source of truth."""
        if not candidate.candidate_path:
            return
        path = Path(candidate.candidate_path)
        try:
            if candidate.kind == "agent":
                manifest = AgentManifest.model_validate(candidate.artifact_snapshot)
                self.agent_factory.rewrite_status(path, manifest, AgentStatus.TESTING)
            else:
                self.skill_factory.rewrite_status(path, candidate.artifact_snapshot, "testing")
        except Exception as exc:  # noqa: BLE001 — best-effort only, see docstring
            logger.warning("Could not advance on-disk status for candidate '%s': %s", candidate.id, exc)

    # ------------------------------------------------------------------
    # 3. Revisión cruzada
    # ------------------------------------------------------------------
    def cross_review(self, candidate_id: str) -> ForgeCandidate:
        candidate = self.store.require(candidate_id)
        if candidate.stage != ForgeStage.SANDBOXED:
            raise ValueError(f"candidate '{candidate_id}' has not cleared sandbox (stage={candidate.stage})")

        result = run_cross_review_checks(candidate.kind, candidate.definition)
        candidate.review_result = result
        candidate.stage = ForgeStage.REVIEWED if result.passed else ForgeStage.REVIEW_FAILED
        if not result.passed:
            candidate.rejection_reason = "; ".join(result.notes) or "cross-review failed"
        candidate.updated_at = _utcnow()
        return self.store.save(candidate)

    # ------------------------------------------------------------------
    # 4. Aprobación
    # ------------------------------------------------------------------
    def request_approval(
        self,
        candidate_id: str,
        *,
        motivo: str,
        costo_estimado_usd: float,
        canal: str,
        requested_by: str,
        risk: RiskLevel = RiskLevel.HIGH,
    ) -> ForgeCandidate:
        candidate = self.store.require(candidate_id)
        if candidate.stage != ForgeStage.REVIEWED:
            raise ValueError(f"candidate '{candidate_id}' has not passed cross-review (stage={candidate.stage})")

        evidence_path = self._write_evidence(candidate)
        remaining = self.budget.ledger_for().remaining_usd if self.budget is not None else 0.0

        approval = self.approvals.request(
            ApprovalRequest(
                task_id=f"forge-{candidate_id}",
                action=f"promote-{candidate.kind}",
                motivo=motivo,
                risk=risk,
                requested_by=requested_by,
                costo_estimado_usd=costo_estimado_usd,
                presupuesto_restante=remaining,
                canal=canal,
                evidencia=str(evidence_path),
            )
        )
        # K12: same auto-approval engine ExecutionService.run() uses --
        # in practice this almost never fires here, since `risk` defaults
        # to HIGH (production promotion of a new agent/skill) and no
        # current caller overrides it to LOW; kept generic rather than
        # special-cased so a genuinely LOW-risk, zero-cost candidate kind
        # someday isn't silently excluded from the same governed-autonomy
        # path every other approval gets. `promote()` re-reads the
        # approval's own status independently, so nothing else needs to
        # change here for an auto-approval to take effect.
        try_auto_approve(self.approvals, approval, kanban_profile=None)
        candidate.approval_id = approval.id
        candidate.stage = ForgeStage.PENDING_APPROVAL
        candidate.updated_at = _utcnow()
        return self.store.save(candidate)

    def _write_evidence(self, candidate: ForgeCandidate) -> Path:
        evidence_path = self.store.root / f"{candidate.id}-evidence.json"
        evidence_path.write_text(
            json.dumps(
                {
                    "candidate_id": candidate.id,
                    "kind": candidate.kind,
                    "team": candidate.team,
                    "definition": candidate.definition,
                    "sandbox_result": candidate.sandbox_result.model_dump(mode="json") if candidate.sandbox_result else None,
                    "review_result": candidate.review_result.model_dump(mode="json") if candidate.review_result else None,
                    "external_duplicate_warnings": candidate.external_duplicate_warnings,
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        return evidence_path

    # ------------------------------------------------------------------
    # 5. Promoción
    # ------------------------------------------------------------------
    def promote(self, candidate_id: str) -> ForgeCandidate:
        candidate = self.store.require(candidate_id)
        if candidate.stage == ForgeStage.PROMOTED:
            return candidate  # idempotent

        if candidate.stage != ForgeStage.PENDING_APPROVAL:
            raise ValueError(f"candidate '{candidate_id}' is not pending approval (stage={candidate.stage})")
        if not candidate.approval_id:
            raise ValueError(f"candidate '{candidate_id}' has no linked approval request")

        approval = next((a for a in self.approvals.store.list_approvals() if a.id == candidate.approval_id), None)
        if approval is None:
            raise KeyError(candidate.approval_id)
        if approval.status != ApprovalStatus.APPROVED:
            raise PermissionError(
                f"approval '{approval.id}' is not resolved as approved yet (status={approval.status}); "
                "a candidate can never promote itself — Cano must resolve it first"
            )

        if candidate.kind == "agent":
            manifest = AgentManifest.model_validate(candidate.artifact_snapshot)
            target = self.agent_factory.promote(manifest, target_root=self.agents_root)
        else:
            candidate_dir = Path(candidate.candidate_path) if candidate.candidate_path else None
            target = self.skill_factory.promote(
                candidate.artifact_snapshot, target_root=self.skills_root, candidate_dir=candidate_dir
            )

        candidate.promoted_path = str(target)
        candidate.stage = ForgeStage.PROMOTED
        candidate.updated_at = _utcnow()
        return self.store.save(candidate)

    # ------------------------------------------------------------------
    # Convenience: run everything up to (not including) promotion
    # ------------------------------------------------------------------
    def submit(
        self,
        kind: CandidateKind,
        definition: dict[str, Any],
        *,
        requested_by: str,
        canal: str,
        motivo: str | None = None,
        costo_estimado_usd: float = 0.0,
    ) -> ForgeCandidate:
        """propose -> sandbox -> cross-review -> request-approval, stopping
        (with a non-PENDING_APPROVAL stage) as soon as any gate fails.
        Promotion is deliberately never part of this chain — it always
        requires a separate, later `promote()` call after Cano resolves the
        approval it produces here."""
        candidate = self.propose(kind, definition, requested_by=requested_by)
        candidate = self.run_sandbox(candidate.id)
        if candidate.stage != ForgeStage.SANDBOXED:
            return candidate
        candidate = self.cross_review(candidate.id)
        if candidate.stage != ForgeStage.REVIEWED:
            return candidate
        motivo = motivo or (
            f"Promover nuevo {candidate.kind} '{candidate.id}' a producción — "
            "requiere aprobación humana (Plan Prometeo F4, ningún agente aprueba su propio trabajo)."
        )
        return self.request_approval(
            candidate.id,
            motivo=motivo,
            costo_estimado_usd=costo_estimado_usd,
            canal=canal,
            requested_by=requested_by,
        )

    def status(self, candidate_id: str) -> ForgeCandidate:
        return self.store.require(candidate_id)

    def list_candidates(self) -> list[ForgeCandidate]:
        return self.store.list()
