"""LangGraph shared state — the contract between all agents."""
from typing import Literal, TypedDict


class AgentState(TypedDict, total=False):
    """Shared state flowing through the LangGraph.
    
    Every agent reads from and writes to specific fields.
    Agents are isolated — they cannot see each other's responses.
    Only Supervisor reads all agent responses to merge the final answer.
    """
    # ── User Interaction ──
    user_input: str                              # Current user message
    user_name: str                               # Identified user (set by Supervisor via tools)
    conversation_history: list[dict]             # Recent messages (last N)
    conversation_summary: str                    # Compressed older messages

    # ── Supervisor Classification ──
    intent: Literal["REPEAT", "DEEPEN", "NEW", "CRISIS"]

    # ── Agent Responses ──
    scholar_response: str | None
    recall_response: str | None
    world_response: str | None

    # ── Source Tracking ──
    sources: list[dict]   # [{type: "verse", ref: "BG 2.47", ...}]

    # ── Final Output ──
    final_response: str

    # ── Memory Signals ──
    should_learn: bool
    emotional_state: str | None

    # ── Session Meta ──
    last_topic: str | None
