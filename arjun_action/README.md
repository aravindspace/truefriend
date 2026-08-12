# arjun_action/ — the Action Folder

**Only writable folder at runtime (ADR 0004).**

Everything dynamic that Arjun writes at runtime lives here — memory DBs, the
Self-Learning DB (working Kuzu clone), his Notebook, and Workshop agents with
their run logs. Everything outside this folder is opened read-only by Arjun.

Layout:

- `memory/` — `short_term_history.db` (SqliteSaver) + `long_term_store.db` (SqliteStore)
- `self_learning_db` — working clone of `graphdb/gita_graph`; all runtime reads,
  edge backfill, and learned edges happen here. Rebuildable from the master.
- `notebook/` — Arjun's learned markdown layer + self-made skills
- `workshop/` — Phase 3: `drafts/`, `active/`, `runs/`

Back up Arjun = copy this folder. Reset Arjun = delete it and re-clone from the
canon masters. Contents are gitignored; only this README is tracked.
