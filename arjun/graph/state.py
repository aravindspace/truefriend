"""The single shared graph state — §6.1 of arjun_architecture.md.

Carried through every node; persisted per-thread by the checkpointer.

Schema style (LangGraph 1.x guidance, verified 2026-07-17): the graph state
itself extends ``MessagesState`` (TypedDict-based — ``create_agent`` does not
support Pydantic state schemas); the structured members are Pydantic models,
so validation lives in the values while the state container stays framework-
native.
"""

from typing import Literal, Optional

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field, model_validator

# Canonical enums from the Canon (gita_data_injection_architecture.md).
Anartha = Literal["Kama", "Krodha", "Lobha", "Moha", "Mada", "Matsarya"]
Guna = Literal["Satva", "Rajas", "Tamas"]

_SUM_TOLERANCE = 1e-6


class GunaBalance(BaseModel):
    """§9.1 — ``guna_balance: {sattva, rajas, tamas} — sums to 1``."""

    sattva: float = Field(ge=0.0, le=1.0)
    rajas: float = Field(ge=0.0, le=1.0)
    tamas: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _sums_to_one(self):
        total = self.sattva + self.rajas + self.tamas
        if abs(total - 1.0) > _SUM_TOLERANCE:
            raise ValueError(f"guna_balance must sum to 1, got {total}")
        return self


class Feeling(BaseModel):
    """§9.1 — ``active_feelings: [{name, intensity, cause}]``."""

    name: str
    intensity: float = Field(ge=0.0, le=1.0)
    cause: str


#: §9.1 / CONTEXT.md "Gut Baseline" — steady, sattvic, devotional.
GUT_BASELINE = GunaBalance(sattva=0.7, rajas=0.2, tamas=0.1)


class LimbicState(BaseModel):
    """§6.1 ``limbic_state`` — guna balance, active feelings (name/intensity/cause)."""

    guna_balance: GunaBalance = Field(default_factory=lambda: GUT_BASELINE.model_copy())
    active_feelings: list[Feeling] = Field(default_factory=list)


class Person(BaseModel):
    """§6.1 ``person`` — identity (name or guest id), promotion status (§4)."""

    id: str  # "guest_<uuid>" or Person Key namespace id "{name}_{uuid}"
    display_name: Optional[str] = None
    is_guest: bool = True
    uniquename_set: bool = False  # Promotion complete only when True (§4 two-step)


class GutRead(BaseModel):
    """§6.2 step 1 — the Gut screen's structured output (built fully in P1.8).

    ``self_harm_flag`` is mirrored to top-level state (§6.1); the rest rides
    here for the Thyroid (§6.2 step 2) and frontal_compose (§6.2 step 5).
    ``shared_name``/``chosen_uniquename`` power the conversational identity
    flow (§4, owner decision 2026-07-17): promotion happens from what the
    person says to Arjun, never from a form.
    """

    self_harm_flag: bool = False
    injection_attempt: bool = False
    off_mission: bool = False
    problem_domain_guess: list[str] = Field(default_factory=list)
    emotional_temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    shared_name: str = ""  # the person naturally introduced themselves
    chosen_uniquename: str = ""  # they picked a Uniquename when Arjun asked


class TurnPlan(BaseModel):
    """§6.1 ``turn_plan`` — which subagents this turn needs, what for (§6.2 step 3)."""

    run_routing: bool = False  # graph scholar (Kuzu) — anartha reading + node walk
    routing_purpose: str = ""
    run_retrieval: bool = False  # vector scholar (Qdrant)
    retrieval_purpose: str = ""
    run_temporal: bool = False
    temporal_purpose: str = ""
    run_world: bool = False  # only when current facts matter (§6.2 step 3)
    world_purpose: str = ""


class RetrievedChunk(BaseModel):
    """§6.1 ``retrieved`` items — chunk_ids + full verbatim text (§8.2).

    ``source`` separates Canon citations from Arjun's own Notebook
    understanding (§8.2 step 4); text is never rephrased (§5).
    """

    chunk_id: str
    text: str
    source: Literal["canon", "notebook"]
    chunk_type: Optional[Literal["HISTORICAL_ACCOUNT", "TEACHING", "ANALOGY"]] = None


class MemoryRecall(BaseModel):
    """§6.1 ``memory_recall`` — profile, episodes, diagnoses, commitments (§7.2)."""

    profile: list[str] = Field(default_factory=list)
    episodes: list[str] = Field(default_factory=list)
    diagnoses: list[str] = Field(default_factory=list)
    commitments: list[str] = Field(default_factory=list)


class WorldItem(BaseModel):
    """§6.1 ``world_context`` items — web tool results, timestamped + sourced (§6.3)."""

    content: str
    source: str
    timestamp: str  # ISO 8601


class TierDecision(BaseModel):
    """§6.1 ``tier`` — the Thyroid's named profile for this turn (§6.2 step 2)."""

    profile: Literal["small_talk", "counseling"]
    compose_tier: str
    max_tokens: int
    max_tool_calls_per_subagent: int
    recursion_limit: int


class ArjunState(MessagesState):
    """§6.1 — the one state object every organ reads and writes.

    ``messages`` (conversation window, add_messages reducer) comes from
    ``MessagesState``. Each remaining key is written by exactly one node per
    turn, so no extra reducers are needed for the parallel subagent fan-out.
    """

    person: Person
    limbic_state: LimbicState
    gut_read: Optional[GutRead]
    turn_plan: Optional[TurnPlan]
    routing_context: Optional[object]  # RoutingResult — graph scholar's findings
    retrieved: list[RetrievedChunk]  # vector scholar's findings
    memory_recall: Optional[MemoryRecall]
    world_context: list[WorldItem]
    tier: Optional[TierDecision]
    self_harm_flag: bool  # §6.1 / §9.2 — the Adrenals' urgency hormone; routes nothing
    identity_directive: str  # §4 — the Identity organ's guidance for frontal_compose


#: Checkpoint serde allow-list (§5 checkpoint security): exactly the state
#: models a checkpoint may deserialize — strict msgpack blocks everything else.
#: The routing scholar's models (RoutingResult and its members) live in
#: arjun.subagents.routing; listed here as literal (module, class) tuples to
#: avoid a circular import, so ``routing_context`` restores from a checkpoint
#: instead of being blocked (needed for resume AND for reading state back).
STATE_MSGPACK_ALLOWLIST = tuple(
    ("arjun.graph.state", cls.__name__)
    for cls in (
        GunaBalance, Feeling, LimbicState, Person, GutRead,
        TurnPlan, RetrievedChunk, MemoryRecall, WorldItem, TierDecision,
    )
) + (
    ("arjun.subagents.routing", "RoutingResult"),
    ("arjun.subagents.routing", "RoutingDecision"),
    ("arjun.subagents.routing", "AnarthaReading"),
)


def initial_state(person: Person) -> ArjunState:
    """A fresh turn state: empty results, baseline mood, no hormone."""
    return ArjunState(
        messages=[],
        person=person,
        limbic_state=LimbicState(),
        gut_read=None,
        turn_plan=None,
        routing_context=None,
        retrieved=[],
        memory_recall=None,
        world_context=[],
        tier=None,
        self_harm_flag=False,
        identity_directive="",
    )
