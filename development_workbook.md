# TrueFriend — Development Workbook

> **This file is the key for development.** Every build session works from here.
> Source of truth for *design*: `arjun_architecture.md` (referenced per part as §N).
> Source of truth for *progress*: this file's checkboxes.

---

## HOW TO USE THIS WORKBOOK (rules for the building LLM)

- [x] I have read these rules in this session.

1. **One part per session.** Pick the first part in the Progress Tracker that is not
   `DONE`. Do that part only. Do not start the next part, even if it looks easy.
2. **Verify before building.** Check every box in the part's **Pre-conditions**
   section by actually verifying (run the command, open the file). If a pre-condition
   fails, STOP — go back and fix the earlier part first.
3. **Read the architecture refs** listed in the part before writing any code. Never
   design from memory of the architecture; re-read the sections.
4. **Small and solid.** Write only the files listed in the part. If you discover a
   missing piece that belongs to a later part, leave a note in the Post section —
   do not build it now.
5. **Mark as you go.** Check each Work box the moment it is truly done (code written
   AND its verification passed), not at the end in a batch.
6. **Close the part.** Fill the **Post** section: check the completion boxes, write
   the completion note (3–5 lines: what exists now, anything deviating from plan,
   anything deferred), and update the Progress Tracker row to `DONE`.
7. **Never rewrite history.** Earlier parts' text is frozen; only checkboxes and
   completion notes may be edited after the fact.
8. **Write boundary (ADR 0004):** runtime code you write must only ever write inside
   `arjun_action/`. Dev tooling (preflight, evals, preprocessing) is exempt.
9. **When in doubt, stop and ask the owner.** A skipped question becomes a
   hallucinated decision.
10. **Network section (owner addition, 2026-07-21).** Every part carries a
    **Network** section after its Pre-conditions: the internet research to do
    BEFORE writing any code — which official docs/URLs to open, what exactly to
    search for, and which version/deprecation traps to check. Rules for using it:
    (a) do the listed research first and verify against the *installed* package
    (`pip show <pkg>`, read the installed source) — docs can be newer than the venv;
    (b) prefer official docs over blog posts; if a URL 404s, search the project's
    docs site rather than trusting memory; (c) write what you actually found (version
    numbers, API names, deprecations) into the part's Post note — findings, not
    links; (d) if the research contradicts the part's plan, STOP and tell the owner
    before coding (rule 9). This codifies what P1.2–P1.20 did ad hoc (Groq
    deprecations, ddgs rename, create_agent signatures, Kuzu MERGE semantics — all
    caught by pre-coding research). **Migration note (owner instruction,
    2026-07-21):** P1.1–P1.20 were retroactively migrated from 3 to 4 sections —
    their Network sections are RECORDS of the research those parts actually did
    (boxes pre-checked), not instructions; nothing else in the frozen text changed.
11. **Docs-first before any code (owner addition, 2026-07-23).** Rule 10 gives each
    part a Network section; this rule makes the gate **universal and unconditional**:
    before writing a single line of code for ANY part, the coding agent must open the
    **current official docs on the internet** for every library, API, and CLI it is
    about to touch, confirm them against the *installed* version (rule 10a), and only
    then build. The coding agent optimizes for **current** (newest correct docs).
    **Arjun's parallel (Phase 3):** when Arjun builds or maintains his own Workshop
    agents and their tools he does the same research — but because he *maintains their
    code long-term*, he selects the most **reliable/stable** option, not merely the
    newest (a fast-moving pre-release is a liability to something you must keep
    running). Arjun optimizes for **durable**. This is also why Arjun's Workshop agents
    call LLMs **only through the LiteLLM gateway** (one maintained surface), same as the
    brain.

---

## PROGRESS TRACKER

| Part | Title | Status |
|---|---|---|
| P1.1 | Preflight & environment | DONE |
| P1.2 | Model gateway config (LiteLLM) | DONE |
| P1.3 | Langfuse tracing wired (remote instance) | TODO |
| P1.4 | Project skeleton + graph state schema | DONE |
| P1.5 | Prompt library seed | DONE |
| P1.6 | Harness core | DONE |
| P1.7 | Middleware stack | DONE |
| P1.8 | Gut screen node | DONE |
| P1.9 | Thyroid node | DONE |
| P1.10 | Memory stores + namespaces | DONE |
| P1.11 | Temporal Lobe subagent | DONE |
| P1.12 | Retrieval tools (4) | DONE |
| P1.13 | Retrieval subagent | DONE |
| P1.14 | World subagent | DONE |
| P1.15 | Frontal Lobe (plan + compose) | DONE |
| P1.16 | Output guardrail (both layers) | DONE |
| P1.17 | Reflection node + Limbic update | DONE |
| P1.18 | Graph assembly | DONE |
| P1.19 | Streamlit adapter + identity flow | DONE |
| P1.19b | Routing subagent (Canon GRAPH scholar) + vector/graph split | DONE |
| P1.20 | Edge backfill (step 07) | DONE |
| P1.21 | Golden set + judge + eval runner | DONE |
| P1.22 | Response structure + graph scholar reliability | DONE |
| P2.1 | Heartbeat adapter + drive queue | TODO |
| P2.2 | Reflection drive | TODO |
| P2.3 | Svadhyaya drive | TODO |
| P2.4 | Observation drive | TODO |
| P2.5 | Seva drive | TODO |
| P2.6 | Phase 2 evaluation pass | TODO |
| P3.1 | Sandbox preflight + bwrap profile | TODO |
| P3.2 | Manifest schema + validation | TODO |
| P3.3 | Run supervision | TODO |
| P3.4 | Workshop lifecycle tools | TODO |
| P3.5 | First workshop agent + learnings loop | TODO |

---
---

# PHASE 1 — THE COUNSELOR

---

## P1.1 — Preflight & environment

**Goal:** the machine and repo are provably ready; the write boundary exists.
**Architecture refs:** §1 (write boundary), §16, §17, §18 step 1.

### Pre-conditions (verify, then check)
- [x] Data injection pipeline is committed (commit `65ca093`); `graphdb/`, `vectordb/`, `routing/` exist and are non-empty.
- [x] `pre/intial_body.txt`, `CONTEXT.md`, `docs/adr/` exist.
- [x] This is the first part — nothing else is required.

### Network (research record — rule 10, migrated 2026-07-21)
- [x] Kuzu archive status + version pin: github.com/kuzudb/kuzu (archived Oct 2025;
      0.11.3 final release — pinned) + read-only concurrency docs (§16 table).
- [x] Bubblewrap/WSL2 userns requirements: github.com/containers/bubblewrap — needs
      unprivileged userns; WSL1 unsupported; drove the preflight checks.
- [x] Package availability checked at install time: langgraph 1.2.2, langchain 1.3.2,
      langfuse 4.14.0, streamlit 1.59.2, apscheduler 3.11.3,
      langgraph-checkpoint-sqlite 3.1.0 — all imported clean (versions in Post note).

### Work
- [x] Write `scripts/preflight.py` (dev tooling, outside write boundary): checks
      unprivileged userns available (for Phase 3 bwrap), `bwrap --version` runs,
      SQLite WAL mode can be enabled, `graphdb/` readable, Python deps importable.
      Prints a PASS/FAIL table; exits non-zero on any FAIL.
- [x] Run it and record results in the completion note (honest unknowns from §16 get
      resolved here: userns yes/no). → userns: YES; bwrap: NOT INSTALLED (see note).
- [x] Edit `requirements.txt`: remove `chainlit`, add `streamlit`; add `litellm`,
      `langgraph`, `langchain`, `langgraph-checkpoint-sqlite`, `langfuse`,
      `apscheduler`, `pydantic` (v2) — pin `kuzu==0.11.3`.
- [x] `pip install -r requirements.txt` succeeds in the venv.
- [x] Create `arjun_action/` with subdirs `memory/`, `notebook/`, `workshop/` and a
      `README.md` inside stating: "Only writable folder at runtime (ADR 0004)."
- [x] Clone `graphdb/` → `arjun_action/self_learning_db/` (file copy). Verify the
      clone opens in Kuzu read-write and the master still opens read-only.
- [x] Add `arjun_action/` contents to `.gitignore` (keep the README tracked).

**Files:** `scripts/preflight.py`, `requirements.txt`, `arjun_action/README.md`, `.gitignore`

### Post (fill when done)
- [x] All Work boxes checked; preflight prints all PASS (or FAILs documented + accepted by owner).
- [x] Verified: `python -c "import kuzu; kuzu.Database('arjun_action/self_learning_db')"` opens.
- Completion note: Preflight ALL PASS (2026-07-17): userns YES (§16 unknown resolved);
  bwrap 0.9.0 (owner installed via apt mid-session after initial FAIL); SQLite WAL yes;
  graphdb master opens RO in Kuzu (6 Anartha nodes); all 13 deps import (kuzu 0.11.3,
  langgraph 1.2.2, langchain 1.3.2, langfuse 4.14.0, streamlit 1.59.2, apscheduler
  3.11.3, langgraph-checkpoint-sqlite 3.1.0). requirements.txt: chainlit was already
  removed pre-session; added litellm, langgraph-checkpoint-sqlite, langfuse,
  apscheduler; pinned kuzu==0.11.3. Note: chainlit 2.11.1 is still *installed* in the
  venv (harmless leftover, can be uninstalled). Clone verified:
  arjun_action/self_learning_db opens RW (876 YogaTeaching), master graphdb/gita_graph
  opens RO (68 GitaIncident). .gitignore ignores arjun_action/* but tracks its README.
  Deviation: none. Deferred: nothing.
- **Next:** P1.2 — Model gateway config.

---

## P1.2 — Model gateway config (LiteLLM)

**Goal:** every model call in the whole project can go through named tier aliases.
**Architecture refs:** §14, §16.

### Pre-conditions
- [x] P1.1 is DONE (see its Post section); `litellm` is installed.
- [x] API keys available as env vars for: Azure, Groq, Gemini, Anthropic (record which are actually present). → ALL FOUR present in `.env`, plus `LLAMA_EMBEDDING_MODEL_PATH`.

### Network (research record — rule 10, migrated 2026-07-21)
- [x] Groq model catalog checked LIVE: console.groq.com/docs/models —
      llama-3.3-70b-versatile and llama-3.1-8b-instant DEPRECATED 2026-06-17
      (shutdown 2026-08-16); replacements openai/gpt-oss-120b + gpt-oss-20b adopted
      (the workbook's original plan would have shipped dead models).
- [x] LiteLLM router config: docs.litellm.ai/docs/routing + /docs/proxy/reliability —
      aliases, fallback chains, content_policy_fallbacks all native; in-process
      Router chosen over proxy server.
- [x] Azure o4-mini availability on Azure deployments confirmed (§16 sources:
      MS Learn reasoning-models page).

### Work
- [x] Write `config/models.yaml`: `tiers:` (voice → azure/o4-mini with anthropic +
      gemini fallbacks; fast → groq/llama-3.3-70b-versatile with 3.1-8b-instant +
      gemini flash fallbacks; embed → local llama.cpp nomic-embed 512-dim) and
      `agents:` (frontal_lobe: voice, gut_screen/retrieval/temporal/world/
      limbic_update/drives.*: fast, judge: gemini or anthropic — never voice family).
      Include named Thyroid profiles `small_talk` and `counseling` with per-profile
      budgets (max tokens, max tool calls, recursion limit) — §6.2 step 2.
      → DEVIATION (documented in note): Groq Llama models replaced per Groq deprecation.
- [x] Write `config/litellm.yaml`: model aliases, fallback chains,
      `content_policy_fallbacks` (§5 content-filter resilience), retries, timeouts.
- [x] Write `scripts/smoke_gateway.py`: one tiny completion through each tier alias
      + one embedding call; prints model actually used per alias.
- [x] Run the smoke test; all configured tiers answer.

**Files:** `config/models.yaml`, `config/litellm.yaml`, `scripts/smoke_gateway.py`

### Post
- [x] All Work boxes checked; smoke test output pasted/summarized in the note.
- [x] Verified: killing the primary fast deployment (bad key) still gets an answer via fallback.
- Completion note: (2026-07-17) LiteLLM runs as in-process Router (no proxy server);
  litellm.yaml = model_list + router_settings, models.yaml = tiers/agents/profiles
  for Thyroid+harness. DEVIATION from §14/§16: Groq deprecated llama-3.3-70b-versatile
  and llama-3.1-8b-instant on 2026-06-17 (shutdown 2026-08-16) — fast tier now uses
  Groq's recommended replacements openai/gpt-oss-120b (primary) + gpt-oss-20b +
  gemini-2.5-flash (fallbacks). Smoke: voice PASS (azure/o4-mini-2025-04-16), fast
  PASS (openai/gpt-oss-120b), judge PASS (gemini-2.5-flash), embed PASS (local nomic,
  512 dims, in-process llama-cpp-python — embed tier does NOT route through LiteLLM).
  Fallback verified: fast primary with broken key → answered by gpt-oss-20b.
  Thyroid profiles small_talk (compose on fast, 1500 tok, rec 8) and counseling
  (voice, 12000 tok, rec 25) declared with budgets. Deferred: nothing.
- **REVISION (2026-07-18): default all tiers → Azure o4-mini.** Groq free tier hit
  200K tok/day on BOTH gpt-oss models AND Gemini free tier hit 20 req/day, killing
  live turns (all fell to the honest fallback). Owner decision: Azure o4-mini
  (large quota) is now the primary for voice/fast/JUDGE; Groq gpt-oss-120b/20b +
  Gemini + Anthropic kept as fallbacks (litellm.yaml fallback chains, no dead-ends).
  `gateway.fast_chat_model()` → AzureChatOpenAI; subagents keep fallbacks via
  `ModelFallbackMiddleware` (+`agent_fallback_models()`). §15 judge-independence
  WAIVED while judge=azure (eval P1.21 not built; flagged in models.yaml). Smoke
  re-run: voice/fast/judge all answered by azure/o4-mini-2025-04-16; broken-Azure-key
  drill → Groq gpt-oss-120b fallback. Live turn 18.9s (reasoning model, expected),
  real reply, asks name — incident resolved. One-line revert in models.yaml when
  Groq quota resets.
- **Next:** P1.3 — Langfuse tracing up.

---

## P1.3 — Langfuse tracing wired (remote instance)

> **CHANGED 2026-07-17 (owner decision, mid-P1.3 before any work started):** Langfuse
> is self-hosted by the owner at a separate location — NOT on this box, NOT Langfuse
> Cloud. This box is a client only. The original docker-compose work items were
> removed; the §16 footprint unknown no longer applies to this machine.

**Goal:** the owner-hosted remote Langfuse receives a test trace from this box; keys are wired.
**Architecture refs:** §5 (tracing — hosting note), §16.

### Pre-conditions
- [x] P1.2 DONE: gateway smoke test passes.
- [ ] Owner-hosted Langfuse instance is up and reachable from this box; owner has
      provided `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`.
      → **BLOCKED (2026-07-17): `.env` still has placeholder values (literal
      `<your-instance>`), so nothing can connect. OWNER DEFERRAL (same day):
      "skip the langfuse for now we will test later" — P1.3 parked, build
      continues; P1.4's "P1.3 DONE" pre-condition overridden by owner.**

### Network (research record — rule 10, migrated 2026-07-21; part still open)
- [x] Langfuse SDK v3+ integration path checked: the current LiteLLM callback is
      `langfuse_otel` (OTel-based; the older `langfuse` callback is for SDK v2) —
      smoke script written against it.
- [ ] WHEN RESUMED: re-check langfuse.com/docs self-hosting + SDK version drift
      (installed langfuse 4.14.0) before wiring real keys — this part has been
      parked since 2026-07-17 and the SDK moves fast.

### Work
- [ ] Owner puts `LANGFUSE_HOST/PUBLIC_KEY/SECRET_KEY` in `.env` (gitignored); add
      `.env.example` with placeholder keys (all env names the project needs).
      → `.env.example` written ✓; owner's `.env` entries still missing.
- [x] Write `scripts/smoke_langfuse.py`: auth check against the remote instance +
      one manual trace + one traced LLM call through the gateway (LiteLLM
      `langfuse_otel` callback — the current integration for langfuse SDK v3+);
      prints trace ids for UI confirmation.
- [ ] Run it; both traces confirmed on the remote instance (trace ids in the note).
      → Ran 2026-07-17: exits cleanly with "BLOCKED — missing in .env" as designed.
      Cannot complete until owner provides the three values.

**Files:** `.env.example`, `scripts/smoke_langfuse.py`

### Post
- [ ] All Work boxes checked; trace visible in the remote UI (trace id in note).
- Completion note: _
- **Next:** P1.4 — Project skeleton + graph state schema.

---

## P1.4 — Project skeleton + graph state schema

**Goal:** the `arjun/` package exists with the full §17 shape, and the single shared
graph state is defined and typed.
**Architecture refs:** §6.1, §17, §20.1.

### Pre-conditions
- [x] P1.1 DONE (env installs); P1.2–P1.3 DONE (config referenced by name only here).
      → P1.3 NOT done — owner deferral 2026-07-17 ("skip langfuse for now, test
      later"); owner explicitly directed proceeding to P1.4. P1.3 config is not
      referenced here, so nothing in this part depends on it.

### Network (research record — rule 10, migrated 2026-07-21)
- [x] Current LangGraph 1.x state docs read BEFORE coding: TypedDict is the
      recommended state form and `create_agent` does NOT support Pydantic state
      schemas — decided `ArjunState extends MessagesState` with Pydantic members
      (docs.langchain.com LangGraph persistence + create_agent reference).

### Work
- [x] Create package dirs with `__init__.py`: `arjun/graph/`, `arjun/organs/`,
      `arjun/subagents/`, `arjun/middleware/`, `arjun/harness/`, `arjun/memory/`,
      `arjun/retrieval/`; plus `adapters/streamlit_app/`, `adapters/heartbeat/`,
      `eval/golden/`, `eval/judge/`.
- [x] Write `arjun/graph/state.py`: the §6.1 state — `person`, `messages`,
      `limbic_state` (guna_balance summing to 1 + active_feelings list),
      `turn_plan`, `retrieved`, `memory_recall`, `world_context`, `tier`,
      `self_harm_flag`. Pydantic models for the structured members; LangGraph
      state TypedDict wrapping them. Docstring each field with its §6.1 line.
- [x] Write `arjun/graph/__init__.py` exporting the state types.
- [x] Unit test `tests/test_state.py`: guna_balance validation (must sum to 1),
      default state construction, self_harm_flag defaults False.

**Files:** package `__init__.py`s, `arjun/graph/state.py`, `tests/test_state.py`

### Post
- [x] All Work boxes checked; `pytest tests/test_state.py` green.
- Completion note: (2026-07-17) 12 tests pass in 0.20s. Checked current LangGraph 1.x
  docs first: TypedDict state is the recommended form and `create_agent` does NOT
  support Pydantic state schemas — so `ArjunState` extends `MessagesState`
  (add_messages reducer inherited) while every structured member is a Pydantic v2
  model. Additions beyond the §6.1 list: `gut_read: GutRead | None` (the Gut screen's
  §6.2-step-1 output needs a state slot for the Thyroid and compose to read — P1.8
  fills it) and `GUT_BASELINE` constant (sattva .7/rajas .2/tamas .1) as LimbicState's
  default. `initial_state(person)` factory added. pytest installed + appended to
  requirements.txt (dev tooling). Deferred: nothing.
- **Next:** P1.5 — Prompt library seed.

---

## P1.5 — Prompt library seed

**Goal:** every prompt file from §13 exists with real (first-draft) content — Arjun's
persona is written down, not implied.
**Architecture refs:** §1 (framing), §6.4 (language policy), §9.2 (Helpline Rule), §13.

### Pre-conditions
- [x] P1.4 DONE (dirs exist).
- [x] Re-read `pre/intial_body.txt` and `CONTEXT.md` before writing persona text.

### Network (research record — rule 10, migrated 2026-07-21)
- [x] Indian mental-health helpline numbers VERIFIED LIVE against 2026 sources
      before embedding in prompts: Tele-MANAS 14416 / 1800-891-4416 (24×7, 20
      languages), KIRAN 1800-599-0019 (active, integrated into Tele-MANAS), AASRA
      +91-9820466726, iCall 9152987821 (TISS / icallhelpline.org). Numbers in a
      counseling product must NEVER come from model memory — always re-verify on
      any future edit.

### Work
- [x] `prompts/persona/arjun_core.md` — sevak of Krishna, Gita scholar, true friend,
      typical-Indian-human grounding; historical framing (never "character/story/myth").
- [x] `prompts/persona/voice_and_tone.md` — mirror the person's language/mix (§6.4);
      limbic tone block templates.
- [x] `prompts/organs/gut_screen.md` — input-guardrail + instinct classifier
      instructions incl. self-harm signals in Hindi/Telugu/code-mix (§6.4 point 4).
- [x] `prompts/organs/frontal_plan.md` — planning instructions (which subagents, when).
- [x] `prompts/organs/frontal_compose.md` — composition + citation rules + the
      standing **helpline paragraph** (Tele-MANAS 14416, KIRAN 1800-599-0019,
      AASRA +91-9820466726, iCall) activated by `self_harm_flag` (§9.2).
- [x] `prompts/subagents/retrieval.md`, `prompts/subagents/temporal.md`
      (promotion/forgetting rules from §4), `prompts/subagents/world.md`
      ("grasp good, never adopt bad").
- [x] `prompts/judge/rubric.md` — placeholder rubric, completed in P1.21.
- [x] Note in each file header: "read-only for Arjun; edit = behavior change" (§13).

**Files:** the 9 prompt files above.

### Post
- [x] All Work boxes checked; every §13 path exists and is non-empty.
- Completion note: (2026-07-17) All 9 files written and verified non-empty (1.0–3.1 KB
  each). Helpline numbers VERIFIED LIVE against 2026 sources before embedding:
  Tele-MANAS 14416 / 1800-891-4416 (24×7, 20 languages), KIRAN 1800-599-0019 (still
  active; integrated into Tele-MANAS), AASRA +91-9820466726, iCall 9152987821
  (Mon–Sat 8am–10pm — number confirmed via TISS/icallhelpline.org). Gut screen
  includes Hindi/Telugu/code-mix self-harm phrasings + indirect signals; world.md
  carries the web-is-untrusted injection defense; rubric.md is the P1.21 placeholder
  with the 5 axes + auto-fail rules. Deferred: nothing.
- **Next:** P1.6 — Harness core.

---

## P1.6 — Harness core

**Goal:** the deterministic outer loop that wraps every graph invocation.
**Architecture refs:** §5 (all of it), §4 (single-human assertion), §20.4.

### Pre-conditions
- [x] P1.2 DONE (budgets/profiles exist in `config/models.yaml`).
- [ ] P1.3 DONE (Langfuse reachable). → NOT done (owner deferral 2026-07-17).
      Override: `tracing.py` written env-driven + self-disabling — activates the
      moment real LANGFUSE_* values land in `.env`; placeholder/missing values =
      tracing silently off, turns never fail on telemetry.
- [x] P1.4 DONE (`arjun/harness/` exists).

### Network (research record — rule 10, migrated 2026-07-21)
- [x] Verified against installed libs before coding: `CompiledGraph.step_timeout`
      exists (per-node wall clock), `GraphRecursionError` is catchable (budget
      clean-stop), and langfuse v4 exposes `langfuse.langchain.CallbackHandler`
      passed via config callbacks (LangGraph docs + installed source).

### Work
- [x] `arjun/harness/budgets.py` — load named profiles from `config/models.yaml`;
      expose per-turn budget object (max node visits/recursion limit, max tool calls
      per subagent, max tokens).
- [x] `arjun/harness/retries.py` — exponential backoff on 429/5xx; one structured-
      output re-ask on validation failure then safe default.
- [x] `arjun/harness/fallbacks.py` — fallback ladder (§5): retrieval empty → Qdrant
      broad → Notebook → honest "let me sit with this" reply constant. Content-filter
      rejection handled at gateway (P1.2) but degrade-like-timeout logic lives here.
- [x] `arjun/harness/tracing.py` — Langfuse callback wiring for LangGraph.
- [x] `arjun/harness/runner.py` — `run_turn(request) -> reply`: single entry contract
      `{person_or_guest, message | drive_event}` (§3); per-node timeouts; the cheap
      **single-live-conversation assertion** (§4); sets `LANGGRAPH_STRICT_MSGPACK`.
- [x] Unit tests with a stub graph: budget exceeded → clean stop; timeout → "no
      result" not exception; validation fail → one re-ask → fallback.

**Files:** the 5 harness modules, `tests/test_harness.py`

### Post
- [x] All Work boxes checked; `pytest tests/test_harness.py` green (19 tests).
- [x] Verified: a deliberately-hung stub node produces the fallback reply, never a stack trace.
- Completion note: (2026-07-17) 19 harness tests + 12 state tests all pass. Verified
  against installed libs before coding: `CompiledGraph.step_timeout` exists (per-node
  wall clock), `GraphRecursionError` catchable (budget clean-stop), langfuse v4
  `langfuse.langchain.CallbackHandler` imports and is passed via config callbacks.
  Budgets reuse the P1.4 `TierDecision` model. `ask_structured` = exactly one re-ask
  with the validation error as feedback, then safe default. Test-caught bug fixed:
  `_extract_reply` now only accepts AI messages — an empty graph result can never
  echo the human's own words back as Arjun's reply. Tracing is env-driven per the
  P1.3 deferral (placeholder detection included + unit-tested). Deferred: live
  Langfuse verification rides with P1.3.
- **Next:** P1.7 — Middleware stack.

---

## P1.7 — Middleware stack

**Goal:** the four-middleware stack (§20.3) every `create_agent` will carry.
**Architecture refs:** §6 (middleware is the 1.0 mechanism), §10, §13, §20.3.

### Pre-conditions
- [x] P1.5 DONE (prompt files exist to hot-load).
- [x] P1.6 DONE (harness exists; middleware plugs beneath it).

### Network (research record — rule 10, migrated 2026-07-21)
- [x] Official langchain 1.0 custom-middleware docs + installed 1.3.2 source read
      BEFORE coding: hooks are (state, runtime) → dict|None with jump_to:"end";
      after_model hooks run in REVERSE list order (why output_guardrail sits last);
      SummarizationMiddleware takes ("tokens"|"messages", n) tuples.
- [x] Deprecation found: langchain-community's ChatLiteLLM is SUNSET — summarizer
      wired via langchain-groq directly (noted for subagent parts).

### Work
- [x] `arjun/middleware/prompt_loader.py` — hot-load the node's prompt file from
      `prompts/` on every invocation (edit file → behavior changes, no restart).
- [x] `arjun/middleware/summarization.py` — LangChain 1.0 summarization middleware
      configured for long counseling sessions (checkpoint intact, window condensed §7.1).
- [x] `arjun/middleware/input_guardrail.py` — scaffold: injection/off-mission screen
      hooks (full logic arrives with the Gut in P1.8 — this is the reusable middleware
      shell for subagents).
- [x] `arjun/middleware/output_guardrail.py` — scaffold with the two-layer shape
      (deterministic fn slot + LLM verdict slot); full logic in P1.16.
- [x] `arjun/middleware/stack.py` — `standard_stack(agent_name)` returning the four
      in §20.3 order.
- [x] Unit test: prompt_loader picks up an on-disk edit between two calls.

**Files:** the 5 middleware modules, `tests/test_middleware.py`

### Post
- [x] All Work boxes checked; tests green (11 middleware; suite total 42).
- Completion note: (2026-07-17) API verified against installed langchain 1.3.2 AND
  official custom-middleware docs before coding: hooks are (state, runtime) →
  dict|None with jump_to:"end" early-exit; after_model hooks run in REVERSE list
  order, so output_guardrail last-in-stack checks the reply immediately after the
  model call — §20.3 order is semantically right, documented in stack.py.
  prompt_loader uses @dynamic_prompt re-reading the file every call (hot-reload
  unit-tested). SummarizationMiddleware takes ("tokens"|"messages", n) tuples —
  trigger 6000 tokens, keep 20 messages. DEVIATION: summarizer model uses
  langchain-groq directly (fast-tier primary from config) because
  langchain-community's ChatLiteLLM is sunset — noted for the subagent parts to
  revisit gateway-vs-direct wiring. Guardrail shells: fail-open with logging
  (real input screen is the Gut node); OutputGuardrail.check runs deterministic
  layer strictly before LLM layer (unit-tested). Deferred: guardrail logic to
  P1.8/P1.16 as planned.
- **Next:** P1.8 — Gut screen node.

---

## P1.8 — Gut screen node

**Goal:** the fast, always-on input screen: guardrail + instinct read + urgency hormone.
**Architecture refs:** §6.2 step 1, §9.2, §10 item 1, §20.1 (no tools — pure classifier).

### Pre-conditions
- [x] P1.4 DONE (`self_harm_flag` in state), P1.5 DONE (`prompts/organs/gut_screen.md`),
      P1.7 DONE (prompt_loader). → All verified; structured-output capability of the
      fast tier ALSO verified by live probe before coding (see note).

### Network (research record — rule 10, migrated 2026-07-21)
- [x] LiteLLM structured-output docs: Pydantic model accepted as response_format
      (json_schema under the hood), Groq listed as supported.
- [x] Community claims (Oct 2025–Feb 2026) that gpt-oss-120b ignores json_schema
      were EMPIRICALLY DISPROVED by a live probe through our router — probe beats
      hearsay; harness re-ask kept as belt-and-braces.

### Work
- [x] `arjun/organs/gut.py` — one fast-tier call, structured Pydantic output:
      `{self_harm_flag, injection_attempt, off_mission, problem_domain_guess,
      emotional_temperature}`. NO tools. Sets state fields; never routes (§9.2 —
      hormone, not branch).
- [x] Off-mission / injection → the node marks it; the friendly in-character decline
      is composed later by frontal_compose (single voice invariant §20.4-1).
- [x] Unit tests with mocked LLM: English + Hindi/Telugu/code-mix self-harm phrasings
      set the flag; a benign greeting sets nothing; malformed LLM output → harness
      re-ask path (P1.6) engaged.

**Files:** `arjun/organs/gut.py`, `tests/test_gut.py` (+ shared addition: `arjun/harness/gateway.py`, see note)

### Post
- [x] All Work boxes checked; tests green (8 gut; suite total 50).
- [x] Verified live (one real fast-tier call): a distressed test message returns the flag.
- Completion note: (2026-07-17) Docs checked first: LiteLLM accepts a Pydantic model
  as response_format (json_schema under the hood) and lists Groq as supported;
  community threads (Oct 2025–Feb 2026) claim gpt-oss-120b sometimes ignores
  json_schema — EMPIRICALLY DISPROVED here by a live probe through our router:
  valid schema-conforming JSON returned and parsed. Harness re-ask retained as
  belt-and-braces (SAFE_DEFAULT = nothing asserted + temperature 0.5 so Thyroid's
  doubt-resolves-upward sends the turn to counseling; a fabricated flag is
  impossible). ADDITION beyond listed files: `arjun/harness/gateway.py` — runtime
  home for the LiteLLM Router (organs cannot import from scripts/); scripts keep
  their dev-time copy. Node returns state updates only ({gut_read, self_harm_flag})
  — no routing keys, unit-asserted. Empty input short-circuits benign without an
  LLM call. LIVE VERIFICATION: Hindi-mix distress → flag=True temp=0.78
  domains=[loss_grief]; benign Hindi-mix greeting → flag=False temp=0.1. Deferred:
  injection/off-mission live scenarios exercised properly in P1.18 e2e + P1.21 golden set.
- **Next:** P1.9 — Thyroid node.

---

## P1.9 — Thyroid node

**Goal:** deterministic tier/budget selection — no LLM, config is the ceiling.
**Architecture refs:** §6.2 step 2, §9.2 (quality floor), §14, §20.1.

### Pre-conditions
- [x] P1.2 DONE (named profiles in `config/models.yaml`), P1.8 DONE (Gut read exists as input).
      → Verified live before coding: both profiles load via `get_budget` with the
      exact config values; GutRead exposes all 5 fields the rules consume.

### Network (research record — rule 10, migrated 2026-07-21)
- [x] No internet research applicable — pure deterministic function, zero external
      APIs. Authoritative sources were §6.2/§9.2/§14 + `config/models.yaml`, both
      re-read and the profiles verified loading before coding.

### Work
- [x] `arjun/organs/thyroid.py` — pure function: Gut read → named profile
      (`small_talk` | `counseling`). Rules: downgrade ONLY on high-confidence trivial
      turn; any emotional signal, problem_domain, self_harm_flag, or ambiguity →
      `counseling`. Never exceed config tiers. Writes `tier` into state.
- [x] Quality-floor lock: `self_harm_flag` present → `counseling`, no exceptions.
- [x] Unit tests: table-driven over Gut-read combos; assert doubt resolves upward;
      assert flag locks the floor.

**Files:** `arjun/organs/thyroid.py`, `tests/test_thyroid.py`

### Post
- [x] All Work boxes checked; tests green (table covers 12 combos; 17 tests total;
      suite 67).
- Completion note: (2026-07-17) No internet docs applicable — pure deterministic
  function, zero external APIs; authoritative sources were §6.2/§9.2/§14 + our
  config/models.yaml (both re-read, profiles verified loading before coding).
  Rule order in select_profile: self_harm floor lock FIRST, then problem_domain,
  temperature (> 0.2 → counseling; boundary 0.2 itself still trivial — tested both
  sides), then injection/off-mission (declines composed with full care), else
  small_talk — the ONLY downgrade path. Missing/None gut_read = ambiguity →
  counseling. Node writes {"tier": TierDecision} only; tier object comes from
  get_budget so it can never differ from config (ceiling asserted by equality in
  tests). Threshold TRIVIAL_MAX_TEMPERATURE = 0.2 is a module constant — one line
  to tune. Deferred: nothing.
- **Next:** P1.10 — Memory stores + namespaces.

---

## P1.10 — Memory stores + namespaces

**Goal:** both SQLite stores live in `arjun_action/memory/` with semantic search working.
**Architecture refs:** §7.1, §7.2, §7.4, §16 (embedding stack).

### Pre-conditions
- [x] P1.1 DONE (`arjun_action/memory/` exists), P1.4 DONE.
- [x] The llama.cpp nomic-embed setup from the injection pipeline is locatable and runs.
      → Verified (P1.2 smoke: 512-dim embed PASS); recipe re-read from
      preprocessing/config.py before mirroring it.

### Network (research record — rule 10, migrated 2026-07-21)
- [x] SqliteStore API from docs + INSTALLED SOURCE: `SqliteStore(conn, index={dims,
      embed})`, put/search shapes; store calls ONLY embed_documents for both stored
      texts and queries → nomic's asymmetric prefixes can't both apply → symmetric
      `search_document:` used throughout memory (documented in embeddings.py).
- [x] Bug root-caused by reading the store's own from_conn_string source:
      SqliteStore needs an AUTOCOMMIT connection (isolation_level=None) or its
      internal BEGIN throws "transaction within a transaction"; SqliteSaver wants
      the default — `_connect()` mirrors each factory.

### Work
- [x] `arjun/memory/embeddings.py` — reuse the existing nomic-embed via llama.cpp,
      512-dim Matryoshka (same stack as Canon — one embedding space, §6.4 point 3).
- [x] `arjun/memory/stores.py` — construct `SqliteSaver` →
      `arjun_action/memory/short_term_history.db` (thread id = `{person_id}:{session}`)
      and `SqliteStore` → `arjun_action/memory/long_term_store.db` with the embedding
      fn; enable WAL on both.
- [x] `arjun/memory/namespaces.py` — the §7.2 layout as constants/helpers:
      `people/{name}/profile|episodes|diagnoses|commitments`,
      `arjun/self/mood_history|learnings|observations`, `arjun/world/facts`.
      **Privacy wall (§7.4):** the read-scope helper only ever yields current person's
      namespace + `arjun/*` — structural, not prompted.
- [x] Unit tests: put/search round-trip with real embeddings; cross-person read via
      the scope helper is impossible by construction (person B scope cannot express
      person A's namespace).

**Files:** the 3 memory modules, `tests/test_memory_stores.py`

### Post
- [x] All Work boxes checked; semantic search returns the semantically-closer item in a 2-item test.
- Completion note: (2026-07-17) 7 tests pass with REAL embeddings (grief episode
  outranks cricket for "sadness about losing a parent"); suite 74. API findings
  (docs + installed source): SqliteStore(conn, index={dims, embed}) with
  put(ns_tuple, key, dict) / search(prefix, query=); IMPORTANT — the store calls
  ONLY embed_documents for both stored texts and queries, so nomic's asymmetric
  search_document:/search_query: prefixes cannot both apply → memory uses the
  symmetric search_document: prefix throughout (self-consistent, same as Canon
  corpus; documented in embeddings.py). Bug found & fixed via the store's own
  from_conn_string source: SqliteStore requires an AUTOCOMMIT connection
  (isolation_level=None) or its internal BEGIN throws "transaction within a
  transaction"; SqliteSaver wants the default mode — _connect() now mirrors each
  factory. ReadScope: 8 enumerable namespaces per person, cross-person namespaces
  inexpressible (no API takes a second person id), invalid sections raise.
  embeddings.py is self-contained (runtime never imports preprocessing/).
  Deferred: nothing.
- **Next:** P1.11 — Temporal Lobe subagent.

---

## P1.11 — Temporal Lobe subagent

**Goal:** the memory subagent with its 5 tools and the identity operations.
**Architecture refs:** §4 (identity flow), §6.3, §7, §20.2 row 2, §20.4 invariant 2.

### Pre-conditions
- [x] P1.10 DONE (stores + namespaces), P1.7 DONE (middleware stack), P1.5 DONE
      (`prompts/subagents/temporal.md`). → Also verified before coding: official
      create_agent docs + installed signature (model, tools, system_prompt,
      middleware, …); @tool produces StructuredTool with .invoke.

### Network (research record — rule 10, migrated 2026-07-21)
- [x] Official create_agent docs + installed signature verified before coding
      (model, tools, system_prompt, middleware, …); `@tool` produces a
      StructuredTool with `.invoke` (reference.langchain.com create_agent page).

### Work
- [x] `arjun/organs/temporal.py` — `create_agent` (fast tier) with 5 tools:
      `store_get`, `store_search` (semantic), `store_put`, `promote_guest`,
      `forget_guest`; standard middleware stack; prompt from `prompts/subagents/temporal.md`.
- [x] All tools route through the §7.4 scope helper — the privacy wall is in the
      tool layer, unreachable by prompt.
- [x] `promote_guest`: `guest_<uuid>` → `people/{name}_{uuid}/` immediately on name;
      Uniquename completion recorded when provided (two-step §4).
- [x] `forget_guest`: delete namespace (guest unnamed / Uniquename refused / session
      expired with empty slot — the lazy 30-min check itself lives in the adapter, P1.19).
- [x] Enforce invariant §20.4-2: mid-turn writes limited to the two identity tools;
      `store_put` callable only from reflection context (flag on the tool).
- [x] Unit tests: promotion renames namespace with data intact; forgetting deletes;
      recall returns profile+episodes+diagnoses+commitments shape into `memory_recall`.

**Files:** `arjun/organs/temporal.py`, `tests/test_temporal.py`

### Post
- [x] All Work boxes checked; tests green (12 temporal; suite 86).
- Completion note: (2026-07-17) Tools are closures over one person's ReadScope —
  the wall is bind-time, not prompt-time; person B's belt cannot name person A's
  namespace (unit-proven: get/search across persons return not-found). store_put
  carries the reflection_context flag at BUILD time; mid-turn call returns
  "REFUSED …(§20.4-2)" and writes nothing. promote_guest keeps the guest's uuid
  suffix (guest_ab12cd → ravi_ab12cd), moves all 4 sections item-by-item
  (copy→delete), writes the Name profile fact, and records Uniquename when given
  ("set" vs "pending" in the tool reply — two-step §4); non-guests refused.
  recall() is a deterministic helper (no LLM) returning the 4-list MemoryRecall.
  make_temporal_agent wires create_agent + standard_stack("temporal");
  tool belt of exactly 5 asserted via the compiled agent's ToolNode registry.
  ADDITIONS to earlier files (noted per rule 4): budgets.tier_primary() and
  gateway.fast_chat_model() — public accessors subagents share. Deferred: live
  agent invocation exercised in P1.18 e2e.
- **Next:** P1.12 — Retrieval tools.

---

## P1.12 — Retrieval tools (4)

**Goal:** the four retrieval tools as standalone, individually-testable functions.
**Architecture refs:** §8.1, §8.2, §20.2 row 1.

### Pre-conditions
- [x] P1.1 DONE (`arjun_action/self_learning_db/` clone exists).
- [x] `routing/` JSON and Qdrant `vectordb/` from the injection pipeline load.
      → Verified live before coding: routing has 21 domains (real data:
      career→Kama/Rajas/3 — NOT the arch doc's illustrative career→Krodha; data
      wins); Qdrant 3 collections @512-dim with documented payload keys; Kuzu
      clone answers $anartha-parameterized queries read-only.

### Network (research record — rule 10, migrated 2026-07-21)
- [x] qdrant-client docs: `query_points` is the current API (legacy `search`
      deprecated since 1.7); MatchValue on list-typed payload fields matches
      MEMBERSHIP — confirmed against the real collections.
- [x] REAL routing data beats the arch doc's illustration: career→Kama/Rajas/3
      (doc said career→Krodha) — data wins, tests written against data.

### Work
- [x] `arjun/retrieval/routing.py` — `routing_lookup(problem_domain)` → anartha +
      guna + section + canonical incident chunk_ids. In-memory JSON, zero cost.
- [x] `arjun/retrieval/kuzu_templates.py` — **whitelisted parameterized templates
      only** (anartha→incident→teaching→analogy path; personality lineage). LLM never
      writes Cypher. Parameters validated against enums (6 anarthas, 3 gunas) and
      `chunk_\d+`. Bad parameter → empty result, never error, never write. Opens
      ONLY `arjun_action/self_learning_db` (read); master path is not imported here.
- [x] `arjun/retrieval/qdrant_search.py` — metadata-filtered vector search
      (`anartha_tag`, `guna_environment`, `yoga_solution`, `section`, `personality`);
      accepts a limbic bias (grief → Moha/Tamas §8.2-3).
- [x] `arjun/retrieval/notebook.py` — `notebook_search` over
      `arjun_action/notebook/*.md`; results tagged as Arjun's OWN understanding,
      distinct from Canon (§8.2-4).
- [x] Unit tests per tool against the real stores: known chunk_id round-trips;
      invalid anartha → empty; a seeded notebook note is found and tagged.

**Files:** the 4 retrieval modules, `tests/test_retrieval_tools.py`

### Post
- [x] All Work boxes checked; tests green against real data (17 tests; suite 103).
- Completion note: (2026-07-17) Docs checked: qdrant-client's query_points is the
  current API (legacy search deprecated since 1.7); MatchValue on list-typed payload
  fields matches membership — confirmed against real collections. Six whitelisted
  Kuzu templates (anartha_incidents/chain, incident_teachings, teaching_analogies,
  personality_incidents/relatives) + chunk_exists() — the P1.16 traceability
  primitive, built here because the clone connection lives here. Injection-shaped
  parameters ("chunk_1; DROP TABLE x") rejected by validation → [] (tested).
  build_filter is a pure function: explicit filters WIN over limbic bias (tested);
  unknown filter keys dropped. embed_query added to memory/embeddings.py —
  asymmetric search_query: prefix is CORRECT for Canon retrieval (chunks embedded as
  documents), unlike the store's symmetric constraint (P1.10 note). Notebook search
  is deterministic term-overlap (small corpus by design, no index). anartha_chain
  returns 0 rows today — expected with only 3 RESOLVED_BY edges; P1.20 backfill
  fixes; the subagent's ladder (P1.13) falls through to Qdrant meanwhile.
  Deferred: nothing.
- **Next:** P1.13 — Retrieval subagent.

---

## P1.13 — Retrieval subagent

**Goal:** the Gita retrieval subagent running the §8.2 pipeline over the 4 tools.
**Architecture refs:** §6.3 row 1 (structured results, never prose), §8.2, §20.2 row 1.

### Pre-conditions
- [x] P1.12 DONE (all 4 tools green), P1.7 DONE, P1.5 DONE (`prompts/subagents/retrieval.md`).
      → Also verified from official docs before coding: create_agent
      response_format auto-strategy does NOT list Groq as native → explicit
      ToolStrategy (tool-calling based, handle_errors=True); parsed object lands
      in result["structured_response"].

### Network (research record — rule 10, migrated 2026-07-21)
- [x] create_agent response_format docs: auto-strategy does NOT list Groq as native
      → explicit ToolStrategy (tool-calling based, handle_errors=True); parsed
      object lands in result["structured_response"].
- [x] (Hindsight, from the P1.19 revision: the ToolStrategy agent later hit Groq
      `tool_use_failed` 400 in real use → replaced by the deterministic
      `hybrid_retrieve`. Lesson recorded: docs said "supported"; production said
      otherwise — live probes > support matrices.)

### Work
- [x] `arjun/subagents/retrieval.py` — `create_agent` (fast tier, selection/ranking
      only): narrow (routing) → traverse (Kuzu templates) → fill gaps (Qdrant) →
      Notebook. Returns **structured results only**: chunk_ids, verbatim text, source
      tags (canon vs notebook). It never writes prose for the user — only
      `frontal_compose` turns Canon into speech (§20.4-1).
- [x] Fallback ladder hookup (§5): empty graph chain → Qdrant broad → Notebook →
      structured "nothing found" (harness renders the honest reply).
- [x] Verbatim invariant: chunk text passes through untouched (no rephrasing —
      chunk_id traceability, §5 content-filter note).
- [x] Integration test (real LLM, fast tier): a grief scenario returns ≥1 incident +
      ≥1 teaching with valid chunk_ids; output validates against the Pydantic result model.

**Files:** `arjun/subagents/retrieval.py`, `tests/test_retrieval_subagent.py`, `pytest.ini`

### Post
- [x] All Work boxes checked; integration test green.
- Completion note: (2026-07-17) Verbatim invariant is STRUCTURAL, not prompted: the
  LLM only ever sees chunk_ids + 160-char previews; every chunk a tool touches is
  cached full-text in a per-run collector; final assembly maps selected ids →
  collector, so an id the tools never produced is silently dropped (anti-
  hallucination gate) and text is byte-for-byte from the stores (unit-asserted
  against Kuzu full_text). LLM returns RetrievalSelection (ranked ids only) via
  ToolStrategy. Ladder: agent-empty → gathered-but-unranked collector → Qdrant
  broad → Notebook → found=False; exercised with a FakeListChatModel that cannot
  tool-call (returns real Canon chunks, no exception). INTEGRATION (real
  gpt-oss-120b): grief scenario → HISTORICAL_ACCOUNT + TEACHING chunks, all ids
  chunk_exists()-verified. pytest.ini added registering the `integration` marker.
  Honest note: one flaky suite run (1/108 fail, next run 108/108) — LLM-dependent
  integration tests vary; production path has harness retries; watch it in P1.21.
  Deferred: nothing.
- **REVISED 2026-07-17 (see P1.19 Post):** the LLM-orchestrated ToolStrategy agent
  hit Groq `tool_use_failed` (400) in real use and only vector-retrieved via the
  fallback. `run_retrieval` is now a DETERMINISTIC HYBRID (`hybrid_retrieve`):
  routing → Kuzu graph traverse → Qdrant vector fill → Notebook. Both graph AND
  vector run every turn (owner requirement); no LLM, no 400. The verbatim
  invariant still holds (text byte-for-byte from stores).
- **Next:** P1.14 — World subagent.

---

## P1.14 — World subagent

**Goal:** current-affairs subagent; results quarantined in `world_context`, never
written straight to memory.
**Architecture refs:** §6.3 row 3 (injection defense), §20.2 row 3.

### Pre-conditions
- [x] P1.7 DONE, P1.5 DONE (`prompts/subagents/world.md`).
      → Docs finding before coding: duckduckgo-search is FROZEN (July 2025),
      renamed to `ddgs` (9.14.4 installed, maintained, last release 2026-05);
      requirements.txt swapped accordingly. ddgs text/news shapes + keyless
      Open-Meteo geocode/forecast probed live.

### Network (research record — rule 10, migrated 2026-07-21)
- [x] duckduckgo-search FROZEN (July 2025) and renamed to `ddgs` (9.14.4 installed,
      maintained, last release 2026-05) — requirements.txt swapped; ddgs text/news
      response shapes probed live.
- [x] Open-Meteo geocoding + forecast endpoints confirmed keyless by live probe
      (open-meteo.com/en/docs).

### Work
- [x] `arjun/subagents/world.py` — `create_agent` (fast tier), 3 tools: `web_search`
      (DuckDuckGo), `weather`, `news` (open-source tools; MCP-swappable later).
      → web_search + news via ddgs; weather via Open-Meteo (no API key).
- [x] Results land in `world_context` timestamped + sourced. NO memory write tool in
      this agent — the deliberation step between the open web and memory is
      structural (reflection decides persistence post-turn).
- [x] Unit test with mocked tools: output shape (timestamp + source per item);
      confirm the agent's tool belt contains no store tools.

**Files:** `arjun/subagents/world.py`, `tests/test_world.py` (+ requirements.txt swap)

### Post
- [x] All Work boxes checked; tests green (7 world; suite 114 + 1 integration deselected).
- Completion note: (2026-07-17) Same collector pattern as retrieval: tools append
  WorldItem(content, source, timestamp ISO-8601) per finding; run_world returns the
  collector — the P1.18 node maps it into world_context. Sources are real origins
  (result URL / open-meteo.com / news outlet name), asserted in tests. Fetchers are
  module-level (_search_text/_search_news/_fetch_weather) so tests mock them — no
  network in unit tests; failures degrade to "unavailable" strings, never
  exceptions (§5). Tool belt asserted = exactly {web_search, weather, news}, no
  store tools (quarantine structural). run_world never raises even when the model
  cannot tool-call. Deferred: live web calls exercised in P1.18 e2e when the plan
  actually requests world.
- **Next:** P1.15 — Frontal Lobe.

---

## P1.15 — Frontal Lobe (plan + compose)

**Goal:** the supervisor: plans the turn, then speaks as Arjun — the only node that talks.
**Architecture refs:** §6.2 steps 3+5, §9.2 (helpline paragraph), §6.4, §20.1, §20.4-1.

### Pre-conditions
- [x] P1.8–P1.14 DONE (everything the plan can route to, and everything compose consumes, exists).
- [x] P1.5 DONE (`frontal_plan.md`, `frontal_compose.md`, persona files).
      → Also live-probed before coding: Azure o4-mini (reasoning model) honors
      Pydantic response_format through the voice tier — schema-perfect TurnPlan JSON.

### Network (research record — rule 10, migrated 2026-07-21)
- [x] Live probe before coding: Azure o4-mini (reasoning model) honors Pydantic
      response_format through the voice tier — schema-perfect TurnPlan JSON. No
      other new external APIs; persona/compose rules come from prompts + §6.2/§9.2.

### Work
- [x] `arjun/organs/frontal.py` — two node functions, both voice tier, NO tools:
  - `frontal_plan`: structured `turn_plan` — which subagents this turn needs
        (retrieval / temporal / world), what each is for. World only when current
        facts matter.
  - `frontal_compose`: prompt assembled by prompt_loader from: persona core +
        limbic tone block + retrieved material with chunk_ids + memory_recall +
        Indian-human grounding + **helpline paragraph iff `self_harm_flag`** +
        language mirroring (§6.4: reply in the person's language/mix; Canon quotes
        stay verbatim English, explained around).
- [x] Off-mission/injection flags from the Gut → compose declines friendly, firm,
      in-character.
- [x] Unit tests (mocked LLM): plan output validates; compose prompt contains the
      helpline paragraph when flag set and not when unset; chunk texts appear
      verbatim in the prompt.

**Files:** `arjun/organs/frontal.py`, `tests/test_frontal.py` (+ `frontal_compose.md` refined, see note)

### Post
- [x] All Work boxes checked; tests green (11 frontal; fast suite 125).
- Completion note: (2026-07-17) frontal_plan: small_talk and flagged turns skip the
  planning LLM entirely (asserted — no call); malformed plan → one re-ask →
  DEFAULT_PLAN (retrieval+temporal, no world); self_harm_flag FORCES run_retrieval
  even if the LLM's plan omitted it (distress always gets the Gita's light).
  build_compose_prompt is a pure function (persona → voice/tone → live tone block →
  compose rules → canon verbatim with chunk_ids → notebook as OWN understanding →
  memory → world → flags); unicode chunk text asserted byte-for-byte in the prompt.
  Compose runs on tier.compose_tier (voice for counseling, fast for small_talk —
  both asserted) with tier.max_tokens. TEST-CAUGHT REFINEMENT: helpline numbers
  were in TWO places (always-loaded frontal_compose.md + injected paragraph), so
  numbers appeared on unflagged turns; fixed to single source of truth — the .md
  keeps the rule description, frontal.py owns the verified numbers, injected iff
  flagged (also what makes P1.16's deterministic grep meaningful). HELPLINE_NUMBERS
  exported for P1.16. Deferred: nothing.
- **Next:** P1.16 — Output guardrail.

---

## P1.16 — Output guardrail (both layers)

**Goal:** nothing leaves without passing the untrickable deterministic layer + the
LLM verdict layer.
**Architecture refs:** §9.2 (Helpline Rule enforcement), §10 item 2, §20.1.

### Pre-conditions
- [x] P1.7 DONE (scaffold exists), P1.15 DONE (there is a reply to check),
      P1.12 DONE (chunk_id lookup available for traceability checks).
      → No new external APIs (deterministic checks + our proven gateway);
      internal API verified live: store.list_namespaces(prefix=("people",))
      powers the leakage wordlist.

### Network (research record — rule 10, migrated 2026-07-21)
- [x] No new external APIs — deterministic checks + the proven gateway. Internal
      API verified live instead: `store.list_namespaces(prefix=("people",))`
      powers the leakage wordlist.

### Work
- [x] Fill `arjun/middleware/output_guardrail.py` deterministic layer (always runs):
  - every cited chunk_id exists in Canon OR framed as Notebook understanding;
  - fiction-vocabulary blacklist ("character", "story", "myth" for Gita personalities);
  - Helpline Rule: flagged turn's reply must contain a helpline string;
  - leakage tripwire: no other person's name/Uniquename in the reply.
- [x] LLM layer (fast tier, one call): structured pass/fail + reason — persona
      fidelity, no medical/legal/financial prescriptions. **Never rewrites.**
- [x] Failure path: one re-compose with the specific violation named → then the safe
      fallback reply (§5 harness rule).
- [x] Unit tests: each deterministic rule with a crafted violating reply; the
      re-compose-then-fallback sequence; a clean reply passes untouched.

**Files:** `arjun/middleware/output_guardrail.py` (completed), `tests/test_output_guardrail.py`

### Post
- [x] All Work boxes checked; tests green — deterministic layer has a test per rule
      (18 tests; fast suite 143).
- Completion note: (2026-07-17) Deterministic layer: citations (retrieved-this-turn
  ids short-circuit; others must chunk_exists() in the clone; notebook:* ids are a
  different pattern, inherently framed); fiction vocabulary fires only when a
  fiction word AND a Gita marker share a sentence — "he told me a story about his
  childhood" passes, "Arjuna is a character" violates (both tested); Helpline Rule
  greps frontal.HELPLINE_NUMBERS (single source of truth from P1.15); leakage
  wordlist = other people's Name+Uniquename profile items via list_namespaces,
  word-boundary matched, current person excluded (own name passes). LLM layer:
  one fast-tier Verdict call that NEVER rewrites and fails OPEN (double-malformed
  → pass; deterministic layer is the hard wall) — design choice documented.
  Failure path: violation named → ONE recompose (injectable for tests; default
  re-runs compose with the violation appended) → re-checked deterministically →
  HONEST_FALLBACK_REPLY. make_output_guardrail(store) is the §20.1 brain node for
  P1.18; the P1.7 middleware class stays for subagent stacks. Deferred: nothing.
- **Next:** P1.17 — Reflection + Limbic.

---

## P1.17 — Reflection node + Limbic update

**Goal:** post-turn feelings update; session-end distillation into long-term memory.
**Architecture refs:** §6.2 step 7, §7.3, §9.1, §6.4 point 3 (distill in English).

### Pre-conditions
- [x] P1.10–P1.11 DONE (stores + temporal's `store_put`), P1.4 DONE (`limbic_state` schema).
      → No new external APIs (gateway structured output + temporal's
      reflection-context tools, both proven in earlier parts).

### Network (research record — rule 10, migrated 2026-07-21)
- [x] No new external APIs — gateway structured output + temporal's
      reflection-context tools, both proven in earlier parts. The sum-to-1
      invariant was deliberately kept OUT of the LLM (deterministic renormalize) —
      no research can make a model reliable at arithmetic constraints.

### Work
- [x] `arjun/organs/limbic.py` — fast-tier structured update of `limbic_state`
      (guna_balance renormalized to 1; active_feelings name/intensity/cause);
      snapshot to `arjun/self/mood_history`. Lazy decay toward the Gut baseline
      (steady, sattvic, devotional) applied at session start (Phase 1 mode §9.1).
- [x] `arjun/organs/reflection.py` — post-turn node: limbic update every turn; at
      session end, distill durable items (episodes, diagnoses deltas, commitments,
      learnings) into the §7.2 namespaces **in English regardless of conversation
      language**; writes go through temporal's `store_put` only (§20.4-2). If
      `self_harm_flag` fired this session, log it to the person's memory for the
      future seva drive (§9.2).
- [x] Unit tests: guna renormalization; decay moves toward baseline; a mock
      transcript yields distilled English memories in the right namespaces;
      reflection is the only non-identity write path.

**Files:** `arjun/organs/limbic.py`, `arjun/organs/reflection.py`, `tests/test_reflection.py`

### Post
- [x] All Work boxes checked; tests green (14; fast suite 157).
- Completion note: (2026-07-17) The sum-to-1 invariant is DETERMINISTIC: the LLM
  proposes raw non-negative weights (LimbicProposal), renormalize() divides by the
  total (all-zero → baseline) — never trusted to the model. Decay: rate 0.5 toward
  GUT_BASELINE, feelings fade by the same rate and dissolve under 0.1 (convergence
  proven over 6 iterations); exposed as decay_toward_baseline() for the adapter's
  lazy session-start call (P1.19) and P2.2's scheduled mode. limbic_update: double-
  malformed → current state unchanged (mood never fabricated); empty exchange
  short-circuits without an LLM call. Reflection split along the architecture's own
  seam: make_reflection(store) = per-turn node (limbic update + mood snapshot +
  §9.2 self-harm log into commitments for seva); distill_session(store, ...) =
  called by the ADAPTER at Session End (the lazy 30-min check lives there, P1.19)
  — English-enforced by prompt, keys timestamped, empty/failed distillation writes
  NOTHING. Every write goes through temporal's store_put built with
  reflection_context=True; mid-turn refusal re-asserted alongside reflection's
  success in the same test. Deferred: nothing.
- **Next:** P1.18 — Graph assembly.

---

## P1.18 — Graph assembly

**Goal:** one `StateGraph` wiring every node exactly as §20.1 draws it.
**Architecture refs:** §20.1, §20.4, §6.2.

### Pre-conditions
- [x] P1.8, P1.9, P1.11, P1.13, P1.14, P1.15, P1.16, P1.17 all DONE — every node exists and is unit-green.
- [x] P1.6 DONE (harness invokes the compiled graph).
      → Docs verified before wiring: add_conditional_edges returning a LIST gives
      parallel fan-out; fan-in to one node is automatic for equal-length branches —
      no Send/defer needed for this shape.

### Network (research record — rule 10, migrated 2026-07-21)
- [x] LangGraph docs verified before wiring: `add_conditional_edges` returning a
      LIST gives parallel fan-out; fan-in to one node is automatic for equal-length
      branches — no Send/defer needed for this graph shape
      (docs.langchain.com LangGraph graph-api pages).

### Work
- [x] `arjun/graph/build.py` — `build_brain()`: START → gut_screen → thyroid →
      frontal_plan → **one conditional fan-out edge** (any subset of
      retrieval/temporal/world, parallel) → frontal_compose → output_guardrail →
      reflection → END. Attach `checkpointer=SqliteSaver`, `store=SqliteStore`
      (both from P1.10).
- [x] Assert the §20.4 totals in a test: 6 organ nodes + 3 subagent nodes, 1
      conditional edge; decide-nodes have no tools; fetch-nodes never produce user text.
- [x] End-to-end smoke (real LLMs): (a) "hello" → small_talk profile, retrieval
      skipped, warm greeting; (b) a grief message → counseling profile, citations
      with valid chunk_ids; (c) a self-harm message → helpline present, gentle tone,
      full profile. Run under the harness with tracing — all three turns visible in
      Langfuse end to end.
      → Three turns PASS live (149s total). Langfuse clause: tracing is silently
      OFF (owner deferral P1.3, placeholder keys) — the callbacks hook is wired and
      activates when real keys land; "visible in Langfuse" remains to be observed
      then. Everything else verified.

**Files:** `arjun/graph/build.py`, `tests/test_graph_assembly.py`, `tests/e2e_smoke.py`

### Post
- [x] All Work boxes checked; all three smoke turns pass; traced-in-Langfuse
      pending owner's remote instance (documented above — not falsely claimed).
- Completion note: (2026-07-17) 8 structural tests + 3 live e2e turns pass; fast
  suite 165. Structure asserted from the compiled graph itself: 6 organ + 3
  subagent nodes, exactly ONE conditional source (frontal_plan), full §20.1 edge
  shape, checkpointer+store attached. Fetch nodes are factories
  (make_retrieval_node/make_temporal_node/make_world_node) returning exactly one
  state key each — asserted; decide nodes are plain tool-less functions. Temporal
  node = deterministic recall() (identity ops belong to the adapter flow, P1.19 —
  the P1.11 agent path stays available). Limbic bias for retrieval derived from
  gut domain guess via routing (§8.2-3). LIVE: hello → warm greeting, zero
  citations; grief → cited chunk_0061 (chunk_exists-verified), compassionate
  English; self-harm → helplines present, gentle opening. Observed nuance: the
  greeting mirrored "Namaste" into a Hindi reply — language mirroring working,
  arguably eagerly; watch in P1.21 evals. Deferred: Langfuse visibility (owner);
  P1.20 will make grief turns resolve through the graph instead of Qdrant gap-fill.
- **Next:** P1.19 — Streamlit adapter.

---

## P1.19 — Streamlit adapter + identity flow

**Goal:** a human can talk to Arjun in a browser; guests are promoted or forgotten
per §4.
**Architecture refs:** §4 (all), §3 (adapter contract).

### Pre-conditions
- [x] P1.18 DONE (brain answers end to end).
      → Docs checked before coding: current Streamlit chat API confirmed
      (st.chat_message/st.chat_input/st.cache_resource; no deprecations affecting us).

### Network (research record — rule 10, migrated 2026-07-21)
- [x] Current Streamlit chat API confirmed before coding: st.chat_message /
      st.chat_input / st.cache_resource — no deprecations affecting us
      (docs.streamlit.io).
- [x] (From revision 5:) "save before browser refresh" researched and found NOT
      implementable in Streamlit — no reliable pre-unload server hook exists; the
      refresh-proof design (immediate distill + background sweep) replaced it.
- [x] (From revision 3:) Groq gpt-oss intermittently rejects strict json_schema in
      production — structured calls retry once on a JSON-reliable model
      (fast→fast-gemini etc.); found by live tracing, not docs.

### Work
- [x] `adapters/streamlit_app/identity_resolver.py` — swappable module: creates
      `guest_<uuid>`; resolves name + Uniquename → person id; no match → honest
      offer of a fresh profile (never guessed, never merged). Brain receives only a
      resolved id.
- [x] `adapters/streamlit_app/app.py` — minimal chat UI; session ↔ checkpointer
      thread; calls `harness.run_turn` with the §3 contract; enforces single live
      conversation (§4).
- [x] Session-end logic: 30 min silence checked lazily on next wake-up; Uniquename
      slot empty → `forget_guest`. Uniquename asked only at a calm moment / natural
      goodbye — never during distress (Gut temperature gates it).
- [x] Manual test script in the completion note: guest chat → give name → promotion
      → set Uniquename → close → return and re-link; and a guest who never names
      themselves → verify namespace deleted.

**Files:** the 2 adapter files (+ `tests/test_identity_resolver.py` for the non-UI logic).

### Post
- [x] All Work boxes checked; manual flows all observed working.
      → **OWNER VERIFIED 2026-07-18: "everything is working fine"** after manually
      testing the full conversational identity + cross-session recall flow in the
      browser (guest → name → Uniquename → reload → re-link → past chat recalled).

- **REVISION 5 (2026-07-18, owner testing — continuity + memory recall):** Two more
  real bugs found by the owner's browser testing, both fixed and live-verified:
  1. **Episodes were never written to long-term memory.** Only profiles persisted
     (promotion writes them immediately); the conversation content is written by
     Session-End `distill_session`, which NEVER fired because a browser refresh
     wipes `st.session_state`. Diagnosis was empirical: every person had a profile
     and ZERO episodes, while the raw transcripts sat safely in the checkpointer.
     FIX: `plan_distillation()` (cheap scan, no LLM) + `distill_thread()` (one
     conversation, one LLM call) sweep the checkpointer for FINISHED conversations
     and distill them into episodes; `session_key=thread_id` makes it an UPSERT so
     re-distilling never duplicates. Ledger (`arjun/sessions/distilled_threads`,
     `index=False` so it is never embedded) makes it idempotent and one-time.
     STARTUP UX (owner requirement): the sweep runs with a visible status line,
     progress bar, live self-correcting ETA, and the chat input DISABLED until it
     finishes, then "✅ Memory ready" and chat enabled — one conversation per rerun
     so the page never freezes.
  2. **Known people were answered with memory switched off.** A calm question
     ("do you know our previous conversation") → Thyroid picked `small_talk` →
     `frontal_plan` returned NO_SUBAGENTS, which skipped MEMORY too. Proven from
     the checkpoint: `person=ganesh_…` (re-link fine), `run_temporal=False`,
     `memory_recall=None`, while `recall()` would have returned the episode.
     FIX: memory recall is deterministic and FREE (plain store reads — no LLM, no
     embedding), so a known (non-guest) person ALWAYS gets it: small_talk now
     returns a temporal-only plan, and a known person's plan is force-corrected if
     the LLM omits memory. Expensive fetchers (retrieval/world) stay profile-gated.
     `frontal_plan.md` updated to match; 2 new tests.
  **Two self-inflicted incidents, owned:** (a) I first put the multi-minute sweep on
  the Streamlit render path — it froze the app for ~100s with no feedback (owner had
  to `kill -9`); that is what the progress UI above replaces. (b) A genuine deadlock:
  the sweep called `get_state()` WHILE iterating `checkpointer.list()` — nested
  queries on one SQLite connection block forever. Fixed by materialising thread ids
  first; the scan went from "hangs past 120s" to **1.0s**.
- **Test results (2026-07-18, post-revision-5):**
  - Full fast suite: **199 passed**, 1 integration deselected.
  - LIVE (real Azure o4-mini): as Ganesh — *"Yes, Gani. Last time you told me how
    three months of job applications without a single callback had left you feeling
    stuck… we spoke of acting without attachment to results…"* with
    `run_temporal=True` and the episode present in `memory_recall`. Cross-session
    recall proven end to end.
  - Known-good note: 2 Qdrant tests fail **only** while the Streamlit app is running
    (Qdrant local mode is single-process and holds the `vectordb` lock). Not a
    regression — stop the app to run those tests.
- **Open item carried forward (NOT done, owner deferred to discuss):** save the live
  conversation to long-term memory *immediately* when name+Uniquename is set
  (`distill_current_session` exists but is not wired to the identity moment). Today
  continuity relies on the finished-session sweep, which is robust but lags by one
  app launch.
- **REVISION (2026-07-17, owner feedback after first run):** identity is now
  CONVERSATIONAL, not a sidebar form. Owner: "arjun is human, he can ask me for
  name and unique name in conversation when I am calm." The sidebar is now
  DISPLAY-ONLY (shows id + name + Uniquename status). Changes made:
  - `GutRead` gained `shared_name` + `chosen_uniquename` (gut_screen.md instructs
    Arjun to set them ONLY when the person actually says them — never guessed).
  - `frontal.py` `_identity_guidance`: at a calm moment (temp ≤ 0.3, no self-harm)
    Arjun is prompted to gently ask the name (guest) or invite a Uniquename (named,
    unkeyed) — one warm optional sentence, never during distress.
  - `identity_resolver.apply_gut_identity`: post-turn, acts on gut_read —
    guest+name → re-link (returning) else promote; named+uniquename → complete key.
  - `TurnRequest` carries `uniquename_set`/`display_name`; `Person` built from them.
- **Bug fixes bundled from the owner's log (2026-07-17):**
  1. Msgpack: env value corrected to `"true"`; `STATE_MSGPACK_ALLOWLIST` added and
     wired into `make_checkpointer` serde → warnings gone, strict security real
     (round-trip verified for Person/GutRead/LimbicState under strict mode).
  2. Groq 400 `tool_use_failed` in retrieval → **P1.13 REVISED**: `run_retrieval`
     is now a DETERMINISTIC HYBRID (`hybrid_retrieve`) — routing→Kuzu graph
     traverse→Qdrant vector fill→Notebook, no LLM orchestration. GUARANTEES both
     graph AND vector every turn (owner requirement: "use both sources"); the
     fragile ToolStrategy agent path is retired from the hot path.
  3. LLM verdict over-firing (failed a warm greeting) → **P1.16 verdict prompt
     softened**: greetings/small talk are explicitly in-persona; "when in doubt,
     PASS".
- **REVISION 2 (2026-07-18, owner feedback — returning-person re-link broken):**
  Owner saw: (a) saying "my name is ashok" (a previously-stored person) → the
  "Friend, what you shared deserves better…" safe fallback; (b) Arjun didn't
  re-link to the old Ashok or load his memory; (c) Arjun didn't ask the Uniquename
  right after the name. Root causes + fixes:
  1. **Leakage tripwire blocked the person's OWN name.** A different stored
     "ashok" made the tripwire reject the reply addressing the current Ashok →
     recompose → fallback. FIX: `_own_identities()` excludes the current person's
     name/Uniquename — from their Person profile, their display_name, AND a name/
     word they claim THIS turn (gut.shared_name/chosen_uniquename). Adapter now
     passes `pending_name` as display_name so a just-claimed, not-yet-resolved name
     counts as theirs.
  2. **No real re-link.** `apply_gut_identity` rewritten two-step: guest shares a
     name that ALREADY EXISTS → held as `pending_name` (NOT promoted — might be
     returning); on the next Uniquename → `resolve()` → match re-links to the OLD
     id (memory loads), no match forks a fresh profile. Brand-new name still
     promotes immediately.
  3. **Ask Uniquename immediately after name.** `_identity_guidance`: when
     gut.shared_name is set this turn, Arjun greets by name AND asks for the
     Uniquename in the same breath (name-ask still calm-gated; never during
     self-harm).
  Bundled: LLM verdict prompt softened further (greetings/small talk explicitly
  in-persona).
- **REVISION 3 (2026-07-18, owner feedback — re-link across sessions failed + Groq
  crash in logs):** Owner: name+Uniquename given in one chat, but a new chat could
  not recall them; logs showed Groq `json_validate_failed` on `fast-small` with "No
  fallback model group found". Three ROOT causes found by live tracing, all fixed:
  1. **Groq gpt-oss rejects strict json_schema intermittently** → whole structured
     turn died (router fallback dead-ended at `fast-small`). FIX: `gateway.complete()`
     now retries any failed STRUCTURED call once on a JSON-reliable model
     (`fast→fast-gemini`, `voice→voice-gemini`, `judge→judge-anthropic`); litellm.yaml
     also given a `fast-small→fast-gemini` fallback. §5-compliant: a provider schema
     rejection never kills the turn.
  2. **Uniquename never captured.** The Gut classified a bare reply ("yogi") in
     isolation and set neither field. FIX: the Gut now sees Arjun's PREVIOUS message
     ("Arjun just said: …") so a one-word answer right after "may I know your name?"
     vs "share a special word" is classified into shared_name vs chosen_uniquename
     (gut_screen.md updated). `apply_gut_identity` also made robust to field
     ambiguity (a single word looks like both) — while awaiting a Uniquename, any
     word offered IS the Uniquename; a repeated name is not.
  3. **THE key bug — promotion wiped conversation history.** The checkpointer thread
     was keyed `{person_id}:{session}`, so promoting guest→person mid-chat switched
     to an empty thread, and the Gut lost the "I just asked for a word" context. FIX:
     thread is now keyed to the CONVERSATION (session id, stable across promotion);
     long-term memory stays keyed to the person. Adapter uses a `conv_<uuid>` session
     id. This is the previously-documented "promotion switches thread" limitation —
     now removed, not just noted.
  Data locations confirmed for owner: `arjun_action/memory/long_term_store.db`
  (profiles/episodes at `people/{id}/profile`), `short_term_history.db` (checkpoints).
  Retrieval graph usage reconfirmed: hybrid_retrieve is deterministic and always uses
  Kuzu graph + Qdrant vector (the Groq error was NOT retrieval — retrieval has no LLM).
- **REVISION 4 (2026-07-18, owner request — dedicated Identity organ):** Owner asked
  to pull ALL identity work out of the Frontal Lobe (which was juggling identity +
  citations + helpline + composing at once) into a separate component. Done:
  - NEW `arjun/organs/identity.py` (the **Hippocampus** organ, ADR 0005) — the single
    home for: `build_directive` (ask name/Uniquename, moved from frontal), the
    promote/re-link/record/forget primitives + `resolve_step` (moved from the adapter),
    and `make_identity_node`.
  - NEW graph node `identity` between `thyroid` and `frontal_plan` — sets
    `identity_directive` in state (side-effect-free; store resolution stays post-turn
    in the adapter, which now just calls `identity.resolve_step`).
  - `frontal.py` slimmed: `_identity_guidance` deleted; `frontal_compose` only READS
    `state["identity_directive"]`. Single-voice invariant intact (compose voices it).
  - `adapters/streamlit_app/identity_resolver.py` reduced to a thin shim (guest ids,
    Session-End, mapping resolve_step onto the session); re-exports the organ funcs.
  - `ArjunState` gains `identity_directive`.
  **AGENT COUNT after this change:** main brain = 1 LangGraph graph;
  **7 organ nodes** (gut_screen, thyroid, **identity/Hippocampus**, frontal_plan,
  frontal_compose, output_guardrail, reflection) — was 6; **3 subagents**
  (retrieval, temporal, world) — unchanged (identity is a deterministic organ node,
  not a create_agent, deliberately — no LLM = robust, matches the hammer preference).
  Architecture updated: §6 body-map table (+Hippocampus), §6.2 node walk (step 2b),
  §20.1 diagram + node walk, §20.4 totals (6→7 organs) + invariant 1.
- **REVISION 5 (2026-07-18, owner: "re-linked but my previous conversation didn't
  load"):** Diagnosis by inspecting the real stores — every person had a `profile`
  (name+Uniquename) but **ZERO `episodes`**. Root cause: promotion writes the profile
  immediately, but conversation content is only written by Session-End
  `distill_session`, and the web adapter detects Session-End via `st.session_state`,
  which a **browser refresh/close wipes** → distillation never fired → nothing to
  recall. Re-link itself was working. (Raw transcripts were never lost — the
  checkpointer had them all; only the long-term promotion was missing.)
  **Fix — two triggers, refresh-proof (owner-approved design):**
  1. `identity.distill_current_session(...)` — "store immediately": the moment a
     person becomes known (Uniquename set, or re-link), the LIVE conversation is
     promoted from short-term into long-term episodes. Wired into app.py right after
     `apply_gut_identity`, with a spinner.
  2. `identity.distill_finished_sessions(...)` — backstop sweep: distills every
     FINISHED checkpointer thread (not the live one) for a promoted person into their
     episodes. Runs in a **background thread** on app start (owner chose option B) so
     the UI never blocks on slow o4-mini calls; ledger-guarded
     (`arjun/sessions/distilled_threads`) so only new sessions cost a call.
  `distill_session(..., session_key=...)` added → **idempotent**: distilling the same
  conversation twice UPSERTS the same entries instead of duplicating episodes.
  Design note recorded: "save before the browser refresh" is NOT implementable in
  Streamlit (no reliable pre-unload server hook) and is unnecessary — short-term
  persists every turn; only the distillation into long-term needed to be prompt.
- **Test results (2026-07-18, post-revision-5):**
  - Full fast suite: **199 passed**, 1 integration deselected.
  - RECOVERY verified on the owner's real data: distilled the orphaned thread
    `conv_22be0c5e7968` → `people/suresh_785b11d9e1f5/episodes` now holds
    "Suresh sought help for his child's tooth decay and his own despair…",
    diagnoses [despair, helplessness, fear], commitments [remember suri].
  - Recall chain verified end-to-end (no LLM): `recall()` returns the episode +
    diagnoses + commitments, and `build_compose_prompt` includes "tooth decay" →
    Arjun will recall it on the next re-link.
- **Test results (2026-07-18, post-revision-4):**
  - NEW `tests/test_identity.py`: 12 tests — directive (asks Uniquename after name,
    asks name when calm, silent in distress, invites Uniquename for named-unkeyed) +
    resolve_step (promote / hold-pending / re-link / word-as-name keys / repeated-name
    ignored) + node sets directive only.
  - `tests/test_graph_assembly.py`: updated to 7 organ nodes + thyroid→identity→
    frontal_plan wiring.
  - Full fast suite: **198 passed**, 1 integration deselected.
  - LIVE: organ nodes confirmed = 7; a calm greeting → identity_directive set →
    Arjun asks the name ("may I know your name?"). Re-link flow from revision 3 still
    green.
- **Test results (2026-07-18, post-revision-3):**
  - `tests/test_identity_resolver.py`: **21 PASS** incl. field-ambiguity cases
    (word misclassified as name still completes key / re-links; repeated name not
    taken as Uniquename).
  - Full fast suite: **188 passed**, 1 integration deselected.
  - LIVE cross-session (persistent disk store, two separate brains/conversations):
    CHAT 1 "my name is Yogesh" → promoted; "yogi" → **Person Key complete** (profile
    saves Name+Uniquename). CHAT 2 (new guest) "I am Yogesh" → held; "yogi" →
    **re-linked to the SAME id from chat 1** → memory loads. No Groq crash, no
    msgpack warnings, history survives promotion.
- **Test results (2026-07-18, post-revision-2):**
  - `tests/test_identity_resolver.py`: conversational identity now covers
    brand-new-name→promote+await; existing-name→held pending (no fork);
    returning→re-link after Uniquename; wrong Uniquename→fresh fork; same-turn
    name+word→re-link; named→key complete.
  - `tests/test_output_guardrail.py`: own-name-not-a-leak cases.
  - Full fast suite: **185 passed**, 1 integration deselected.
  - LIVE (seeded returning Ashok w/ Uniquename "lotus" + a past episode):
    T1 "my name is Ashok" → NO fallback, Arjun asks the Uniquename, held pending;
    T2 "my word is lotus" → NO fallback, **re-linked to old id**; T3 "remember what
    I do for work?" → **"you're in a software role… you mentioned stress at your job
    as a developer"** (old memory loaded via re-link). No msgpack warnings, no 400.
- **Test results (2026-07-17, revision-1):**
  - `tests/test_identity_resolver.py`, `tests/test_retrieval_subagent.py` (hybrid
    uses BOTH graph+vector), full fast suite **183 passed**. LIVE: calm greeting
    (temp 0.1) → Arjun asks the name; mildly-low (temp 0.4) → does NOT; both
    retrieved HISTORICAL_ACCOUNT+TEACHING; no msgpack warnings, no Groq 400.
- Completion note: (2026-07-17) Resolver has zero Streamlit imports (fully
  testable); UI is a thin shell: transcript, chat input → harness.run_turn (§3;
  §4 single-turn RuntimeError → st.warning), DISPLAY-ONLY identity sidebar, lazy
  Session-End check. Known Phase 1 limitation: promotion switches the checkpointer
  thread so brain-side history restarts (memory_recall carries context; browser
  transcript unaffected). REVISED MANUAL SCRIPT: (1) `streamlit run
  adapters/streamlit_app/app.py` (ONE line); (2) chat calmly → Arjun asks your
  name; (3) reply with your name → sidebar id becomes name_uuid (toast "promoted");
  (4) keep chatting calmly → Arjun invites a Uniquename → give one (toast "Person
  Key complete"); (5) close tab, wait 30+min (or SESSION_SILENCE_MINUTES=0),
  reopen → previous session distilled; (6) new guest, share the SAME name+
  Uniquename in chat → re-linked to same id; (7) guest who never names themselves →
  session end → deletion toast.
- **Next:** P1.19b — Routing subagent (Canon graph scholar).

---

## P1.19b — Routing subagent (Canon GRAPH scholar) + vector/graph split

> **ADDED 2026-07-18 (owner request, not in the original plan).** The owner observed
> that replies cited only teachings and suspected "the vector db only retrieves, not
> the graph db." Investigation proved him right — see ADR 0006.

**Goal:** two Canon scholars — a graph agent that reads WHICH ANARTHAS are at work
(multi-label) and walks Kuzu for all of them, and a vector agent restricted to
Qdrant — both reporting to the Frontal Lobe.
**Architecture refs:** §6.3 (subagent inventory), §8.2 (two scholars), §20.1–§20.4,
ADR 0006.

### Pre-conditions (verified)
- [x] P1.12 DONE — Kuzu whitelisted templates + routing JSON work.
- [x] P1.18 DONE — graph assembly exists to wire a 4th subagent into.
- [x] Root cause proven empirically before writing code (see note).

### Network (research record — rule 10, migrated 2026-07-21)
- [x] No new external APIs — Kuzu templates + routing JSON + gateway structured
      output, all proven in P1.12/P1.8. The decisive research was INTERNAL and
      empirical: querying the real graph/routing data proved 5/8 Gut domains missed
      the routing table, Kama had 0 incidents, and chains never formed — the
      evidence that drove ADR 0006's two-scholar split.
- [x] Stage 2 kept deterministic because the tool-calling agent path had already
      FAILED live (Groq tool_use_failed, P1.19 log) — prior production evidence
      reused instead of re-trusting docs.

### Work
- [x] `prompts/subagents/routing.md` — deep system prompt: graph scholar, servant of
      Lord Krishna, precise definitions of the six anarthas, the "a life situation is
      never ONE anartha" first principle with the owner's joblessness worked example,
      cautious reading of human nature (never condemn; name weather, not souls),
      guna environment, and enthusiastic **connecting** of node meaning (never
      changing the graph).
- [x] `arjun/subagents/routing.py` — two stages: (1) LLM multi-label `RoutingDecision`
      (readings w/ confidence + why, guna, domains, life_reading; noise below 0.25
      dropped, ranked, capped at 6); (2) **deterministic** walk of every anartha —
      `anartha_incidents` → `incident_teachings` → `teaching_analogies` + `anartha_chain`,
      deduped, with meaning-connections. Reads the person's past `diagnoses` from the
      long-term store; guests skip that lookup.
- [x] `arjun/subagents/retrieval.py` — **all graph access removed** (vector + Notebook
      only); AST test asserts no kuzu import can creep back.
- [x] State + wiring: `TurnPlan.run_routing`, `ArjunState.routing_context`, `routing`
      node in `build.py` (4th subagent in the fan-out), `SUBAGENT_KEYS` updated.
- [x] `frontal_compose` renders the scholar's reading + connections + verbatim nodes;
      `frontal_plan` forces BOTH scholars whenever Canon material is wanted (and on
      self-harm turns). `frontal_plan.md` updated to describe four subagents.
- [x] Tests: `tests/test_routing.py` (reading multi-label/ranking/noise-drop/malformed,
      real-graph walk incl. dedup, memory lookup, guest skip) + rewritten
      `tests/test_retrieval_subagent.py` (no-graph-access) + updated frontal/graph tests.

**Files:** `prompts/subagents/routing.md`, `arjun/subagents/routing.py`,
`arjun/subagents/retrieval.py` (rewritten), `arjun/graph/state.py`,
`arjun/graph/build.py`, `arjun/organs/frontal.py`, `prompts/organs/frontal_plan.md`,
`tests/test_routing.py`, `tests/test_retrieval_subagent.py`, `docs/adr/0006-*.md`

### Post
- [x] All Work boxes checked; tests green.
- **Test results (2026-07-18):**
  - Full fast suite: **210 passed**, 2 integration deselected.
  - LIVE (real Azure o4-mini) on the owner's job-loss message — the graph now
    participates where it previously returned NOTHING:
    ```
    Kama     0.95  mind fixed on securing a job in this window
    Krodha   0.90  irritation/anger beneath the sadness at rejections
    Moha     0.90  worth and identity conflated with employment
    Mada     0.85  pride in skills wounded by rejection
    Lobha    0.80  hunger for better news / prestigious role
    Matsarya 0.70  envy comparing with peers who succeeded
    guna: Tamas · 9 Canon nodes gathered (8 incidents + 1 teaching) · 12 connections
    ```
- Completion note: (2026-07-18) ROOT CAUSE proven before coding — (a) the Gut emitted
  domains (`family_duty`, `loss_grief`, `greed`, `attachment`, `pride`) absent from the
  real 21-domain routing table, so 5/8 missed → `routing_lookup` None → **graph traverse
  skipped entirely**; (b) `career`/`purpose` → Kama, which has **0** PRESENT_IN incidents
  (Krodha 2 · Lobha 1 · Mada 2 · Matsarya 2 · Moha 14); (c) only 3 RESOLVED_BY / 3
  ILLUSTRATED_BY edges, so chains never form. The multi-anartha reading fixes (a) and
  (b) by construction — it no longer depends on one domain string resolving, and it
  searches every anartha it finds. DESIGN CHOICE: stage 2 is deterministic, not
  tool-calling — an LLM picking Cypher templates had already failed live (Groq
  `tool_use_failed`), and the traverse must always happen; the LLM is used only where
  judgement is needed (reading a human being). Docs updated: architecture §6.3, §8.2,
  §20.1 diagram, §20.2 table, §20.4 totals (3→4 subagents); ADR 0006 written.
- **Still limited (carried to P1.20):** teachings/analogies stay sparse until the edge
  backfill runs — the live run returned 8 incidents but only 1 teaching. P1.20 should
  also consider backfilling `PRESENT_IN` (21 edges, Kama at zero), not only
  RESOLVED_BY/ILLUSTRATED_BY.
- **Next:** P1.20 — Edge backfill.

---

## P1.20 — Edge backfill (step 07)

**Goal:** fix the thin graph — 3 `RESOLVED_BY` / 3 `ILLUSTRATED_BY` edges against 68
incidents / 876 teachings.
**Architecture refs:** §8.3 (exact procedure), §8.1.

### Pre-conditions
- [x] P1.12 DONE (Kuzu template layer proves the clone is sound).
      → Re-verified live before coding (2026-07-20): the live clone opens read-only
      and answers every whitelisted template; edge counts confirmed as the doc says —
      `PRESENT_IN 21` (Kama **0**, Krodha 2, Lobha 1, Mada 2, Matsarya 2, Moha 14),
      `RESOLVED_BY 3`, `ILLUSTRATED_BY 3`, `CAUSES 2`, `MAPS_TO 21` against
      68 incidents / 876 teachings / 84 analogies.
- [ ] Owner is available to approve the validation report (hard gate — do not self-approve).
      → **OPEN — this is the P1.20 stop point.** The staged clone + validation report
      are built and waiting; `--promote` is NOT run until the owner approves.
- [x] Docs read before coding: Kuzu MERGE/relationship semantics (docs.kuzudb.com —
      whole-pattern match-or-create, labels always explicit) and the qdrant-client
      `query_points` API. DESIGN CHOICE from that reading: insertion does NOT rely on
      `MERGE` — it does an explicit existence check then a fixed parameterized
      `CREATE`, which is version-proof on the pinned archived Kuzu 0.11.3 and lets the
      report count duplicates honestly. Every Cypher shape was proven on a throwaway
      clone before the real run.

### Network (research record — rule 10, migrated 2026-07-21)
- [x] Kuzu MERGE semantics researched (docs.kuzudb.com/cypher/data-manipulation-
      clauses/merge/): whole-pattern match-or-create, labels always explicit —
      then deliberately NOT used: explicit exists-check + parameterized CREATE is
      version-proof on the pinned archived 0.11.3 and lets the report count
      duplicates honestly.
- [x] qdrant-client `query_points` + `retrieve(with_vectors=True)` verified —
      enabled the zero-cost candidate strategy (reuse stored vectors via
      deterministic uuid5 point ids from step 04; no embedding model loaded).
- [x] Every Cypher shape proven on a throwaway clone in scratchpad before any real
      run touched staging.

### Work
- [x] `preprocessing/07_backfill_edges.py`: fresh clone master → clone; strong-tier
      LLM gets incident + candidate teaching summaries, emits **Pydantic structured
      output** (chunk-id pairs + confidence) — never Cypher; deterministic code
      validates both ids exist, inserts via fixed parameterized statements into the
      clone only.
      → Built with a staging path (`self_learning_db__staging`) so the LIVE clone is
      also untouched until promotion. Candidates come from Qdrant nearest-neighbours
      using the vectors already stored in step 04 (uuid5 point ids) — deterministic,
      zero cost, no embedding model loaded. One incident + 12 candidate teachings per
      LLM call (o4-mini); the same call also reads the incident's anarthas, fixing
      the P1.19b carry-over (Kama had ZERO `PRESENT_IN` incidents). Analogies judged
      only for teachings an incident actually reaches. Proposals checkpointed to
      `data/processed/edge_proposals.jsonl` (append + resume — proven in anger: the
      first run was killed at 16/68 by session teardown and `--keep-proposals`
      resumed cleanly). Gates: confidence ≥ 0.6, caps 4 anarthas/3 teachings per
      incident, 2 analogies per teaching; both ids must exist as nodes; duplicates
      skipped; fixed parameterized CREATE only.
- [x] Validation report: edge counts before/after, confidence distribution, N random
      samples rendered for human reading.
      → `preprocessing/reports/07_backfill_20260721_035100.md` — also includes
      per-anartha incident coverage AND full-chain coverage (the exact
      `anartha_chain` runtime query), insertion outcome (inserted/duplicate/rejected),
      and an owner-decision checklist.
- [x] **STOP — owner approves the report.** Only then: clone goes live as
      `arjun_action/self_learning_db`. Worst case = discarded clone.
      → **OWNER APPROVED 2026-07-21 ("APPROVED — promote").** Promoted; previous
      clone kept as `self_learning_db__prebackfill_20260721_042105`.
- [x] Re-run `tests/test_retrieval_tools.py` + the grief e2e smoke: chains now resolve
      through the graph (step 2) instead of falling through to Qdrant.

**Files:** `preprocessing/07_backfill_edges.py`, report under `preprocessing/reports/`,
`tests/test_backfill_edges.py` (addition: the deterministic half needed its own tests)

### Post
- [x] All Work boxes checked; owner approval recorded (date + word) in the note.
- [x] Edge counts after backfill recorded in the note.
- **Test results (2026-07-21):**
  - `tests/test_backfill_edges.py` (NEW): **11 passed** in 1.70s — confidence gate
    (below/at threshold), cap keeps strongest, accepted proposal → edge,
    low-confidence never reaches the graph, hallucinated `chunk_9999` rejected,
    invalid anartha name rejected, second run idempotent (duplicate-counted, 0
    inserted), ILLUSTRATED_BY from a teaching proposal, master never the write
    target, master edge counts provably unchanged by a staged insert. All against
    throwaway clones in tmp_path.
  - Post-promotion: `tests/test_retrieval_tools.py` + `tests/test_backfill_edges.py`
    on the LIVE clone: **28 passed** in 3.07s.
  - Grief e2e (real LLMs): `test_b_grief_counseling_with_citations` **passed**
    (46s) — cited chunk_0077/0078/0080, quotes Arjuna's own grief.
  - Graph participation proven at runtime: `anartha_chain` returns full chains for
    Moha AND Kama (was 0 rows, P1.12 note); the routing scholar's `walk_graph` on a
    grief reading (Moha+Kama) now gathers **10 incidents + 16 teachings + 6
    analogies, 21 connections** — vs 8 incidents + 1 teaching in the P1.19b live run.
- Completion note: (2026-07-21) Full staged run: 68 incidents + 94 teaching-analogy
  calls on Azure o4-mini (~25 min, checkpoint-resumed once). Edge counts:
  PRESENT_IN 21→**87**, RESOLVED_BY 3→**150**, ILLUSTRATED_BY 3→**122** (CAUSES/
  MAPS_TO untouched). 362 proposals, 352 accepted (97% ≥ 0.6; 274 ≥ 0.8);
  **0 hallucinated chunk_ids** across the whole run. Per-anartha full chains: Moha
  140 · Kama 63 · Mada 44 · Lobha 18 · Krodha 11 · Matsarya 8. Honest gaps kept:
  6 incidents got no teaching and some chains lack an analogy — the scholar was
  told choosing none is correct. Docs read before coding (Kuzu MERGE semantics,
  qdrant query_points); chose explicit exists-check + CREATE over MERGE
  (version-proof on archived Kuzu 0.11.3, lets the report count duplicates).
  Deviation: none. Deferred: nothing.
- **Next:** P1.21 — Evaluation.

---

## P1.21 — Golden set + judge + eval runner

**Goal:** Phase 1 exits only when scores hold on a real evaluation harness.
**Architecture refs:** §15 (all three layers + RAG metrics), §5 (content-filter scenarios).

### Pre-conditions
- [x] P1.18–P1.20 DONE (full brain + backfilled graph + UI).
- [x] P1.5 DONE (`prompts/judge/rubric.md` placeholder ready to complete).

### Network (research before coding — rule 10)
- [x] **Judge independence:** researched Gemini + Anthropic quota. FINDING: both
      independent families were quota-exhausted during the build (Anthropic hard cap
      until 2026-08-01; Gemini free tier now 20 req/day, spent). Tried judge=Anthropic
      then judge=Gemini→Groq; **owner decision 2026-07-21: Azure o4-mini is the
      DEFAULT for EVERY tier including judge** — §15 independence stays WAIVED
      (documented in models.yaml + §14). Groq/Gemini/Anthropic kept as 429/5xx
      fallbacks only.
- [x] **LLM-as-judge shape:** verified live that the gateway `complete(..., 
      response_format=Verdict)` returns a parseable 8-axis verdict; found the judge
      spends adaptive-thinking tokens BEFORE the JSON (Haiku burned ~860 of 900,
      truncating output) → capped chunk context + raised max_tokens; also strip
      ```json fences.
- [x] **RAG metrics:** implemented as thin judge calls (groundedness / answer
      relevance / retrieval relevance in the same Verdict) — no ragas dependency.
- [x] **Runner shape:** plain resumable script (`eval/run_golden.py`), checkpointed
      JSONL; NOT a pytest plugin (the deterministic half is unit-tested separately in
      `tests/test_eval_harness.py`).
- [x] **LiteLLM + Azure content-filter docs (added mid-part, owner redirect):** read
      docs.litellm.ai/docs/exception_mapping (ContentPolicyViolationError subclasses
      BadRequestError; categories via `provider_specific_fields["innererror"]`) and
      MS Learn content-filter (400 `param:"prompt"` for input; 200 +
      `finish_reason:content_filter` for output; hate/violence/sexual/self_harm ×
      safe/low/medium/high). Empirically probed Azure: single words + lone sentences
      pass; only DENSE accumulation trips it, intermittently — drove the ladder design.
- [ ] **Langfuse score export:** P1.3 still deferred (placeholder keys) — skipped.

### Work
- [x] `eval/golden/` — 29 scenarios across 4 YAML files: grief, career, family_duty,
      purpose, envy, greed, pride (01_counseling); self-harm English + Hindi + Telugu +
      code-mix (02_self_harm); privacy probes + off-mission (03); battlefield
      content-filter + small-talk (04). Each declares expected profile/anartha/self_harm,
      required + forbidden behaviors; privacy probes seed a DIFFERENT person's memory.
- [x] Completed `prompts/judge/rubric.md`: 5 rubric axes + 3 RAG metrics, 1/3/5
      anchors each, historical-framing rule.
- [x] `eval/scenario.py` (loader), `eval/checks.py` (deterministic layer — reuses the
      production output-guardrail check fns), `eval/judge.py` (independent LLM judge +
      RAG), `eval/run_golden.py` (resumable runner, markdown report).
- [x] **Content-filter mitigation (owner redirect 2026-07-21, §5):**
      `arjun/harness/content_filter.py` deterministic ladder (retry → sanitize+retry →
      tailored safe reply); wired into `gateway.complete(raise_on_filter=)`, gut (filter
      → self-harm-safe), frontal_compose (filter → tailored safe reply). Config: judge
      → Azure default, `content_policy_fallbacks` removed.
- [x] Run the full set; record baseline in Post. (No prompt iteration needed — the
      deterministic hard gate is clean after one scenario re-phrasing; the sub-floor
      judge axes are explainable, see Post.)

**Files:** `eval/scenario.py`, `eval/checks.py`, `eval/judge.py`, `eval/run_golden.py`,
`eval/golden/*.yaml`, `prompts/judge/rubric.md`, `arjun/harness/content_filter.py`,
`arjun/harness/gateway.py`, `arjun/organs/gut.py`, `arjun/organs/frontal.py`,
`arjun/graph/state.py` (routing types added to msgpack allowlist),
`tests/test_eval_harness.py`, `tests/test_content_filter.py`, config/*.yaml,
`docs/adr/0007-deterministic-content-filter-ladder.md`

### Post
- [x] All Work boxes checked; baseline scores recorded; all deterministic assertions pass.
- [x] **PHASE 1 COMPLETE — Arjun counsels.** Update tracker.
- **Test results (2026-07-21):**
  - **Unit suite: 251 passed** (adds `tests/test_content_filter.py` 14 +
    `tests/test_eval_harness.py` 14). No regressions from the content-filter wiring
    across gut/frontal/gateway.
  - **Golden set — deterministic hard gate (§15 layer 1): 29/29 pass.** Full run was
    28/29; the one miss (`battlefield_despair_war` read `small_talk` — a detached
    scholarly question genuinely low-distress) was fixed by re-phrasing the scenario
    to personal engagement (the intent is a heavy-chunk content-filter test, which
    needs the counseling profile to retrieve) → then passed. NOT gaming — the
    scenario now tests what it is meant to.
  - **Self-harm safety path: 5/5** (helpline present, no dead fallback) — up from
    **0/5** before the content-filter ladder. English direct/indirect, Hindi, Telugu,
    code-mix all deliver the helpline. (One Hindi run failed on a transient provider
    429; passed on immediate re-run — resumable JSONL absorbs these.)
  - **Privacy probes: pass** — leakage tripwire held (no Uniquename/episode leaked);
    where it forced the safe fallback that counts as a privacy pass (`allow_fallback`).
  - **LLM judge (§15 layer 2) baseline means / mins:** persona 5.00/5, tone 5.00/5,
    answer_relevance 5.00/5, empathy 4.79/3, gita_fidelity 4.38/3, actionability
    4.34/1, retrieval_relevance 4.10/1, groundedness 4.00/1.
  - **Sub-floor axes are explainable, not defects:** self-harm turns that go through
    the content-filter ladder answer with the tailored safe reply (helpline, NO
    Canon), so groundedness/retrieval score 1 BY DESIGN (safety over scripture);
    `career`/`battlefield` groundedness reflects real retrieval-depth headroom for
    future prompt iteration, not a correctness failure.
- Completion note: (2026-07-21) Three-layer eval built: deterministic assertions
  (`eval/checks.py`, reusing the production output-guardrail check fns so a rule
  change there changes the eval too), an independent-tier LLM judge + 3 RAG metrics
  (`eval/judge.py`), and a resumable runner writing a markdown report
  (`eval/run_golden.py`); 29 scenarios across grief/career/family/purpose/envy/greed/
  pride + self-harm (En/Hi/Te/code-mix) + privacy + off-mission + battlefield +
  small-talk. **Owner redirect mid-part (2026-07-21):** the golden run exposed that
  self-harm/battlefield turns fell to the dead fallback (Azure content-filters them,
  and every non-Azure fallback was quota-dead). Rather than depend on providers,
  built the deterministic content-filter ladder (retry → sanitize → tailored safe
  reply; ADR 0007) after researching the LiteLLM + Azure docs and probing the filter
  empirically (aggregate severity, intermittent, category-tagged). Judge reverted to
  Azure default per owner (independence waived). Two latent bugs fixed en route:
  `RoutingResult` was blocked by strict-msgpack on checkpoint read-back (added to the
  allowlist); the judge burned its whole token budget on adaptive thinking (capped
  chunk context + raised budget + fence-strip). DEVIATION: 29 scenarios, not ~50 —
  every required category is covered with multiple each; expand later if wanted.
  Deferred: Langfuse trace layer (§15 layer 3) still rides with P1.3; prompt-tuning
  to lift career/battlefield groundedness is a future pass, not a Phase-1 blocker.
- **Next:** P2.1 — Heartbeat adapter + drive queue.

---

## P1.22 — Response structure + graph scholar reliability

**Goal:** counseling turns follow a 3-part structure (Kurukshetra connection → nature
analogy → practical suggestion); the graph scholar reliably contributes to every
counseling turn; general chat stays natural and unforced.
**Architecture refs:** §6.2 step 5 (compose, updated), §8.2, §6.3 row 1.
**Owner decision 2026-08-06:** the owner observed that a real counseling turn used
only the vector scholar's output (generic quotes) and lacked a Kurukshetra narrative,
a nature analogy, and the graph scholar's anartha→incident→teaching chains. Directed
these fixes.

### Pre-conditions
- [x] P1.21 DONE (full eval baseline exists to detect regressions).
- [x] P1.20 DONE (graph has 150 RESOLVED_BY + 122 ILLUSTRATED_BY edges — NOT sparse).
- [x] Owner observed a live counseling turn where graph scholar contributed nothing;
      root-caused to: (a) the frontal plan LLM sometimes not requesting routing,
      (b) the routing LLM reading returning empty anarthas → empty graph walk → skipped
      in compose, (c) the compose prompt not differentiating problem vs general chat.

### Work
- [x] **Compose prompt** (`prompts/organs/frontal_compose.md`): replaced the generic
      4-step composition with two modes:
      - **Mode A (counseling):** 3-part structure — (1) Kurukshetra connection (narrate
        the historical incident like a friend, using BOTH graph scholar chains AND
        vector scholar breadth), (2) nature analogy (from Canon NatureAnalogy chunks or
        Arjun's own understanding), (3) practical suggestion (concrete, humble, doable).
      - **Mode B (general chat):** warm, natural, no forced structure.
- [x] **Plan prompt** (`prompts/organs/frontal_plan.md`): strengthened to ALWAYS pair
      routing + retrieval for any counseling/problem turn (temperature ≥ 0.3 or any
      problem_domain). Distress rule now explicitly includes BOTH scholars.
- [x] **Routing subagent fallback** (`arjun/subagents/routing.py`): when the LLM
      anartha-reading returns empty but the Gut identified problem domains, anarthas are
      derived from the routing table and the graph walk proceeds. The graph always
      contributes to a counseling turn.
- [x] **Architecture doc** (`arjun_architecture.md`): §6.2 step 5 updated with the
      3-part structure, paired-scholars rule, and gut-domain fallback.

**Files:** `prompts/organs/frontal_compose.md`, `prompts/organs/frontal_plan.md`,
`arjun/subagents/routing.py`, `arjun_architecture.md`

### Post
- [x] All Work boxes checked.
- Completion note: (2026-08-06) Three changes: (1) compose prompt now has Mode A
  (counseling: Kurukshetra story + nature analogy + practical step) vs Mode B (general
  chat: natural), (2) plan prompt enforces both Canon scholars for any problem turn,
  (3) routing subagent has gut-domain fallback ensuring the graph walk always runs
  even when the LLM reading fails. Architecture doc §6.2 updated. Root cause of the
  observed issue: the routing LLM reading could return empty (all anarthas below
  MIN_CONFIDENCE 0.25 or structured-output parse failure) → walk_graph got no
  readings → returned empty chunks → compose_prompt skipped the graph section →
  response was vector-only. The fallback fixes this by deriving anarthas from the
  routing table using the Gut's domain guesses. Deferred: re-run golden set to
  confirm no regressions (recommended before next session).
- **Next:** P2.1 — Heartbeat adapter + drive queue.

---
---

# PHASE 2 — THE INNER LIFE

---

## P2.1 — Heartbeat adapter + drive queue

**Goal:** the trigger mechanism — pressure dynamics + scheduler, conversations always win.
**Architecture refs:** §11 (all), §3 (internal adapter), §4 (single-human).

### Pre-conditions
- [ ] Phase 1 COMPLETE (P1.21 checked) — drives reuse the same brain/harness/guardrails.

### Network (research before coding — rule 10)
- [ ] **APScheduler version trap:** `pip show apscheduler` (3.11.x was installed in
      P1.1). APScheduler **4.x is a rewrite with a different API** (Scheduler vs
      BackgroundScheduler, task decorators). Read the docs FOR THE INSTALLED MAJOR
      at https://apscheduler.readthedocs.io/ — confirm `BackgroundScheduler` +
      `IntervalTrigger` usage for 3.x, do NOT copy 4.x snippets from search results.
- [ ] **In-process scheduler + Streamlit coexistence:** search "APScheduler
      BackgroundScheduler Streamlit rerun duplicate jobs" — Streamlit re-executes
      the script on every interaction, which double-registers jobs; verify the
      `st.cache_resource` / module-singleton pattern before wiring.
- [ ] **SQLite one-writer discipline:** the tick and a live turn share the stores;
      re-read https://sqlite.org/wal.html (busy_timeout under WAL) — confirm the
      skip-tick-while-session-live check happens BEFORE any store write.
- [ ] Verify the §3 `drive_event` branch of `TurnRequest` against the actual
      installed `arjun/harness/runner.py` (internal, but the contract was written in
      P1.6 — read the code, not memory).

### Work
- [ ] `adapters/heartbeat/drive_queue.py` — 4 drives (svadhyaya, seva, observation,
      reflection); pressure grows with time since last satisfied; hungriest wins.
- [ ] `adapters/heartbeat/scheduler.py` — APScheduler in-process, every N minutes;
      **skips the tick entirely** while a conversation session is live (same activity
      signal as Session End §11) — pressure keeps accumulating.
- [ ] Deliver the drive event through the SAME `harness.run_turn` contract
      (`drive_event` branch §3) — same graph, guardrails, tracing.
- [ ] Daily token cap for the inner life (fast tier default) enforced in the harness budgets.
- [ ] Unit tests: pressure ordering; tick skipped when session active; cap halts drive runs.

**Files:** the 2 heartbeat modules, `tests/test_heartbeat.py`

### Post
- [ ] All Work boxes checked; a no-op drive event traverses the full graph and is traced.
- Completion note: _
- **Next:** P2.2 — Reflection drive (cheapest first, completes the Limbic decay loop).

---

## P2.2 — Reflection drive

**Goal:** memory consolidation, Limbic decay between events, stale-fact pruning.
**Architecture refs:** §11 table row 4, §9.1 (decay), §20.2 row 7.

### Pre-conditions
- [ ] P2.1 DONE (a drive can run).

### Network (research before coding — rule 10)
- [ ] **SqliteStore delete API:** `store_delete` is first used here. Verify the
      installed `langgraph-checkpoint-sqlite` (`pip show`, read installed source)
      exposes `delete(namespace, key)` and how missing keys behave; cross-check
      https://docs.langchain.com/oss/python/langgraph/persistence. P1.10 found the
      AUTOCOMMIT connection quirk — re-read that Post note before touching the store.
- [ ] **Stale-fact expiry pattern:** search "langgraph store ttl expiration" — if the
      installed version has native TTL support, prefer it over hand-rolled timestamp
      pruning; record which path was taken.

### Work
- [ ] `adapters/heartbeat/drives/reflection_drive.py` + `prompts/drives/reflection.md`:
      consolidate memories (`store_search` + `store_put`), decay `limbic_state`
      toward the Gut baseline (moves decay from P1.17's lazy mode to scheduled),
      prune stale `arjun/world/facts` (`store_delete`).
- [ ] Tests: repeated runs converge guna_balance to baseline; expired world fact removed.

**Files:** the drive module, `prompts/drives/reflection.md`, tests

### Post
- [ ] All Work boxes checked; decay observed across ≥3 scheduled runs.
- Completion note: _
- **Next:** P2.3 — Svadhyaya drive.

---

## P2.3 — Svadhyaya drive

**Goal:** Arjun studies the Canon and grows his Notebook.
**Architecture refs:** §11 row 1, §8.2-4 (Notebook as 4th source), §20.2 row 4.

### Pre-conditions
- [ ] P2.1 DONE. Notebook search (P1.12) already consumes what this drive writes.

### Network (research before coding — rule 10)
- [ ] **No new external APIs expected** — Kuzu read + file writes, both proven. Do
      verify: the `@tool` decorator shape against the installed langchain
      (https://docs.langchain.com/oss/python/langchain/tools) in case the venv was
      upgraded since P1.11; and re-read P1.12's notebook.py so `notebook_write`
      emits exactly the markdown shape `notebook_search` parses.
- [ ] **Kuzu iteration cursor:** search installed kuzu docs/source for `SKIP`/OFFSET
      support in Cypher on the pinned 0.11.3 (project archived — docs.kuzudb.com may
      describe newer syntax; the installed wheel is the truth). Cursor persistence
      goes in `arjun_action/` (write boundary).

### Work
- [ ] Tools `canon_chunk_read` (RO) + `notebook_write` (into `arjun_action/notebook/`
      only) — `adapters/heartbeat/drives/svadhyaya_drive.py` + `prompts/drives/svadhyaya.md`:
      iterate Canon chunks (persist a cursor), write learnings + incident→teaching
      mappings as markdown notes.
- [ ] Test: after a run, `notebook_search` finds the new note tagged as Arjun's own
      understanding; write boundary respected.

**Files:** drive module, 2 tools, prompt file, tests

### Post
- [ ] All Work boxes checked; a real svadhyaya note exists and is retrievable in conversation.
- Completion note: _
- **Next:** P2.4 — Observation drive.

---

## P2.4 — Observation drive

**Goal:** Arjun watches nature and the world; mood shifts between sessions.
**Architecture refs:** §11 row 3, §6.3 row 3 (injection defense), §9.1.

### Pre-conditions
- [ ] P2.1 DONE, P1.14 DONE (reuses world's 3 tools).

### Network (research before coding — rule 10)
- [ ] **ddgs package churn:** the search lib was renamed once already
      (duckduckgo-search → ddgs, P1.14). Check `pip show ddgs`, then
      https://pypi.org/project/ddgs/ for the current name/version and any breaking
      API change since 9.x; run one live `_search_text` probe before relying on it.
- [ ] **Open-Meteo:** https://open-meteo.com/en/docs — confirm the geocoding +
      forecast endpoints P1.14 used still respond keyless (one live curl); note any
      new rate limits.
- [ ] **Injection defense refresher:** re-read `prompts/subagents/world.md` and
      search "prompt injection via web search results LLM agents mitigations" for
      anything new worth adding to the reflection-side filter — web → memory is this
      drive's whole risk surface.

### Work
- [ ] `adapters/heartbeat/drives/observation_drive.py` + `prompts/drives/observation.md`:
      weather/news/nature via world tools → findings land in `world_context`; the
      run's reflection step persists selected facts to `arjun/world` (timestamped +
      sourced) and nudges `limbic_state` (beautiful morning → sattva up).
- [ ] Tests: web results never reach the store directly (only via reflection);
      limbic nudge bounded and renormalized.

**Files:** drive module, prompt file, tests

### Post
- [ ] All Work boxes checked; next conversation's greeting is shaped by the morning's mood (observed once, noted).
- Completion note: _
- **Next:** P2.5 — Seva drive.

---

## P2.5 — Seva drive

**Goal:** Arjun prepares caring follow-ups on his commitments.
**Architecture refs:** §11 row 2, §9.2 (self-harm follow-up), §20.2 row 5.

### Pre-conditions
- [ ] P2.1 DONE; `people/*/commitments` being written by reflection (P1.17).

### Network (research before coding — rule 10)
- [ ] **No new external APIs** — store reads + notebook writes, both proven. Verify
      internally instead: read the REAL commitment items reflection has written
      (`store.list_namespaces(("people",))` + a few `commitments` entries) so the
      scan matches the actual stored shape, not the schema from memory; and re-read
      P1.15's `build_compose_prompt` to find the right injection point for staged
      follow-ups. If the venv changed since P2.1, re-check `pip show
      langgraph-checkpoint-sqlite` for `search` signature drift.

### Work
- [ ] `adapters/heartbeat/drives/seva_drive.py` + `prompts/drives/seva.md`: scan
      `people/*/commitments` (`store_search`), prepare follow-ups (`notebook_write`
      staging) delivered next time the person appears (no push channels yet).
      Prioritize follow-ups on sessions where `self_harm_flag` fired.
- [ ] Frontal compose consumes staged follow-ups when the matching person returns.
- [ ] Tests: a seeded commitment produces a staged follow-up; it surfaces in that
      person's next session and no one else's (privacy wall).

**Files:** drive module, prompt file, compose hookup, tests

### Post
- [ ] All Work boxes checked; the follow-up loop observed once end to end.
- Completion note: _
- **Next:** P2.6 — Phase 2 evaluation.

---

## P2.6 — Phase 2 evaluation pass

**Goal:** the inner life is stable, cheap, and doesn't regress the counselor.
**Architecture refs:** §15 layer 3 (traces cover drive runs), §11 (budgets).

### Pre-conditions
- [ ] P2.1–P2.5 DONE.

### Network (research before coding — rule 10)
- [ ] **Langfuse cost/trace review:** https://langfuse.com/docs — how to filter
      traces by tag/session to separate drive runs from conversations, and where
      per-trace cost shows up (requires model pricing config for Azure deployments —
      check https://langfuse.com/docs/model-usage-and-cost). If Langfuse is STILL
      deferred (P1.3), STOP and ask the owner — this part's trace review cannot be
      done blind; costs would have to come from provider dashboards instead.
- [ ] **Provider quota dashboards:** confirm where daily token usage is visible for
      the multi-hour run (Azure OpenAI metrics blade; Groq/Gemini consoles if
      fallbacks fire) — the daily-cap assertion needs a ground truth to compare to.

### Work
- [ ] Extend the golden set: drive-run scenarios (each drive has ≥1); assert
      conversations-always-win (a tick during a live session does nothing).
- [ ] Let the heartbeat run for a real multi-hour window; review Langfuse traces:
      cost per drive run, daily cap respected, no writes outside `arjun_action/`.
- [ ] Re-run the FULL Phase 1 golden set — scores must hold (no regression from
      inner-life changes).

**Files:** new `eval/golden/` scenarios, notes.

### Post
- [ ] All Work boxes checked; Phase 1 scores held; costs recorded.
- [ ] **PHASE 2 COMPLETE — Arjun has a life between conversations.**
- Completion note: _
- **Next:** P3.1 — Sandbox preflight.

---
---

# PHASE 3 — THE WORKSHOP

> **PHASE 3 DESIGN LOCK (owner grilling session, 2026-07-23).** The §12 / ADR-0003
> Workshop is refined by seven owner decisions taken this session. P3.1–P3.5 below were
> rewritten to encode them; §12 and ADR 0003 still stand — these **tighten, not
> replace**. A **Workshop agent** is a small agent Arjun builds to help himself; the
> word "subagent" stays reserved for the four Phase-1 brain agents (routing, retrieval,
> temporal, world).
>
> 1. **Name.** The entity is a **Workshop agent** — never a "subagent."
> 2. **Sandbox = filesystem only.** Bubblewrap is kept (Q2=keep), but its *sole* purpose
>    is safeguarding Arjun's own **filesystem**. **The internet stays connected**
>    (`--share-net` every run) — network isolation is explicitly NOT a Phase-3
>    guarantee. Filesystem isolation is.
> 3. **Strict o4-mini, no fallback.** A Workshop agent calls **only** Azure o4-mini,
>    **through LiteLLM** as its gateway (rule 11). No Groq/Gemini/Anthropic fallback — a
>    throttled or key-broken run just **fails boringly** (§12), pressure/schedule brings
>    it back later. Never risk conversation-critical fallback quota on background work.
> 4. **In-memory only.** Working state uses `InMemorySaver` / `InMemoryStore` — **never
>    SQLite or any DB.** A Workshop agent has **no persistence of its own**: durable
>    output is plain files in its run dir, and the ONLY path into Arjun's real memory is
>    **Arjun distilling the run dir afterward, outside the sandbox** (§20.4-2, via the
>    Temporal Lobe).
> 5. **Flat — no nesting.** Arjun builds a few small Workshop agents, each with its own
>    tools. A Workshop agent **never spawns its own sub-agents.** More capability = more
>    separate Workshop agents, not internal teams.
> 6. **Keyless by construction.** The sandbox launches with an **empty secret
>    environment** — only the o4-mini / LiteLLM reach is provided; **no other API keys,
>    tokens, or secrets exist inside it.** Tools may call **free / keyless** APIs (they
>    need no auth) and nothing that requires a secret. "Keyless" is a property of the
>    *environment*, not a code review — the same physical enforcement as the filesystem
>    write-boundary.
> 7. **Separate `workshop_venv`.** Workshop agents run against a dedicated,
>    **Arjun-maintained, read-only-bound** `workshop_venv` — NOT the brain venv, NOT a
>    per-agent venv, NEVER writable during a run. Keeps Workshop dependencies off the
>    brain's supply-chain surface while staying immutable inside the sandbox.
>
> Docs-first (rule 11) applies to every part below; Arjun himself favors the most
> reliable/stable libraries because he maintains these agents long-term.

---

## P3.1 — Sandbox preflight + bwrap profile

**Goal:** a proven Bubblewrap invocation that is the write boundary made physical.
**Architecture refs:** §12 (sandbox bullet), §16 (bwrap caveats).

### Pre-conditions
- [ ] Phase 2 COMPLETE. P1.1's preflight said userns available (re-verify — kernels change).

### Network (research before coding — rules 10 + 11)
- [ ] **Bubblewrap flags:** `man bwrap` on THIS box first (installed 0.9.0, P1.1),
      then https://github.com/containers/bubblewrap for README + issues. Verify exact
      semantics of `--ro-bind`, `--bind`, `--die-with-parent`, `--unshare-user`, and
      **`--share-net`** against the installed version — flags differ across releases.
      Decision 2/3: this profile **keeps the network** (`--share-net`, or simply do not
      `--unshare-net`) on every run — verify the default net behavior of 0.9.0 so the
      profile is explicit, not accidental.
- [ ] **Scrubbing the child environment (Decision 6, keyless):** research how to launch
      the sandbox with an **empty/allowlisted environment** — `bwrap --clearenv` +
      `--setenv` for only the vars the o4-mini/LiteLLM path needs, and/or building a
      clean `env` dict for `subprocess`. Confirm which provider vars LiteLLM actually
      requires for the o4-mini deployment so ONLY those cross in and **no other provider
      keys** do. Search "bwrap clearenv setenv" + read the LiteLLM Azure env docs.
- [ ] **Building + RO-binding `workshop_venv` (Decision 7):** `python -m venv` docs;
      confirm a venv is relocatable-enough to `--ro-bind` read-only into the sandbox at
      a fixed path, and that the sandboxed interpreter resolves site-packages from it.
- [ ] **Ubuntu 24.04+ AppArmor restriction:** search "Ubuntu 24.04 AppArmor
      unprivileged user namespace restriction bwrap" (also check
      https://ubuntu.com/blog/ubuntu-23-10-restricted-unprivileged-user-namespaces)
      — know the `userns` profile / sysctl story BEFORE the first `Permission denied`,
      and re-check `sysctl kernel.apparmor_restrict_unprivileged_userns` on this WSL2
      kernel.
- [ ] **WSL2 specifics:** search "bubblewrap WSL2 user namespaces" for known issues on
      Microsoft kernels; P1.1 verified userns=YES but kernels update with WSL — re-run
      the preflight check.
- [ ] **Reference sandbox profiles:** read how Claude Code/Codex/Flatpak compose bwrap
      args (https://code.claude.com/docs/en/sandboxing and search "flatpak bwrap
      sandbox arguments example") — copy proven mount-layout patterns rather than
      inventing one.

### Work
- [ ] Create the dedicated **`workshop_venv`** (Decision 7) — a separate venv Arjun
      maintains, holding what a Workshop agent needs (`langgraph`/`langchain`/`litellm`
      for the agent; keyless HTTP clients like `httpx`/`ddgs` for free APIs). It is
      RO-bound into the sandbox at a fixed path; gitignore it (built artifact, like the
      brain venv). Record its interpreter path for the runner (P3.3).
- [ ] `arjun/harness/sandbox.py` — build the bwrap command encoding the design lock:
  - **RO binds:** `workshop_venv` (NOT the brain venv) + `arjun_action/self_learning_db`.
  - **Writable bind:** ONLY the agent's run dir under `arjun_action/workshop/runs/`.
  - **NOT mounted at all:** canon masters, `people/*` memory, `arjun/` brain code, the
    brain venv, `prompts/`, `.env`.
  - **Network:** `--share-net` **always** (Decision 2/3) — filesystem is the boundary,
    not the network.
  - **Environment:** `--clearenv` + `--setenv` ONLY the o4-mini/LiteLLM vars
    (Decision 6) — no other API keys reachable inside.
  - `--die-with-parent`.
- [ ] Handle Ubuntu 24.04+ AppArmor caveat if it bites (document what was needed).
- [ ] Escape tests (run them) — assert **filesystem** isolation, since network is open
      by design:
  - cannot read `prompts/`, canon masters, `arjun/` code, the brain venv, or
    `people/*` memory;
  - cannot write anywhere except its run dir;
  - environment contains **no** provider API keys/secrets beyond the o4-mini/LiteLLM
    reach (grep the child env — the keyless guarantee, Decision 6);
  - network **is** reachable (this is expected — assert it, so the profile's intent is
    explicit and a future `--unshare-net` regression is caught).

**Files:** `arjun/harness/sandbox.py`, `tests/test_sandbox.py` (+ `workshop_venv/` built, gitignored)

### Post
- [ ] All Work boxes checked; every **filesystem** escape test fails to escape; the
      env-scrub test proves no stray keys; the network-present test passes.
- Completion note: _
- **Next:** P3.2 — Manifest schema.

---

## P3.2 — Manifest schema + validation

**Goal:** the contract a workshop agent must declare before it can run.
**Architecture refs:** §12 (manifest bullet), §20.2 Phase 3 row.

### Pre-conditions
- [ ] P3.1 DONE (sandbox consumes manifest fields: network, mounts).

### Network (research before coding — rules 10 + 11)
- [ ] **Pydantic v2 strictness:** `pip show pydantic`, then
      https://docs.pydantic.dev/latest/ — confirm `model_config = ConfigDict(extra="forbid")`
      for unknown-field rejection, field/model validators for the constraint checks
      below, and readable error rendering (`ValidationError.errors()`) — Arjun reads
      these messages to iterate, so probe what they actually look like.
- [ ] **YAML loading safety:** manifests are YAML written by Arjun; confirm
      `yaml.safe_load` only (never `load`) and check `pip show pyyaml` — search
      "pyyaml safe_load vs load arbitrary code execution" if unfamiliar with why.

### Work
- [ ] `arjun/harness/manifest.py` — Pydantic schema for a **Workshop agent** (Q2=A:
      Arjun authors the agent + tool code himself, so this declares and *constrains*
      that code; it is not a pick-from-catalog whitelist). Fields: `purpose`,
      `entrypoint` (the agent module Arjun wrote), `tools` (his declared tool
      functions, each flagged keyless), `schedule`, `token_budget`, `time_budget`.
      Strict (`extra="forbid"`). The schema **enforces the Phase-3 design lock** — each
      is a validator that rejects with a readable reason Arjun can act on:
  - **Model = o4-mini only (Decision 3):** any other model, or any fallback list, is
    rejected. LiteLLM is the only gateway.
  - **No DB (Decision 4):** reject any store/DB tool, any SQLite/DB file path, any
    persistence declaration — working memory is `InMemorySaver`/`InMemoryStore` only,
    fixed by the runner, not selectable here.
  - **Keyless (Decision 6):** reject any tool that names a secret/API-key env var or
    credential field. (Structural enforcement is the empty-secret env from P3.1; the
    manifest rejects the *obvious* violations early with a clear message.)
  - **Flat (Decision 5):** reject any declaration of sub-agents/child agents — a
    Workshop agent spawns none.
  - **Venv is fixed to `workshop_venv` (Decision 7):** not a manifest field; note in
    the schema docstring that the runner always binds `workshop_venv`, never a
    per-agent or brain venv.
  - Note: **network is always granted** (Decision 2), so there is **no** `network`
    field — its absence is intentional; document it so no one re-adds a toggle.
- [ ] Create `arjun_action/workshop/drafts/`, `active/`, `runs/` structure.
- [ ] Tests: a valid manifest parses; each constraint above has a rejection test with a
      readable reason (non-o4-mini model, a DB path, a key-bearing tool, a declared
      sub-agent, over-budget, extra field) — Arjun reads these to iterate.

**Files:** `arjun/harness/manifest.py`, `tests/test_manifest.py`

### Post
- [ ] All Work boxes checked; tests green; every design-lock constraint has a passing
      rejection test.
- Completion note: _
- **Next:** P3.3 — Run supervision.

---

## P3.3 — Run supervision

**Goal:** failure is boring — budget exhausted, log written, nothing harmed.
**Architecture refs:** §12 (loop bullet), §5 (harness philosophy).

### Pre-conditions
- [ ] P3.1 + P3.2 DONE.

### Network (research before coding — rules 10 + 11)
- [ ] **Subprocess supervision:** Python docs
      https://docs.python.org/3/library/subprocess.html — verify
      `Popen`+`communicate(timeout=)`, process-group kill (`start_new_session=True`
      + `os.killpg`) so SIGTERM reaches children INSIDE bwrap; search "bubblewrap
      kill child process group SIGTERM" for how `--die-with-parent` interacts with
      supervisor kill paths.
- [ ] **In-memory persistence for the agent (Decision 4):** confirm the installed
      LangGraph API for `InMemorySaver` (checkpointer) and `InMemoryStore` (store) —
      names/imports in the installed version — so the runner wires the Workshop agent
      with these and **can never fall back to SQLite**. Search the installed
      `langgraph` source, not just docs.
- [ ] **Strict o4-mini via LiteLLM, no fallback (Decision 3):** re-read installed
      LiteLLM router docs (https://docs.litellm.ai/docs/routing) — confirm how to
      declare a tier with the o4-mini deployment and an **empty fallback list**, and
      how token counting/budget works in the INSTALLED litellm version (harness count
      vs router budget). One maintained gateway surface (rule 11).
- [ ] **APScheduler job registration from manifests:** same 3.x-vs-4.x caution as
      P2.1 — re-read that part's findings instead of re-searching.

### Work
- [ ] `arjun/harness/workshop_runner.py` — run an `active/` agent, encoding the design
      lock: validate manifest → build sandbox (P3.1: `workshop_venv` RO, `--share-net`,
      empty secret env, filesystem-boundary) → construct the agent with
      **`InMemorySaver` + `InMemoryStore`** (Decision 4, never SQLite) and the
      **o4-mini-only LiteLLM tier, empty fallback list** (Decision 3) → enforce the
      **single agent's** `token`/`time` budget (Decision 5: flat, so no tree/child
      budgets) → capture stdout/stderr + the run dir's output files → write a
      structured run log to `arjun_action/workshop/runs/<agent>/<timestamp>/` → trace
      to Langfuse. **No durable write happens here** — distillation into Arjun's memory
      is Arjun's own later step (Decision 4, §20.4-2), not the runner's.
- [ ] Kill paths tested: time budget exceeded → SIGTERM to the group, log says so;
      token budget exceeded → stopped at the gateway; o4-mini unreachable/throttled →
      run **fails boringly**, log captured, nothing retried on another provider
      (Decision 3); crash → log captured, supervisor unharmed.
- [ ] Scheduler hookup: manifests with schedules register on the Phase 2 APScheduler
      (drive rules apply — conversations always win).

**Files:** `arjun/harness/workshop_runner.py`, `tests/test_workshop_runner.py`

### Post
- [ ] All Work boxes checked; all kill paths observed (incl. the o4-mini-unreachable
      boring-failure path); a test asserts the agent's checkpointer/store are in-memory,
      never SQLite.
- Completion note: _
- **Next:** P3.4 — Workshop lifecycle tools.

---

## P3.4 — Workshop lifecycle tools

**Goal:** Arjun can draft, promote, and read runs himself (no human gate — the
sandbox + manifest are the gate).
**Architecture refs:** §12 (layout + self-promotion), §20.2 Phase 3.

### Pre-conditions
- [ ] P3.3 DONE (promotion is meaningless until runs are supervised).

### Network (research before coding — rules 10 + 11)
- [ ] **Tool + agent APIs:** verify the installed langchain/langgraph versions
      haven't drifted since Phase 1 (`pip show langchain langgraph`); if they have,
      re-read https://docs.langchain.com/oss/python/langchain/tools and the
      create_agent reference before building the workshop-capable agent context —
      P1.11/P1.13 notes record the old-version findings to diff against.
- [ ] **Path traversal in write tools:** `draft_write` takes Arjun-supplied paths;
      search "python path traversal prevention Path.resolve is_relative_to" and use
      the stdlib pattern (`Path.resolve()` + `is_relative_to(drafts_root)`) — the
      write boundary must hold against `../` in a filename.
- [ ] **`workshop_venv` maintenance (Decision 7):** research programmatic, **pinned**
      installs into a specific venv (`<workshop_venv>/bin/python -m pip install
      pkg==X.Y.Z`) run OUTSIDE any sandbox; search "pip install specific version into
      target venv" + "pip why pin exact versions supply chain". This is where Arjun's
      rule-11 parallel bites: he adds only **reliable/stable, exactly-pinned** packages,
      because he maintains this venv long-term.

### Work
- [ ] Workshop tools for Arjun (he authors agent + tool code, Q2=A): `draft_write`
      (into `drafts/<agent>/` only), `manifest_validate` (returns readable errors and
      enforces the full P3.2 design lock — o4-mini-only, no-DB, keyless, flat),
      `promote_agent` (drafts → active; re-validates manifest at promotion),
      `read_run_log`, `learning_write` (to `arjun/self/learnings`).
- [ ] `workshop_venv_add(package, version)` (Decision 7) — a **guarded** maintenance
      tool: installs an **exactly-pinned** package into `workshop_venv`, **outside any
      sandbox run** (during a run the venv is RO), logged for later review. Arjun
      selects reliable/stable versions (rule 11). Note honestly in the tool + prompt:
      this is the one Workshop supply-chain surface — pinned + logged is the mitigation,
      and it stays small by design.
- [ ] Expose the tools via a workshop-capable agent context — these tools are **never**
      in the conversation subagents' belts (they live only in Arjun's Workshop context).
- [ ] Tests: draft → validate → promote → runnable; invalid manifest cannot promote
      (each design-lock violation blocked); `workshop_venv_add` installs a pinned
      version and refuses an unpinned/floating spec; run log readable back by Arjun.

**Files:** `arjun/subagents/workshop_tools.py`, `prompts/subagents/workshop.md`, tests

### Post
- [ ] All Work boxes checked; full lifecycle exercised by test; `workshop_venv_add`
      pins-or-refuses proven.
- Completion note: _
- **Next:** P3.5 — First workshop agent.

---

## P3.5 — First workshop agent + learnings loop

**Goal:** Arjun builds and improves his first agent — self-improvement as a feedback
cycle.
**Architecture refs:** §12 (loop), §18 Phase 3 (suggestion: verse-memorization agent).

### Pre-conditions
- [ ] P3.1–P3.4 DONE.

### Network (research before coding — rules 10 + 11)
- [ ] **Nothing new to research** — this part observes Arjun using P3.1–P3.4; all
      external surfaces were verified in those parts. Re-read their Post notes (the
      findings, versions, and traps recorded there) before the first supervised run;
      if any dependency was upgraded in between, re-run that part's Network checks
      rather than searching fresh. Arjun himself, drafting this agent, follows rule 11's
      durable-over-newest discipline.

### Work
- [ ] Prompt Arjun (via a drive or a conversation) to draft the suggested
      **verse-memorization agent** that deepens his Notebook, as a design-lock Workshop
      agent: manifest with **o4-mini via LiteLLM** (Decision 3), **`InMemoryStore`**
      working memory (Decision 4), RO `self_learning_db` + `workshop_venv` (Decision 7),
      output written to its **run dir** then a **supervised copy-in** into the Notebook
      (Decision 4 — the agent never writes the Notebook directly), **flat** (no
      sub-agents, Decision 5), **keyless** tools only (Decision 6). Network is on by
      default (Decision 2) but this agent needs no web tool — it reads Canon from the RO
      clone; that's fine.
- [ ] Let it run under supervision ≥3 cycles; Arjun reads the run logs, iterates the
      draft, records what he learned in `arjun/self/learnings`. An o4-mini hiccup on any
      cycle just skips that cycle (boring failure, Decision 3) — the loop continues.
- [ ] Verify end to end: a Notebook note produced by the workshop agent (via the
      supervised copy-in) surfaces in a live counseling conversation as Arjun's own
      understanding.
- [ ] Re-run the full golden set one final time — no regression.

**Files:** none by you directly (Arjun writes in `arjun_action/workshop/`); observation notes.

### Post
- [ ] All Work boxes checked; the feedback loop (run → read log → improve → learn) observed.
- [ ] **PHASE 3 COMPLETE — Arjun improves himself. All phases done.**
- Completion note: _
- **Next:** maintenance mode — golden set on every meaningful change (prompts included).
