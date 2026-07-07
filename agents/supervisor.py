"""Supervisor agent — orchestrator + user-facing conversationalist.

Two calls per turn:
1. classify_intent: Simple LLM call → REPEAT/DEEPEN/NEW/CRISIS
2. synthesize_response: ReAct agent with user tools → final friendly answer
"""
import logging
from pathlib import Path
from langchain_core.messages import HumanMessage, SystemMessage

from langgraph.prebuilt import create_react_agent

from llm import create_llm
from tools.user_tools import save_user_name, lookup_user_profile

logger = logging.getLogger(__name__)

# User management tools for the Supervisor ReAct agent
SUPERVISOR_TOOLS = [save_user_name, lookup_user_profile]


def _load_prompt(prompt_name: str) -> str:
    """Load system prompt template from prompts/ directory."""
    prompt_path = Path(__file__).parent.parent / "prompts" / f"{prompt_name}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
    return prompt_path.read_text()


async def classify_intent(state: dict) -> dict:
    """Classify user intent into REPEAT/DEEPEN/NEW/CRISIS.

    Simple LLM call — no tools needed, just outputs one word.
    """
    llm = create_llm("supervisor_classify")
    system_prompt = _load_prompt("supervisor_classify")

    # Build context for classification
    context_parts = []
    if state.get("conversation_history"):
        recent = state["conversation_history"][-5:]  # Last 5 msgs for context
        context_parts.append("Recent conversation:\n" + "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in recent
        ))
    if state.get("conversation_summary"):
        context_parts.append(f"Earlier context: {state['conversation_summary']}")

    context = "\n\n".join(context_parts) if context_parts else "No prior context."

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Context:\n{context}\n\nUser message: {state['user_input']}"),
    ]

    response = await llm.ainvoke(messages)
    intent = response.content.strip().upper()

    # Validate intent
    valid_intents = {"REPEAT", "DEEPEN", "NEW", "CRISIS"}
    if intent not in valid_intents:
        logger.warning(f"Invalid intent '{intent}', defaulting to NEW")
        intent = "NEW"

    logger.info(f"Intent classified: {intent}")
    return {"intent": intent}


# Lazy-loaded ReAct agent for response synthesis
_respond_agent = None


def _get_respond_agent():
    """Lazy-load the Supervisor ReAct agent for response synthesis."""
    global _respond_agent
    if _respond_agent is None:
        llm = create_llm("supervisor_respond")
        _respond_agent = create_react_agent(
            model=llm,
            tools=SUPERVISOR_TOOLS,
        )
    return _respond_agent


async def synthesize_response(state: dict) -> dict:
    """Merge agent responses into a single, warm, conversational answer.

    Uses a ReAct agent with user management tools. The Supervisor can:
    - Call save_user_name() when it detects the user's name
    - Call lookup_user_profile() to get context about returning users
    - Naturally handle name extraction as part of conversation
    """
    prompt_template = _load_prompt("supervisor_respond")

    # Build agent responses summary
    agent_parts = []
    if state.get("recall_response"):
        agent_parts.append(f"From Memory (previous conversations):\n{state['recall_response']}")
    if state.get("scholar_response"):
        agent_parts.append(f"From Gita Scholar (knowledge graph):\n{state['scholar_response']}")
    if state.get("world_response"):
        agent_parts.append(f"From World Connector (current events):\n{state['world_response']}")

    agent_responses = "\n\n".join(agent_parts) if agent_parts else "No agent responses available."

    # Build conversation history string
    history_str = ""
    if state.get("conversation_history"):
        recent = state["conversation_history"][-5:]
        history_str = "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in recent
        )

    # Fill template
    system_prompt = prompt_template.format(
        user_name=state.get("user_name", "") or "unknown (not yet provided)",
        emotional_state=state.get("emotional_state", "unknown"),
        agent_responses=agent_responses,
        conversation_history=history_str or "Start of conversation.",
        user_input=state.get("user_input", ""),
    )

    agent = _get_respond_agent()

    try:
        result = await agent.ainvoke({
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=state["user_input"]),
            ],
        })

        # Extract final response from message history
        final_message = result["messages"][-1]
        response_text = final_message.content

        # Extract user_name if the Supervisor saved it via tool
        # Check tool messages for save_user_name calls
        user_name = state.get("user_name", "")
        for msg in result["messages"]:
            if hasattr(msg, "name") and msg.name == "save_user_name":
                # Tool was called — parse the response to see if name was saved
                content = msg.content if hasattr(msg, "content") else ""
                if "profile created" in content.lower() or "welcome back" in content.lower():
                    # Extract name from the tool call arguments
                    pass  # Name will be in the tool_call args
            if hasattr(msg, "tool_calls"):
                for tc in msg.tool_calls:
                    if tc.get("name") == "save_user_name":
                        saved_name = tc.get("args", {}).get("name", "")
                        if saved_name:
                            user_name = saved_name
                            logger.info(f"Supervisor saved user name: {user_name}")

        return {
            "final_response": response_text,
            "user_name": user_name,
            "should_learn": True,
        }

    except Exception as e:
        logger.error(f"Supervisor ReAct agent failed: {e}", exc_info=True)
        return {
            "final_response": "I'm here for you, friend. Could you tell me more?",
            "should_learn": False,
        }
