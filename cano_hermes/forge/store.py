"""File-backed persistence for `ForgeCandidate` tracking records.

Mirrors the shape of `SQLiteStore` (save/get/list) but stays file-based:
candidates are throwaway pipeline state (like `storage/workspaces/`), not a
durable domain record — so one JSON file per candidate under
`storage/forge/candidates/` is simpler than a new sqlite table and needs no
migration. `agents/**/*.yaml` and `skills/**/manifest.json` remain the only
durable, versioned artifacts once a candidate is promoted.
"""
from __future__ import annotations

from pathlib import Path

from .models import ForgeCandidate


class ForgeCandidateStore:
    def __init__(self, root: Path | str = "storage/forge/candidates") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, candidate_id: str) -> Path:
        return self.root / f"{candidate_id}.json"

    def save(self, candidate: ForgeCandidate) -> ForgeCandidate:
        self._path(candidate.id).write_text(candidate.model_dump_json(indent=2), encoding="utf-8")
        return candidate

    def get(self, candidate_id: str) -> ForgeCandidate | None:
        path = self._path(candidate_id)
        if not path.exists():
            return None
        return ForgeCandidate.model_validate_json(path.read_text(encoding="utf-8"))

    def require(self, candidate_id: str) -> ForgeCandidate:
        candidate = self.get(candidate_id)
        if candidate is None:
            raise KeyError(candidate_id)
        return candidate

    def list(self) -> list[ForgeCandidate]:
        candidates = []
        for path in sorted(self.root.glob("*.json")):
            candidates.append(ForgeCandidate.model_validate_json(path.read_text(encoding="utf-8")))
        return candidates
