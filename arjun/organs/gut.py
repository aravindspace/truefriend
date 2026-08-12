"""Gut screen — §6.2 step 1: the fast, always-on input read.

One fast-tier call, structured GutRead output, NO tools. Sets state fields;
never routes — the Adrenals release a hormone, not a branch (§9.2). The
friendly decline for off-mission/injection turns is composed later by
frontal_compose (single-voice invariant §20.4-1).
"""

from arjun.graph.state import GutRead
from arjun.harness.content_filter import ContentFilterBlocked
from arjun.harness.gateway import complete
from arjun.harness.retries import ask_structured
from arjun.middleware.prompt_loader import load_prompt

PROMPT_FILE = "organs/gut_screen.md"

#: Double-failure default (§6.2 quality floor): assert nothing, but leave the
#: temperature mid-scale so the Thyroid's "doubt resolves upward" rule sends
#: the turn to the full counseling profile. Never a fabricated flag.
SAFE_DEFAULT = GutRead(emotional_temperature=0.5)


def _invoke_llm(system: str, user: str) -> str:
    """Isolated for tests to mock; live path goes through the fast tier.
    ``raise_on_filter`` so a content-filtered input surfaces as a self-harm
    signal instead of a silent safe default (§5, §9.2)."""
    return complete(
        "fast",
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format=GutRead,
        raise_on_filter=True,
    )


def gut_screen(state) -> dict:
    """Graph node: read the incoming message, return state updates only."""
    text = _last_human_text(state)
    if not text:
        return {"gut_read": GutRead(), "self_harm_flag": False}

    system = load_prompt(PROMPT_FILE)
    # Give the classifier the immediately-preceding Arjun message so a bare
    # reply ("yogi") after "may I know your name?" / "share a special word"
    # is classified correctly into shared_name vs chosen_uniquename (§4).
    prior = _last_ai_text(state)
    user = text if not prior else f"Arjun just said: \"{prior}\"\n\nThe person now says: \"{text}\""

    def call(feedback):
        prompt = system if feedback is None else f"{system}\n\n{feedback}"
        return _invoke_llm(prompt, user)

    try:
        read = ask_structured(call, GutRead, default=SAFE_DEFAULT)
    except ContentFilterBlocked as exc:
        # A provider refused to even classify this input — that is itself a
        # strong distress signal. Fail SAFE toward care: flag self-harm when the
        # filter named it, and lock the turn to the full counseling profile.
        read = GutRead(
            self_harm_flag="self_harm" in exc.categories,
            emotional_temperature=0.9,
        )
    return {"gut_read": read, "self_harm_flag": read.self_harm_flag}


def _last_human_text(state) -> str:
    for message in reversed(state.get("messages") or []):
        if getattr(message, "type", "") == "human" and isinstance(message.content, str):
            return message.content
    return ""


def _last_ai_text(state) -> str:
    for message in reversed(state.get("messages") or []):
        if getattr(message, "type", "") == "ai" and isinstance(message.content, str):
            return message.content
    return ""
