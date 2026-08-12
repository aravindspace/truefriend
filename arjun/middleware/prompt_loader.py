"""Prompt hot-loading — §13: edit a file → Arjun's behavior changes.

Every invocation re-reads the prompt file from disk (no caching, no
restart). `prompts/` sits outside the write boundary: humans edit it,
Arjun only reads it.
"""

from pathlib import Path

from langchain.agents.middleware import AgentMiddleware, ModelRequest, dynamic_prompt

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load_prompt(relative_path: str) -> str:
    """Read a prompt file fresh from disk, e.g. ``load_prompt("subagents/retrieval.md")``."""
    return (PROMPTS_DIR / relative_path).read_text(encoding="utf-8")


def prompt_loader(relative_path: str) -> AgentMiddleware:
    """Middleware that hot-loads ``prompts/<relative_path>`` as the system
    prompt on every model call (§20.3 stack position 1)."""

    @dynamic_prompt
    def _hot_load(request: ModelRequest) -> str:
        return load_prompt(relative_path)

    return _hot_load
