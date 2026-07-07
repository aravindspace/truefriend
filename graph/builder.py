"""LangGraph graph construction — wires nodes + edges into compiled graph.

Scholar, Recall, and World Connector are ReAct agents with tool bindings.
Supervisor respond is a ReAct agent with user management tools.
Supervisor classify remains a simple prompt-and-respond function.
Memory Keeper remains a simple prompt-and-respond function.
"""
import logging
from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    supervisor_classify_node,
    scholar_node,
    recall_node,
    world_connector_node,
    supervisor_respond_node,
    memory_keeper_node,
    summarize_history_node,
)

logger = logging.getLogger(__name__)


def build_graph():
    """Build and compile the TrueFriend multi-agent graph.

    Topology (linear with conditional skips):
        supervisor_classify
            → maybe_recall → maybe_scholar → maybe_world
        → supervisor_respond (ReAct w/ user tools) → memory_keeper → summarize_history → END

    Each maybe_* node checks intent and runs/skips accordingly:
        REPEAT  → recall only
        DEEPEN  → recall + scholar
        NEW     → scholar + world_connector
        CRISIS  → all three

    User identification is handled by supervisor_respond via ReAct tools
    (save_user_name, lookup_user_profile) — no separate identify_user node.
    """
    # Conditional wrappers — each checks intent before running
    async def maybe_recall(state: dict) -> dict:
        """Run recall if intent requires it."""
        intent = state.get("intent", "")
        if intent in ("REPEAT", "DEEPEN", "CRISIS"):
            return await recall_node(state)
        return {}

    async def maybe_scholar(state: dict) -> dict:
        """Run scholar if intent requires it."""
        intent = state.get("intent", "")
        if intent in ("DEEPEN", "NEW", "CRISIS"):
            return await scholar_node(state)
        return {}

    async def maybe_world(state: dict) -> dict:
        """Run world connector if intent requires it."""
        intent = state.get("intent", "")
        if intent in ("NEW", "CRISIS"):
            return await world_connector_node(state)
        return {}

    graph = StateGraph(AgentState)

    # ── Nodes ──
    graph.add_node("supervisor_classify", supervisor_classify_node)
    graph.add_node("maybe_recall", maybe_recall)
    graph.add_node("maybe_scholar", maybe_scholar)
    graph.add_node("maybe_world", maybe_world)
    graph.add_node("supervisor_respond", supervisor_respond_node)
    graph.add_node("memory_keeper", memory_keeper_node)
    graph.add_node("summarize_history", summarize_history_node)

    # ── Linear pipeline with conditional skips ──
    graph.set_entry_point("supervisor_classify")
    graph.add_edge("supervisor_classify", "maybe_recall")
    graph.add_edge("maybe_recall", "maybe_scholar")
    graph.add_edge("maybe_scholar", "maybe_world")
    graph.add_edge("maybe_world", "supervisor_respond")
    graph.add_edge("supervisor_respond", "memory_keeper")
    graph.add_edge("memory_keeper", "summarize_history")
    graph.add_edge("summarize_history", END)

    compiled = graph.compile()
    logger.info("TrueFriend graph compiled successfully")
    return compiled
