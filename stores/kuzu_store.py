"""KuzuDB graph store — sacred Gita knowledge (read-only at runtime)."""
import logging
from pathlib import Path
from typing import Any

import kuzu

logger = logging.getLogger(__name__)


class KuzuStore:
    """Embedded graph DB for Gita entities, relationships, analogies.

    Sacred source = read-only at runtime. Data is loaded externally.
    All write operations are blocked at the database level.
    """

    def __init__(self, db_path: str | Path = "data/kuzu_db"):
        self._db_path = Path(db_path)
        if not self._db_path.exists():
            raise FileNotFoundError(
                f"KuzuDB not found at {self._db_path}. "
                "Copy your pre-built KùzuDB data into this path before starting."
            )
        self._db = kuzu.Database(str(self._db_path), read_only=True)
        self._conn = kuzu.Connection(self._db)
        logger.info(f"KuzuDB connected (READ-ONLY) at {self._db_path}")

    def query_concepts(self, query_terms: list[str], max_hops: int = 2) -> list[dict[str, Any]]:
        """Find concepts matching query terms and their connections."""
        results = []
        for term in query_terms:
            try:
                # Search concepts by name (case-insensitive partial match)
                res = self._conn.execute("""
                    MATCH (c:Concept)
                    WHERE lower(c.name) CONTAINS lower($term)
                    OPTIONAL MATCH (c)-[:RELATES_TO*1..2]->(related:Concept)
                    OPTIONAL MATCH (c)-[:EXPLAINED_VIA]->(a:Analogy)
                    OPTIONAL MATCH (c)-[:REFERENCED_IN]->(v:Verse)
                    RETURN c.name AS concept,
                           c.description AS description,
                           collect(DISTINCT related.name) AS related_concepts,
                           collect(DISTINCT a.title) AS analogies,
                           collect(DISTINCT v.id) AS verses
                """, parameters={"term": term})
                
                while res.has_next():
                    row = res.get_next()
                    results.append({
                        "concept": row[0],
                        "description": row[1],
                        "related_concepts": row[2],
                        "analogies": row[3],
                        "verses": row[4],
                    })
            except Exception as e:
                logger.warning(f"Query failed for term '{term}': {e}")
        return results

    def query_by_verse(self, chapter: int, verse: int) -> dict[str, Any] | None:
        """Get a specific verse with connected concepts."""
        try:
            verse_id = f"BG_{chapter}_{verse}"
            res = self._conn.execute("""
                MATCH (v:Verse {id: $vid})
                OPTIONAL MATCH (c:Concept)-[:REFERENCED_IN]->(v)
                RETURN v.text AS text,
                       v.translation AS translation,
                       collect(c.name) AS concepts
            """, parameters={"vid": verse_id})
            
            if res.has_next():
                row = res.get_next()
                return {
                    "text": row[0],
                    "translation": row[1],
                    "concepts": row[2],
                }
        except Exception as e:
            logger.warning(f"Verse query failed: {e}")
        return None

    def get_all_concepts(self) -> list[str]:
        """Get all concept names — used by Gita Learner."""
        try:
            res = self._conn.execute("MATCH (c:Concept) RETURN c.name")
            concepts = []
            while res.has_next():
                concepts.append(res.get_next()[0])
            return concepts
        except Exception as e:
            logger.warning(f"Failed to list concepts: {e}")
            return []

    def close(self) -> None:
        """Close DB connection."""
        # KuzuDB handles cleanup on garbage collection
        logger.info("KuzuDB connection closed")
