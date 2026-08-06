"""K2 — closes the execution cycle K1 left open.

Two gaps this fills (see plan HERMES-KICKOFF K2, gaps 5 and 10):

1. `REVIEW` was a de facto terminal state: `ExecutionService.run()`
   transitions a task to REVIEW on a completed/simulated result, but nothing
   ever moved it to DONE. `complete_execution()` below is the missing other
   half of that transition.
2. `ExecutionResult.artifacts` (`domain/models.py`) was always empty --
   nothing wrote to `settings.artifact_path` even though
   `Settings.ensure_directories()` already creates it. `collect_artifacts()`
   is the missing writer.

Decision -- what counts as an "artifact":
Executors don't yet separate "deliverable output" from "scratch work". In
dry_run mode nothing is written to the workspace at all (`CommandExecutor.
execute` returns a simulated result without touching disk beyond `mkdir`);
in real mode the executor's subprocess just runs with `cwd=workspace`, so
whatever files a run happens to produce land directly in
`storage/workspaces/<task_id>/<executor_id>/` with no convention
distinguishing "output" from "cache". Rather than guess a per-executor
output directory that doesn't exist yet, this copies the *whole* workspace
tree to `storage/artifacts/<task_id>/<executor_id>/`, excluding only:

  - well-known junk directories a shelled-out toolchain can leave behind
    (`.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `.mypy_cache`,
    `.pytest_cache`, `.ruff_cache`) -- obvious noise, never a deliverable;
  - the `usage-<task_id>.json` sidecar `HermesAgentExecutor` writes -- that
    is budget bookkeeping already ingested by `BudgetService`, not a
    deliverable for a human to review.

Everything else is treated as output. When executors grow a real
output-vs-scratch convention (a declared output dir, a manifest, ...) this
should narrow to copy only that instead of the whole tree.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from cano_hermes.domain.enums import RiskLevel, TaskStatus
from cano_hermes.domain.models import ExecutionResult, TaskEvent, TaskRecord

JUNK_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


def _is_bookkeeping_file(path: Path, task_id: str) -> bool:
    return path.name == f"usage-{task_id}.json"


def collect_artifacts(workspace: Path, destination: Path, task_id: str) -> list[str]:
    """Copy `workspace`'s output tree into `destination`, skipping known
    junk directories and the usage-file sidecar.

    Returns the copied file paths (as strings), sorted for determinism. A
    missing or empty workspace (e.g. a dry_run that never touched disk)
    yields an empty list rather than an error -- "no artifacts" is a normal,
    expected outcome, not a failure.
    """
    if not workspace.exists():
        return []

    copied: list[str] = []
    for item in sorted(workspace.rglob("*")):
        if item.is_dir():
            continue
        relative = item.relative_to(workspace)
        # Checks every path component, not just the parent directories: a
        # git worktree's root `.git` is a *file* (a gitdir pointer), not a
        # directory, so this also has to catch a junk name sitting at the
        # leaf, not only ones a directory walk would descend past.
        if any(part in JUNK_DIR_NAMES for part in relative.parts):
            continue
        if _is_bookkeeping_file(item, task_id):
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        copied.append(str(target))
    return copied


def complete_execution(
    engine,
    task: TaskRecord,
    executor_id: str,
    result: ExecutionResult,
    workspace: Path,
    artifacts_root: Path,
    usage: dict | None = None,
) -> ExecutionResult:
    """Runs right after `ExecutionService.run()` persists the raw execution
    row (K1). Only called for a completed/simulated run (REVIEW branch) --
    never for a failed one, since there is nothing to hand off.

    - Copies workspace outputs into
      `storage/artifacts/<task_id>/<executor_id>/`.
    - Records the resulting paths on `result.artifacts` and re-persists the
      execution row (`executions.artifacts_json`), plus a `task.artifacts`
      event so the timeline shows what was produced.
    - Closes the loop: LOW-risk tasks auto-transition REVIEW -> DONE.
      MEDIUM/HIGH/CRITICAL stay in REVIEW for a human (or an explicitly
      authorized later step) to close via `POST /api/tasks/{id}/complete`.
      No auto-approval is added here for the non-LOW path -- that is K12's
      job, not K2's.
    """
    destination = artifacts_root / task.id / executor_id
    artifact_paths = collect_artifacts(workspace, destination, task.id)
    result.artifacts = artifact_paths

    engine.store.save_execution(result, usage=usage or {})
    engine.store.add_event(
        TaskEvent(
            task_id=task.id,
            kind="task.artifacts",
            actor=executor_id,
            payload={"paths": artifact_paths, "count": len(artifact_paths)},
        )
    )

    if task.risk == RiskLevel.LOW:
        engine.transition(
            task.id,
            TaskStatus.DONE,
            "completion",
            {"reason": "low-risk-auto-complete", "artifacts": artifact_paths},
        )

    return result
