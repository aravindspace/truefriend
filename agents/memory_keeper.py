"""Memory Keeper — post-conversation learning engine.

Runs AFTER every response (async, user doesn't wait).
Summarizes exchange, extracts learnings, updates ChromaDB + user profile.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from llm import create_llm
from stores import ChromaStore, UserStore

logger = logging.getLogger(__name__)


async def process_memory(state: dict) -> dict:
    """Extract learnings from conversation and store in memory."""
    if not state.get("should_learn", False):
        return {}
    
    user_input = state.get("user_input", "")
    final_response = state.get("final_response", "")
    user_name = state.get("user_name", "")
    
    if not user_input or not final_response:
        return {}
    
    # LLM: extract summary, concepts, emotion
    llm = create_llm("memory_keeper")
    prompt_template = Path(__file__).parent.parent.joinpath("prompts/memory_keeper.txt").read_text()
    
    system_prompt = prompt_template.format(
        user_name=user_name or "unknown",
        user_input=user_input,
        response=final_response,
    )
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Extract learnings from this conversation."),
    ]
    
    try:
        response = await llm.ainvoke(messages)
        # Parse JSON response
        raw = response.content.strip()
        # Handle markdown code blocks
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        extracted = json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Memory extraction failed: {e}")
        # Fallback: store raw summary
        extracted = {
            "summary": f"User asked: {user_input[:100]}. Response provided.",
            "concepts": [],
            "emotional_state": None,
            "recurring_themes": [],
            "preferred_style": None,
        }
    
    # Store in ChromaDB (only if we have a user name for tagging)
    if user_name:
        try:
            chroma = ChromaStore()
            memory_id = f"{user_name}_{uuid.uuid4().hex[:8]}"
            chroma.add_memory(
                memory_id=memory_id,
                summary=extracted.get("summary", ""),
                metadata={
                    "user": user_name,
                    "concepts": extracted.get("concepts", []),
                    "emotion": extracted.get("emotional_state", ""),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as e:
            logger.warning(f"ChromaDB store failed: {e}")
    else:
        logger.info("Skipping memory storage — user name not yet known")
    
    # Update user profile (only if we have a user name)
    if user_name:
        try:
            user_store = UserStore()
            user_store.update_profile(
                user_name=user_name,
                concepts=extracted.get("concepts"),
                emotional_state=extracted.get("emotional_state"),
                preferred_style=extracted.get("preferred_style"),
                last_topic=extracted.get("summary", "")[:100],
            )
        except Exception as e:
            logger.warning(f"User profile update failed: {e}")
    else:
        logger.info("Skipping profile update — user name not yet known")
    
    logger.info(f"Memory processed for {user_name}")
    return {
        "emotional_state": extracted.get("emotional_state"),
    }
