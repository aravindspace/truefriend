"""Routing subagent — the GRAPH scholar (owner decision 2026-07-18, ADR 0006).

Two-stage, and only the first stage uses an LLM:

  1. READ the human being — a deep, cautious, multi-label anartha reading
     (a real life incident carries several anarthas at once, §8.2). Structured
     output; the prompt in ``prompts/subagents/routing.md`` carries the Gita
     scholarship.
  2. WALK the Canon graph deterministically for EVERY anartha found —
     incidents, the teachings that resolve them, the analogies that illustrate
     them, plus the routing table's canonical incidents. No Cypher from the
     LLM, no tool-calling fragility: the traverse always happens.

This agent owns the graph (Kuzu). The retrieval subagent owns the vector store
(Qdrant). Both hand their findings to the Frontal Lobe, which alone speaks.
"""

import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field

from arjun.graph.state import RetrievedChunk
from arjun.harness.gateway import complete
from arjun.harness.retries import ask_structured
from arjun.memory.namespaces import ReadScope
from arjun.middleware.prompt_loader import load_prompt
from arjun.retrieval.kuzu_templates import ANARTHAS, run_template
from arjun.retrieval.routing import routing_lookup

logger = logging.getLogger("arjun.subagents")

PROMPT_FILE = "subagents/routing.md"

#: Keep the gathered context useful rather than overwhelming.
MAX_INCIDENTS_PER_ANARTHA = 3
MAX_TEACHINGS_PER_INCIDENT = 2
MAX_ANALOGIES_PER_TEACHING = 1
MAX_ANARTHAS = 6
#: Below this confidence an anartha is noise, not insight.
MIN_CONFIDENCE = 0.25

AnarthaName = Literal["Kama", "Krodha", "Lobha", "Moha", "Mada", "Matsarya"]


class AnarthaReading(BaseModel):
    """One anartha the scholar sees at work in this person's situation."""

    anartha: AnarthaName
    confidence: float = Field(ge=0.0, le=1.0)
    why: str = ""  # how it shows up HERE, in this person's own words


class RoutingDecision(BaseModel):
    """The scholar's reading of the human being (LLM output)."""

    readings: list[AnarthaReading] = Field(default_factory=list)
    guna_environment: Literal["Satva", "Rajas", "Tamas"] = "Rajas"
    problem_domains: list[str] = Field(default_factory=list)
    life_reading: str = ""  # reasoned understanding in Gita terms


class RoutingResult(BaseModel):
    """What the Frontal Lobe receives: the reasoning AND the original nodes."""

    decision: RoutingDecision = Field(default_factory=RoutingDecision)
    chunks: list[RetrievedChunk] = Field(default_factory=list)  # verbatim Canon
    connections: list[str] = Field(default_factory=list)  # node ↔ problem meaning

    @property
    def found(self) -> bool:
        return bool(self.chunks)


def _invoke_llm(system: str, user: str) -> str:
    """Isolated for tests to mock; runs on the voice tier — this reading needs
    real reasoning, not a cheap label."""
    return complete(
        "voice",
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format=RoutingDecision,
        max_tokens=4000,
    )


def read_situation(
    message: str, past_diagnoses: Optional[list[str]] = None, gut_domains: Optional[list[str]] = None
) -> RoutingDecision:
    """Stage 1 — the cautious multi-anartha reading of a human situation."""
    context = [f"The person says:\n\"{message}\""]
    if gut_domains:
        context.append(f"First instinct about the problem domain: {', '.join(gut_domains)}")
    if past_diagnoses:
        # Long-term memory (§7.2 diagnoses) — is this an old pattern or new?
        context.append("Earlier assessments of this same person:\n- " + "\n- ".join(past_diagnoses))

    def call(feedback):
        system = load_prompt(PROMPT_FILE)
        return _invoke_llm(system if feedback is None else f"{system}\n\n{feedback}", "\n\n".join(context))

    decision = ask_structured(call, RoutingDecision, default=RoutingDecision())
    # Keep only honest signals, strongest first.
    decision.readings = sorted(
        (r for r in decision.readings if r.confidence >= MIN_CONFIDENCE and r.anartha in ANARTHAS),
        key=lambda r: r.confidence,
        reverse=True,
    )[:MAX_ANARTHAS]
    return decision


def walk_graph(decision: RoutingDecision) -> tuple[list[RetrievedChunk], list[str]]:
    """Stage 2 — deterministic traverse of EVERY anartha found. Returns the
    verbatim Canon nodes plus the meaning-connections drawn to the problem."""
    collected: dict[str, RetrievedChunk] = {}
    connections: list[str] = []

    def keep(chunk_id: str, text: str, kind: str) -> bool:
        if chunk_id in collected:
            return False
        collected[chunk_id] = RetrievedChunk(
            chunk_id=chunk_id, text=text, source="canon", chunk_type=kind
        )
        return True

    for reading in decision.readings:
        anartha = reading.anartha

        # Canonical incidents named by the routing table, then graph incidents.
        for domain in decision.problem_domains:
            info = routing_lookup(domain)
            if info and info.anartha == anartha:
                connections.append(f"{anartha}: '{domain}' routes here (guna {info.guna})")

        incidents = run_template("anartha_incidents", anartha=anartha)[:MAX_INCIDENTS_PER_ANARTHA]
        for inc in incidents:
            if keep(inc["chunk_id"], inc["full_text"], "HISTORICAL_ACCOUNT"):
                connections.append(
                    f"{anartha} ({reading.why[:80]}) ← incident {inc['chunk_id']}: {inc.get('name','')[:90]}"
                )
            for teach in run_template("incident_teachings", chunk_id=inc["chunk_id"])[:MAX_TEACHINGS_PER_INCIDENT]:
                if keep(teach["chunk_id"], teach["full_text"], "TEACHING"):
                    connections.append(
                        f"   → resolved by {teach['chunk_id']}: {teach.get('name','')[:90]}"
                    )
                for ana in run_template("teaching_analogies", chunk_id=teach["chunk_id"])[:MAX_ANALOGIES_PER_TEACHING]:
                    if keep(ana["chunk_id"], ana["full_text"], "ANALOGY"):
                        connections.append(f"      → illustrated by {ana['chunk_id']}: {ana.get('name','')[:80]}")

        # Whole-chain template too — catches chains the step-wise walk misses.
        for row in run_template("anartha_chain", anartha=anartha):
            for prefix, kind in (
                ("incident", "HISTORICAL_ACCOUNT"),
                ("teaching", "TEACHING"),
                ("analogy", "ANALOGY"),
            ):
                keep(row[f"{prefix}_id"], row[f"{prefix}_text"], kind)

    return list(collected.values()), connections


def run_routing(
    message: str,
    store=None,
    person_id: str = "",
    gut_domains: Optional[list[str]] = None,
) -> RoutingResult:
    """The full routing pass: read the human, then walk the graph for them."""
    past: list[str] = []
    if store is not None and person_id and not person_id.startswith("guest_"):
        try:  # long-term memory informs the reading (§7.2 diagnoses)
            past = [
                i.value.get("text", "")
                for i in store.search(ReadScope(person_id).person("diagnoses"), limit=5)
            ]
        except Exception as exc:
            logger.warning("routing could not read past diagnoses (%s)", exc)

    decision = read_situation(message, past_diagnoses=past, gut_domains=gut_domains)

    # Fallback: if the LLM reading returned no usable anarthas but the Gut
    # identified problem domains, derive anarthas from the routing table so
    # the graph walk still happens (owner decision 2026-08-06).
    if not decision.readings and gut_domains:
        seen: set[str] = set()
        fallback_readings: list[AnarthaReading] = []
        for domain in gut_domains:
            info = routing_lookup(domain)
            if info and info.anartha not in seen:
                seen.add(info.anartha)
                fallback_readings.append(
                    AnarthaReading(
                        anartha=info.anartha,
                        confidence=0.5,
                        why=f"derived from gut domain '{domain}' (LLM reading unavailable)",
                    )
                )
        if fallback_readings:
            decision.readings = fallback_readings
            decision.problem_domains = list(gut_domains)
            logger.info("routing LLM reading empty; falling back to gut domains: %s", seen)

    chunks, connections = walk_graph(decision)
    return RoutingResult(decision=decision, chunks=chunks, connections=connections)
