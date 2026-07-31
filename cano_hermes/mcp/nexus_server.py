from __future__ import annotations

import json
import sys

from cano_hermes.config import settings
from cano_hermes.nexus.context import ContextBuilder
from cano_hermes.nexus.graph import KnowledgeGraph
from cano_hermes.nexus.markdown import MarkdownVault


def handle(request: dict) -> dict:
    method = request.get("method")
    params = request.get("params", {})
    vault = MarkdownVault(settings.vault_path)
    graph = KnowledgeGraph(vault)
    if method == "tools/list":
        return {
            "tools": [
                {"name": "nexus_search", "description": "Search approved Markdown knowledge"},
                {"name": "nexus_context", "description": "Build a bounded context packet"},
            ]
        }
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name == "nexus_search":
            return {"content": [note.__dict__ for note in vault.search(arguments.get("query", ""))]}
        if name == "nexus_context":
            packet = ContextBuilder(vault, graph).build(arguments.get("query", ""))
            return {"content": packet.__dict__}
        raise ValueError(f"Unknown tool: {name}")
    raise ValueError(f"Unknown method: {method}")


def main() -> None:
    for line in sys.stdin:
        try:
            request = json.loads(line)
            result = handle(request)
            response = {"jsonrpc": "2.0", "id": request.get("id"), "result": result}
        except Exception as exc:  # protocol boundary
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(exc)}}
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
