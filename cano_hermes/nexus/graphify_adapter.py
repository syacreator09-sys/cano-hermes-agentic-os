from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GraphifyAdapter:
    """Imports Graphify graph.json without making Graphify the source of truth."""

    def load(self, path: Path | str) -> dict[str, Any]:
        graph_path = Path(path)
        data = json.loads(graph_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Graphify export must be a JSON object")
        return data

    def summarize(self, data: dict[str, Any]) -> dict[str, int]:
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        return {"nodes": len(nodes) if isinstance(nodes, list) else 0, "edges": len(edges) if isinstance(edges, list) else 0}

    def query(self, path: Path | str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """K11 (plan HERMES-KICKOFF) -- best-effort node lookup against a
        graphify graph.json export (`graphify update <path>`, produced by
        the graphify CLI/skill, node-link JSON with `nodes`/`edges` lists).
        Scored the same way `MarkdownVault.search` scores notes
        (term-frequency over a haystack of label/id/source_file), so
        `ContextBuilder` can rank and cap graphify matches with a familiar
        interface next to vault notes.

        Never raises: a missing or malformed graph (nobody has run graphify
        against this repo yet, or `graphify-out/` was cleaned) just returns
        `[]` -- Nexus context keeps working off the vault alone, matching
        this adapter's own "import without becoming source of truth"
        contract (see the class docstring).
        """
        try:
            data = self.load(path)
        except (FileNotFoundError, ValueError, json.JSONDecodeError):
            return []

        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        if not isinstance(nodes, list):
            return []
        terms = [term.casefold() for term in query.split() if term]
        if not terms:
            return []

        scored: list[tuple[int, dict[str, Any]]] = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            haystack = " ".join(str(node.get(key, "")) for key in ("label", "id", "source_file")).casefold()
            score = sum(haystack.count(term) for term in terms)
            if score:
                scored.append((score, node))
        scored.sort(key=lambda item: -item[0])

        degree: dict[Any, int] = {}
        if isinstance(edges, list):
            for edge in edges:
                if not isinstance(edge, dict):
                    continue
                for key in ("source", "target"):
                    node_id = edge.get(key)
                    if node_id is not None:
                        degree[node_id] = degree.get(node_id, 0) + 1

        return [
            {
                "id": node.get("id"),
                "label": node.get("label"),
                "source_file": node.get("source_file") or None,
                "type": node.get("file_type"),
                "degree": degree.get(node.get("id"), 0),
            }
            for _, node in scored[:limit]
        ]
