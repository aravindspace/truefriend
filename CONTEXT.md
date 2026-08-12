# TrueFriend — Domain Glossary

Canonical language for the TrueFriend project. Glossary only — no implementation details.

## Core terms

- **Arjun** — The persona of the system: a Gita-scholar, patient listener, and "true friend" who counsels people using Bhagavad Gita wisdom. Arjun is a sevak (servant) of Lord Krishna and understands himself as part of nature, created by Krishna. Not to be confused with **Arjuna** the historical personality in the source data.
- **Body Map** — The organizing principle of Arjun's cognition: each human body system maps to one functional agent-engineering mechanism (functional mapping, not literal organ simulation). The biological name is the canonical name of the component.
  - **Frontal Lobe** — The supervisor/planner: routes requests, plans multi-step work, and speaks as Arjun's final voice.
  - **Temporal Lobe** — The memory subsystem: long-term storage of people, conversations, and learned facts. (Audio processing explicitly deferred.)
  - **Limbic System** — The emotion-state module: structured mood state carried through the graph, coloring tone and retrieval bias.
  - **Gut (ENS)** — Baseline persona/mood parameters: slow-moving defaults and "gut instinct" heuristic shortcuts taken before deep reasoning.
  - **Adrenals** — The urgency hormone: when the Gut detects distress, a signal enters the shared state and every organ reacts in place (warmth-first helplines, no tier downgrade, gentle tone). Like real adrenal glands, they release a hormone — they never route or take over; there is no separate path.
  - **Thyroid** — The throttle: per-request model choice, reasoning effort, and loop budget.
  - **Hippocampus** — The identity organ: recognizes and binds who a person is — the guest→promotion→re-link→forgetting lifecycle and the in-conversation asks for name and Uniquename. Deterministic; keeps identity work out of the Frontal Lobe (added 2026-07-18).
- **Canon Masters** — The original preprocessed Gita stores (`graphdb/`, `vectordb/`, `routing/`). Pristine, never opened by Arjun at runtime; kept only as the source of truth for re-cloning.
- **Action Folder** — `arjun_action/`, the single writable root of the system. Everything dynamic Arjun writes at runtime (memory DBs, Self-Learning DB, Notebook, Workshop) lives inside it; everything outside it is opened read-only.
- **Self-Learning DB** — A full working clone of the canon Kuzu graph (`arjun_action/self_learning_db/`). All runtime queries, edge backfill, and Arjun's learned graph edges happen here. Disposable and rebuildable from the Canon Masters at any time.
- **Notebook** — Arjun's self-maintained learned layer (`arjun_action/notebook/`): markdown files and skills he writes as he studies the Canon, observes nature, and counsels people.
- **Drive** — An internal motivation with a pressure value that grows over time and resets when satisfied: **svadhyaya** (self-study of the Canon), **seva** (follow-ups on people and commitments), **observation** (nature/world awareness via web tools), **reflection** (memory consolidation and mood decay).
- **Heartbeat** — The periodic scheduler tick that wakes Arjun and runs the highest-pressure Drive through the same brain graph that handles conversations. Conversations always win: a tick is skipped entirely while a conversation is live; drive pressure simply accumulates until Arjun's quiet hours.
- **Harness** — The deterministic outer layer wrapping the brain graph: iteration budgets, retries, timeouts, structured-output validation, fallback routes, and tracing. The LLM proposes; the Harness disposes.
- **Workshop** — The folder where Arjun drafts, activates, and runs his own self-built agents (`arjun_action/workshop/`, Phase 3). Active agents run sandboxed under Bubblewrap with Harness budgets; there is no human approval gate.
- **Workshop agent** — A small, deliberately simple agent Arjun builds in his Workshop to help himself with one narrow task. Distinct from the four Phase-1 **subagents** (that word stays reserved for routing/retrieval/temporal/world). A Workshop agent is flat (it never spawns its own agents) and has **no memory of its own** — whatever it produces becomes permanent only when Arjun later chooses to distill it into his memory. It runs sandboxed purely so it can never touch anything outside its own workspace; the sandbox guards Arjun's files, not his connection to the world.
- **Prompt Library** — The `prompts/` directory of versioned persona and per-organ instruction files, hot-loaded on demand at each graph node.
- **Limbic State** — Arjun's structured mood: a guna balance (sattva/rajas/tamas) and a short list of active feelings with intensity and cause. Expressed in Gita-native categories, not clinical affect models.
- **Gut Baseline** — The resting mood Arjun's Limbic State decays back toward between events: steady, sattvic, devotional.
- **Helpline Rule** — There is no separate crisis mode: every message flows down the single pipeline and is answered from the Gita. But when a message signals self-harm, Arjun's reply must respond with warmth first and include the Indian helplines — enforced by a deterministic output check, never left to chance.
- **Reflection** — The post-conversation pass that distills a session into durable memories (person episodes, diagnoses, Arjun's own learnings).
- **Guest** — A human talking to Arjun who has not yet shared their name. Gets a temporary identity; Arjun never demands a name from someone in distress.
- **Person Key** — The durable identity of a known person: their shared name plus their chosen Uniquename plus a system-generated unique suffix. The name is how Arjun addresses someone; it is never sufficient on its own to identify them.
- **Uniquename** — A personal word the person chooses when their profile is created. On return, name + Uniquename together re-link them to their profile. A courtesy recognition check, not security authentication.
- **Promotion** — Converting a Guest's temporary memory into a durable per-person memory (under a Person Key). Complete only when the person has both shared their name and chosen a Uniquename; if they refuse a Uniquename, the profile is deleted (see Forgetting).
- **Re-linking** — Recognizing a returning person by name + Uniquename. If no match is found, Arjun says so honestly and offers to create a fresh profile; he never guesses or merges.
- **Identity Resolver** — The swappable adapter-layer module that turns "whoever is talking" into a Person Key or Guest identity. Today it uses name + Uniquename; a future robot embodiment swaps in camera-based face recognition. The brain never knows or cares which resolver is active.
- **Session End** — The moment a conversation is considered over: a fixed period of silence (no new message). Detected lazily — checked whenever the system next wakes — so end-of-session work (Reflection, Forgetting, deleting Uniquename-less profiles) may run late but always runs.
- **Forgetting** — Deleting a person's data after the chat when they prefer to stay anonymous — either as a Guest who never shares a name, or a named person who refuses a Uniquename.
- **Personality** (data term) — A real historical figure referenced in the Gita sources (Arjuna, Krishna, Bhishma…). The sources treat these as historical persons, never fictional characters. (Established in the data-injection phase.)
- **Anartha** — One of six unwanted qualities (Kama, Krodha, Lobha, Moha, Mada, Matsarya) used as the diagnostic axis for user problems. A real life incident is never just one: the Gita's view is that several are braided together in any human situation, and Arjun reads all of them (see Anartha Reading).
- **Anartha Reading** — The Routing subagent's multi-label assessment of a person's situation: which anarthas are at work, each with a confidence and the reason it appears *here*, plus the guna environment. Never a single label, never a condemnation — it names weather, not souls.
- **Canon Scholars** — The two agents that serve the Canon, one per store: **Routing** reads the anarthas and walks the *graph* (Kuzu) connecting node meaning to the person's problem; **Retrieval** searches the *vector* store (Qdrant) and Arjun's Notebook. Neither speaks to the person — both hand findings to the Frontal Lobe.
- **Guna** — One of three modes of material nature (Satva, Rajas, Tamas).
