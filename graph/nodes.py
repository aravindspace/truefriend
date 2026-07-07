"""LangGraph node wrappers — thin shells around agent functions.

Scholar, Recall, and World Connector nodes embed ReAct sub-graphs
that autonomously reason over tools (KuzuDB, ChromaDB, DuckDuckGo).
Supervisor respond is also a ReAct agent with user management tools.
"""
import logging
from agents.supervisor import classify_intent, synthesize_response
from agents.scholar import scholar_search
from agents.world_connector import world_search
from agents.recall_agent import recall_search
from agents.memory_keeper import process_memory
from llm import create_llm
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


async def supervisor_classify_node(state: dict) -> dict:
    """Classify user intent."""
    return await classify_intent(state)


async def scholar_node(state: dict) -> dict:
    """Gita Scholar — query knowledge graph + study notes."""
    return await scholar_search(state)


async def recall_node(state: dict) -> dict:
    """Recall Agent — search conversation memory."""
    return await recall_search(state)


async def world_connector_node(state: dict) -> dict:
    """World Connector — search web, map to Gita."""
    return await world_search(state)


async def supervisor_respond_node(state: dict) -> dict:
    """Supervisor — merge agent responses into final answer.
    
    Also handles user identification via ReAct tools (save_user_name,
    lookup_user_profile) when user_name is not yet known.
    """
    return await synthesize_response(state)


async def memory_keeper_node(state: dict) -> dict:
    """Memory Keeper — extract learnings, store in ChromaDB + user profile."""
    return await process_memory(state)


async def summarize_history_node(state: dict) -> dict:
    """Compress old conversation history when it gets long."""
    history = state.get("conversation_history", [])
    
    if len(history) < 10:
        return {}
    
    # Keep last 10, summarize older ones
    old_messages = history[:-10]
    kept_messages = history[-10:]
    
    if not old_messages:
        return {}
    
    # Summarize old messages
    old_text = "\n".join(
        f"{m.get('role', '?')}: {m.get('content', '')}"
        for m in old_messages
    )
    
    existing_summary = state.get("conversation_summary", "")
    
    llm = create_llm("supervisor_classify")  # Lightweight model
    messages = [
        SystemMessage(content="Summarize this conversation concisely, preserving key topics, emotions, and decisions."),
        HumanMessage(content=f"Previous summary: {existing_summary}\n\nNew messages to summarize:\n{old_text}"),
    ]
    
    response = await llm.ainvoke(messages)
    
    return {
        "conversation_summary": response.content,
        "conversation_history": kept_messages,
    }
