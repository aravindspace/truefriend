# ADR 0006 — Two Canon scholars: a graph agent and a vector agent

**Status:** Accepted (2026-07-18)

## Context

The Canon lives in two stores (Kuzu graph, Qdrant vectors) but was served by ONE
hybrid retrieval agent. In live use the owner noticed replies that quoted only
teachings — never a recorded incident, never an analogy — and suspected the graph
was not being used at all. It wasn't. Three compounding faults, found by tracing a
real turn:

1. **Vocabulary mismatch.** The Gut emitted problem domains (`family_duty`,
   `loss_grief`, `greed`, `attachment`, `pride`) that do not exist in the real
   routing table (`family`, `duty`, `loss`, …). 5 of 8 missed → `routing_lookup`
   returned `None` → `anartha=""` → **the graph traverse was skipped entirely**.
2. **Dead-end anartha.** Even on a hit, `career`/`purpose` both route to Kama, and
   `PRESENT_IN` has **zero** incidents for Kama (Krodha 2 · Lobha 1 · Mada 2 ·
   Matsarya 2 · Moha 14, of 68 incidents).
3. **Broken chains.** Only 3 `RESOLVED_BY` and 3 `ILLUSTRATED_BY` edges exist, so
   `incident_teachings` returns nothing even when incidents are found (P1.20).

Underneath all three sat a modelling error: routing a situation to ONE anartha. The
Gita's own view is that a real human incident carries several at once — joblessness
is Krodha (anxiety), Kama (fixed desire for that job/salary), Lobha (appetite for
more), Mada (wounded pride in one's skills), Moha (identity fused with employment),
and Matsarya (comparison with peers).

## Decision

Split the Canon across **two subagents**, each owning one store, both reporting to
the Frontal Lobe:

- **`routing` — the graph scholar.** Stage 1: a cautious, **multi-label** anartha
  reading of the person (LLM, structured, with confidence + why per anartha, guna
  environment, and a reasoned life-reading; deep Gita scholarship lives in
  `prompts/subagents/routing.md`). Stage 2: a **deterministic** walk of the Kuzu
  graph for *every* anartha found, drawing meaning-connections between nodes and
  the person's problem. It reads the person's past `diagnoses` from long-term
  memory, and never writes to the graph.
- **`retrieval` — the vector scholar.** Qdrant + Notebook only; all graph imports
  removed (asserted by an AST test).

`frontal_plan` runs both whenever Canon material is needed — vector-without-graph
is precisely the failure this ADR exists to prevent.

Stage 2 is deterministic on purpose: an LLM choosing Cypher templates via tool
calls had already proved fragile (Groq `tool_use_failed`), and the traverse must
always happen. The LLM is used only where judgement is genuinely required — reading
a human being.

## Consequences

- The graph demonstrably participates: the owner's job-loss message now yields 6
  anarthas and 9 Canon nodes, where it previously yielded 0 graph nodes.
- Each source is independently testable and independently debuggable; a regression
  in one cannot silently masquerade as the other.
- Subagents go 3 → 4; `TurnPlan` gains `run_routing`; state gains `routing_context`.
- Cost: one extra reasoning-tier call per counseling turn (the anartha reading).
- **Still limited by the thin graph** — teachings/analogies remain sparse until the
  P1.20 edge backfill runs. This ADR makes the graph reachable; P1.20 makes it rich.
  P1.20 should also consider backfilling `PRESENT_IN` (21 edges, Kama at zero).
