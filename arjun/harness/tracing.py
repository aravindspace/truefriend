"""Langfuse tracing wiring — §5 (hosting note: owner-hosted remote instance).

Env-driven and self-disabling: with real LANGFUSE_* values in the
environment the callback handler is attached to every graph invocation;
with missing or placeholder values tracing is silently off. A turn never
fails because telemetry did (P1.3 owner deferral, 2026-07-17).

Integration pattern verified 2026-07-17: langfuse SDK v4 exposes
``langfuse.langchain.CallbackHandler``; passing it in ``config["callbacks"]``
covers LangGraph the same as LangChain.
"""

import logging
import os

logger = logging.getLogger("arjun.harness")

_REQUIRED = ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")


def tracing_enabled() -> bool:
    values = [os.environ.get(name, "") for name in _REQUIRED]
    if not all(values):
        return False
    return not any("<" in v for v in values)  # placeholder like <your-instance>


def get_callbacks() -> list:
    """Langfuse callback handler(s) for graph config — [] when tracing is off."""
    if not tracing_enabled():
        return []
    try:
        from langfuse.langchain import CallbackHandler

        return [CallbackHandler()]
    except Exception as exc:
        logger.warning("Langfuse callback unavailable (%s) — tracing off this turn", exc)
        return []
