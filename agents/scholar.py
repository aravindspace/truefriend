"""Gita Scholar agent — ReAct agent with Gita knowledge tools.

Tools: search_gita_concepts, get_verse, list_all_concepts, search_study_notes
Writes to: scholar_response in AgentState
"""
import logging
from pathlib import Path

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from llm import create_llm
from tools.kuzu_tools import search_gita_concepts, get_verse, list_all_concepts
from tools.note_tools import search_study_notes

logger = logging.getLogger(__name__)

# Load system prompt once
_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "scholar.txt"

# Tools available to the Scholar agent
SCHOLAR_TOOLS = [search_gita_concepts, get_verse, list_all_concepts, search_study_notes]


def build_scholar_agent():
    """Build and compile the Scholar ReAct agent."""
    llm = create_llm("scholar")
    system_prompt = _PROMPT_PATH.read_text()
    return create_react_agent(
        model=llm,
        tools=SCHOLAR_TOOLS,
        prompt=system_prompt,
    )


# Compile once at module level for reuse
_scholar_agent = None


def _get_agent():
    """Lazy-load the compiled agent."""
    global _scholar_agent
    if _scholar_agent is None:
        _scholar_agent = build_scholar_agent()
    return _scholar_agent


async def scholar_search(state: dict) -> dict:
    """Query Gita knowledge using ReAct reasoning loop.

    The agent autonomously decides which tools to call:
    - search_gita_concepts for concept queries
    - get_verse for specific verse lookups
    - list_all_concepts to discover topics
    - search_study_notes for detailed explanations
    """
    user_input = state.get("user_input", "")
    if not user_input:
        return {"scholar_response": None}

    agent = _get_agent()

    try:
        result = await agent.ainvoke({
            "messages": [HumanMessage(content=user_input)],
        })

        # Extract the final response from the agent's message history
        final_message = result["messages"][-1]
        response_text = final_message.content

        if not response_text or response_text.strip().lower() in ["", "none", "empty"]:
            return {"scholar_response": None}

        logger.info("Scholar ReAct agent completed reasoning")
        return {"scholar_response": response_text}

    except Exception as e:
        logger.warning(f"Scholar agent failed: {e}")
        return {"scholar_response": None}
