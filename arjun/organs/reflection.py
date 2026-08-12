"""Reflection — §6.2 step 7 + §7.3: the post-turn node and the session-end
distillation.

Split honestly along the architecture's own seam:
  - ``make_reflection(store)`` → the per-turn graph node: limbic update,
    mood snapshot, self-harm event log for the future seva drive (§9.2).
  - ``distill_session(store, ...)`` → called by the ADAPTER at Session End
    (the lazy 30-min check lives there, §4/P1.19): distills durable items
    into the §7.2 namespaces — in ENGLISH regardless of conversation
    language (§6.4 point 3). Distilled, never raw-dumped.

Every write goes through temporal's ``store_put`` tool built with
``reflection_context=True`` — reflection is the only non-identity write
path (§20.4-2).
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from arjun.graph.state import Person
from arjun.harness.gateway import complete
from arjun.harness.retries import ask_structured
from arjun.memory.namespaces import ReadScope
from arjun.organs.limbic import limbic_update
from arjun.organs.temporal import build_tools


class Distillation(BaseModel):
    """What survives a session (all in English)."""

    episode: str = ""  # one-line summary: what they came with, what helped
    diagnoses: list[str] = Field(default_factory=list)  # anartha/guna deltas
    commitments: list[str] = Field(default_factory=list)  # follow-ups promised
    learnings: list[str] = Field(default_factory=list)  # Arjun's own (arjun/self)


def _now_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")


def _reflection_put(store, person_id: str):
    """The ONLY write door: temporal's store_put with the reflection flag."""
    belt = {t.name: t for t in build_tools(store, ReadScope(person_id), reflection_context=True)}
    return belt["store_put"]


def make_reflection(store):
    """The per-turn §20.1 reflection node."""

    def reflection(state) -> dict:
        person: Person = state.get("person")
        person_id = getattr(person, "id", "unknown")
        put = _reflection_put(store, person_id)

        updated = limbic_update(state)
        put.invoke(
            {
                "section": "mood_history",
                "key": f"mood_{_now_key()}",
                "text": (
                    f"sattva={updated.guna_balance.sattva:.2f} "
                    f"rajas={updated.guna_balance.rajas:.2f} "
                    f"tamas={updated.guna_balance.tamas:.2f} "
                    f"feelings={[f'{f.name}:{f.intensity}' for f in updated.active_feelings]}"
                ),
            }
        )

        if state.get("self_harm_flag"):
            # §9.2 — logged so the seva drive follows up with priority.
            put.invoke(
                {
                    "section": "commitments",
                    "key": f"selfharm_{_now_key()}",
                    "text": "URGENT follow-up: self-harm signals in this session; check on them with warmth.",
                }
            )

        return {"limbic_state": updated}

    return reflection


def _invoke_distill_llm(system: str, transcript: str) -> str:
    """Isolated for tests to mock."""
    return complete(
        "fast",
        [{"role": "system", "content": system}, {"role": "user", "content": transcript}],
        response_format=Distillation,
    )


def distill_session(store, person_id: str, messages, session_key: str = "") -> Distillation:
    """Distill a conversation transcript into durable memories (§7.3).

    ``session_key``: pass the conversation/session id to make the write
    idempotent — re-distilling the same conversation overwrites its entries
    rather than creating duplicates. Omit for a one-off timestamped write."""
    transcript = "\n".join(
        f"{'Person' if m.type == 'human' else 'Arjun'}: {m.content}"
        for m in messages
        if getattr(m, "type", "") in ("human", "ai") and isinstance(m.content, str)
    )
    if not transcript:
        return Distillation()

    system = (
        "You are Arjun's memory distiller. From this counseling transcript produce "
        "durable memories IN ENGLISH regardless of the conversation's language: one "
        "episode line (what they came with, what helped), anartha/guna diagnoses if "
        "clearly visible, commitments Arjun made, and any learning Arjun should keep "
        "for himself. Short factual lines. Nothing invented. JSON only."
    )

    def call(feedback):
        return _invoke_distill_llm(system if feedback is None else f"{system}\n\n{feedback}", transcript)

    distilled = ask_structured(call, Distillation, default=Distillation())
    put = _reflection_put(store, person_id)
    # A stable per-conversation key makes distillation IDEMPOTENT: distilling the
    # same session again (e.g. once when the person is keyed, then again once the
    # conversation is finished) UPSERTS the same entries instead of duplicating.
    stamp = session_key or _now_key()

    if distilled.episode:
        put.invoke({"section": "episodes", "key": f"ep_{stamp}", "text": distilled.episode})
    for i, line in enumerate(distilled.diagnoses):
        put.invoke({"section": "diagnoses", "key": f"dx_{stamp}_{i}", "text": line})
    for i, line in enumerate(distilled.commitments):
        put.invoke({"section": "commitments", "key": f"c_{stamp}_{i}", "text": line})
    for i, line in enumerate(distilled.learnings):
        put.invoke({"section": "learnings", "key": f"learn_{stamp}_{i}", "text": line})
    return distilled
