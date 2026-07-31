from __future__ import annotations

import re
import subprocess
from pathlib import Path


SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")


class WorktreeManager:
    def __init__(self, root: Path | str = "storage/worktrees") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, repository: Path, task_id: str, worker: str) -> Path:
        name = SAFE_NAME.sub("-", f"{task_id}-{worker}").strip("-")
        target = self.root / name
        branch = f"hermes/{name}"
        if target.exists():
            raise FileExistsError(target)
        subprocess.run(
            ["git", "-C", str(repository), "worktree", "add", "-b", branch, str(target)],
            check=True,
            capture_output=True,
            text=True,
        )
        return target

    def remove(self, repository: Path, target: Path) -> None:
        if self.root.resolve() not in target.resolve().parents:
            raise ValueError("Refusing to remove unmanaged worktree")
        subprocess.run(
            ["git", "-C", str(repository), "worktree", "remove", str(target)],
            check=True,
            capture_output=True,
            text=True,
        )
