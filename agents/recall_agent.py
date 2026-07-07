"""Recall Agent — ReAct agent that searches conversation memory.

Tools: search_conversation_memory
Writes to: recall_response in AgentState
"""
import logging
from pathlib import Path

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from llm import create_llm
from tools.memory_tools import search_conversation_memory

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "recall.txt"

RECALL_TOOLS = [search_conversation_memory]

_recall_agent = None


def _get_agent():
    """Lazy-load the compiled agent."""
    global _recall_agent
    if _recall_agent is None:
        llm = create_llm("recall")
        system_prompt = _PROMPT_PATH.read_text()
        _recall_agent = create_react_agent(
            model=llm,
            tools=RECALL_TOOLS,
            prompt=system_prompt,
        )
    return _recall_agent


async def recall_search(state: dict) -> dict:
    """Search conversation memory using ReAct reasoning loop.

    The agent decides whether and how to search past conversations,
    evaluating relevance of results autonomously.
    """
    user_input = state.get("user_input", "")
    user_name = state.get("user_name", "")

    if not user_input:
        return {"recall_response": None}

    agent = _get_agent()

    # Include user_name in the query so the agent can pass it to the tool
    query_with_context = user_input
    if user_name:
        query_with_context = (
            f"Search memories for user '{user_name}'. Their question: {user_input}"
        )

    try:
        result = await agent.ainvoke({
            "messages": [HumanMessage(content=query_with_context)],
        })

        final_message = result["messages"][-1]
        response_text = final_message.content

        if not response_text or response_text.strip().lower() in [
            "", "none", "empty", "no relevant memories",
        ]:
            return {"recall_response": None}

        logger.info("Recall ReAct agent found relevant memories")
        return {"recall_response": response_text}

    except Exception as e:
        logger.warning(f"Recall agent failed: {e}")
        return {"recall_response": None}
