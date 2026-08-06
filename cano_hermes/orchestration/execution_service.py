from __future__ import annotations

import json
from pathlib import Path

from cano_hermes.domain.enums import TaskStatus
from cano_hermes.domain.models import ApprovalRequest, ExecutionResult
from cano_hermes.governance.approvals import ApprovalService
from cano_hermes.governance.budget import BudgetService
from cano_hermes.governance.policy import PermissionEngine
from cano_hermes.runtimes.base import ExecutionPacket
from cano_hermes.runtimes.claude_code import ClaudeCodeExecutor
from cano_hermes.runtimes.codex import CodexExecutor
from cano_hermes.runtimes.container_sandbox import ContainerSandboxExecutor
from cano_hermes.runtimes.hermes_agent import HermesAgentExecutor
from cano_hermes.runtimes.openclaw import OpenClawExecutor


class ExecutionService:
    def __init__(
        self,
        engine,
        mode="dry_run",
        workspace_root: Path | str = "storage/workspaces",
        approvals: ApprovalService | None = None,
        budget: BudgetService | None = None,
    ):
        self.engine = engine
        self.mode = mode
        self.workspace_root = Path(workspace_root)
        self.policy = PermissionEngine(mode)
        self.executors = {
            "claude-code": ClaudeCodeExecutor(mode=mode),
            "codex": CodexExecutor(mode=mode),
            "hermes-agent": HermesAgentExecutor(mode=mode),
            "openclaw": OpenClawExecutor(mode=mode),
            "container-sandbox": ContainerSandboxExecutor(mode=mode),
        }
        # Compose the governance services rather than reimplementing their
        # logic here: ApprovalService and BudgetService each own a single
        # sqlite-backed responsibility (governance/approvals.py, budget.py).
        # Both default to the engine's own store so callers that don't care
        # about DI (tests, scripts) get a working service for free.
        self.approvals = approvals or ApprovalService(engine.store)
        self.budget = budget or BudgetService(engine.store)

    async def run(self, task_id: str, executor_id: str | None = None) -> ExecutionResult:
        task = self.engine.require(task_id)
        executor_id = executor_id or ("claude-code" if task.domain in {"research", "engineering"} else "hermes-agent")
        decision = self.policy.evaluate("simulate" if self.mode == "dry_run" else "production_write", task.risk)

        estimated_cost = task.budget.max_cost_usd
        ledger = self.budget.ledger_for()
        budget_allows = self.budget.can_spend(estimated_cost)

        if not decision.allowed or not budget_allows:
            reason = decision.reason if not decision.allowed else "daily budget would be exceeded"
            self.engine.transition(task.id, TaskStatus.APPROVAL, "permission-engine", {"reason": reason})
            evidence_path = self._write_evidence(task, executor_id, reason)
            approval = self.approvals.request(
                ApprovalRequest(
                    task_id=task.id,
                    action=executor_id,
                    motivo=reason,
                    risk=task.risk,
                    requested_by=str(task.metadata.get("requested_by", "system")),
                    costo_estimado_usd=estimated_cost,
                    presupuesto_restante=ledger.remaining_usd,
                    canal=task.domain,
                    evidencia=str(evidence_path),
                )
            )
            return ExecutionResult(
                task_id=task.id,
                executor=executor_id,
                status="approval_required",
                summary=reason,
                metrics={"approval_id": approval.id},
            )

        executor = self.executors[executor_id]
        workspace = self.workspace_root / task.id / executor_id
        self.engine.transition(task.id, TaskStatus.RUNNING, "execution-service", {"executor": executor_id})
        result = await executor.execute(
            ExecutionPacket(
                task_id=task.id,
                objective=task.objective,
                workspace=workspace,
                timeout_seconds=task.budget.timeout_seconds,
                max_turns=task.budget.max_turns,
            )
        )
        # Reconcile whatever this specific run actually cost (e.g.
        # hermes-agent's --usage-file) against today's ledger. Ingesting by
        # exact path (not a directory sweep) keeps this exactly-once even
        # across many task runs — see BudgetService.ingest_workspace for why
        # a tree-wide sweep is deliberately *not* used here.
        usage_file = workspace / f"usage-{task.id}.json"
        if usage_file.exists():
            self.budget.ingest_usage_file(usage_file)
        status = TaskStatus.REVIEW if result.status in {"completed", "simulated"} else TaskStatus.FAILED
        self.engine.transition(task.id, status, executor_id, {"execution_id": result.execution_id, "summary": result.summary[:500]})
        return result

    def _write_evidence(self, task, executor_id: str, reason: str) -> Path:
        """Persist a small draft/dry-run snapshot backing an approval
        request. `ApprovalRequest.evidencia` must point at something real
        Cano can open, not just restate the reason in prose."""
        evidence_dir = self.workspace_root / task.id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = evidence_dir / f"approval-evidence-{task.id}.json"
        evidence_path.write_text(
            json.dumps(
                {
                    "task_id": task.id,
                    "objective": task.objective,
                    "domain": task.domain,
                    "risk": task.risk.value,
                    "proposed_executor": executor_id,
                    "reason": reason,
                    "mode": self.mode,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return evidence_path
