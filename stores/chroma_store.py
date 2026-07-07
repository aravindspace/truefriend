"""ChromaDB vector store — conversation memory."""
import logging
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class ChromaStore:
    """Embedded vector store for conversation memories.
    
    Stores embedded Q&A summaries with metadata (user, concepts, emotion, timestamp).
    Grows with every conversation via Memory Keeper.
    Read by Recall Agent for semantic similarity search.
    """

    def __init__(
        self,
        db_path: str | Path = "data/chroma_db",
        collection_name: str = "truefriend_memory",
    ):
        self._db_path = Path(db_path)
        self._db_path.mkdir(parents=True, exist_ok=True)
        
        self._client = chromadb.PersistentClient(
            path=str(self._db_path),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"ChromaDB initialized at {self._db_path}, "
            f"collection='{collection_name}', "
            f"docs={self._collection.count()}"
        )

    def add_memory(
        self,
        memory_id: str,
        summary: str,
        metadata: dict[str, Any],
    ) -> None:
        """Store a conversation summary with metadata.
        
        Args:
            memory_id: Unique ID (e.g., uuid or timestamp-based)
            summary: Concise Q&A summary text
            metadata: {user, concepts, emotion, timestamp, ...}
                      Note: ChromaDB metadata values must be str, int, float, or bool.
                      Lists should be joined as comma-separated strings.
        """
        # ChromaDB requires metadata values to be primitives
        clean_metadata = {}
        for k, v in metadata.items():
            if isinstance(v, list):
                clean_metadata[k] = ",".join(str(i) for i in v)
            elif isinstance(v, (str, int, float, bool)):
                clean_metadata[k] = v
            else:
                clean_metadata[k] = str(v)

        self._collection.add(
            ids=[memory_id],
            documents=[summary],
            metadatas=[clean_metadata],
        )
        logger.info(f"Stored memory {memory_id} for user={metadata.get('user', '?')}")

    def search_memories(
        self,
        query: str,
        user_name: str | None = None,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Semantic search over conversation memories.
        
        Returns list of {id, summary, metadata, distance} sorted by relevance.
        """
        where_filter = None
        if user_name:
            where_filter = {"user": user_name}

        results = self._collection.query(
            query_texts=[query],
            n_results=max_results,
            where=where_filter,
        )

        memories = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                memories.append({
                    "id": results["ids"][0][i],
                    "summary": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None,
                })
        return memories

    def count(self) -> int:
        """Total memories stored."""
        return self._collection.count()
