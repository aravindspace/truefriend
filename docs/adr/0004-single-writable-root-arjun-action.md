# ADR 0004 — Single writable root: `arjun_action/`

**Status:** Accepted (2026-07-14)

## Context

Arjun's dynamic state was scattered across the repo: memory DBs at the root, the
Kuzu working clone in `self_learning_db/`, learned notes in `notebook/`, self-built
agents in `agents_workshop/`. The owner wants one invariant that is trivial to state,
audit, back up, and sandbox — especially with the humanoid-robot end goal, where the
mind's mutable state must be a portable unit.

## Decision

All runtime writes happen inside a single folder, **`arjun_action/`**:
`memory/` (SqliteSaver + SqliteStore files), `self_learning_db/` (Kuzu working
clone), `notebook/` (learned markdown + skills), `workshop/` (drafts/active/runs).
Everything outside it — brain code in `arjun/`, canon masters, `prompts/`,
`config/`, `eval/` — is opened read-only at runtime. Exceptions: Langfuse traces go
to Langfuse's own service storage; dev-time tooling run by the owner (preprocessing,
eval runners) is outside the rule.

## Consequences

- Backup = copy one folder; reset = delete it and re-clone from masters; the
  Bubblewrap mount rules (ADR 0003) become a physical enforcement of the same
  boundary.
- Arjun can never rewrite his own persona: `prompts/` is outside the boundary; his
  learned voice grows only in `arjun_action/notebook/`.
- Code (`arjun/`) and data (`arjun_action/`) are separate top-level folders — the
  "being" spans two directories, accepted for the cleaner code/data split.
