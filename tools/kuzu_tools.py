"""KuzuDB tools — Bhagavad Gita knowledge graph queries.

These tools wrap KuzuStore methods for use by the Scholar ReAct agent.
KuzuDB is read-only; no write operations are exposed.
"""
import logging
from langchain_core.tools import tool

from stores import KuzuStore

logger = logging.getLogger(__name__)


@tool
def search_gita_concepts(query: str) -> str:
    """Search the Bhagavad Gita knowledge graph for concepts matching the query.

    Use this tool when the user asks about Gita philosophy, concepts like dharma,
    karma, yoga, detachment, etc. Returns concept names, descriptions, related
    concepts, analogies, and verse references.

    Args:
        query: A search term or concept name (e.g. 'karma', 'detachment', 'duty')
    """
    try:
        kuzu = KuzuStore()
        # Split query into individual terms for broader matching
        terms = [t.strip() for t in query.lower().split() if len(t.strip()) > 2]
        if not terms:
            terms = [query.strip()]
        results = kuzu.query_concepts(terms)
        kuzu.close()
    except Exception as e:
        logger.warning(f"KuzuDB concept search failed: {e}")
        return f"Knowledge graph search failed: {e}"

    if not results:
        return "No matching concepts found in the Gita knowledge graph."

    parts = []
    for r in results:
        part = f"Concept: {r['concept']}\n"
        part += f"Description: {r.get('description', 'N/A')}\n"
        if r.get('related_concepts'):
            part += f"Related: {', '.join(r['related_concepts'])}\n"
        if r.get('analogies'):
            part += f"Analogies: {', '.join(r['analogies'])}\n"
        if r.get('verses'):
            part += f"Verses: {', '.join(r['verses'])}\n"
        parts.append(part)

    return "\n".join(parts)


@tool
def get_verse(chapter: int, verse: int) -> str:
    """Get a specific Bhagavad Gita verse by chapter and verse number.

    Use this tool when the user asks about a specific verse (e.g. BG 2.47)
    or when you want to cite a verse to support your response.

    Args:
        chapter: Chapter number (1-18)
        verse: Verse number within the chapter
    """
    try:
        kuzu = KuzuStore()
        result = kuzu.query_by_verse(chapter, verse)
        kuzu.close()
    except Exception as e:
        logger.warning(f"KuzuDB verse query failed: {e}")
        return f"Verse lookup failed: {e}"

    if not result:
        return f"Verse BG {chapter}.{verse} not found in the knowledge graph."

    output = f"BG {chapter}.{verse}\n"
    if result.get('text'):
        output += f"Sanskrit: {result['text']}\n"
    if result.get('translation'):
        output += f"Translation: {result['translation']}\n"
    if result.get('concepts'):
        output += f"Connected concepts: {', '.join(result['concepts'])}\n"

    return output


@tool
def list_all_concepts() -> str:
    """List all concept names available in the Gita knowledge graph.

    Use this tool when you want to discover what topics are covered in the
    knowledge graph, or when the user's query doesn't match any specific concept
    and you want to find the closest available topic.
    """
    try:
        kuzu = KuzuStore()
        concepts = kuzu.get_all_concepts()
        kuzu.close()
    except Exception as e:
        logger.warning(f"KuzuDB list concepts failed: {e}")
        return f"Failed to list concepts: {e}"

    if not concepts:
        return "No concepts found in the knowledge graph."

    return f"Available concepts ({len(concepts)}): {', '.join(concepts)}"
