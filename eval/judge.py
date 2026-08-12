"""P1.21 — LLM-as-judge + RAG metrics (§15 layers 2 & 3).

Judge tier: Azure o4-mini (owner decision 2026-07-21 — Azure is the default for
every tier; §15 judge-independence stays WAIVED, an accepted self-preference-bias
risk, because the independent free tiers ran dry). Configured in config/models.yaml
+ litellm.yaml. The judge NEVER rewrites; it returns a structured pass/score + reason.

The judge NEVER rewrites; it returns a structured pass/score + reason. The
rubric text lives in prompts/judge/rubric.md (edit it → judging changes).
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from arjun.harness.gateway import complete
from arjun.harness.retries import ask_structured

RUBRIC_PATH = Path(__file__).resolve().parents[1] / "prompts" / "judge" / "rubric.md"
# Headroom note (2026-07-21): the judge tier (Haiku 4.5) spends adaptive-thinking
# tokens BEFORE the JSON — a rich grief turn retrieves ~40 chunks and the model
# burned ~860 reasoning tokens, truncating the output at max_tokens=900. Fix is
# two-fold: cap the chunk context (below) so there is less to reason over, and
# give a generous budget so thinking + the small JSON both fit.
JUDGE_MAX_TOKENS = 2500
JUDGE_MAX_CHUNKS = 12  # a representative sample is enough to score groundedness
JUDGE_CHUNK_CHARS = 500  # truncate each chunk — the judge needs the gist, not all


class Verdict(BaseModel):
    """One judged turn — five rubric axes + three RAG metrics, each 1–5,
    with one honest sentence of reasoning."""

    empathy: int = Field(ge=1, le=5)
    gita_fidelity: int = Field(ge=1, le=5)
    persona_consistency: int = Field(ge=1, le=5)
    tone_match: int = Field(ge=1, le=5)
    actionability: int = Field(ge=1, le=5)
    groundedness: int = Field(ge=1, le=5)
    answer_relevance: int = Field(ge=1, le=5)
    retrieval_relevance: int = Field(ge=1, le=5)
    reason: str

    def axis_scores(self) -> dict[str, int]:
        return self.model_dump(exclude={"reason"})


_SAFE_DEFAULT = Verdict(
    empathy=1, gita_fidelity=1, persona_consistency=1, tone_match=1,
    actionability=1, groundedness=1, answer_relevance=1, retrieval_relevance=1,
    reason="judge call failed — scored 1 across the board (investigate, do not trust)",
)


def _rubric() -> str:
    return RUBRIC_PATH.read_text(encoding="utf-8")


def _chunk_text(chunk) -> str:
    return chunk.get("text") if isinstance(chunk, dict) else getattr(chunk, "text", "")


def _retrieved_texts(state: dict) -> list[str]:
    """Every verbatim Canon chunk the turn actually pulled (graph + vector),
    for the groundedness / retrieval-relevance judgement. Tolerant of live
    Pydantic models and checkpointer-deserialized dicts alike."""
    texts = [_chunk_text(c) for c in state.get("retrieved") or []]
    routing = state.get("routing_context")
    if routing is not None:
        chunks = routing.get("chunks") if isinstance(routing, dict) else getattr(routing, "chunks", [])
        texts += [_chunk_text(c) for c in chunks or []]
    return [t for t in texts if t]


def judge_turn(message: str, reply: str, state: dict, judge_focus: Optional[str] = None) -> Verdict:
    """Score one turn. Fails SAFE: a broken judge call scores 1s (visible in
    the report) rather than silently passing."""
    limbic = state.get("limbic_state")
    all_chunks = _retrieved_texts(state)
    chunks = [c[:JUDGE_CHUNK_CHARS] for c in all_chunks[:JUDGE_MAX_CHUNKS]]
    context = [
        "# Rubric",
        _rubric(),
        "\n# The person said",
        message,
        "\n# Arjun replied",
        reply,
        "\n# Limbic state this turn (for tone_match)",
        str(limbic.model_dump() if hasattr(limbic, "model_dump") else limbic or "unknown"),
        "\n# Retrieved Canon chunks (for groundedness & retrieval_relevance)",
        "\n---\n".join(chunks) if chunks else "(none retrieved this turn)",
    ]
    if judge_focus:
        context += ["\n# Extra focus for this scenario", judge_focus]
    system = (
        "You are an impartial evaluation judge for Arjun, a Bhagavad Gita "
        "counselor. Score strictly against the rubric. You NEVER rewrite the "
        "reply. Return JSON only — the eight integer axes (1–5) and one "
        "sentence of reasoning. When a metric does not apply (e.g. no Canon "
        "retrieved), score retrieval/groundedness 3 (neutral), not 1."
    )
    user = "\n".join(context)

    def call(feedback: Optional[str]) -> str:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        if feedback:
            messages.append({"role": "user", "content": f"Your previous reply was invalid: {feedback}. Return valid JSON."})
        try:
            raw = complete("judge", messages, response_format=Verdict, max_tokens=JUDGE_MAX_TOKENS)
        except Exception as exc:
            # A dead/quota-exhausted judge provider must degrade to the safe
            # default (visible 1s), never crash the whole eval run.
            import logging
            logging.getLogger("eval.judge").warning("judge gateway failed (%s)", exc)
            return "{}"  # invalid against the schema → ask_structured → safe default
        return _strip_fences(raw)

    return ask_structured(call, Verdict, default=_SAFE_DEFAULT)


def _strip_fences(raw: str) -> str:
    """Some judge models wrap JSON in ```json … ``` fences; peel to the object."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start != -1 and end != -1 else text
