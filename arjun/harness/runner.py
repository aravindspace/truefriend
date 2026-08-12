"""run_turn — the deterministic outer loop wrapping every graph invocation.

§5: the LLM proposes; the harness disposes. §3: one entry contract for
conversations and (Phase 2) drive events. §4: single-human deployment —
exactly one live turn at any moment, enforced cheaply, never assumed.
"""

import logging
import os
import threading
from typing import Optional

# Checkpoint security (§5): strict msgpack deserialization must be set
# before langgraph's serde is imported anywhere. Value must be the literal
# "true" (verified from the lib's own warning text); our own state models
# are explicitly allow-listed in make_checkpointer.
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from langchain_core.messages import HumanMessage
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel, model_validator

from arjun.graph.state import Person, initial_state
from arjun.harness.budgets import get_budget
from arjun.harness.fallbacks import HONEST_FALLBACK_REPLY
from arjun.harness.tracing import get_callbacks

logger = logging.getLogger("arjun.harness")

#: §5 per-node wall clock (seconds) — LangGraph enforces it per superstep.
DEFAULT_STEP_TIMEOUT = 60

# §4 single-live-conversation assertion: one graph turn at a time, ever.
_live_turn = threading.Lock()


class TurnRequest(BaseModel):
    """§3 entry contract: {person_or_guest, message | drive_event}.

    Identity status riders (adapter-owned, §4): whether the Uniquename is
    set and the name Arjun addresses them by — the brain uses them to know
    when to ask, conversationally, for name or Uniquename."""

    person_or_guest: str
    message: Optional[str] = None
    drive_event: Optional[str] = None
    uniquename_set: bool = False
    display_name: Optional[str] = None

    @model_validator(mode="after")
    def _exactly_one_payload(self):
        if bool(self.message) == bool(self.drive_event):
            raise ValueError("exactly one of message | drive_event is required")
        return self

    def person(self) -> Person:
        return Person(
            id=self.person_or_guest,
            is_guest=self.person_or_guest.startswith("guest_"),
            uniquename_set=self.uniquename_set,
            display_name=self.display_name,
        )


def run_turn(
    request: TurnRequest,
    graph,
    *,
    profile: str = "counseling",
    session: str = "default",
    step_timeout: int = DEFAULT_STEP_TIMEOUT,
) -> str:
    """One full turn through the brain. Always returns a reply string —
    budget exhaustion, timeouts, and crashes degrade to the honest fallback,
    never to a stack trace (§5)."""
    if not _live_turn.acquire(blocking=False):
        raise RuntimeError("single-live-conversation violated (§4): a turn is already running")
    try:
        budget = get_budget(profile)
        graph.step_timeout = step_timeout

        state = initial_state(request.person())
        text = request.message or f"[drive_event] {request.drive_event}"
        state["messages"] = [HumanMessage(content=text)]

        # Thread is keyed to the CONVERSATION (session), not the person — so a
        # mid-conversation promotion (guest → person) does NOT wipe the message
        # history (§4). Long-term memory is keyed to the person separately.
        config = {
            "configurable": {"thread_id": session},
            "recursion_limit": budget.recursion_limit,
            "callbacks": get_callbacks(),
        }
        result = graph.invoke(state, config)
        return _extract_reply(result)
    except GraphRecursionError:
        logger.warning("turn hit recursion_limit=%d — clean stop", budget.recursion_limit)
        return HONEST_FALLBACK_REPLY
    except Exception as exc:
        logger.error("turn failed (%s: %s) — fallback reply", type(exc).__name__, exc)
        return HONEST_FALLBACK_REPLY
    finally:
        _live_turn.release()


def _extract_reply(result: dict) -> str:
    """The last AI message — a human's own words are never echoed back as
    Arjun's reply (only frontal_compose talks, §20.4-1)."""
    messages = result.get("messages") or []
    last = messages[-1] if messages else None
    if last is not None and getattr(last, "type", "") == "ai":
        content = last.content
        if isinstance(content, str) and content.strip():
            return content
    return HONEST_FALLBACK_REPLY
