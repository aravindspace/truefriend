# ADR 0002 — Pristine canon masters + disposable self-learning clone

**Status:** Accepted (2026-07-13)

## Context

The preprocessed Gita stores (Kuzu graph, Qdrant, routing JSON) are expensive to
rebuild and irreplaceable. The Kuzu graph's `RESOLVED_BY` / `ILLUSTRATED_BY` chains
are nearly empty (3 edges each vs 68 incidents / 876 teachings), so the canonical
incident→teaching→analogy traversal usually returns nothing and needs backfilling.
The fear: an LLM (o4-mini) hallucinating Cypher could corrupt or delete graph data.

## Decision

1. The original stores (`graphdb/`, `vectordb/`, `routing/`) are **canon masters** —
   never opened by Arjun at runtime, kept only for re-cloning.
2. All runtime traffic and all writes (edge backfill, Arjun's learned edges) run
   against a full clone in `self_learning_db/`.
3. The LLM never emits raw Cypher. Runtime reads use a whitelist of parameterized
   query templates with enum/ID-validated parameters. Backfill uses Pydantic
   structured output (chunk-id pairs) inserted by deterministic code.
4. Retrieval is hybrid from day one: routing JSON → Kuzu templates → Qdrant
   metadata-filtered vector search when graph paths are missing.

## Consequences

- Worst case at runtime: an empty result (falls back to Qdrant). Worst case at
  backfill: bad edges in a disposable clone. No path exists from a hallucination to
  canon data loss.
- Storage doubles for the graph (master + clone) — acceptable, it is a single file.
- `self_learning_db/` can be rebuilt from masters at any time; treat it as cattle,
  not a pet.
