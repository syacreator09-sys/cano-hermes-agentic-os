from __future__ import annotations

from dataclasses import dataclass

from .graph import KnowledgeGraph
from .markdown import MarkdownVault


@dataclass(frozen=True)
class ContextPacket:
    query: str
    notes: list[dict[str, str]]
    related_nodes: list[str]
    token_hint: int


class ContextBuilder:
    def __init__(self, vault: MarkdownVault, graph: KnowledgeGraph) -> None:
        self.vault = vault
        self.graph = graph

    def build(self, query: str, max_notes: int = 6, max_chars_per_note: int = 1800) -> ContextPacket:
        matches = self.vault.search(query, limit=max_notes)
        related: set[str] = set()
        notes = []
        total_chars = 0
        for note in matches:
            excerpt = note.content[:max_chars_per_note]
            total_chars += len(excerpt)
            notes.append({"id": note.id, "title": note.title, "path": note.path, "excerpt": excerpt})
            related.update(self.graph.neighborhood(note.id, depth=1, limit=10))
        return ContextPacket(query, notes, sorted(related), max(1, total_chars // 4))
