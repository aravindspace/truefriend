"""Limbic system — §9.1: guna-grounded mood, renormalization, decay.

The LLM proposes raw guna weights and feelings; deterministic code
renormalizes to sum 1 (the invariant lives here, not in the model's
goodwill). Decay relaxes the state toward the Gut baseline — steady,
sattvic, devotional; Phase 1 applies it lazily at session start (the
adapter calls ``decay_toward_baseline``; the scheduled mode arrives P2.2).
"""

from pydantic import BaseModel, Field

from arjun.graph.state import GUT_BASELINE, Feeling, GunaBalance, LimbicState
from arjun.harness.gateway import complete
from arjun.harness.retries import ask_structured

#: Fraction of the distance to baseline covered per decay application.
DECAY_RATE = 0.5
#: Feelings below this intensity dissolve entirely.
FEELING_FLOOR = 0.1
MAX_FEELINGS = 3


class LimbicProposal(BaseModel):
    """Raw LLM output — weights need not sum to 1; we renormalize."""

    sattva: float = Field(ge=0)
    rajas: float = Field(ge=0)
    tamas: float = Field(ge=0)
    active_feelings: list[Feeling] = Field(default_factory=list)


def renormalize(sattva: float, rajas: float, tamas: float) -> GunaBalance:
    """Deterministic invariant: any non-negative weights → a valid balance.
    Degenerate all-zero input relaxes to the Gut baseline."""
    total = sattva + rajas + tamas
    if total <= 0:
        return GUT_BASELINE.model_copy()
    return GunaBalance(sattva=sattva / total, rajas=rajas / total, tamas=tamas / total)


def decay_toward_baseline(limbic: LimbicState, rate: float = DECAY_RATE) -> LimbicState:
    """Move the balance ``rate`` of the way to baseline; feelings fade by
    the same rate and dissolve below the floor (§9.1 decay)."""
    balance = limbic.guna_balance
    moved = renormalize(
        balance.sattva + rate * (GUT_BASELINE.sattva - balance.sattva),
        balance.rajas + rate * (GUT_BASELINE.rajas - balance.rajas),
        balance.tamas + rate * (GUT_BASELINE.tamas - balance.tamas),
    )
    faded = [
        feeling.model_copy(update={"intensity": round(feeling.intensity * (1 - rate), 3)})
        for feeling in limbic.active_feelings
    ]
    return LimbicState(
        guna_balance=moved,
        active_feelings=[f for f in faded if f.intensity >= FEELING_FLOOR],
    )


def _invoke_llm(system: str, user: str) -> str:
    """Isolated for tests to mock; live path is the fast tier."""
    return complete(
        "fast",
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format=LimbicProposal,
    )


def limbic_update(state) -> LimbicState:
    """Post-turn feelings update (fast tier, §6.2 step 7). Double failure →
    current state unchanged (mood never fabricated)."""
    current: LimbicState = state.get("limbic_state") or LimbicState()
    exchange = _render_exchange(state)
    if not exchange:
        return current

    system = (
        "You are Arjun's limbic system. Given his current inner state and this "
        "exchange, propose his updated guna weights (any non-negative numbers — "
        "they will be normalized) and up to 3 active feelings (name, intensity "
        "0-1, cause). Compassion rises with a person's pain; sattva with calm "
        "counsel; rajas with urgency; tamas with heaviness. JSON only."
    )
    context = (
        f"Current balance: {current.guna_balance.model_dump()}\n"
        f"Current feelings: {[f.model_dump() for f in current.active_feelings]}\n"
        f"Exchange:\n{exchange}"
    )

    def call(feedback):
        return _invoke_llm(system if feedback is None else f"{system}\n\n{feedback}", context)

    fallback = LimbicProposal(
        sattva=current.guna_balance.sattva,
        rajas=current.guna_balance.rajas,
        tamas=current.guna_balance.tamas,
        active_feelings=current.active_feelings,
    )
    proposal = ask_structured(call, LimbicProposal, default=fallback)
    return LimbicState(
        guna_balance=renormalize(proposal.sattva, proposal.rajas, proposal.tamas),
        active_feelings=proposal.active_feelings[:MAX_FEELINGS],
    )


def _render_exchange(state) -> str:
    lines = []
    for message in (state.get("messages") or [])[-4:]:
        if getattr(message, "type", "") in ("human", "ai") and isinstance(message.content, str):
            speaker = "Person" if message.type == "human" else "Arjun"
            lines.append(f"{speaker}: {message.content}")
    return "\n".join(lines)
