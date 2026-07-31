from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from .markdown import MarkdownVault


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    kind: str = "wikilink"


class KnowledgeGraph:
    def __init__(self, vault: MarkdownVault) -> None:
        self.vault = vault

    def edges(self) -> list[Edge]:
        notes = self.vault.index()
        title_map = {note.title.casefold(): note.id for note in notes.values()}
        id_map = {note.id.casefold(): note.id for note in notes.values()}
        result: list[Edge] = []
        for note in notes.values():
            for link in note.links:
                target = id_map.get(link.casefold()) or title_map.get(link.casefold()) or link
                result.append(Edge(note.id, target))
        return result

    def neighborhood(self, node: str, depth: int = 1, limit: int = 30) -> list[str]:
        adjacency: dict[str, set[str]] = defaultdict(set)
        for edge in self.edges():
            adjacency[edge.source].add(edge.target)
            adjacency[edge.target].add(edge.source)
        visited = {node}
        queue = deque([(node, 0)])
        while queue and len(visited) < limit:
            current, level = queue.popleft()
            if level >= depth:
                continue
            for neighbor in sorted(adjacency[current]):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, level + 1))
        visited.discard(node)
        return sorted(visited)
