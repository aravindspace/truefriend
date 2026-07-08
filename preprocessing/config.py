"""
Shared configuration for the Gita RAG preprocessing pipeline.

Provides:
    - Azure OpenAI LLM client (o4-mini deployment)
    - nomic-embed-text-v1.5 embedding via local llama.cpp server
    - Project paths
    - Retry-with-backoff decorator for rate-limit handling
    - Processing pause between sequential LLM calls
"""

import os
import time
import functools
import logging
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
VECTORDB_DIR = PROJECT_ROOT / "vectordb"
GRAPHDB_DIR = PROJECT_ROOT / "graphdb" / "gita_graph"
ROUTING_DIR = PROJECT_ROOT / "routing"

# Source files
GITA_TEXT_PATH = DATA_RAW / "gita_text.txt"
MINISTRUCTURE_PATH = DATA_RAW / "ministructure.txt"
KURU_FAMILY_PATH = DATA_RAW / "kuru_family.txt"

# Intermediate outputs
CHUNKS_RAW_PATH = DATA_PROCESSED / "chunks_raw.jsonl"
CHUNKS_TAGGED_PATH = DATA_PROCESSED / "chunks_tagged.jsonl"

# Final outputs
ROUTING_JSON_PATH = ROUTING_DIR / "ministructure.json"

# Ensure directories exist
for d in (DATA_PROCESSED, VECTORDB_DIR, GRAPHDB_DIR.parent, ROUTING_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# LLM client — Azure OpenAI (o4-mini reasoning model)
# ---------------------------------------------------------------------------
def get_azure_llm() -> AzureChatOpenAI:
    """
    Return an AzureChatOpenAI instance configured from .env.

    NOTE: o4-mini is a reasoning model — it does NOT support the
    ``temperature`` parameter.  We omit it entirely so the API
    does not reject the request.
    """
    return AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
    )


# ---------------------------------------------------------------------------
# Embedding client — nomic-embed-text-v1.5 via llama-cpp-python (in-process)
# ---------------------------------------------------------------------------
LLAMA_EMBEDDING_MODEL_PATH = os.getenv(
    "LLAMA_EMBEDDING_MODEL_PATH", "models/nomic-embed-text-v1.5.Q8_0.gguf"
)
NOMIC_EMBEDDING_DIMS = 512  # Matryoshka truncation (supported: 64, 128, 256, 512, 768)


def _resolve_model_path() -> Path:
    """Return the absolute path to the GGUF model file."""
    p = Path(LLAMA_EMBEDDING_MODEL_PATH)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p


class LlamaCppEmbeddings:
    """
    In-process embedding via llama-cpp-python's Llama class, serving
    nomic-embed-text-v1.5.

    - Prepends the required nomic task prefixes automatically
      (``search_document:`` for indexing, ``search_query:`` for retrieval).
    - Truncates the 768-dim output to ``dims`` using Matryoshka
      representation learning — the first N dimensions of the full output
      are a valid N-dimensional embedding.
    - No server needed — model runs directly in the Python process.
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        dims: int = NOMIC_EMBEDDING_DIMS,
    ):
        from llama_cpp import Llama

        resolved = Path(model_path) if model_path else _resolve_model_path()
        self._logger = logging.getLogger("llama_embed")
        self._logger.info("Loading embedding model: %s", resolved)

        self.model = Llama(
            model_path=str(resolved),
            embedding=True,
            verbose=False,
            n_ctx=8192,
        )
        self.dims = dims
        self._logger.info("Embedding model loaded (Matryoshka %d-dim)", dims)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed one or more documents (prefixed with ``search_document:``)."""
        results = []
        for text in texts:
            output = self.model.create_embedding(f"search_document: {text}")
            vec = output["data"][0]["embedding"][: self.dims]
            results.append(vec)
        return results

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query (prefixed with ``search_query:``)."""
        output = self.model.create_embedding(f"search_query: {text}")
        return output["data"][0]["embedding"][: self.dims]


# Singleton — load model once and reuse across the pipeline
_embeddings_instance: LlamaCppEmbeddings | None = None


def get_embeddings() -> LlamaCppEmbeddings:
    """Return a shared nomic-embed-text-v1.5 embedding instance (loads model on first call)."""
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = LlamaCppEmbeddings()
    return _embeddings_instance


# ---------------------------------------------------------------------------
# Retry with exponential back-off
# ---------------------------------------------------------------------------
def retry_with_backoff(
    max_retries: int = 6,
    base_delay: float = 2.0,
    max_delay: float = 120.0,
):
    """
    Decorator: retry on rate-limit (429) and transient errors with
    exponential back-off.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger("retry")
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    err = str(exc).lower()
                    retryable = any(
                        kw in err
                        for kw in [
                            "429",
                            "rate limit",
                            "rate_limit",
                            "too many requests",
                            "timeout",
                            "timed out",
                            "503",
                            "502",
                            "connection",
                            "server error",
                        ]
                    )
                    if not retryable or attempt == max_retries:
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        "Attempt %d/%d failed: %s — retrying in %.1fs …",
                        attempt + 1,
                        max_retries,
                        exc,
                        delay,
                    )
                    time.sleep(delay)

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Processing pause (configurable via env)
# ---------------------------------------------------------------------------
PROCESSING_DELAY = float(os.getenv("PROCESSING_DELAY", "1.0"))


def processing_pause():
    """Sleep between sequential LLM / embedding calls to stay within rate limits."""
    time.sleep(PROCESSING_DELAY)
