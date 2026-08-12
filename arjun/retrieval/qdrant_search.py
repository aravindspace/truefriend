"""Qdrant metadata-filtered vector search — §8.2 step 3: fill gaps.

Uses the current ``query_points`` API (legacy ``search`` is deprecated).
Payload metadata fields are lists; a ``MatchValue`` condition on a list
field matches membership. Chunk text passes through verbatim (§5).
"""

import logging
from pathlib import Path
from typing import Optional

from arjun.graph.state import RetrievedChunk
from arjun.memory.embeddings import embed_query

VECTORDB_PATH = Path(__file__).resolve().parents[2] / "vectordb"

logger = logging.getLogger("arjun.retrieval")

COLLECTIONS = ("historical_account", "teaching", "analogy")
FILTER_KEYS = ("anartha_tag", "guna_environment", "yoga_solution", "section", "personality")

_client = None


def _qdrant():
    global _client
    if _client is None:
        from qdrant_client import QdrantClient

        _client = QdrantClient(path=str(VECTORDB_PATH))
    return _client


def build_filter(filters: Optional[dict], limbic_bias: Optional[dict]):
    """Merge explicit filters with the limbic bias (§8.2-3: grief →
    Moha/Tamas). Explicit filters win; unknown keys are dropped. Returns a
    qdrant Filter or None. Pure — unit-testable without a client."""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    merged = {k: v for k, v in (filters or {}).items() if k in FILTER_KEYS}
    for key, value in (limbic_bias or {}).items():
        if key in FILTER_KEYS and key not in merged:
            merged[key] = value
    if not merged:
        return None
    return Filter(
        must=[FieldCondition(key=k, match=MatchValue(value=v)) for k, v in merged.items()]
    )


def qdrant_search(
    query: str,
    collection: str,
    filters: Optional[dict] = None,
    limbic_bias: Optional[dict] = None,
    limit: int = 5,
) -> list[RetrievedChunk]:
    """Semantic search over one Canon collection. Bad collection or a
    failure → [] (the ladder descends, §5)."""
    if collection not in COLLECTIONS:
        return []
    try:
        response = _qdrant().query_points(
            collection_name=collection,
            query=embed_query(query),
            query_filter=build_filter(filters, limbic_bias),
            limit=limit,
            with_payload=True,
        )
        return [
            RetrievedChunk(
                chunk_id=point.payload["chunk_id"],
                text=point.payload["text"],  # verbatim — never rephrased
                source="canon",
                chunk_type=point.payload.get("chunk_type"),
            )
            for point in response.points
        ]
    except Exception as exc:
        logger.warning("qdrant search failed (%s) — empty result", exc)
        return []
