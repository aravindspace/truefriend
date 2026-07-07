"""Memory tools — ChromaDB conversation memory search.

Wraps ChromaStore.search_memories for use by the Recall ReAct agent.
"""
import logging
from langchain_core.tools import tool

from stores import ChromaStore

logger = logging.getLogger(__name__)


@tool
def search_conversation_memory(query: str, user_name: str = "") -> str:
    """Search past conversation memories for relevant previous discussions.

    Use this tool to check if the user has asked about this topic before.
    Returns summaries of past conversations ranked by semantic relevance.

    Args:
        query: The search query — what the user is asking about now
        user_name: The user's name to filter memories (leave empty for all users)
    """
    try:
        chroma = ChromaStore()
        memories = chroma.search_memories(
            query=query,
            user_name=user_name if user_name else None,
            max_results=5,
        )
    except Exception as e:
        logger.warning(f"ChromaDB search failed: {e}")
        return f"Memory search failed: {e}"

    if not memories:
        return "No relevant past conversations found."

    parts = []
    for i, mem in enumerate(memories, 1):
        part = f"Memory {i} (distance: {mem.get('distance', '?'):.3f}):\n"
        part += f"  Summary: {mem['summary']}\n"
        meta = mem.get('metadata', {})
        if meta.get('concepts'):
            part += f"  Concepts: {meta['concepts']}\n"
        if meta.get('emotion'):
            part += f"  Emotion: {meta['emotion']}\n"
        parts.append(part)

    return "\n".join(parts)
