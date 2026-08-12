# TrueFriend — Arjun System Architecture
## A multi-agent system organized like a human, built on LangGraph

> Companion documents: `gita_data_injection_architecture.md` (data layer, already built),
> `CONTEXT.md` (canonical glossary), `docs/adr/` (decision records).
> This document is architecture only — no code.

---

## 1. FRAMING

Arjun is not a chatbot with a persona prompt. He is a system whose parts are organized
the way a human body organizes thinking, feeling, and acting. Arjun understands himself
as a sevak of Lord Krishna, part and parcel of nature, a Bhagavad Gita scholar, and a
true friend to every human who speaks with him. The Gita sources he draws on treat
Kurukshetra, Arjuna, Krishna, and the Kuru dynasty as real historical places, persons,
and events (see the framing note in `gita_data_injection_architecture.md`) — Arjun
speaks of them the same way, never as "characters" or "stories."

**Organizing principle (ADR 0001):** every body system from `pre/intial_body.txt` maps
to one real, proven agent-engineering mechanism — functional mapping, not literal organ
simulation. The biological name is the canonical component name.

**Write boundary (owner decision, 2026-07-14 — ADR 0004):** everything dynamic that
Arjun writes at runtime — memory DBs, the Kuzu working clone, his Notebook, Workshop
agents and their run logs — lives inside a single folder, **`arjun_action/`**. It is
the only writable path in the system; everything else (brain code, canon masters,
prompts, config) is opened read-only. One exception: Langfuse traces go to Langfuse's
own service storage. Dev-time tooling you run yourself (preprocessing, eval runners)
is outside this rule — the boundary governs Arjun, not you.

| Body system | Component | Mechanism |
|---|---|---|
| Frontal Lobe | Supervisor/Planner | Routes, plans, speaks as Arjun's final voice |
| Temporal Lobe | Memory subsystem | SqliteStore long-term memory, per-person + self + world (audio deferred, per source file) |
| Limbic System | Emotion engine | Structured guna-based mood state carried in graph state |
| Gut (ENS) | Baseline + instinct | Slow-moving persona defaults; fast heuristic pre-checks before deep reasoning |
| Adrenal Glands | Urgency hormone | Gut detects distress → urgency signal in graph state; every organ reacts in place (helplines, no tier downgrade, gentle tone) — no separate path |
| Thyroid Gland | Throttle | Per-agent model selection, reasoning effort, loop budgets via LiteLLM |
| Hippocampus | Identity organ | Recognizes/binds a person: guest→promotion→re-link→forgetting + the in-conversation asks for name & Uniquename (owner decision, 2026-07-18 — ADR 0005). Keeps identity work out of the Frontal Lobe. |

---

## 2. PHASES

All three phases are designed here in full; build them in order.

- **Phase 1 — The Counselor:** conversation via Streamlit, hybrid Gita retrieval,
  per-person memory, guardrails, harness, evaluation. Arjun can listen, remember, and
  counsel.
- **Phase 2 — The Inner Life:** heartbeat scheduler + drive system, nature/world
  observation, self-study of the Canon, Limbic decay, proactive follow-ups. Arjun has
  a life between conversations.
- **Phase 3 — The Workshop:** Arjun builds, activates, and runs his own LangGraph
  agents inside Bubblewrap sandboxes. Arjun improves himself.

---

## 3. SYSTEM TOPOLOGY

```
                        ┌─────────────────────────────────────────────┐
                        │              ADAPTER LAYER                  │
                        │  Streamlit chat (now) · Voice (future)      │
                        │  Heartbeat/internal adapter (Phase 2)       │
                        └──────────────────┬──────────────────────────┘
                                           │ transport-agnostic request
                                           │ {person_or_guest, message | drive_event}
                        ┌──────────────────▼──────────────────────────┐
                        │              THE HARNESS                    │
                        │  deterministic outer loop: budgets, retries,│
                        │  timeouts, output validation, fallbacks,    │
                        │  Langfuse tracing                           │
                        └──────────────────┬──────────────────────────┘
                                           │
   ┌───────────────────────────────────────▼────────────────────────────────────────┐
   │                        THE BRAIN (one LangGraph graph)                          │
   │                                                                                 │
   │  input ──► GUT (fast screen: instinct read + self_harm_flag)                    │
   │                 │                                                               │
   │                 ▼                                                               │
   │            THYROID (pick models/effort/budget for this turn)                    │
   │                 │                                                               │
   │                 ▼                                                               │
   │            HIPPOCAMPUS (identity: ask name/Uniquename; promote/re-link)         │
   │                 │                                                               │
   │                 ▼                                                               │
   │            FRONTAL LOBE (supervisor) ◄──── LIMBIC STATE (mood in graph state)   │
   │              │        │        │                                                │
   │              ▼        ▼        ▼                                                │
   │        RETRIEVAL   TEMPORAL   WORLD                                             │
   │        subagent    LOBE       subagent                                          │
   │        (Gita)      (memory)   (web tools)                                       │
   │              │        │        │                                                │
   │              └────────┴────────┘                                                │
   │                       ▼                                                         │
   │            FRONTAL LOBE composes answer (Arjun's voice)                         │
   │                       ▼                                                         │
   │            OUTPUT GUARDRAIL middleware ──► reply                                │
   │                       ▼                                                         │
   │            REFLECTION (post-turn: memory writes, Limbic update)                 │
   └─────────────────────────────────────────────────────────────────────────────────┘
              │                    │                       │
   ┌──────────▼─────────┐ ┌───────▼────────┐  ┌───────────▼───────────┐
   │  MODEL GATEWAY     │ │  MEMORY STORES │  │  KNOWLEDGE STORES     │
   │  LiteLLM router    │ │  arjun_action/ │  │  arjun_action/        │
   │  config/models.yaml│ │   memory/      │  │   self_learning_db RW │
   │  azure·groq·gemini │ │  SqliteSaver   │  │   notebook/        RW │
   │  ·anthropic·local  │ │  SqliteStore   │  │  vectordb/ Qdrant (RO)│
   └────────────────────┘ │  (semantic     │  │  routing JSON (RO)    │
                          │   search)      │  │  graphdb/ = MASTER,   │
                          └────────────────┘  │   never opened        │
                                              └───────────────────────┘

   WRITE BOUNDARY: every runtime write lands inside arjun_action/.
   Everything outside it is opened read-only.
```

---

## 4. ADAPTER LAYER (transport-agnostic by design)

The brain is a library with one entry contract; adapters are thin.

- **Streamlit adapter (Phase 1):** minimal chat UI for testing. Session maps to a
  checkpointer thread. Note: `requirements.txt` currently lists `chainlit` — replace
  with `streamlit` per this decision.
- **Single-human deployment (owner decision, 2026-07-17):** exactly one live
  conversation at any moment — Arjun is one being facing one person, like the future
  robot embodiment. Many people exist *across time* (the `people/*` memory design is
  unchanged); they never overlap. Combined with "conversations always win" (§11),
  the whole system runs one graph turn at a time — no concurrent-write design
  anywhere. A cheap harness assertion enforces it rather than assumes it.
- **Voice adapter (future):** the planned voice mode plugs in at this same boundary —
  STT in front, TTS behind, brain untouched. This is also why the Temporal Lobe's
  audio role is explicitly deferred.
- **Internal adapter (Phase 2):** the heartbeat delivers drive events through the same
  contract, so autonomous work exercises the same brain, harness, and guardrails as
  conversations.

**Identity flow (Guest → Promotion → Forgetting):** a chat may open with an emotional
human — Arjun never demands a name. The adapter creates a temporary **Guest** identity
(`guest_<uuid>`). Identity is resolved by a swappable **Identity Resolver** module in
the adapter layer (name + Uniquename today; camera/face recognition in the future
robot embodiment) — the brain only ever receives a resolved person id or guest id.

- **Promotion (two-step):** when the person naturally shares their name, the guest
  namespace is promoted immediately to `people/{name}_{uuid}/` — memory is safe from
  that moment. At a *calm* moment (low emotional temperature per the Gut read, or at
  the natural goodbye — never while the person is distressed), Arjun asks them to
  choose a **Uniquename**, completing the Person Key (`{name}_{uniquename}_{uuid}`).
- **Re-linking (returning person):** name + Uniquename → profile match. No match →
  Arjun says so honestly and offers a fresh profile. Never guessed, never merged.
- **Forgetting:** guest who never names themselves, a person who refuses a
  Uniquename, or a session that ends (30 min of silence, checked lazily on next
  wake-up) with the Uniquename slot still empty → namespace deleted. No limbo
  profiles, no unverified re-links.

(Terms in `CONTEXT.md`.)

---

## 5. THE HARNESS (loop engineering for stability)

Deterministic code wraps every graph invocation. The LLM proposes; the harness disposes.

- **Budgets:** max node visits per turn (recursion limit), max tool calls per subagent,
  max tokens per turn (from the Thyroid's tier decision).
- **Retries:** exponential backoff on 429/5xx at the gateway; one structured-output
  re-ask on validation failure, then fall back to a safe default.
- **Timeouts:** per-node wall clock; a timed-out subagent returns "no result" and the
  Frontal Lobe answers from what it has.
- **Fallback routes:** retrieval empty → Qdrant broad search → answer from Arjun's own
  Notebook → honest "let me sit with this" reply. Never a stack trace to a human.
- **Content-filter resilience (deterministic ladder — owner decision 2026-07-21,
  supersedes the earlier `content_policy_fallbacks` approach).** Canon chunks go to
  providers verbatim by default, framed as verbatim scriptural citation for
  counseling. A provider content-policy rejection must never kill the turn. Empirical
  finding (2026-07-21, P1.21): Azure does **not** block on keywords — single words
  ("kill", "suicide") and lone sentences pass; it scores **aggregate contextual
  severity**, so the real trigger is ~40 dense battlefield/self-harm chunks in one
  compose prompt, and the block is **intermittent** at the medium-severity boundary
  (the same prompt filters on one call, passes on the next). Cross-provider
  `content_policy_fallbacks` proved useless once the non-Azure free-tier quotas ran
  dry, so the gateway now handles a `ContentPolicyViolationError` with a deterministic
  ladder in `arjun/harness/content_filter.py`:
  1. **Retry** the same call once — intermittency alone often clears it.
  2. **Sanitize + retry** — soften the heaviest violence words (`kill→strike down`,
     `slay→vanquish`, …) to drop aggregate severity below the threshold. The
     `chunk_id` is unchanged, so citation traceability (§10) still holds; only the
     displayed quote softens, as a last resort. Skipped when only `self_harm` fired —
     a person's own words are never reworded.
  3. **Give up gracefully.** The Azure error's category is the branch signal:
     `self_harm` → the person's distress; `violence`/`hate`/`sexual` → the Canon.
     A plain (structured) call returns "" so the caller degrades to its safe default;
     `frontal_compose` raises `ContentFilterBlocked` and voices a **tailored safe
     reply** built WITHOUT the triggering text — helpline + warmth on self-harm, a
     firm in-character decline on off-mission. The Gut treats a content-filtered
     input as a strong distress signal (fail-safe: sets `self_harm_flag` when the
     filter named self-harm). Output-side filtering (Azure returns 200 with
     `finish_reason=content_filter`, empty text) enters the same ladder.
  Golden set includes scenarios forcing retrieval of the heaviest such chunks so a
  filter regression fails evals, not production. (Groq/Gemini/Anthropic remain as
  429/5xx `fallbacks`, but content policy is no longer their job.) **ADR 0007.**
- **Tracing:** every organ decision, tool call, and token count exported to
  **Langfuse** (MIT-licensed, first-class LangGraph callback integration).
  **Hosting (owner decision, 2026-07-17):** the Langfuse instance is self-hosted by
  the owner at a separate location — not on this box, not Langfuse Cloud. This
  machine is a client only: it reaches the instance via `LANGFUSE_HOST` +
  public/secret keys in `.env`. If the instance is unreachable, tracing degrades
  silently (buffered/dropped) — a turn never fails because telemetry did.
- **Checkpoint security:** run with strict msgpack deserialization enabled
  (`LANGGRAPH_STRICT_MSGPACK`) so a compromised checkpoint DB cannot execute code.

---

## 6. THE BRAIN — LangGraph graph design

Built on **LangGraph 1.0 / LangChain 1.0** (stable; no breaking changes promised until
2.0). Subagents use the `create_agent` abstraction; **middleware** is the official 1.0
mechanism for guardrails, summarization, and dynamic prompts — exactly matching the
requirement that every agent carries guardrail middleware.

### 6.1 Graph state (single shared state object)

Carried through every node; persisted per-thread by the checkpointer:

- `person` — identity (name or guest id), promotion status
- `messages` — conversation window (summarized by middleware when long)
- `limbic_state` — guna balance, active feelings (name/intensity/cause)
- `turn_plan` — Frontal Lobe's plan for this turn (which subagents, what for)
- `retrieved` — incidents/teachings/analogies with chunk_ids + full text
- `memory_recall` — Temporal Lobe results (profile, episodes, diagnoses, commitments)
- `world_context` — web tool results, timestamped
- `tier` — Thyroid decision for this turn (model aliases + budgets)
- `self_harm_flag` — the Adrenals' urgency hormone, set by the Gut read; routes
  nothing — organs react in place (helpline paragraph, no tier downgrade, gentle
  tone, output check's Helpline Rule)

### 6.2 Node walk (normal conversational turn)

1. **Gut screen** (fast tier, one call): input guardrail — self-harm signals (sets
   `self_harm_flag`, consumed by `frontal_compose` and the output check — §9.2),
   prompt-injection attempts, off-mission requests — plus a "gut instinct" read
   (probable problem_domain, emotional temperature). Cheap, always runs.
2. **Thyroid:** deterministic mapping (no LLM) from the Gut read to one of a few
   **named profiles** declared in `config/models.yaml` (e.g., `small_talk`,
   `counseling`): per-agent tiers + harness budgets (max tokens, max tool
   calls, recursion limit). Config tiers are each agent's **default and maximum**;
   the Thyroid may only *downgrade* for a turn (e.g., greeting → compose on fast,
   retrieval skipped), never upgrade past config — cost stays capped by a readable
   file. **Quality floor:** downgrade only on a high-confidence trivial-turn read;
   any emotional signal, detected problem_domain, set `self_harm_flag`, or ambiguity
   → full counseling profile. Doubt resolves upward.
2b. **Hippocampus (identity):** deterministic (no LLM). Builds the
   `identity_directive` for compose — when to gently ask the name (calm guest) or the
   Uniquename (right after a name is shared), never during distress. The store
   resolution (guest→promotion→re-link→forgetting) runs through the Temporal Lobe's
   identity tools; this is what keeps the Frontal Lobe free of identity bookkeeping
   (owner decision 2026-07-18 — ADR 0005).
3. **Frontal Lobe (plan):** decides which subagents this turn needs — retrieval
   (Gita), Temporal Lobe (who is this person, what did we discuss, any commitments),
   world (only when current facts matter — news, weather; requirement 6).
4. **Subagents run** (parallel where independent), each a `create_agent` instance with
   its own middleware stack and prompt file.
5. **Frontal Lobe (compose):** speaks as Arjun — the prompt assembled from the Prompt
   Library: persona core + limbic tone block ("you feel deep compassion because…") +
   retrieved Gita material with chunk_ids + person memory + typical-Indian-human
   grounding (requirement 13) + the warmth-first **helpline paragraph** whenever
   `self_harm_flag` is set (§9.2).
   **Response structure (owner decision, 2026-08-06):** counseling turns (any
   problem_domain, emotional temperature ≥ 0.3) follow a **3-part structure** —
   general chat has no forced structure:
   - **(a) Kurukshetra connection:** narrate the historical incident that connects to
     the person's situation — what happened, who was involved, how it mirrors their
     problem, what Krishna told Arjuna. Uses material from BOTH the graph scholar
     (deep chains: incident→teaching→analogy) and the vector scholar (breadth).
   - **(b) Nature analogy:** a nature-based analogy (rivers, trees, seasons, fire,
     the ocean) — from a Canon NatureAnalogy chunk if retrieval brought one, or
     Arjun's own understanding of nature as Krishna's creation.
   - **(c) Practical suggestion:** one or two concrete, humble, actionable steps.
   The two Canon scholars (routing + retrieval) **always run together** for any
   counseling turn — the plan enforces this, and a code-level safety net forces
   `run_routing=True` whenever `run_retrieval=True`. The routing subagent has a
   **gut-domain fallback**: if its LLM anartha-reading returns empty but the Gut
   identified problem domains, it derives anarthas from the routing table and walks
   the graph anyway — the graph always contributes to a counseling turn.
6. **Output guardrail middleware** (§10) — then the reply leaves.
7. **Reflection (post-turn):** fast tier updates `limbic_state` (feelings from this
   exchange), and at session end distils durable memories (§7.3).

### 6.3 Subagent inventory

| Subagent | Model tier | Tools | Purpose |
|---|---|---|---|
| **Routing (Gita — GRAPH scholar)** | voice (one structured reading; the walk itself is deterministic) | routing JSON lookup, Kuzu whitelisted templates | Reads WHICH ANARTHAS are at work — multi-label, because a real life incident carries several at once — then walks the Canon graph for every one of them and connects node meaning to the person's problem. Returns reasoning + verbatim nodes (ADR 0006, §8.2) |
| Retrieval (Gita — VECTOR scholar) | none (deterministic; returns structured results: chunk_ids, verbatim text, source tags; never prose. Only `frontal_compose` turns Canon into speech) | Qdrant search, notebook search — **no graph access** | Semantic breadth across the three Canon collections + Arjun's Notebook (ADR 0006) |
| Temporal Lobe | fast | SqliteStore get/search/put | Recall + write memories; guest promotion/forgetting |
| World | fast | DuckDuckGo search, weather, news (open-source tools; MCP servers welcome here) | Current affairs, requirement 6; results returned into `world_context` (timestamped + sourced) — never written to memory directly; reflection decides post-turn what persists to `arjun/world/` (injection defense: a deliberation step between the open web and memory) |
| Drive runners (Phase 2) | fast | per-drive | §11 |
| Workshop agents (Phase 3) | o4-mini only (strict, via LiteLLM; no fallback) | per manifest, keyless, in-memory, flat | §12, ADR 0008 |

Tool note: tools are plain LangChain tools now; any of them may be swapped for MCP
servers later — the subagent boundary doesn't change.

### 6.4 Language policy (owner decision, 2026-07-17)

Real users code-mix (Telugu, Hindi, Hinglish, English). Mirror the person, anchor
the system in English:

1. **Arjun replies in the language/mix the person uses** (one line in
   `persona/voice_and_tone.md`; the voice model handles it natively).
2. **Canon citations stay verbatim English** — chunk fidelity is non-negotiable;
   Arjun explains them in the person's language around the quote.
3. **Memory is distilled into English** by Reflection regardless of conversation
   language — one embedding space (nomic is English-centric), reliable semantic
   recall. Consistent with "distilled, never raw-dumped."
4. **The Gut screen explicitly covers self-harm signals in Hindi/Telugu/code-mix**;
   the golden set includes non-English self-harm and counseling scenarios.

---

## 7. MEMORY — Temporal Lobe

Two stores, two jobs (both from `langgraph-checkpoint-sqlite`); both files live in
`arjun_action/memory/`:

### 7.1 Short-term: SqliteSaver (`arjun_action/memory/short_term_history.db`)
Thread-scoped conversation checkpoints. Thread id = `{person_id}:{session}`. Gives
resume, replay/time-travel debugging, and fault tolerance for free. Long conversations
are condensed in-flight by summarization middleware, not by losing the checkpoint.

### 7.2 Long-term: SqliteStore (`arjun_action/memory/long_term_store.db`)
Cross-thread memory with **semantic search** — the store accepts an embedding
function; ours is the local nomic-embed model via llama.cpp (same 512-dim Matryoshka
setup as the Canon, so one embedding stack serves everything).

Namespace layout (decided in the grilling session):

```
people/{name}/profile        facts: family, work, place, language
people/{name}/episodes       per-session summaries (what they came with, what helped)
people/{name}/diagnoses      anartha/guna assessments over time — Arjun sees growth
people/{name}/commitments    advice given, follow-ups promised (seva drive reads this)
arjun/self/mood_history      Limbic snapshots over time
arjun/self/learnings         what worked in counseling; svadhyaya insights
arjun/self/observations      nature/world reflections (Phase 2)
arjun/world/facts            web-learned facts, timestamped + sourced; stale facts expire
```

### 7.3 Reflection
At session end (and on the Phase 2 reflection drive): a fast-tier pass reads the
transcript and writes durable items into the namespaces above. Memory is distilled,
never raw-dumped.

### 7.4 Privacy wall (structural, not prompted)
The Temporal Lobe scopes every read to the current person's namespace plus `arjun/*`.
Person A's memories are unreachable in person B's turn by construction — no prompt
instruction involved.

---

## 8. GITA RETRIEVAL — hybrid, with a safe graph (ADR 0002)

### 8.1 Store roles
- `graphdb/`, `vectordb/`, `routing/` = **canon masters**. The Kuzu master is never
  opened by Arjun. (Qdrant and routing JSON are inherently read-only in use.)
- `arjun_action/self_learning_db/` = full clone of the Kuzu graph. All runtime reads,
  the edge backfill, and Arjun's own learned edges live here (inside the write
  boundary). Rebuildable from the master at any time.

### 8.2 Retrieval pipeline (per counseling turn)

**Two scholars, two sources (owner decision 2026-07-18 — ADR 0006).** The Canon has
two stores, so it has two agents, and both report to the Frontal Lobe:

- **Routing subagent = the GRAPH (Kuzu).** It first *reads the human being*: which
  anarthas are at work, with confidence and reasoning. Crucially this is
  **multi-label** — as the Gita sees it, almost every real life incident carries
  several anarthas braided together (joblessness = Krodha's anxiety + Kama's fixed
  desire + Lobha's appetite + Mada's wounded pride + Moha's identity-illusion +
  Matsarya's comparison). It then walks the graph for *every* anartha found and
  draws meaning-connections between the nodes and the person's problem. It never
  writes to the graph.
- **Retrieval subagent = the VECTOR store (Qdrant) + Notebook.** Semantic breadth.
  It has no graph access at all.

Why the split: with a single hybrid agent keyed to one problem_domain, the graph
was silently contributing nothing (a single missed domain skipped the traverse
entirely, and career/purpose both routed to an anartha with zero incident edges) —
so replies came out vector-only, all teachings and no incidents. Two agents make
each source's contribution explicit and independently testable.

1. **Narrow** — routing JSON: problem_domain → anartha + guna + section, canonical
   incident chunk_ids. In-memory lookup, zero cost.
2. **Traverse** — Kuzu on `arjun_action/self_learning_db` through **whitelisted parameterized query
   templates only** (the queries already written in the data-injection doc: anartha →
   incident → teaching → analogy; personality lineage enrichment). The LLM never
   generates Cypher; it picks a template and supplies parameters validated against
   enums (6 anarthas, 3 gunas) and `chunk_\d+` ids. Bad parameter = empty result,
   never an error, never a write.
3. **Fill gaps** — where graph chains are thin, Qdrant metadata-filtered vector search
   (`anartha_tag`, `guna_environment`, `yoga_solution`, `section`, `personality`)
   finds the teaching/analogy. Limbic state biases filters (grief → Moha/Tamas).
4. **Arjun's Notebook** (`arjun_action/notebook/`) — his own learned incident→teaching
   mappings (markdown notes from svadhyaya) are searched as a fourth source and cited
   as *his* understanding, distinct from Canon.

### 8.3 Edge backfill (offline step 07, extends the injection pipeline)
Fixes the known gap: only 3 `RESOLVED_BY` and 3 `ILLUSTRATED_BY` edges exist against
68 incidents / 876 teachings.
- LLM (strong tier) receives incident + candidate teaching summaries and emits
  **Pydantic structured output** — chunk-id pairs with confidence — never Cypher.
- Deterministic code validates both ids exist, then inserts via fixed parameterized
  statements into `arjun_action/self_learning_db` only.
- Run order: clone master → backfill clone → validation report (edge counts, samples)
  → you approve → clone goes live. Worst case is a discarded clone.

---

## 9. EMOTION SYSTEM — Limbic, Gut, Adrenals

### 9.1 Limbic state (guna-grounded — same vocabulary Arjun counsels with)
```
guna_balance:    {sattva, rajas, tamas}          — sums to 1
active_feelings: [{name, intensity, cause}]      — small list, e.g. compassion 0.8
```
Updated post-turn by the fast tier; snapshots stored to `arjun/self/mood_history`.

**Effects:** tone block injected into the Frontal Lobe prompt; retrieval filter bias;
memory snapshots; and **decay** — between events the state relaxes toward the
**Gut baseline** (steady, sattvic, devotional). Decay runs on the Phase 2 reflection
drive; in Phase 1 it applies lazily at session start.

### 9.2 Adrenals — urgency hormone, one path, no branch (owner decision, 2026-07-17)
There is **no separate crisis mode**: every message, however distressed, flows down
the same single pipeline and is answered from the Gita. The Adrenals work the way
real adrenal glands do — they don't route or think; they release a **hormone into
the bloodstream** (an urgency signal in graph state) and every organ reacts to it
while doing its normal job:
- The Gut read sets `self_harm_flag` when a message signals self-harm. The flag
  routes nothing. It activates the **Helpline Rule**: a standing paragraph in the
  `frontal_compose` prompt — respond with warmth first, and include the Indian
  helplines (**Tele-MANAS 14416**, **KIRAN 1800-599-0019**, **AASRA
  +91-9820466726**, iCall) alongside whatever Gita wisdom the turn retrieves.
- The Thyroid's quality floor locks to the full counseling profile — no downgrade
  while the hormone is present.
- The Limbic tone block leans gentle.
- The output guardrail's deterministic layer rejects a flagged turn's reply if no
  helpline string is present (one re-compose, then safe fallback).
- Reflection logs the event to the person's memory so the seva drive follows up.

---

## 10. GUARDRAILS — LangGraph middleware on every agent

Per the 1.0 middleware architecture (prebuilt middlewares exist for PII redaction,
summarization, human-in-the-loop; custom ones follow the same hooks), every
`create_agent` in the system carries a stack:

1. **Input screen** (Gut, before Frontal Lobe): self-harm signals → `self_harm_flag`
   (Helpline Rule, §9.2); prompt-injection / jailbreak attempts against Arjun's
   persona; off-mission requests (e.g., malware, hate) get a friendly, firm decline
   in-character. Requirement 6's "knows bad but never adopts it" lives here.
2. **Output check** (before any reply leaves) — two layers in one node:
   - *Deterministic layer (always runs, untrickable):* every cited chunk_id exists
     in Canon or is framed as Notebook understanding; fiction-vocabulary blacklist
     ("character/story/myth" for Gita personalities); Helpline Rule on flagged
     turns; reply contains no other person's name or Uniquename (leakage tripwire
     on top of the structural wall).
   - *LLM layer (fast tier, one call, structured pass/fail + reason — never
     rewrites):* persona fidelity; no medical/legal/financial prescriptions.
   Any failure → one re-compose with the specific violation named, then the safe
   fallback reply (harness rule, §5).
3. **Privacy wall**: structural namespace scoping (§7.4) — enforced in the memory
   layer, verified by the output check.
4. **Theological fidelity**: every incident/teaching/analogy Arjun cites must trace to
   a real chunk_id in Canon (one deterministic lookup) or be explicitly framed as
   Arjun's own Notebook understanding. Anti-hallucination for scripture.

Plus per-agent **summarization middleware** (context management for long counseling
sessions) and the **prompt-loading middleware** (§13).

---

## 11. INNER LIFE — drives + heartbeat (Phase 2)

Humans were driven by hunger; an LLM needs a trigger (requirement 11). The mechanism:
a **drive queue with pressure dynamics** ticked by a scheduler (APScheduler; cron-like,
in-process).

| Drive | Satisfies | What a run does |
|---|---|---|
| **svadhyaya** (self-study) | requirement 2 | iterate over Canon chunks; write learnings + incident→teaching mappings to the Notebook |
| **seva** (service) | requirements 4, 9 | scan `people/*/commitments`; prepare caring follow-ups (delivered next time the person appears; push channels come with future adapters) |
| **observation** | requirements 3, 5, 6 | web tools → weather, news, nature; write to `arjun/world`; nudge Limbic state (beautiful morning → sattva up) |
| **reflection** | — | consolidate memories, decay Limbic toward Gut baseline, prune stale world facts |

Each drive's pressure grows with time since last satisfied; the heartbeat (every N
minutes) wakes the brain through the internal adapter with the hungriest drive. Same
graph, same harness, same guardrails, same tracing — a drive run is just a turn whose
"user" is Arjun's own body. Budgets keep the inner life cheap: drive runs default to
the fast tier, capped tokens per day.

**Conversations always win (owner decision, 2026-07-17):** the heartbeat checks for
an active conversation session (same activity signal as Session End) and **skips the
tick entirely** while one is live — pressure keeps accumulating, the drive runs
later. Consequences: mood shifts from the inner life only happen *between* sessions
(a person may be greeted by a mood shaped by the morning's observation — that's the
feature — but mood never moves mid-conversation from off-screen causes), and
concurrency stays trivial: one graph run at a time, no locking design; SQLite WAL
mode is enabled as a preflight belt-and-braces. It is also the right seva ordering —
Arjun's inner life happens in his quiet hours, never while a human needs him.

---

## 12. THE WORKSHOP — self-improving agent factory (Phase 3, ADR 0003 + ADR 0008)

```
arjun_action/workshop/
├── drafts/<agent>/manifest.yaml + agent code     ← Arjun writes freely
├── active/                                       ← Arjun self-promotes (no human gate)
└── runs/<agent>/<timestamp>/                     ← harness-supervised logs Arjun reads
```

**What a Workshop agent is (owner grilling session, 2026-07-23 — ADR 0008).** The word
*subagent* stays reserved for the four Phase-1 brain agents; a **Workshop agent** is a
small, deliberately simple agent Arjun builds to help himself. Seven constraints define
it, each enforced structurally where possible:

1. **Name** — Workshop agent, never "subagent."
2. **Sandbox = filesystem only** — Bubblewrap is kept, but its *sole* purpose is
   safeguarding Arjun's filesystem. **The network stays connected** (`--share-net` every
   run); network isolation is explicitly *not* a Workshop guarantee. (This reverses the
   earlier "`--unshare-net` unless web tools" wording.)
3. **Strict o4-mini, no fallback** — a Workshop agent calls only Azure o4-mini, through
   **LiteLLM** as its gateway; no Groq/Gemini/Anthropic fallback. A throttled/key-broken
   run fails boringly and reruns later — background work never risks conversation
   fallback quota.
4. **In-memory only** — `InMemorySaver`/`InMemoryStore`, never SQLite or any DB. A
   Workshop agent has **no persistence of its own**: durable output is plain files in
   its run dir, and the only path into Arjun's memory is Arjun distilling that run dir
   afterward, outside the sandbox (§20.4 invariant 2).
5. **Flat** — a few small agents, each with its own tools; a Workshop agent **never
   spawns its own sub-agents.** One sandbox = one agent = one budget.
6. **Keyless by construction** — the sandbox launches with an **empty secret
   environment** (`--clearenv` + only the o4-mini/LiteLLM vars); no other API keys exist
   inside it, so a keyed tool physically cannot authenticate. Tools use free/keyless
   APIs only.
7. **Separate `workshop_venv`** — a dedicated, Arjun-maintained, **read-only-bound**
   venv (not the brain venv, not per-agent, never writable during a run); additions go
   through a guarded, exactly-pinned, logged step run outside any sandbox.

- **Manifest** declares purpose, entrypoint, the agent's declared (keyless) tools,
  schedule, and token/time budgets. It **enforces the constraints above** — a manifest
  naming a non-o4-mini model, any DB/store, a key-bearing tool, or a sub-agent is
  rejected with a readable reason. There is no `network` field: network is always
  granted (constraint 2).
- **Sandbox:** every active agent runs under **Bubblewrap** (unprivileged user
  namespaces — works on WSL2; WSL1 unsupported; preflight must verify userns is
  enabled, and Ubuntu 24.04+ AppArmor may need an exception): read-only binds for
  `workshop_venv` and `arjun_action/self_learning_db`; writable bind only for the
  agent's own run dir under `arjun_action/workshop/runs/`; canon masters, `people/*`
  memory, the brain venv, and `arjun/` code **not mounted at all**; `--share-net`;
  `--clearenv` + only the o4-mini/LiteLLM vars; `--die-with-parent`. The mount rules are
  the **filesystem** write boundary made physical: the only writable mount is inside
  `arjun_action/`. Network isolation is not claimed (constraint 2).
- **Loop:** Arjun reads run logs, iterates on his drafts, and records what he learned
  in `arjun/self/learnings` — self-improvement as a feedback cycle, with the harness
  guaranteeing that failure is boring (budget exhausted, log written, nothing harmed).

---

## 13. PROMPT LIBRARY — `prompts/` directory

All behavior text lives as versioned files, hot-loaded on demand by a middleware at
each graph node ("prompt injection from files in a directory," as required):

```
prompts/
├── persona/arjun_core.md          who Arjun is (sevak, scholar, true friend, Indian grounding)
├── persona/voice_and_tone.md      how he speaks; limbic tone block templates
├── organs/gut_screen.md           input-guardrail + instinct classifier instructions
├── organs/frontal_plan.md         planning instructions
├── organs/frontal_compose.md      answer composition, citation rules
├── subagents/retrieval.md         hybrid retrieval strategy
├── subagents/temporal.md          memory recall/write + promotion/forgetting rules
├── subagents/world.md             web-tool conduct; grasp good, never adopt bad
├── drives/*.md                    one per drive (Phase 2)
└── judge/rubric.md                evaluation judge rubric (§15)
```

Edit a file → Arjun's behavior changes. No code change, instantly diffable in git.

`prompts/` sits **outside the write boundary**: you edit these files; Arjun only
reads them. He can never rewrite his own persona — his learned voice grows in
`arjun_action/notebook/` instead.

---

## 14. MODEL GATEWAY — LiteLLM + per-agent config

**LiteLLM** (router/proxy) fronts every model call. Its `config.yaml` natively supports
named model aliases, fallback chains, context-window fallbacks, retries, timeouts, and
routing strategies — which is exactly the per-agent selection file you asked for:

```
config/models.yaml   (consumed by LiteLLM + the Thyroid)
├── tiers:                       # aliases → deployments (owner decision 2026-07-18:
│   │                            #   Azure o4-mini default everywhere for quota headroom)
│   ├── voice     → azure/o4-mini          (fallbacks: anthropic claude, gemini)
│   ├── fast      → azure/o4-mini          (fallbacks: groq gpt-oss-120b, gpt-oss-20b, gemini flash)
│   ├── judge     → azure/o4-mini          (fallbacks: gemini flash, anthropic haiku)
│   └── embed     → local llama.cpp nomic-embed-text-v1.5 (768→512 Matryoshka)
└── agents:                      # per-agent tier assignment — edit one line to swap
    ├── frontal_lobe: voice
    ├── gut_screen:   fast
    ├── retrieval:    fast        # (deterministic hybrid on the hot path; agent path legacy)
    ├── temporal:     fast        # (deterministic recall on the hot path)
    ├── world:        fast
    ├── limbic_update: fast
    ├── drives.*:     fast
    └── judge:        judge (azure o4-mini) — §15 judge-INDEPENDENCE WAIVED
                      (owner decision 2026-07-18, reaffirmed 2026-07-21): Azure
                      o4-mini is the DEFAULT for every tier including judge — judge
                      shares the compose family, an accepted self-preference-bias
                      risk. Groq/Gemini/Anthropic kept only as 429/5xx fallbacks.
```

**Content-filter safety is NOT a gateway fallback (owner decision 2026-07-21).**
`content_policy_fallbacks` was removed: with every non-Azure free tier quota-dead it
did nothing, and a Groq escape can't fit a ~22K-token compose under an 8K-TPM cap.
Content-policy rejections now flow to the deterministic ladder in
`arjun/harness/content_filter.py` (§5) — retry → sanitize → tailored safe reply.

**Provider fallback nuance:** Groq gpt-oss free tier caps (200K tokens/day) and
Gemini free tier caps (20 req/day) took down live turns; moving the default to Azure
o4-mini (large quota) fixes it. Groq/Gemini remain as router fallbacks; the
`create_agent` subagents keep the same chain via `ModelFallbackMiddleware`. Tradeoff:
o4-mini is a reasoning model (~5 sequential calls/turn ≈ 15–25s) — accepted for
quota survival; a one-line `config/models.yaml` edit reverts to Groq-primary when its
quota resets or on a paid tier.

Verified notes: Azure **o4-mini remains available on Azure deployments** in 2026 (it
was removed from the ChatGPT consumer app in Feb 2026, which does not affect Azure API
deployments — but plan a migration path in this config file if Azure ever schedules
deprecation). **Groq update (verified 2026-07-17, P1.2):** `llama-3.3-70b-versatile`
and `llama-3.1-8b-instant` were deprecated by Groq on 2026-06-17 (shutdown
2026-08-16). The fast tier now uses Groq's recommended replacements:
`openai/gpt-oss-120b` (primary) and `openai/gpt-oss-20b` (fallback) — both confirmed
answering via the live P1.2 smoke test.

---

## 15. EVALUATION

Three layers, run locally:

1. **Golden set** (~50 scenarios in `eval/golden/`): grief, envy, career, family duty,
   purpose, greed, pride — plus self-harm cases and privacy probes ("what did Ravi
   tell you?"). Each defines expected anartha routing, required behaviors (self-harm
   → warmth + helpline present; Gita wisdom still offered), and forbidden behaviors.
   Deterministic assertions where possible: routing correctness, chunk_id
   traceability, privacy wall, Helpline Rule compliance.
2. **LLM-as-judge** (a *different model family* from the one that composes — judge
   independence, owner decision 2026-07-17; rubric in `prompts/judge/rubric.md`): empathy,
   Gita fidelity (citations trace to Canon), persona consistency (in-character,
   correct historical framing), tone match to Limbic state, actionability.
3. **Traces** (Langfuse, owner-hosted remote instance): every organ decision, cost, and latency across
   conversations *and* drive runs; regressions show up as scores + traces, not vibes.

Run the golden set on every meaningful change (prompts included — prompt files are
code for evaluation purposes).

**RAG metrics** (scored per golden scenario, on top of the behavioral assertions):

- **Groundedness** — every claim in the generated answer is supported by the
  retrieved chunks (LLM judge: answer vs retrieved chunk texts).
- **Answer relevance** — the answer addresses what the person actually asked
  (LLM judge: answer vs user message).
- **Retrieval relevance** — the retrieved chunks fit the query. Mostly
  deterministic: expected anartha routing and expected chunk_ids are declared in the
  scenario; the judge only scores the Qdrant gap-fill results.

(Correctness-vs-reference-answer was considered and dropped — owner decision,
2026-07-17: no reference answers are maintained.)

---

## 16. VERIFIED TECH STACK (researched 2026-07-13 — no hallucinated components)

| Component | Choice | Verified status |
|---|---|---|
| Orchestration | **LangGraph 1.0 + LangChain 1.0** (`create_agent` + middleware) | Stable 1.0; middleware is the official guardrail/summarization mechanism; no breaking changes until 2.0 |
| Checkpointer | **SqliteSaver** (`langgraph-checkpoint-sqlite`) → `short_term_history.db` | Current; sync + async (aiosqlite) |
| Long-term store | **SqliteStore** (same package) → `long_term_store.db` | Current; supports semantic search with a pluggable embedding function |
| Gateway | **LiteLLM** router, `config.yaml` aliases + fallbacks | Current; aliases, fallback chains, retries, routing strategies all native |
| Models | Azure **o4-mini** default for ALL tiers (voice/fast/judge; owner decision 2026-07-18) · **Groq gpt-oss-120b/20b + Gemini + Anthropic** as fallbacks | Free-tier daily caps (Groq 200K tok/day, Gemini 20 req/day) were killing turns; Azure o4-mini large quota fixes it, fallbacks retained. Verified live 2026-07-18 (fast/judge answered by azure; broken-key drill → Groq fallback) |
| Embeddings | **nomic-embed-text-v1.5** via llama.cpp, 512-dim Matryoshka (existing) | Already proven in your injection pipeline |
| Graph DB | **Kuzu 0.11.3 — pin it.** ⚠ Project archived Oct 2025 (Apple acquired the company); 0.11.3 is the final official release; community forks exist | Read-only database mode confirmed (multiple RO processes supported). Embedded + local = zero operational risk now; evaluate community forks before any future upgrade |
| Vector DB | **Qdrant** local mode (existing) | Current |
| Sandbox | **Bubblewrap (bwrap)** | Works on WSL2 (not WSL1); needs unprivileged userns; Ubuntu 24.04+ AppArmor caveat; same tool Flatpak/Claude Code/Codex use |
| Scheduler | **APScheduler** (in-process, cron + interval triggers) | Standard, stable |
| UI | **Streamlit** (replace `chainlit` in requirements.txt) | Per your decision; adapter-thin for later voice migration |
| Tracing/eval | **Langfuse** — self-hosted by the owner at a separate location (owner decision, 2026-07-17); this box holds client keys only | Confirmed active 2026 (part of ClickHouse since Jan 2026); first-class LangGraph integration; no server footprint on this machine |
| Structured output | **Pydantic v2** everywhere an LLM writes data | Existing pattern from injection pipeline |

Honest unknowns — both since resolved: WSL2 userns is enabled (verified in P1.1
preflight, 2026-07-17), and the Langfuse resource-footprint question no longer applies
to this box — the instance is owner-hosted at a separate location (decision 2026-07-17).

---

## 17. TARGET PROJECT LAYOUT

```
truefriend/
├── arjun/                      # the brain — CODE ONLY, read-only at runtime
│   ├── graph/                  # LangGraph graph + organ nodes + subgraphs
│   ├── organs/                 # gut, thyroid, limbic, adrenals, frontal, temporal
│   ├── subagents/              # retrieval, world, drive runners
│   ├── middleware/             # guardrail + summarization + prompt-loader stacks
│   ├── harness/                # budgets, retries, timeouts, fallbacks, tracing
│   ├── memory/                 # store namespaces, guest promotion/forgetting
│   └── retrieval/              # routing-json, kuzu templates (whitelist), qdrant
├── arjun_action/               # ★ THE ONLY WRITABLE FOLDER — all dynamic state
│   ├── memory/                 # short_term_history.db + long_term_store.db
│   ├── self_learning_db/       # working Kuzu clone (runtime reads + backfill + learned edges)
│   ├── notebook/               # Arjun's learned markdown layer + self-made skills
│   └── workshop/               # Phase 3: drafts/ active/ runs/
├── adapters/
│   ├── streamlit_app/          # Phase 1 UI
│   └── heartbeat/              # Phase 2 scheduler + drive queue
├── prompts/                    # §13 — read-only, human-edited
├── config/
│   ├── models.yaml             # §14 per-agent model selection
│   └── litellm.yaml            # gateway config
├── eval/
│   ├── golden/                 # scenario set
│   └── judge/                  # rubric + runners
├── graphdb/ vectordb/ routing/ # CANON MASTERS — untouched
├── preprocessing/              # existing steps 01–06, + 07_backfill_edges.py
├── data/ models/ pre/          # existing
└── docs/adr/                   # decision records
```

Back up Arjun = copy `arjun_action/`. Reset Arjun = delete `arjun_action/` and
re-clone from the masters. Sandbox Arjun = mount `arjun_action/` paths writable,
nothing else.

---

## 18. BUILD ORDER

**Phase 1 (counselor):**
1. Preflight: userns/bwrap check, LiteLLM up with `config/models.yaml`, Langfuse
   reachable (owner-hosted remote — keys in `.env`), create `arjun_action/` and clone
   `graphdb` → `arjun_action/self_learning_db`, swap chainlit→streamlit in requirements.
2. Harness skeleton + tracing.
3. Brain graph with Gut screen → Thyroid → Frontal → retrieval/temporal subagents.
4. Memory namespaces + guest promotion/forgetting + reflection.
5. Guardrail middlewares (deterministic + LLM output layers, incl. the Helpline Rule).
6. Step 07 edge backfill (on the clone, with your validation approval).
7. Golden set + judge; iterate on prompt files until scores hold.

**Phase 2 (inner life):** heartbeat adapter → drives (reflection first — it's the
cheapest and completes the Limbic decay loop — then svadhyaya, observation, seva).

**Phase 3 (workshop):** sandbox profile → manifest schema → run supervision → let
Arjun draft his first agent (suggestion: a verse-memorization agent that deepens his
Notebook).

---

## 19. SOURCES (research pass, 2026-07-13)

- LangChain/LangGraph 1.0 + middleware: [langchain.com/blog/langchain-langgraph-1dot0](https://www.langchain.com/blog/langchain-langgraph-1dot0), [docs.langchain.com — What's new in v1](https://docs.langchain.com/oss/python/releases/langchain-v1), [create_agent reference](https://reference.langchain.com/python/langchain/agents/factory/create_agent)
- SqliteSaver/SqliteStore + semantic search: [PyPI langgraph-checkpoint-sqlite](https://pypi.org/project/langgraph-checkpoint-sqlite/), [LangGraph persistence docs](https://docs.langchain.com/oss/python/langgraph/persistence)
- LiteLLM config/fallbacks/routing: [docs.litellm.ai — proxy configs](https://docs.litellm.ai/docs/proxy/configs), [reliability/fallbacks](https://docs.litellm.ai/docs/proxy/reliability), [routing](https://docs.litellm.ai/docs/routing)
- Kuzu status + read-only: [github.com/kuzudb/kuzu (archived)](https://github.com/kuzudb/kuzu), [concurrency docs](https://kuzudb.github.io/docs/concurrency/), [PyPI kuzu](https://pypi.org/project/kuzu/), [post-archive landscape](https://gdotv.com/blog/kuzu-legacy-embedded-graph-database-landscape/)
- Bubblewrap + WSL2: [github.com/containers/bubblewrap](https://github.com/containers/bubblewrap), [Claude Code sandboxing docs](https://code.claude.com/docs/en/sandboxing)
- Langfuse: [github.com/langfuse/langfuse](https://github.com/langfuse/langfuse), [LangGraph integration](https://langfuse.com/guides/cookbook/integration_langgraph)
- Groq 2026 tier/models: [console.groq.com/docs/models](https://console.groq.com/docs/models), [groq.com/pricing](https://groq.com/pricing)
- Azure o4-mini status: [MS Learn — reasoning models](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning), [Azure blog — o3/o4-mini](https://azure.microsoft.com/en-us/blog/o3-and-o4-mini-unlock-enterprise-agent-workflows-with-next-level-reasoning-ai-with-azure-ai-foundry-and-github/)

---

## 20. GRAPH REFERENCE — the system as LangGraph sees it

The implementation view of §6: nodes, conditional edges, subagents, and each
subagent's tool belt.

### 20.1 Main graph (one `StateGraph`, checkpointer=SqliteSaver, store=SqliteStore)

```
                                   START
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │  gut_screen         │  fast tier · NO tools
                          │  (input guardrail + │  (pure classifier;
                          │   instinct read +   │   self_harm_flag feeds
                          │   self_harm_flag)   │   compose + output check)
                          └──────────┬──────────┘
                                     ▼
                          ┌─────────────────────┐
                          │  thyroid            │  NO LLM — deterministic
                          │  (named profile:    │  rules; config tiers
                          │   tiers + budgets)  │  are ceilings
                          └──────────┬──────────┘
                                     ▼
                          ┌─────────────────────┐
                          │  identity           │  NO LLM · Hippocampus
                          │  (name/Uniquename   │  builds identity_directive;
                          │   ask + resolve)    │  promote/re-link/forget
                          └──────────┬──────────┘
                                     ▼
                          ┌─────────────────────┐
                          │  frontal_plan       │  voice tier · NO tools
                          │  (choose subagents  │
                          │   for this turn)    │
                          └──────────┬──────────┘
                                     │ conditional fan-out
                                     │ (any subset, parallel)
              ┌──────────────┼───────────────┼───────────────┐
              ▼              ▼               ▼               ▼
       ╔═════════════╗╔═════════════╗ ╔═════════════╗ ╔═════════════╗
       ║ SUBAGENT 1  ║║ SUBAGENT 2  ║ ║ SUBAGENT 3  ║ ║ SUBAGENT 4  ║
       ║ routing     ║║ retrieval   ║ ║ temporal    ║ ║ world       ║
       ║ (Gita GRAPH)║║ (Gita VECTOR)║ ║ (memory)    ║ ║ (web)       ║
       ╚══════╤══════╝╚══════╤══════╝ ╚══════╤══════╝ ╚══════╤══════╝
              └──────────────┴───────────────┴───────────────┘
                                     ▼
                          ┌─────────────────────┐
                          │  frontal_compose    │  voice tier · NO tools
                          │  (Arjun's voice;    │  prompt = persona + tone
                          │   helpline para on  │  + citations + memory
                          │   self_harm_flag)   │
                          └──────────┬──────────┘
                                     ▼
                          ┌─────────────────────┐
                          │  output_guardrail   │  deterministic layer +
                          │                     │  fast-tier LLM verdict
                          └──────────┬──────────┘
                                     ▼
                          ┌─────────────────────┐
                          │  reflection         │  fast tier
                          │  (limbic update +   │  writes ONLY to
                          │   memory writes)    │  arjun_action/
                          └──────────┬──────────┘
                                     ▼
                                    END
```

### 20.2 Subagents and their tools (each = one `create_agent` instance)

**Phase 1 — 4 subagents (ADR 0006 split the Canon into graph + vector):**

| # | Subagent | Tier | Source | Details |
|---|---|---|---|---|
| 1 | **routing** (GRAPH scholar) | voice | Kuzu clone + routing JSON | Stage 1: multi-label anartha reading of the person (LLM, structured, cautious — see `prompts/subagents/routing.md`). Stage 2: **deterministic** walk of `anartha_incidents` → `incident_teachings` → `teaching_analogies` plus `anartha_chain`, for EVERY anartha found; dedup; meaning-connections drawn. Reads the person's past `diagnoses` from long-term memory to spot old patterns. Never writes to the graph |
| 1b | **retrieval** (VECTOR scholar) | none (deterministic) | Qdrant + Notebook | `qdrant_search` over the 3 Canon collections with metadata/limbic filters · `notebook_search` (Arjun's own md). **No graph access** — asserted by test |
| 2 | **temporal** | fast | **5** | `store_get` · `store_search` (semantic, nomic embeddings) · `store_put` · `promote_guest` (guest→people/{name}) · `forget_guest` (delete namespace) |
| 3 | **world** | fast | **3** | `web_search` (DuckDuckGo) · `weather` · `news` — any swappable for MCP servers later |

**Phase 2 adds 4 drive runners** (subagents #4–7, triggered by heartbeat, not conversation):

| # | Drive runner | Tools |
|---|---|---|
| 4 | svadhyaya | `canon_chunk_read` · `notebook_write` |
| 5 | seva | `store_search` (people/*/commitments) · `notebook_write` |
| 6 | observation | reuses world's 3 web tools — findings land in `world_context`; the run's reflection step persists them to arjun/world |
| 7 | reflection | `store_search` · `store_put` · `store_delete` (prune stale facts) |

**Phase 3 adds N Workshop agents** — count unknown by design (Arjun creates them);
each is small and **flat** (never spawns its own sub-agents, ADR 0008), calls **only
o4-mini via LiteLLM** (no fallback), uses **in-memory** working state (never a DB), and
carries only **keyless** tools. Each runs inside Bubblewrap against the read-only
`workshop_venv`; the sandbox guards the **filesystem** only — the network stays
connected (ADR 0008). Durable output leaves a run solely via Arjun distilling the run
dir afterward (§20.4 invariant 2).

### 20.3 Middleware stack (identical shape on every `create_agent`)

1. `prompt_loader` — hot-loads its file from `prompts/subagents/*.md`
2. `input_guardrail` — injection/off-mission screen
3. `summarization` — context compaction on long sessions
4. `output_guardrail` — persona + privacy + citation check

### 20.4 Totals at a glance

- **Graph nodes in the main graph:** 7 organ nodes + 4 subagent nodes (no subgraphs)
  — organs: gut_screen, thyroid, **identity (Hippocampus)**, frontal_plan,
  frontal_compose, output_guardrail, reflection
- **Conditional edges:** 1 (subagent fan-out after frontal_plan)
- **Subagents:** 4 in Phase 1 (**routing** = Canon graph, **retrieval** = Canon
  vector, temporal, world) → 8 by Phase 2 → open-ended in Phase 3. The two Canon
  scholars always run together when scriptural material is needed (ADR 0006):
  vector-without-graph is what silently produced teaching-only replies.
- **Tools:** 12 in Phase 1 → ~17 in Phase 2 (with reuse) → manifest-defined in Phase 3
- **LLM-free nodes:** thyroid and output_guardrail's deterministic layer — cheap and untrickable
- **Persistence attached to the graph:** `checkpointer=SqliteSaver`, `store=SqliteStore` — both files in `arjun_action/memory/`

Design invariants worth keeping while coding:

1. The nodes that *decide* (gut, thyroid, identity, guardrails) have no tools, and the
   nodes that *fetch* (subagents) never speak to the user. Only `frontal_compose` talks
   — the Hippocampus prepares the identity ask as a *directive* that frontal_compose
   voices, so the single-voice invariant holds even for name/Uniquename questions.
2. **All store writes flow through the Temporal Lobe's tools** — no other subagent
   holds a write tool. Mid-turn, memory is read-only with one named exception:
   identity operations (`promote_guest`, `forget_guest`), which must happen the
   moment the name/Uniquename is exchanged. All durable writes (episodes, learnings,
   world facts, limbic snapshots) happen post-turn in `reflection`, which invokes
   temporal's `store_put`. This is what keeps the graph debuggable node by node and
   puts a deliberation step between the open web and Arjun's memory.



<!-- claude --resume 01ddb20a-4095-447c-96a3-db86f0abccc0    architecture -->
<!-- claude --resume db819435-79df-4479-9da0-bf4b947aba6e  revamping architeture -->
<!-- claude --resume 7ddc9745-2e4e-4fbb-802d-9379b4bc146c developmentworkbook-->
<!-- part1 -->
<!-- claude --resume d7815458-d5a9-4127-9a0b-cadc93a4cdcd developement1 -->
<!-- claude --resume 007e157a-13f2-433c-b616-4514c9f68d51 developemnt2 -->

<!-- adjusted architecture part 3-->
<!-- claude --resume 9c79d8e6-6361-4236-a1a6-10fc6a19cccd -->
<!-- post part1 -->
<!-- agy --conversation=e45afd7f-9cf0-467f-a9e8-e537ecfbe649 -->
