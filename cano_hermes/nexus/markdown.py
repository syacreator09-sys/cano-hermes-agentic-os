from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


WIKILINK = re.compile(r"\[\[([^\]|#]+)")


@dataclass(frozen=True)
class Note:
    id: str
    title: str
    path: str
    content: str
    links: tuple[str, ...]


class MarkdownVault:
    def __init__(self, root: Path | str = "vault") -> None:
        self.root = Path(root)

    def index(self) -> dict[str, Note]:
        notes: dict[str, Note] = {}
        if not self.root.exists():
            return notes
        for path in sorted(self.root.rglob("*.md")):
            content = path.read_text(encoding="utf-8", errors="replace")
            rel = path.relative_to(self.root).as_posix()
            note_id = rel.removesuffix(".md")
            title = next((line.removeprefix("# ").strip() for line in content.splitlines() if line.startswith("# ")), path.stem)
            links = tuple(dict.fromkeys(item.strip() for item in WIKILINK.findall(content)))
            notes[note_id] = Note(note_id, title, rel, content, links)
        return notes

    def search(self, query: str, limit: int = 8) -> list[Note]:
        terms = [term.casefold() for term in query.split() if term]
        scored: list[tuple[int, Note]] = []
        for note in self.index().values():
            haystack = f"{note.title}\n{note.content}".casefold()
            score = sum(haystack.count(term) for term in terms)
            if score:
                scored.append((score, note))
        return [note for _, note in sorted(scored, key=lambda item: (-item[0], item[1].title))[:limit]]
