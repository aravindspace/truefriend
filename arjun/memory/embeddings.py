"""Memory embeddings — the same nomic stack as the Canon (§6.4.3, §16).

nomic-embed-text-v1.5 via llama-cpp-python in-process, Matryoshka-truncated
to 512 dims — one embedding space serves memory and Canon alike. Mirrors
the injection pipeline's recipe exactly (preprocessing/config.py); kept
self-contained so runtime never imports dev tooling.

Prefix note (verified 2026-07-17): langgraph's SqliteStore calls only
``embed_documents`` — for stored texts AND search queries — so asymmetric
``search_document:``/``search_query:`` prefixes cannot both apply. Memory
uses the symmetric ``search_document:`` prefix throughout: self-consistent,
and identical to how Canon chunks were embedded.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DIMS = 512  # Matryoshka truncation — first N dims are a valid embedding

_model = None


def _llama():
    """Load the GGUF model once per process."""
    global _model
    if _model is None:
        from llama_cpp import Llama

        path = Path(os.getenv("LLAMA_EMBEDDING_MODEL_PATH", "models/nomic-embed-text-v1.5.Q8_0.gguf"))
        if not path.is_absolute():
            path = REPO_ROOT / path
        _model = Llama(model_path=str(path), embedding=True, verbose=False, n_ctx=8192)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """The store's EmbeddingsFunc: list[str] → list[512-dim vectors]."""
    model = _llama()
    return [
        model.create_embedding(f"search_document: {text}")["data"][0]["embedding"][:DIMS]
        for text in texts
    ]


def embed_query(text: str) -> list[float]:
    """Asymmetric query embedding (``search_query:`` prefix) — for searching
    the Canon in Qdrant, whose chunks were embedded as documents. (The
    memory store stays symmetric; see the prefix note above.)"""
    return _llama().create_embedding(f"search_query: {text}")["data"][0]["embedding"][:DIMS]
