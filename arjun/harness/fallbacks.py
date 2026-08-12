"""Fallback routes — §5: never a stack trace to a human.

The retrieval ladder (empty graph chain → Qdrant broad → Notebook → honest
reply) plugs concrete steps in at P1.13; the ladder mechanics and the
degrade-like-timeout result live here.
"""

import logging
from dataclasses import dataclass
from typing import Callable, Iterable

logger = logging.getLogger("arjun.harness")

#: §5 — the honest reply when every source came back empty or the turn broke.
HONEST_FALLBACK_REPLY = (
    "Friend, what you shared deserves better than a hurried answer. "
    "Let me sit with this for a moment — stay with me, and tell me a little "
    "more about what is weighing on you while I reflect."
)


@dataclass(frozen=True)
class NoResult:
    """A degraded subagent outcome: timeout / content filter / error.

    §5: a timed-out subagent returns "no result" and the Frontal Lobe
    answers from what it has — the same shape covers provider content-policy
    rejection after all gateway fallbacks are exhausted.
    """

    subagent: str
    reason: str  # "timeout" | "content_filter" | "error"


def first_nonempty(steps: Iterable[tuple[str, Callable[[], list]]]) -> tuple[str, list]:
    """Run ladder steps in order; return (step_name, results) for the first
    non-empty result. A step that raises counts as empty — the ladder keeps
    descending. Exhausted ladder → ("none", [])."""
    for name, step in steps:
        try:
            results = step()
        except Exception as exc:
            logger.warning("ladder step %r failed (%s) — descending", name, exc)
            continue
        if results:
            return name, results
    return "none", []
