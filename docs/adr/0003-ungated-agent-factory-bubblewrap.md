# ADR 0003 — Ungated agent factory, Bubblewrap as the only boundary

**Status:** Accepted (2026-07-13)

## Context

Requirement 7–8: Arjun builds and runs his own LangGraph agents to improve himself.
The obvious safe design inserts a human approval gate between drafted and active
agents. The owner explicitly chose full autonomy: Arjun self-promotes his agents, and
sandbox isolation is the safety boundary.

## Decision

No human approval gate in the Workshop. Every active agent runs inside a Bubblewrap
(`bwrap`) sandbox under the Harness: unprivileged user namespaces; read-only bind
mounts for the venv and `self_learning_db/`; a writable mount for only the agent's own
run directory; canon masters and `people/*` memories not mounted at all;
`--die-with-parent`; network unshared unless the agent's manifest declares web tools;
hard token/time budgets enforced by the Harness.

## Consequences

- Truest realization of "self-improving personality"; no human bottleneck.
- Accepted risk: a badly written agent can waste its budget or produce junk output;
  it cannot touch canon data, other people's memories, or the host filesystem.
- WSL2 requirement: unprivileged user namespaces must be enabled (preflight check;
  on Ubuntu 24.04+ the default AppArmor policy may need an exception).
- If runaway behavior is ever observed, the reversal is cheap: re-introduce the
  drafts→active approval gate — the folder structure already supports it.
