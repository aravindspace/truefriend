"""World Connector agent — ReAct agent that bridges current events to Gita wisdom.

Tools: web_search
Writes to: world_response in AgentState
"""
import logging
from pathlib import Path

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from llm import create_llm
from tools.web_tools import web_search

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "world_connector.txt"

WORLD_TOOLS = [web_search]

_world_agent = None


def _get_agent():
    """Lazy-load the compiled agent."""
    global _world_agent
    if _world_agent is None:
        llm = create_llm("world_connector")
        system_prompt = _PROMPT_PATH.read_text()
        _world_agent = create_react_agent(
            model=llm,
            tools=WORLD_TOOLS,
            prompt=system_prompt,
        )
    return _world_agent


async def world_search(state: dict) -> dict:
    """Search web and map findings to Gita wisdom using ReAct reasoning.

    The agent autonomously decides what to search for and how to
    connect the results to Bhagavad Gita teachings.
    """
    user_input = state.get("user_input", "")
    if not user_input:
        return {"world_response": None}

    agent = _get_agent()

    try:
        result = await agent.ainvoke({
            "messages": [HumanMessage(content=user_input)],
        })

        final_message = result["messages"][-1]
        response_text = final_message.content

        if not response_text or response_text.strip().lower() in ["", "none", "empty"]:
            return {"world_response": None}

        logger.info("World Connector ReAct agent completed")
        return {"world_response": response_text}

    except Exception as e:
        logger.warning(f"World Connector agent failed: {e}")
        return {"world_response": None}
