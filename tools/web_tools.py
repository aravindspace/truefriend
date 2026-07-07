"""Web search tools — DuckDuckGo search for the World Connector agent."""
import logging
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchResults

logger = logging.getLogger(__name__)

_search = DuckDuckGoSearchResults(max_results=5)


@tool
def web_search(query: str) -> str:
    """Search the web for current events and information related to the query.

    Use this tool to find modern-day examples, current events, or real-world
    situations that can be connected to Bhagavad Gita wisdom.

    Args:
        query: The search query about a current topic or event
    """
    try:
        results = _search.invoke(query)
    except Exception as e:
        logger.warning(f"Web search failed: {e}")
        return f"Web search failed: {e}"

    if not results:
        return "No web search results found."

    return str(results)
