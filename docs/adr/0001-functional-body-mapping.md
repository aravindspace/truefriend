# ADR 0001 — Functional body mapping, not literal organ simulation

**Status:** Accepted (2026-07-13)

> Amendment (2026-07-17): the Adrenals mapping changed from "crisis interrupt path"
> to "urgency hormone" by owner decision — there is no separate crisis mode or
> subgraph; a single pipeline answers every message from the Gita. The Adrenals now
> release an urgency signal into graph state and every organ reacts in place
> (warmth-first helplines via the deterministic Helpline Rule, no tier downgrade,
> gentle tone — see `arjun_architecture.md` §9.2). The mapping principle itself is
> unchanged, and this remapping is arguably more faithful to the biology.

## Context

Arjun's cognition is organized around a human body map (frontal lobe, temporal lobe,
limbic system, gut, adrenals, thyroid — from `pre/intial_body.txt`). Two ways to
realize this: (a) each organ maps to one proven agent-engineering mechanism inside a
single deterministic LangGraph graph, or (b) each organ is an independent always-on
agent exchanging "hormone" messages asynchronously.

## Decision

Functional mapping (a). Each body system keeps its biological name but is implemented
as a conventional, testable mechanism: Frontal Lobe = supervisor/planner, Temporal
Lobe = memory subsystem, Limbic = structured emotion state, Gut = baseline persona
parameters + fast heuristics, Adrenals = crisis interrupt path, Thyroid = model/effort
throttle.

## Consequences

- One graph, deterministic control flow — debuggable, evaluatable, affordable.
- The "human" identity survives in naming, state design, and the drive system, not in
  emergent multi-process behavior.
- Reversing this (going literal) would mean redesigning state, evaluation, and cost
  model from scratch — effectively a rewrite.
