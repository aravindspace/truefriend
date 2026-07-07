"""LangGraph conditional edge logic — routes by intent.

PROTOTYPE — answering: does intent-based routing dispatch correct agents?
"""
import logging

logger = logging.getLogger(__name__)


def route_by_intent(state: dict) -> str:
    """Route to agent nodes based on classified intent.
    
    REPEAT  -> recall only (fast path)
    DEEPEN  -> recall + scholar (parallel)
    NEW     -> scholar + world_connector (parallel)
    CRISIS  -> all three agents (parallel)
    """
    intent = state.get("intent", "NEW")
    
    routes = {
        "REPEAT": "recall",
        "DEEPEN": "parallel_recall_scholar",
        "NEW": "parallel_scholar_world",
        "CRISIS": "parallel_all",
    }
    
    route = routes.get(intent, "scholar")
    logger.info(f"Routing intent={intent} -> {route}")
    return route


def should_ask_name(state: dict) -> str:
    """Check if we need to ask user's name before proceeding."""
    user_name = state.get("user_name", "")
    if not user_name:
        return "ask_name"
    return "classify"
