"""
04_load_qdrant.py

Read chunks_tagged.jsonl → embed with nomic-embed-text-v1.5 (via llama.cpp)
→ upsert into Qdrant (3 collections, local mode).
"""

import json
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

from config import (
    get_embeddings,
    retry_with_backoff,
    processing_pause,
    get_logger,
    CHUNKS_TAGGED_PATH,
    VECTORDB_DIR,
)

logger = get_logger("load_qdrant")

# ── Constants ────────────────────────────────────────────────────────

VECTOR_SIZE = 512  # nomic-embed-text-v1.5 Matryoshka-truncated dimension

COLLECTION_MAP = {
    "HISTORICAL_ACCOUNT": "historical_account",
    "TEACHING": "teaching",
    "ANALOGY": "analogy",
}

UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # RFC 4122 DNS namespace


# ── Helpers ──────────────────────────────────────────────────────────

def load_chunks() -> list[dict]:
    """Read all chunks from chunks_tagged.jsonl."""
    logger.info("Reading tagged chunks from %s", CHUNKS_TAGGED_PATH)
    chunks = []
    with open(CHUNKS_TAGGED_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chunks.append(json.loads(line))
    logger.info("Loaded %d chunks", len(chunks))
    return chunks


def ensure_collections(client: QdrantClient) -> None:
    """Create the 3 collections if they don't already exist."""
    existing = {c.name for c in client.get_collections().collections}
    for collection_name in COLLECTION_MAP.values():
        if collection_name not in existing:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created collection: %s", collection_name)
        else:
            logger.info("Collection already exists: %s", collection_name)


def build_payload(chunk: dict) -> dict:
    """Build the Qdrant payload from a chunk's metadata."""
    return {
        "text": chunk["text"],
        "context_prefix": chunk["context_prefix"],
        "chunk_type": chunk["chunk_type"],
        "chunk_id": chunk["chunk_id"],
        "brief_summary": chunk.get("brief_summary", ""),
        "chapter_ref": chunk["chapter_ref"],
        "personality": chunk["personality"],
        "emotional_state": chunk["emotional_state"],
        "problem_domain": chunk["problem_domain"],
        "anartha_tag": chunk["anartha_tag"],
        "yoga_solution": chunk["yoga_solution"],
        "guna_environment": chunk["guna_environment"],
        "section": chunk["section"],
    }


def chunk_id_to_uuid(chunk_id: str) -> str:
    """Deterministically convert a chunk_id string to a UUID string."""
    return str(uuid.uuid5(UUID_NAMESPACE, chunk_id))


@retry_with_backoff()
def embed_text(embeddings, text: str) -> list[float]:
    """Embed a single text using nomic-embed-text-v1.5 via llama.cpp."""
    vectors = embeddings.embed_documents([text])
    return vectors[0]


# ── Main pipeline ────────────────────────────────────────────────────

def main():
    logger.info("=== 04_load_qdrant: START ===")

    # 1. Load chunks
    chunks = load_chunks()
    if not chunks:
        logger.warning("No chunks found — nothing to embed.")
        return

    # 2. Initialize Qdrant in local mode
    VECTORDB_DIR.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(VECTORDB_DIR))
    logger.info("Qdrant client initialised (local mode) at %s", VECTORDB_DIR)

    # 3. Ensure collections exist
    ensure_collections(client)

    # 4. Initialize embeddings model
    embeddings = get_embeddings()

    # 5. Embed and upsert each chunk
    total = len(chunks)
    skipped = 0

    for idx, chunk in enumerate(chunks, start=1):
        chunk_type = chunk.get("chunk_type", "")
        collection_name = COLLECTION_MAP.get(chunk_type)

        if collection_name is None:
            logger.warning(
                "Chunk %d/%d (%s): unknown chunk_type '%s' — skipping",
                idx, total, chunk["chunk_id"], chunk_type,
            )
            skipped += 1
            continue

        # Combine context_prefix + text for embedding
        combined_text = f"{chunk['context_prefix']}\n\n{chunk['text']}"

        # Embed
        vector = embed_text(embeddings, combined_text)
        processing_pause()

        # Build point
        point_id = chunk_id_to_uuid(chunk["chunk_id"])
        payload = build_payload(chunk)

        point = PointStruct(
            id=point_id,
            vector=vector,
            payload=payload,
        )

        # Upsert into the correct collection
        client.upsert(
            collection_name=collection_name,
            points=[point],
        )

        print(f"Chunk {idx}/{total} embedded and stored in {collection_name}")
        logger.info(
            "Chunk %d/%d (%s) → %s",
            idx, total, chunk["chunk_id"], collection_name,
        )

    # 6. Print final collection sizes
    print("\n" + "=" * 60)
    print("QDRANT LOADING COMPLETE")
    print("=" * 60)
    for collection_name in COLLECTION_MAP.values():
        info = client.get_collection(collection_name)
        print(f"  {collection_name}: {info.points_count} points")
    if skipped:
        print(f"  Skipped (unknown chunk_type): {skipped}")
    print("=" * 60)

    # Close the client to flush writes
    client.close()
    logger.info("=== 04_load_qdrant: DONE ===")


if __name__ == "__main__":
    main()
