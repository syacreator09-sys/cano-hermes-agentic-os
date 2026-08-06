"""Anti-duplication checks for Plan Prometeo F4.

Two layers, deliberately asymmetric:

1. Hard, blocking: an `id` that already exists under `agents/**/*.yaml` or
   `skills/**/manifest.json` in *this* repo is rejected outright before any
   sandbox/review work happens — cheap and unambiguous.
2. Soft, informative only: a keyword-overlap scan of
   `cano-ai-command-center`'s `SYSTEMS_MATRIX_HERMES.md` (~250 agents living
   in a sibling, read-only system per this repo's own CLAUDE.md) flags
   *semantic* look-alikes without blocking anything — StarHome and
   command-center are different systems and duplicating a function across
   both is sometimes the right call (e.g. StarHome needs its own
   `connection-auditor` even though command-center has `inventory-auditor`).
   This layer never raises: a missing/unreadable matrix file, or no repo
   checked out at all, just means no warnings are produced.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

DEFAULT_COMMAND_CENTER_MATRIX = (
    Path.home() / "repos/cano-ai-command-center/.command-center/hermes-remote/SYSTEMS_MATRIX_HERMES.md"
)

STOPWORDS = {
    "the", "and", "for", "with", "que", "una", "los", "las", "del", "por",
    "para", "sin", "con", "sus", "sobre", "entre", "como", "este", "esta",
    "agent", "agente", "skill", "sistema", "team", "objective", "objetivo",
}


class DuplicateCandidateError(Exception):
    """Raised when a proposed id already exists as a production artifact."""


def existing_agent_ids(agents_root: Path | str = "agents") -> set[str]:
    root = Path(agents_root)
    ids: set[str] = set()
    if not root.exists():
        return ids
    for path in root.rglob("*.yaml"):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        agent_id = data.get("id") if isinstance(data, dict) else None
        if agent_id:
            ids.add(str(agent_id))
    return ids


def existing_skill_ids(skills_root: Path | str = "skills") -> set[str]:
    root = Path(skills_root)
    ids: set[str] = set()
    if not root.exists():
        return ids
    for path in root.rglob("manifest.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        skill_id = data.get("id") if isinstance(data, dict) else None
        if skill_id:
            ids.add(str(skill_id))
    return ids


def check_not_duplicate(
    kind: str,
    candidate_id: str,
    *,
    agents_root: Path | str = "agents",
    skills_root: Path | str = "skills",
) -> None:
    """Raise `DuplicateCandidateError` if `candidate_id` already exists as a
    production agent or skill. Checks *both* namespaces regardless of
    `kind` — an id colliding across kinds (an agent proposed with the id of
    an existing skill, or vice versa) is just as much a collision."""
    existing = existing_agent_ids(agents_root) | existing_skill_ids(skills_root)
    if candidate_id in existing:
        raise DuplicateCandidateError(
            f"id '{candidate_id}' already exists in this repo's agents/skills — "
            "reuse it, or pick a different id (Plan Prometeo F4 anti-duplication rule)"
        )


def _keywords(*texts: str) -> set[str]:
    words: set[str] = set()
    for text in texts:
        for token in re.split(r"[^a-zA-Z0-9]+", text.lower()):
            # >=5 chars cuts common short connector words ("real", "solo",
            # "cada") that would otherwise inflate the overlap count with
            # noise instead of an actual semantic match.
            if len(token) >= 5 and token not in STOPWORDS:
                words.add(token)
    return words


def scan_command_center_matrix(
    candidate_id: str,
    objective: str,
    matrix_path: Path | str = DEFAULT_COMMAND_CENTER_MATRIX,
    *,
    min_overlap: int = 2,
) -> list[str]:
    """Best-effort, read-only, non-blocking. Never raises — returns `[]` on
    any I/O problem (missing checkout, unreadable file, etc.), since this is
    only an informational note in the candidate's report, not a gate."""
    path = Path(matrix_path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    wanted = _keywords(candidate_id, objective)
    if not wanted:
        return []

    warnings: list[str] = []
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        line_keywords = _keywords(line)
        overlap = wanted & line_keywords
        if len(overlap) >= min_overlap:
            warnings.append(f"possible overlap with command-center row (keywords {sorted(overlap)}): {line.strip()}")
    return warnings
