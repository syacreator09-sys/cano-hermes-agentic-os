from __future__ import annotations

from pathlib import Path


class CommandCenterConnector:
    """Read-only locator for the separate Cano AI Command Center."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def health(self) -> dict[str, object]:
        return {"exists": self.root.exists(), "path": str(self.root), "mode": "read-only"}

    def locate(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()
        if self.root.resolve() not in target.parents and target != self.root.resolve():
            raise ValueError("Path escapes Command Center root")
        return target
