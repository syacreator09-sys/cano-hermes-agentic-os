"""K11 (plan HERMES-KICKOFF) -- GraphifyAdapter.query + its wiring into
ContextBuilder.

Covers: (a) `GraphifyAdapter.query` scores/ranks/caps node matches from a
node-link `graph.json`, (b) it degrades to `[]` (never raises) for a
missing/malformed graph, (c) `ContextBuilder` stays exactly vault-only when
no `graphify` adapter is given (backward compatibility with every caller
that predates this field, including `test_foundation.py`), (d) passing a
`GraphifyAdapter` merges `graphify_matches` into the `ContextPacket`.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cano_hermes.nexus.context import ContextBuilder
from cano_hermes.nexus.graph import KnowledgeGraph
from cano_hermes.nexus.graphify_adapter import GraphifyAdapter
from cano_hermes.nexus.markdown import MarkdownVault

ROOT = Path(__file__).resolve().parents[1]

_SAMPLE_GRAPH = {
    "directed": True,
    "multigraph": False,
    "graph": {},
    "nodes": [
        {"id": "n1", "label": "ContextBuilder", "source_file": "cano_hermes/nexus/context.py", "file_type": "code"},
        {"id": "n2", "label": "MarkdownVault", "source_file": "cano_hermes/nexus/markdown.py", "file_type": "code"},
        {"id": "n3", "label": "Unrelated", "source_file": "cano_hermes/other.py", "file_type": "code"},
    ],
    "edges": [
        {"source": "n1", "target": "n2", "relation": "uses"},
    ],
}


class GraphifyAdapterQueryTests(unittest.TestCase):
    def test_query_scores_and_ranks_matches(self):
        with tempfile.TemporaryDirectory() as d:
            graph_path = Path(d) / "graph.json"
            graph_path.write_text(json.dumps(_SAMPLE_GRAPH), encoding="utf-8")
            matches = GraphifyAdapter().query(graph_path, "ContextBuilder", limit=5)
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["id"], "n1")
            self.assertEqual(matches[0]["degree"], 1)

    def test_query_respects_limit(self):
        with tempfile.TemporaryDirectory() as d:
            graph_path = Path(d) / "graph.json"
            graph_path.write_text(json.dumps(_SAMPLE_GRAPH), encoding="utf-8")
            matches = GraphifyAdapter().query(graph_path, "code", limit=2)
            self.assertLessEqual(len(matches), 2)

    def test_missing_graph_returns_empty_list(self):
        matches = GraphifyAdapter().query("/no/such/graphify-out/graph.json", "anything")
        self.assertEqual(matches, [])

    def test_malformed_graph_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as d:
            graph_path = Path(d) / "graph.json"
            graph_path.write_text("not json", encoding="utf-8")
            matches = GraphifyAdapter().query(graph_path, "anything")
            self.assertEqual(matches, [])

    def test_blank_query_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as d:
            graph_path = Path(d) / "graph.json"
            graph_path.write_text(json.dumps(_SAMPLE_GRAPH), encoding="utf-8")
            self.assertEqual(GraphifyAdapter().query(graph_path, "   "), [])


class ContextBuilderGraphifyWiringTests(unittest.TestCase):
    def test_no_graphify_adapter_keeps_vault_only_behavior(self):
        vault = MarkdownVault(ROOT / "vault")
        packet = ContextBuilder(vault, KnowledgeGraph(vault)).build("architecture autonomy")
        self.assertGreaterEqual(len(packet.notes), 1)
        self.assertEqual(packet.graphify_matches, [])

    def test_graphify_matches_merge_into_packet(self):
        vault = MarkdownVault(ROOT / "vault")
        with tempfile.TemporaryDirectory() as d:
            graph_path = Path(d) / "graph.json"
            graph_path.write_text(json.dumps(_SAMPLE_GRAPH), encoding="utf-8")
            builder = ContextBuilder(vault, KnowledgeGraph(vault), GraphifyAdapter(), graph_path)
            packet = builder.build("ContextBuilder")
            self.assertEqual(len(packet.graphify_matches), 1)
            self.assertEqual(packet.graphify_matches[0]["label"], "ContextBuilder")

    def test_graphify_adapter_without_graph_file_degrades_gracefully(self):
        vault = MarkdownVault(ROOT / "vault")
        builder = ContextBuilder(vault, KnowledgeGraph(vault), GraphifyAdapter(), Path("/no/such/graph.json"))
        packet = builder.build("architecture")
        self.assertEqual(packet.graphify_matches, [])


if __name__ == "__main__":
    unittest.main()
