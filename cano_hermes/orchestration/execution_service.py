from __future__ import annotations

import asyncio
import json
from pathlib import Path

from cano_hermes.domain.enums import ApprovalStatus, TaskStatus
from cano_hermes.domain.models import ApprovalRequest, ExecutionResult
from cano_hermes.governance.approvals import ApprovalService
from cano_hermes.governance.auto_approval import try_auto_approve
from cano_hermes.governance.budget import BudgetService
from cano_hermes.governance.policy import PermissionEngine
from cano_hermes.orchestration.completion import complete_execution
from cano_hermes.orchestration.conductor import kanban_profile_for_domain
from cano_hermes.runtimes.aah import AAHExecutor
from cano_hermes.runtimes.base import ExecutionPacket
from cano_hermes.runtimes.claude_code import ClaudeCodeExecutor
from cano_hermes.runtimes.codex import CodexExecutor
from cano_hermes.runtimes.container_sandbox import ContainerSandboxExecutor
from cano_hermes.runtimes.hermes_agent import HermesAgentExecutor
from cano_hermes.runtimes.locks import WriteLockManager
from cano_hermes.runtimes.openclaw import OpenClawExecutor
from cano_hermes.runtimes.worktrees import SAFE_NAME, WorktreeManager

# AgentManifest.runtime (agents/**/*.yaml `runtime:` field) -> registered
# Executor id. Not a 1:1 name match by accident in three cases: "hermes" is
# the manifest spelling of the "hermes-agent" executor; "api" (model-profile
# tier, e.g. kimi/deepseek/nvidia-NIM agents) also runs through hermes-agent,
# which reads packet.metadata["model"/"provider"] to pick the right backend
# (see HermesAgentExecutor.build_args); "browser" maps to openclaw (K10 will
# give it a dedicated runtime, this is the current stand-in); "python" maps
# to container-sandbox, the only executor that runs arbitrary local code in
# an isolated, capability-dropped container rather than shelling out to a
# specific vendor CLI.
AGENT_RUNTIME_TO_EXECUTOR: dict[str, str] = {
    "hermes": "hermes-agent",
    "api": "hermes-agent",
    "claude-code": "claude-code",
    "codex": "codex",
    "browser": "openclaw",
    "python": "container-sandbox",
    "aah": "aah",  # A0: engineering-domain tasks routed to Adaptive Agent Harness
}
DEFAULT_EXECUTOR_ID = "hermes-agent"

# A0: `.aah/bin/factory` is a project-local binary `install.sh` writes into
# this repo's own root (there is no global `factory` on PATH -- AAH is
# installed per-project, see docs/AAH_INTEGRATION_CONTRACT.md section 2).
REPO_ROOT = Path(__file__).resolve().parents[2]
AAH_BINARY = REPO_ROOT / ".aah" / "bin" / "factory"

# Global, named lock: any task whose metadata marks it as a render (Remotion/
# ffmpeg) contends for this single key regardless of its own workspace. No
# render executor exists yet to detect this automatically, so the interim
# convention -- documented here because it's the only place it's enforced --
# is that whoever queues a render sets `metadata={"kind": "render", ...}`.
# The machine has no GPU: renders must always run one at a time, never two in
# parallel, hence one shared lock rather than the usual per-workspace one.
RENDER_LOCK_KEY = "render"


class ExecutionService:
    def __init__(
        self,
        engine,
        mode="dry_run",
        workspace_root: Path | str = "storage/workspaces",
        approvals: ApprovalService | None = None,
        budget: BudgetService | None = None,
        artifacts_root: Path | str = "storage/artifacts",
        lock_manager: WriteLockManager | None = None,
        worktree_manager: WorktreeManager | None = None,
        repository: Path | str | None = None,
    ):
        self.engine = engine
        self.mode = mode
        self.workspace_root = Path(workspace_root)
        self.artifacts_root = Path(artifacts_root)
        self.policy = PermissionEngine(mode)
        self.executors = {
            "claude-code": ClaudeCodeExecutor(mode=mode),
            "codex": CodexExecutor(mode=mode),
            "hermes-agent": HermesAgentExecutor(mode=mode),
            "openclaw": OpenClawExecutor(mode=mode),
            "container-sandbox": ContainerSandboxExecutor(mode=mode),
            "aah": AAHExecutor(str(AAH_BINARY), mode=mode),
        }
        # Compose the governance services rather than reimplementing their
        # logic here: ApprovalService and BudgetService each own a single
        # sqlite-backed responsibility (governance/approvals.py, budget.py).
        # Both default to the engine's own store so callers that don't care
        # about DI (tests, scripts) get a working service for free.
        self.approvals = approvals or ApprovalService(engine.store)
        self.budget = budget or BudgetService(engine.store)
        self.lock_manager = lock_manager or WriteLockManager()
        self.worktree_manager = worktree_manager or WorktreeManager()
        # Worktree isolation for engineering-domain tasks is opt-in: it only
        # activates when a real git `repository` is configured. Left at
        # None (the default used by every test that constructs this class
        # directly), engineering tasks keep using the plain shared
        # workspace exactly as before K2 -- this avoids surprising every
        # existing domain="engineering" test with real `git worktree add`
        # side effects against whatever repo happens to be the process cwd.
        # Production wiring (api/dependencies.py) passes
        # settings.repository_root to actually enable it.
        self.repository = Path(repository) if repository is not None else None

    def _is_render_task(self, task) -> bool:
        return task.metadata.get("kind") == "render"

    # P1 (plan POTENCIA, 2026-08-07): the real strings both CLIs are
    # observed to emit when a subscription window is exhausted (Claude
    # Code: "usage limit"/"5-hour limit" style messaging surfaced via
    # claude_daemon events in this session's own transcripts; Codex: rate/
    # usage errors from the ChatGPT plan). Matched case-insensitively
    # against summary + stderr-ish text CommandExecutor already captures in
    # ExecutionResult.summary on a non-zero exit -- never against stdout
    # content that might contain user data.
    _USAGE_LIMIT_SIGNATURES = ("usage limit", "usage_limit", "rate limit", "quota exceeded")

    def _is_usage_limit_error(self, result: ExecutionResult) -> bool:
        if result.status not in ("failed", "unavailable"):
            return False
        text = (result.summary or "").lower()
        return any(signature in text for signature in self._USAGE_LIMIT_SIGNATURES)

    async def _run_locked(self, lock_target: Path, owner: str, action):
        """Hold `self.lock_manager`'s lock on `lock_target` for the duration
        of `action()`. `WriteLockManager.acquire` itself is fail-fast (it
        raises `RuntimeError` immediately on contention) -- this wraps
        *just the acquisition* in a poll loop so a second contender actually
        *waits* for the first to finish and then runs, instead of erroring
        out. That's what makes two render tasks serialize rather than
        merely "not crash". Acquisition and execution are deliberately
        split (rather than one `try/except RuntimeError` around the whole
        `with` block) so a `RuntimeError` raised by `action()` itself
        propagates normally instead of being mistaken for lock contention
        and retried forever.

        Known limitation: no staleness eviction. A process that dies while
        holding the lock leaves the lock file behind forever, and every
        future contender for that same key will wait indefinitely. Accepted
        gap for K2 -- worth revisiting once K3 adds a real queue/worker
        supervisor that can detect and clear a dead holder.
        """
        while True:
            lock_cm = self.lock_manager.acquire(lock_target, owner)
            try:
                lock_cm.__enter__()
            except RuntimeError:
                await asyncio.sleep(0.05)
                continue
            try:
                return await action()
            finally:
                lock_cm.__exit__(None, None, None)

    def _worktree_for(self, task, executor_id: str) -> Path:
        """Idempotent: a retried run of the same task+executor reuses the
        worktree `WorktreeManager.create` already made instead of crashing
        on `FileExistsError`."""
        name = SAFE_NAME.sub("-", f"{task.id}-{executor_id}").strip("-")
        target = self.worktree_manager.root / name
        if target.exists():
            return target
        return self.worktree_manager.create(self.repository, task.id, executor_id)

    def _resolve_executor_id(self, task) -> str:
        """Derive the executor from the Conductor's Assignment
        (`task.assigned_agent` -> AgentManifest.runtime), instead of the
        domain-only ternary this replaces. Falls back to that same ternary
        only when there is no assignment to read yet (task never went
        through `/api/tasks/{id}/plan`) — an explicit `executor_id` argument
        to `run()` always wins over both and never reaches this method."""
        manifest = self.engine.conductor.registry.get(task.assigned_agent) if task.assigned_agent else None
        if manifest is None:
            return "claude-code" if task.domain in {"research", "engineering"} else DEFAULT_EXECUTOR_ID
        mapped = AGENT_RUNTIME_TO_EXECUTOR.get(manifest.runtime, DEFAULT_EXECUTOR_ID)
        return mapped if mapped in self.executors else DEFAULT_EXECUTOR_ID

    def _build_metadata(self, task) -> dict:
        """Carry the Conductor/ModelRouter's decision into the
        ExecutionPacket so runtime-level overrides already written in
        hermes_agent.py/container_sandbox.py (which read packet.metadata)
        actually activate instead of being unreachable."""
        metadata: dict = {}
        # P1 (plan POTENCIA, 2026-08-07): carried so ClaudeCodeExecutor can
        # pick --model by risk (build_args reads packet.metadata["risk"]).
        metadata["risk"] = task.risk.value
        # A1 (plan AUTONOMÍA TOTAL, 2026-08-08): caller-supplied task_kind
        # ("plan"/"consulta"/"rutina" -- see TaskCreate.metadata) carried
        # the same way, so ClaudeCodeExecutor.build_args's task_kind
        # override (checked before risk) is actually reachable.
        if task.metadata.get("task_kind"):
            metadata["task_kind"] = task.metadata["task_kind"]
        if task.assigned_agent:
            metadata["agent_id"] = task.assigned_agent
        if task.route_profile:
            metadata["route_profile"] = task.route_profile
            profile = self.engine.conductor.router.profile_by_id(task.route_profile)
            if profile is not None:
                metadata["model"] = profile.model
                metadata["provider"] = profile.provider
        manifest = self.engine.conductor.registry.get(task.assigned_agent) if task.assigned_agent else None
        if manifest is not None and manifest.tools:
            metadata["toolsets"] = list(manifest.tools)
        return metadata

    async def run(self, task_id: str, executor_id: str | None = None, execution_id: str | None = None) -> ExecutionResult:
        """`execution_id`, when given, pins the `ExecutionResult.execution_id`
        this run produces instead of letting `ExecutionResult`'s own
        `default_factory` mint a random one. K3's `QueueService` uses this to
        let a caller learn the execution's id *before* the run finishes (at
        enqueue time) and poll `GET /api/executions/{id}` for it -- every
        write path below (the approval-required early return, and the
        normal-completion save further down) is threaded to honor it. Every
        pre-K3 caller omits it and gets the exact same auto-generated-id
        behavior as before."""
        task = self.engine.require(task_id)
        executor_id = executor_id or self._resolve_executor_id(task)
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
            # K12: give the auto-approval engine a chance to resolve this
            # request on its own (actor="policy-engine", never `task`'s own
            # requester) BEFORE treating it as blocked -- see
            # governance/auto_approval.py for the full, all-must-hold
            # condition list. `write_target` mirrors the workspace path
            # this same task would get below if it proceeds, so the
            # engine's "writes stay inside allowed_write_paths" condition
            # (K1/K2) checks the real path this run would actually use.
            write_target = self.workspace_root / task.id / executor_id
            resolved = try_auto_approve(
                self.approvals,
                approval,
                kanban_profile=kanban_profile_for_domain(task.domain),
                write_target=write_target,
                allowed_write_paths=(write_target,),
            )
            if resolved is None or resolved.status != ApprovalStatus.APPROVED:
                blocked_result = ExecutionResult(
                    task_id=task.id,
                    executor=executor_id,
                    status="approval_required",
                    summary=reason,
                    metrics={"approval_id": approval.id},
                )
                if execution_id is not None:
                    blocked_result.execution_id = execution_id
                return blocked_result
            # Auto-approved: fall through to normal execution below exactly
            # as if Cano had already resolved this from the dashboard/
            # Telegram -- no separate code path, no shortcut around any of
            # the locking/workspace/budget-ingestion logic that follows.
            self.engine.transition(
                task.id, TaskStatus.READY, "policy-engine",
                {"reason": "auto-approved", "approval_id": resolved.id},
            )

        executor = self.executors[executor_id]
        # Engineering-domain tasks get an isolated git worktree instead of
        # the shared workspace tree, when a repository is configured (see
        # `self.repository`'s docstring in __init__) -- two code-writing
        # tasks must never share a checkout.
        if task.domain == "engineering" and self.repository is not None:
            workspace = self._worktree_for(task, executor_id)
        else:
            workspace = self.workspace_root / task.id / executor_id
        self.engine.transition(task.id, TaskStatus.RUNNING, "execution-service", {"executor": executor_id})
        packet = ExecutionPacket(
            task_id=task.id,
            objective=task.objective,
            workspace=workspace,
            allowed_write_paths=(workspace,),
            timeout_seconds=task.budget.timeout_seconds,
            max_turns=task.budget.max_turns,
            metadata=self._build_metadata(task),
        )
        # WriteLockManager wraps every run so two tasks never write into the
        # same resource concurrently. Render tasks (metadata.kind=="render")
        # contend for one shared global key instead of their own workspace
        # key, since this machine has no GPU and renders must always be
        # strictly sequential -- see RENDER_LOCK_KEY and _run_locked.
        if self._is_render_task(task):
            lock_target = self.lock_manager.root / RENDER_LOCK_KEY
        else:
            lock_target = workspace
        result = await self._run_locked(
            lock_target, f"{executor_id}:{task.id}", lambda: executor.execute(packet)
        )
        # P1 (plan POTENCIA, 2026-08-07): a subscription hitting its usage
        # window is not a task failure, it's a capacity problem -- retry
        # ONCE with hermes-agent (tier-0 Kimi/OpenRouter, EXECUTOR_SECRET_
        # ALLOWLIST already scopes it to those cheap tiers only) instead of
        # surfacing FAILED. Never escalates to a paid tier-5 profile on its
        # own -- that still requires the normal approval path above.
        if executor_id in ("claude-code", "codex") and self._is_usage_limit_error(result):
            fallback_executor = self.executors.get("hermes-agent")
            if fallback_executor is not None:
                fallback_workspace = self.workspace_root / task.id / "hermes-agent"
                fallback_packet = ExecutionPacket(
                    task_id=task.id, objective=task.objective, workspace=fallback_workspace,
                    allowed_write_paths=(fallback_workspace,), timeout_seconds=task.budget.timeout_seconds,
                    max_turns=task.budget.max_turns, metadata=self._build_metadata(task),
                )
                fallback_result = await self._run_locked(
                    fallback_workspace, f"hermes-agent:{task.id}", lambda: fallback_executor.execute(fallback_packet)
                )
                fallback_result.metrics["degraded_from"] = executor_id
                fallback_result.metrics["degradation_reason"] = "usage_limit"
                result = fallback_result
        if execution_id is not None:
            result.execution_id = execution_id
        # Reconcile whatever this specific run actually cost against today's
        # ledger. Two sources, mutually exclusive in practice by executor:
        # hermes-agent writes a --usage-file; claude-code reports
        # total_cost_usd inline in its parsed stream-json `result` event
        # (ClaudeCodeExecutor.parse_result). Ingesting by exact path/field
        # (not a directory sweep) keeps this exactly-once even across many
        # task runs — see BudgetService.ingest_workspace for why a tree-wide
        # sweep is deliberately *not* used here.
        usage_file = workspace / f"usage-{task.id}.json"
        usage_payload: dict = {}
        if usage_file.exists():
            self.budget.ingest_usage_file(usage_file)
            try:
                usage_payload = json.loads(usage_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                usage_payload = {}
        else:
            cost = result.metrics.get("total_cost_usd")
            if isinstance(cost, (int, float)) and cost > 0:
                self.budget.record_spend(float(cost), force=True)
        if "usage" in result.metrics:
            usage_payload["usage"] = result.metrics["usage"]
        if "total_cost_usd" in result.metrics:
            usage_payload["total_cost_usd"] = result.metrics["total_cost_usd"]

        status = TaskStatus.REVIEW if result.status in {"completed", "simulated"} else TaskStatus.FAILED
        self.engine.transition(task.id, status, executor_id, {"execution_id": result.execution_id, "summary": result.summary[:500]})
        self.engine.store.save_execution(result, usage=usage_payload)
        if status == TaskStatus.REVIEW:
            # K2: copy workspace outputs into storage/artifacts/, record
            # them on the execution row, and auto-close LOW-risk tasks
            # (REVIEW -> DONE). See completion.py for the full contract.
            complete_execution(self.engine, task, executor_id, result, workspace, self.artifacts_root, usage=usage_payload)
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
