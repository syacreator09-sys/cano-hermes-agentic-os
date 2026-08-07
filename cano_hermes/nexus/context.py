from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .graph import KnowledgeGraph
from .graphify_adapter import GraphifyAdapter
from .markdown import MarkdownVault


@dataclass(frozen=True)
class ContextPacket:
    query: str
    notes: list[dict[str, str]]
    related_nodes: list[str]
    token_hint: int
    graphify_matches: list[dict] = field(default_factory=list)


class ContextBuilder:
    """K11 (plan HERMES-KICKOFF) -- single context facade Nexus exposes to
    the rest of the system (`GET /api/nexus/context`, `nexus_server.py`'s
    MCP tool). Mixes independently-optional sources:

    - `MarkdownVault` + `KnowledgeGraph`: full-text search + wikilink
      neighborhood over `settings.vault_path` (the real Obsidian vault,
      `~/StarHomeVault` on this machine). Always on -- this is the original
      Foundation-phase behavior, unchanged.
    - `GraphifyAdapter`: best-effort node lookup over a
      `graphify-out/graph.json` export (a code-structure graph built by the
      graphify CLI/skill). OFF by default (`graphify=None`) so every caller
      that predates this field, including `test_foundation.py`'s
      `ContextBuilder(v, KnowledgeGraph(v))`, keeps getting exactly the
      vault-only packet it got before -- passing a `GraphifyAdapter()`
      instance opts in.

    Extension point for a future gbrain adapter (K11 gate -- credentials +
    RLS decision pending Cano, see `reports/k11-memoria-unificada-*.md`):
    a third constructor arg shaped like `graphify` (an object with a
    `query(text, limit) -> list[dict]` method) would merge into `build()`
    the same way graphify does below -- read-only, additive, no change to
    this class's structure required.
    """

    def __init__(
        self,
        vault: MarkdownVault,
        graph: KnowledgeGraph,
        graphify: GraphifyAdapter | None = None,
        graphify_graph_path: Path | str = Path("graphify-out/graph.json"),
    ) -> None:
        self.vault = vault
        self.graph = graph
        self.graphify = graphify
        self.graphify_graph_path = graphify_graph_path

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

        graphify_matches: list[dict] = []
        if self.graphify is not None:
            graphify_matches = self.graphify.query(self.graphify_graph_path, query, limit=max_notes)

        return ContextPacket(query, notes, sorted(related), max(1, total_chars // 4), graphify_matches)
