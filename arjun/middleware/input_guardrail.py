"""Input guardrail middleware — SCAFFOLD (§10 item 1, §20.3 position 2).

The reusable shell every subagent carries. The full screening logic (the
Gut's injection/off-mission read) arrives in P1.8; the deterministic
output rules arrive in P1.16. This shell only defines the hook shape:
a pluggable ``screen`` callable that inspects state before the model runs.
"""

import logging
from typing import Any, Callable, Optional

from langchain.agents.middleware import AgentMiddleware

logger = logging.getLogger("arjun.middleware")

#: A screen receives the agent state and returns a state update (dict),
#: {"jump_to": "end"} to stop the agent early, or None to pass through.
ScreenFn = Callable[[dict], Optional[dict]]


class InputGuardrail(AgentMiddleware):
    """Runs an optional screen before every model call of the agent."""

    def __init__(self, screen: Optional[ScreenFn] = None):
        super().__init__()
        self.screen = screen

    def before_model(self, state, runtime) -> Optional[dict[str, Any]]:
        if self.screen is None:
            return None  # scaffold: pass-through until P1.8/P1.16 plug logic in
        try:
            return self.screen(state)
        except Exception as exc:
            # A broken guardrail must not kill the turn (§5); it fails open
            # here because the REAL input screen is the Gut node — this
            # middleware is defense-in-depth for subagents.
            logger.error("input screen failed (%s) — passing through", exc)
            return None
