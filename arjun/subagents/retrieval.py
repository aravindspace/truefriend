"""Retrieval subagent — the VECTOR scholar (Qdrant only).

Owner decision 2026-07-18 (ADR 0006): the two Canon sources are split across
two agents. The **routing** subagent owns the graph (Kuzu); THIS agent owns the
vector store and has no graph access at all — no Kuzu import, no templates.
Both hand their findings to the Frontal Lobe, which alone speaks.

Deterministic: metadata-filtered semantic search over the three Canon
collections, plus Arjun's own Notebook. Chunk text is verbatim (§5).
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from arjun.graph.state import RetrievedChunk
from arjun.retrieval.notebook import notebook_search
from arjun.retrieval.qdrant_search import qdrant_search

logger = logging.getLogger("arjun.subagents")

MAX_INCIDENTS, MAX_TEACHINGS, MAX_ANALOGIES, MAX_NOTES = 2, 3, 2, 2


class RetrievalResult(BaseModel):
    """Structured results for frontal_compose (§6.3: never prose)."""

    found: bool = False
    chunks: list[RetrievedChunk] = Field(default_factory=list)


def vector_retrieve(query: str, limbic_bias: Optional[dict] = None) -> RetrievalResult:
    """Semantic search across the Canon collections + Notebook. The limbic bias
    (e.g. grief → Moha/Tamas, §8.2-3) narrows the metadata filters."""
    limbic_bias = limbic_bias or {}
    collected: dict[str, RetrievedChunk] = {}

    def add(chunk: RetrievedChunk) -> None:
        collected.setdefault(chunk.chunk_id, chunk)

    for collection, limit in (
        ("historical_account", MAX_INCIDENTS),
        ("teaching", MAX_TEACHINGS),
        ("analogy", MAX_ANALOGIES),
    ):
        for chunk in qdrant_search(query, collection, limbic_bias=limbic_bias, limit=limit):
            add(chunk)

    for chunk in notebook_search(query, limit=MAX_NOTES):
        add(chunk)  # Arjun's OWN understanding, tagged source="notebook"

    chunks = list(collected.values())
    return RetrievalResult(found=bool(chunks), chunks=chunks)


def run_retrieval(
    query: str,
    problem_domain: str = "",  # kept for call-site stability; unused (graph moved out)
    limbic_bias: Optional[dict] = None,
    model=None,
    summarizer_model=None,
    fallback_models=None,
) -> RetrievalResult:
    """The retrieval entry point (§20.2). Vector store only."""
    return vector_retrieve(query, limbic_bias)
