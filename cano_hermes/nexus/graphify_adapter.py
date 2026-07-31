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
