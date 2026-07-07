"""TrueFriend — Chainlit entry point.

PROTOTYPE — answering: does the full multi-agent pipeline work via Chainlit UI?

Run: chainlit run app.py -w
"""
import logging
from pathlib import Path

import chainlit as cl
from dotenv import load_dotenv

from graph.builder import build_graph
from stores import ChromaStore

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Build graph once at startup
graph = build_graph()

# Pre-initialize ChromaDB so the embedding model downloads now, not on first user message
logger.info("Pre-initializing ChromaDB (embedding model download)...")
_chroma = ChromaStore()
logger.info(f"ChromaDB ready — {_chroma.count()} memories loaded")


@cl.on_chat_start
async def on_chat_start():
    """New session — greet user, ask name."""
    cl.user_session.set("conversation_history", [])
    cl.user_session.set("conversation_summary", "")
    cl.user_session.set("user_name", "")
    
    await cl.Message(
        content=(
            "🙏 Namaste, friend!\n\n"
            "I don't have eyes to see you, but I'd love to know who I'm speaking with. "
            "What should I call you? And tell me — what brings you here today?"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming user message — always runs the full graph pipeline."""
    user_input = message.content
    user_name = cl.user_session.get("user_name", "")
    conversation_history = cl.user_session.get("conversation_history", [])
    conversation_summary = cl.user_session.get("conversation_summary", "")
    
    # Add user message to history
    conversation_history.append({"role": "user", "content": user_input})
    
    # Show thinking step
    async with cl.Step(name="🤔 Understanding...", type="tool") as step:
        step.output = f"Processing message from {user_name or 'new friend'}..."
    
    # Build state for graph — Supervisor handles name extraction via tools
    state = {
        "user_input": user_input,
        "user_name": user_name,
        "conversation_history": conversation_history,
        "conversation_summary": conversation_summary,
        "scholar_response": None,
        "recall_response": None,
        "world_response": None,
        "sources": [],
        "final_response": "",
        "should_learn": False,
        "emotional_state": None,
        "last_topic": None,
    }
    
    # Run the graph
    try:
        result = await graph.ainvoke(state)
        final_response = result.get("final_response", "I'm here for you, friend. Could you tell me more?")
        
        # Persist user_name if the Supervisor extracted it via tools
        updated_name = result.get("user_name", user_name)
        if updated_name and updated_name != user_name:
            logger.info(f"User name updated: '{user_name}' -> '{updated_name}'")
        cl.user_session.set("user_name", updated_name)
        
        # Update session state
        conversation_history.append({"role": "assistant", "content": final_response})
        cl.user_session.set("conversation_history", result.get("conversation_history", conversation_history))
        cl.user_session.set("conversation_summary", result.get("conversation_summary", conversation_summary))
        
        # Show which agents contributed (as steps)
        intent = result.get("intent", "UNKNOWN")
        async with cl.Step(name=f"📋 Intent: {intent}", type="tool") as step:
            parts = []
            if result.get("recall_response"):
                parts.append("🔍 Memory: Found relevant past conversations")
            if result.get("scholar_response"):
                parts.append("📚 Scholar: Retrieved Gita knowledge")
            if result.get("world_response"):
                parts.append("🌍 World: Connected to current events")
            step.output = "\n".join(parts) if parts else "Direct response"
        
        # Send response
        await cl.Message(content=final_response).send()
        
    except Exception as e:
        logger.error(f"Graph execution failed: {e}", exc_info=True)
        await cl.Message(
            content="Something went wrong, friend. Could you try asking again?"
        ).send()
