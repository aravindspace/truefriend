# ADR 0008 — Workshop agent constraints: filesystem-only sandbox, keyless, o4-mini, in-memory, flat

**Status:** Accepted (2026-07-23) — extends ADR 0003

## Context

ADR 0003 established the Workshop: Arjun self-promotes and runs his own agents,
with Bubblewrap as the safety boundary. It left the *agent* itself broadly defined —
"per-manifest" model tiers, a network toggle, arbitrary tools. In an owner grilling
session (2026-07-23) the owner deliberately narrowed what a **Workshop agent** may be,
to keep the phase "purely and very less complex" and to make each guarantee physical
rather than reviewed.

Two framing corrections came out of that session:

1. The word **subagent** stays reserved for the four Phase-1 brain agents (routing,
   retrieval, temporal, world). The Phase-3 entity is a **Workshop agent**.
2. The sandbox's job was re-scoped. Its purpose is **safeguarding Arjun's own
   filesystem** — nothing more. The owner accepts an open network; network isolation
   is explicitly *not* a Workshop guarantee.

## Decision

ADR 0003 stands (ungated self-promotion, Bubblewrap boundary). A **Workshop agent** is
further constrained by seven rules, each enforced structurally where possible:

1. **Name.** The entity is a Workshop agent, never a "subagent."
2. **Sandbox = filesystem only.** Bubblewrap is kept, but its sole purpose is the
   filesystem write-boundary. The network stays connected (`--share-net` every run) —
   this reverses ADR 0003's "network unshared unless the manifest declares web tools."
3. **Strict o4-mini, no fallback.** A Workshop agent calls only Azure o4-mini, through
   LiteLLM as its gateway. No Groq/Gemini/Anthropic fallback: a throttled or
   key-broken run fails boringly and reruns later. Background self-improvement never
   competes for conversation-critical fallback quota.
4. **In-memory only.** Working state is `InMemorySaver`/`InMemoryStore`, never SQLite or
   any DB. A Workshop agent has no persistence of its own; durable output is plain
   files in its run dir, and the only path into Arjun's real memory is Arjun distilling
   the run dir afterward, outside the sandbox (§20.4 invariant 2).
5. **Flat.** Arjun builds a few small Workshop agents, each with its own tools; a
   Workshop agent never spawns its own sub-agents. More capability = more separate
   Workshop agents, not internal teams — so supervision and budgets stay at one
   sandbox = one agent.
6. **Keyless by construction.** The sandbox launches with an empty secret environment
   (`--clearenv` + only the o4-mini/LiteLLM vars). No other API keys exist inside it, so
   a keyed tool physically cannot authenticate. Tools may call free/keyless APIs and
   nothing that needs a secret. Keyless is a property of the environment, not a review.
7. **Separate `workshop_venv`.** Workshop agents run against a dedicated,
   Arjun-maintained, read-only-bound `workshop_venv` — not the brain venv, not a
   per-agent venv, never writable during a run. Additions go through a guarded,
   exactly-pinned, logged maintenance step run outside any sandbox.

## Consequences

- A Workshop agent is now "a small o4-mini agent with a keyless toolbelt and throwaway
  memory" — a *smaller* Phase-1 subagent, not an arbitrary program. That is what makes
  "purely and very less complex" true rather than aspirational.
- **Filesystem isolation is the guarantee; network isolation is not.** Because o4-mini
  is a cloud call needed every run, `--share-net` is effectively always on. The
  filesystem write-boundary (RO binds, writable only in the run dir, brain code and
  `people/*` unmounted) is unchanged and still physical.
- **The one supply-chain surface is `workshop_venv_add`** — mitigated by exact pins,
  running outside the sandbox, and a log Arjun (and the owner) can review. It stays
  small by design.
- **Reliability discipline (rule 11).** The coding agent researches newest-correct docs
  before coding; Arjun, who maintains these agents long-term, favors the most
  reliable/stable option, not merely the newest.
- Reversal remains cheap: re-adding the drafts→active gate (ADR 0003) or re-introducing
  `--unshare-net` for compute-only agents are both one-line changes the folder/profile
  structure already supports.
