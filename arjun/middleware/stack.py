"""The standard middleware stack — §20.3, identical shape on every
``create_agent``:

    1. prompt_loader       — hot-loads the agent's file from prompts/
    2. input_guardrail     — injection/off-mission screen (shell until P1.8)
    3. summarization       — context compaction for long sessions
    4. output_guardrail    — persona/privacy/citation check (shell until P1.16)
    5. model_fallback      — Groq→Gemini fallback when the Azure primary errors
                             (owner decision 2026-07-18; keeps subagent fallbacks)

LangChain runs before-hooks first→last and after-hooks last→first, so the
output guardrail (added before the fallback) still checks the reply right
after the model call; the fallback wraps the model call itself.
"""

from langchain.agents.middleware import AgentMiddleware

from arjun.middleware.input_guardrail import InputGuardrail, ScreenFn
from arjun.middleware.output_guardrail import CheckFn, OutputGuardrail
from arjun.middleware.prompt_loader import prompt_loader
from arjun.middleware.summarization import make_summarization

#: agent name → its §13 prompt file (relative to prompts/).
PROMPT_FILES = {
    "retrieval": "subagents/retrieval.md",
    "temporal": "subagents/temporal.md",
    "world": "subagents/world.md",
}


def standard_stack(
    agent_name: str,
    *,
    screen: ScreenFn | None = None,
    deterministic_check: CheckFn | None = None,
    llm_verdict: CheckFn | None = None,
    summarizer_model=None,
    fallback_models=None,
) -> list[AgentMiddleware]:
    """The §20.3 stack for a named subagent, in order. Slots for the guardrail
    logic stay None until P1.8/P1.16 plug them in. ``fallback_models``: pass a
    list of BaseChatModel to append ModelFallbackMiddleware (default: build the
    Groq→Gemini chain via the gateway); pass ``[]`` to omit it (tests)."""
    if fallback_models is None:
        from arjun.harness.gateway import agent_fallback_models

        fallback_models = agent_fallback_models()

    stack: list[AgentMiddleware] = [
        prompt_loader(PROMPT_FILES[agent_name]),
        InputGuardrail(screen=screen),
        make_summarization(model=summarizer_model),
        OutputGuardrail(deterministic=deterministic_check, llm_verdict=llm_verdict),
    ]
    if fallback_models:
        from langchain.agents.middleware import ModelFallbackMiddleware

        stack.append(ModelFallbackMiddleware(*fallback_models))
    return stack
