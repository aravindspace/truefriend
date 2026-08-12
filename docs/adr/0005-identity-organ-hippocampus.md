# ADR 0005 — Identity as its own organ (Hippocampus)

**Status:** Accepted (2026-07-18)

## Context

Person identity (§4: guest → promotion → re-link → forgetting, and the
in-conversation asks for name and Uniquename) had grown scattered: the
ask-guidance lived inside `frontal_compose`, the resolution (promote/re-link/record)
lived in the Streamlit adapter, and the primitives were duplicated. The Frontal Lobe
was juggling identity bookkeeping on top of citations, the Helpline Rule, memory, and
composing — "heavier to deal with all things at once" (owner). Bugs (leakage blocking
the person's own name, uniquename never captured, promotion wiping the thread) were
hard to reason about because the logic had no single home.

## Decision

Introduce a dedicated **Identity organ** (body-map name **Hippocampus** — where the
brain binds who someone is), `arjun/organs/identity.py`, as the one home for all
identity logic: the `identity_directive` builder, the promote/re-link/record/forget
primitives, and the `resolve_step` decision. A deterministic graph node `identity`
sits between `thyroid` and `frontal_plan` and writes `identity_directive` into state.
`frontal_compose` only READS that directive — it never computes identity again. Store
resolution runs post-turn in the adapter by calling `identity.resolve_step`; the
adapter shrinks to guest-id creation, Session-End, and session mapping.

It is a deterministic organ node, **not** a `create_agent` subagent: identity
decisions are rule-based, and an LLM here would only add fragility (cf. the Groq
JSON failures). This keeps the Phase-1 subagent count at 3 (retrieval, temporal,
world) while organ nodes go 6 → 7.

## Consequences

- The Frontal Lobe composes only; the single-voice invariant (§20.4-1) still holds
  because the Hippocampus emits a *directive* that `frontal_compose` voices.
- All identity behavior is unit-testable in one module (`tests/test_identity.py`);
  the adapter and brain no longer duplicate the logic.
- The body-map (ADR 0001) gains a component; §6, §6.2, §20.1, §20.4 updated.
- Trade-off: resolution still runs post-turn in the adapter (one-turn lag on
  re-link memory load), accepted for Phase 1 to keep the graph node side-effect-free
  and replayable.
