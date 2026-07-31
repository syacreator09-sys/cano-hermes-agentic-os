from __future__ import annotations
from pathlib import Path
from cano_hermes.domain.enums import TaskStatus
from cano_hermes.domain.models import ExecutionResult, TaskEvent
from cano_hermes.governance.policy import PermissionEngine
from cano_hermes.runtimes.base import ExecutionPacket
from cano_hermes.runtimes.claude_code import ClaudeCodeExecutor
from cano_hermes.runtimes.codex import CodexExecutor
from cano_hermes.runtimes.hermes_agent import HermesAgentExecutor
from cano_hermes.runtimes.openclaw import OpenClawExecutor

class ExecutionService:
    def __init__(self, engine, mode="dry_run", workspace_root: Path|str="storage/workspaces"):
        self.engine=engine; self.mode=mode; self.workspace_root=Path(workspace_root); self.policy=PermissionEngine(mode)
        self.executors={"claude-code":ClaudeCodeExecutor(mode=mode),"codex":CodexExecutor(mode=mode),"hermes-agent":HermesAgentExecutor(mode=mode),"openclaw":OpenClawExecutor(mode=mode)}
    async def run(self, task_id: str, executor_id: str|None=None) -> ExecutionResult:
        task=self.engine.require(task_id)
        executor_id=executor_id or ("claude-code" if task.domain in {"research","engineering"} else "hermes-agent")
        decision=self.policy.evaluate("simulate" if self.mode=="dry_run" else "production_write", task.risk)
        if not decision.allowed:
            self.engine.transition(task.id,TaskStatus.APPROVAL,"permission-engine",{"reason":decision.reason})
            return ExecutionResult(task_id=task.id,executor=executor_id,status="approval_required",summary=decision.reason)
        executor=self.executors[executor_id]
        workspace=self.workspace_root/task.id/executor_id
        self.engine.transition(task.id,TaskStatus.RUNNING,"execution-service",{"executor":executor_id})
        result=await executor.execute(ExecutionPacket(task_id=task.id,objective=task.objective,workspace=workspace,timeout_seconds=task.budget.timeout_seconds,max_turns=task.budget.max_turns))
        status=TaskStatus.REVIEW if result.status in {"completed","simulated"} else TaskStatus.FAILED
        self.engine.transition(task.id,status,executor_id,{"execution_id":result.execution_id,"summary":result.summary[:500]})
        return result
