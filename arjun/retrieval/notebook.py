"""Arjun's Notebook search — §8.2 step 4: his OWN learned layer.

Plain markdown notes under arjun_action/notebook/ (written by svadhyaya,
P2.3). Results are tagged ``source="notebook"`` — always cited as Arjun's
own understanding, never as Canon. Simple term-overlap ranking: the
Notebook is small by design; no index to maintain.
"""

import re
from pathlib import Path

from arjun.graph.state import RetrievedChunk

NOTEBOOK_DIR = Path(__file__).resolve().parents[2] / "arjun_action" / "notebook"


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zA-Z]{3,}", text.lower())}


def notebook_search(query: str, limit: int = 3) -> list[RetrievedChunk]:
    """Rank notes by query-term overlap; empty Notebook → [] (ladder, §5)."""
    query_tokens = _tokens(query)
    if not query_tokens:
        return []
    scored = []
    for path in sorted(NOTEBOOK_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        overlap = len(query_tokens & _tokens(text))
        if overlap:
            scored.append((overlap, path.stem, text))
    scored.sort(reverse=True)
    return [
        RetrievedChunk(chunk_id=f"notebook:{stem}", text=text, source="notebook")
        for _, stem, text in scored[:limit]
    ]
