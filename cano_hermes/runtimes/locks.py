from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from time import time


class WriteLockManager:
    def __init__(self, root: Path | str = "storage/locks") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def acquire(self, workspace: Path, owner: str):
        key = workspace.resolve().as_posix().replace("/", "_").replace(":", "_")
        path = self.root / f"{key}.lock"
        try:
            fd = path.open("x", encoding="utf-8")
        except FileExistsError as exc:
            raise RuntimeError(f"Workspace already locked: {workspace}") from exc
        try:
            with fd:
                json.dump({"owner": owner, "workspace": str(workspace), "created_at": time()}, fd)
            yield path
        finally:
            path.unlink(missing_ok=True)
