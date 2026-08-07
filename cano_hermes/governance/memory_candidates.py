from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from cano_hermes.storage.sqlite import SQLiteStore

logger = logging.getLogger(__name__)

_DECISION_TO_STATUS = {"approved": "approved", "rejected": "rejected"}

# K11 (plan HERMES-KICKOFF) -- destination folder for approved candidates
# inside the real Obsidian vault (`~/StarHomeVault`, see `Settings.
# vault_path`). Deliberately NOT one of the vault's existing canonical
# folders (`01-Projects`, `05-Decisions`, `06-Procedures`, `11-Handoffs`) --
# those are "memoria activa" per the vault's own `Home.md` rule ("Los
# agentes proponen candidatos; no modifican memoria activa directamente").
# A human already resolved the candidate via `resolve()` below, but filing
# it into the *right* canonical folder (Decision vs. Procedure vs. Handoff)
# is itself a judgment call this service does not make -- it writes the
# approved candidate here, clearly marked `status: approved_pending_index`,
# and a human moves/rewrites it into the right canonical note when they get
# to it. This is the "promotion" boundary: nothing else in this codebase
# writes to the vault on a memory candidate's behalf.
_VAULT_INBOX_FOLDER = "00-Candidatos-Aprobados"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    return _SLUG_RE.sub("-", value.casefold()).strip("-") or "candidate"


class MemoryCandidateService:
    """K11 -- reader + human-gated resolver for Prometeo F3's
    `memory_candidates` table (`SQLiteStore.add_memory_candidate`, write-only
    until this class existed). This is the ONE path in the codebase that
    promotes a candidate to real memory (root `CLAUDE.md` rule 9: "Store
    durable lessons as candidates; never mutate approved memory directly") --
    `resolve(..., decision="approved")` is the human step that rule requires,
    and promotion to the vault only happens as this call's side effect,
    never on insert.

    Anti-self-approval mirrors `ApprovalService.resolve`'s rule (an actor
    cannot resolve its own request), narrowed to the `decision="approved"`
    path specifically -- unlike `ApprovalService`, which blocks a proposer
    from resolving their own request either way, self-*rejecting* a memory
    candidate here is allowed (declining your own proposal carries none of
    the risk self-approval does: nothing gets written to the vault). The
    check only fires *when the candidate's payload carries a `proposed_by`
    field*: unlike `ApprovalRequest` (a Pydantic model with a mandatory
    `requested_by`), `add_memory_candidate`'s `payload` is caller-defined
    free-form JSON with no schema enforced at the SQLite layer -- a
    candidate proposed before `proposed_by` was a convention has nothing to
    compare against, so the check is skipped rather than raising on data it
    cannot evaluate. New callers should set `proposed_by` to get the same
    guarantee `ApprovalService` gives every approval.
    """

    def __init__(self, store: SQLiteStore, vault_root: Path | str) -> None:
        self.store = store
        self.vault_root = Path(vault_root)

    def list(self, status: str | None = None) -> list[dict]:
        return self.store.list_memory_candidates(status)

    def get(self, candidate_id: str) -> dict:
        candidate = self.store.get_memory_candidate(candidate_id)
        if candidate is None:
            raise KeyError(candidate_id)
        return candidate

    def resolve(self, candidate_id: str, decision: str, actor: str) -> dict:
        if decision not in _DECISION_TO_STATUS:
            raise ValueError(f"decision must be one of {sorted(_DECISION_TO_STATUS)}, got {decision!r}")

        candidate = self.get(candidate_id)
        if candidate["status"] != "candidate":
            raise ValueError(
                f"memory candidate {candidate_id} is already '{candidate['status']}', expected 'candidate'"
            )

        proposed_by = candidate["payload"].get("proposed_by")
        if decision == "approved" and proposed_by and proposed_by == actor:
            raise PermissionError("An actor cannot approve its own memory candidate")

        updated = self.store.resolve_memory_candidate(candidate_id, _DECISION_TO_STATUS[decision], actor)
        promoted_path: Path | None = None
        if decision == "approved":
            promoted_path = self._promote_to_vault(updated)
            logger.info("memory candidate %s promoted to %s", candidate_id, promoted_path)
        return {**updated, "promoted_path": str(promoted_path) if promoted_path else None}

    def _promote_to_vault(self, candidate: dict) -> Path:
        """Writes the approved candidate as a new Markdown note under
        `_VAULT_INBOX_FOLDER`. Never overwrites an existing file for the
        same candidate id (idempotent by construction: `resolve()` already
        refuses to resolve a non-`candidate` row twice, so this only ever
        runs once per id, but the guard stays cheap insurance)."""
        folder = self.vault_root / _VAULT_INBOX_FOLDER
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"{_slug(candidate['namespace'])}--{candidate['id']}.md"
        path = folder / filename

        payload = candidate["payload"]
        frontmatter = {
            "id": f"candidate-{candidate['id']}",
            "type": "memory-candidate",
            "title": f"{candidate['namespace']} — {candidate['id']}",
            "status": "approved_pending_index",
            "sensitivity": "internal",
            "confidence": "proposed",
            "source_type": "agent-proposal",
            "source_refs": [],
            "related": [],
            "retention": "pending-human-index",
            "namespace": candidate["namespace"],
            "approved_by": payload.get("resolved_by"),
            "approved_at": payload.get("resolved_at"),
            "created_at": candidate["created_at"],
        }
        lines = ["---"]
        for key, value in frontmatter.items():
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        lines.append("---")
        lines.append("")
        lines.append(f"# {candidate['namespace']} — {candidate['id']}")
        lines.append("")
        lines.append(
            "Pendiente de índice humano: un agente propuso este candidato y "
            "fue aprobado, pero todavía no ha sido archivado en su carpeta "
            "canónica (`01-Projects`, `05-Decisions`, `06-Procedures` o "
            "`11-Handoffs`). No tratar como memoria activa hasta que un "
            "humano lo mueva/reescriba ahí."
        )
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(payload, indent=2, ensure_ascii=False))
        lines.append("```")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
