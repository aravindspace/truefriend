# TrueFriend — Architecture Overview

A **multi-agent spiritual companion** powered by the Bhagavad Gita.  
Built on **LangGraph** (agent orchestration) + **Chainlit** (chat UI) + **Azure OpenAI** (LLM).

---

## System at a Glance

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CHAINLIT UI (app.py)                            │
│  User types message → build state → invoke LangGraph → persist results    │
│  No name-gating — always runs the full pipeline                           │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     LANGGRAPH PIPELINE (graph/builder.py)                  │
│                                                                            │
│  ┌────────────────────┐    ┌───────────────────────────────────────────┐   │
│  │ supervisor_classify │──▶│ maybe_recall (search past conversations) │   │
│  │  (REPEAT/DEEPEN/   │   └────────────────────┬──────────────────────┘   │
│  │   NEW/CRISIS)       │                        │                         │
│  └────────────────────┘                         ▼                         │
│                            ┌───────────────────────────────────────────┐   │
│                            │ maybe_scholar (query Gita knowledge)     │   │
│                            └────────────────────┬──────────────────────┘   │
│                                                 ▼                         │
│                            ┌───────────────────────────────────────────┐   │
│                            │ maybe_world (web search + Gita mapping)  │   │
│                            └────────────────────┬──────────────────────┘   │
│                                                 ▼                         │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ supervisor_respond (ReAct Agent)                                     │  │
│  │  ┌─────────────────┐  ┌──────────────────────┐                      │  │
│  │  │ save_user_name  │  │ lookup_user_profile  │  ← tools             │  │
│  │  └─────────────────┘  └──────────────────────┘                      │  │
│  │  Merges all agent responses → warm conversational reply             │  │
│  │  Extracts user name naturally → saves via tools                     │  │
│  └──────────────────────────────────────────────┬───────────────────────┘  │
│                                                 ▼                         │
│  ┌───────────────────────────────────────────────────────────────────┐     │
│  │ memory_keeper → summarize_history → END                          │     │
│  │ (extract learnings, store in DB)  (compress if >10 messages)     │     │
│  └───────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## How a User Message Flows (Step by Step)

### 1. Chainlit Entry Point (`app.py`)

```
User message arrives
       │
       ▼
  Build state dict with:
  - user_input, user_name (from session, may be empty)
  - conversation_history, conversation_summary
  - empty agent response slots
       │
       ▼
  graph.ainvoke(state)  ← always runs, never blocks
       │
       ▼
  Persist results:
  - user_name (may be newly extracted by Supervisor)
  - conversation_history, conversation_summary
       │
       ▼
  Send final_response to user
```

**No name-gating.** The app always runs the full pipeline regardless of whether the user's name is known. The Supervisor handles name extraction naturally during conversation.

### 2. LangGraph Pipeline (`graph/builder.py`)

The pipeline is **linear with conditional skips** — every node runs in sequence, but the `maybe_*` nodes check the `intent` before doing real work:

| Step | Node | What It Does |
|------|------|-------------|
| 1 | `supervisor_classify` | **LLM call** — classifies user intent as `REPEAT`, `DEEPEN`, `NEW`, or `CRISIS`. |
| 2 | `maybe_recall` | Runs Recall Agent **only if** intent ∈ {REPEAT, DEEPEN, CRISIS}. |
| 3 | `maybe_scholar` | Runs Scholar Agent **only if** intent ∈ {DEEPEN, NEW, CRISIS}. |
| 4 | `maybe_world` | Runs World Connector **only if** intent ∈ {NEW, CRISIS}. |
| 5 | `supervisor_respond` | **ReAct Agent** — merges all agent responses, handles user identification via tools, produces the final warm reply. |
| 6 | `memory_keeper` | **LLM call** — extracts learnings (summary, emotion, concepts) → stores in ChromaDB + UserStore. |
| 7 | `summarize_history` | If history > 10 messages, **LLM call** — compresses old messages into a summary. |

**Which agents run per intent:**

| Intent | Recall | Scholar | World | Use Case |
|--------|--------|---------|-------|----------|
| `REPEAT` | ✅ | ❌ | ❌ | User re-asks something from past conversations |
| `DEEPEN` | ✅ | ✅ | ❌ | User wants more detail on a known topic |
| `NEW` | ❌ | ✅ | ✅ | User brings up a brand new topic |
| `CRISIS` | ✅ | ✅ | ✅ | User is in emotional distress — all hands on deck |

---

## The Agents

### Supervisor (Orchestrator + Voice)
- **File:** `agents/supervisor.py`
- **Role:** Orchestrator + final voice. Two steps per turn:
  1. `classify_intent()` — Simple LLM call → reads conversation context → outputs one label: REPEAT/DEEPEN/NEW/CRISIS
  2. `synthesize_response()` — **ReAct agent** with user management tools → receives all agent outputs → produces the warm, friendly final response
- **Tools:** `save_user_name`, `lookup_user_profile` — called when the Supervisor detects or needs to verify a user's name
- **Name handling:** If user_name is unknown, the Supervisor extracts it naturally from conversation and calls `save_user_name()`. If the user doesn't provide a name, it responds to their question first and gently asks for the name — never blocks.
- **Personality:** Defined in `prompts/supervisor_respond.txt` — speaks like a wise grandparent, uses simple language, avoids Sanskrit jargon
- **LLM:** Azure OpenAI `o4-mini`

### Scholar (ReAct Agent)
- **File:** `agents/scholar.py`
- **Role:** Bhagavad Gita expert. Autonomously reasons over Gita knowledge tools.
- **Tools:** `search_gita_concepts`, `get_verse`, `list_all_concepts`, `search_study_notes`
- **Data Source:** KuzuDB graph database (read-only) + study notes (markdown files)
- **LLM:** Azure OpenAI `o4-mini` (temp 0.3)

### Recall Agent (ReAct Agent)
- **File:** `agents/recall_agent.py`
- **Role:** Memory searcher. Looks up past conversations for this user.
- **Tools:** `search_conversation_memory`
- **Data Source:** ChromaDB vector store (semantic search over past Q&A summaries)
- **LLM:** Azure OpenAI `o4-mini` (temp 0.1)

### World Connector (ReAct Agent)
- **File:** `agents/world_connector.py`
- **Role:** Bridges current events to Gita wisdom. Searches the web, maps findings to teachings.
- **Tools:** `web_search` (DuckDuckGo)
- **LLM:** Azure OpenAI `o4-mini` (temp 0.3)

### Memory Keeper (Post-response)
- **File:** `agents/memory_keeper.py`
- **Role:** Runs after every response. Extracts:
  - Conversation summary
  - Emotional state
  - Key concepts discussed
  - Preferred communication style
- **Writes to:** ChromaDB (conversation memory) + UserStore (user profile JSON)
- **LLM:** Azure OpenAI `o4-mini` (temp 0.3)

### Gita Learner (Offline Batch)
- **File:** `agents/gita_learner.py`
- **Role:** NOT part of the runtime pipeline. Runs offline via `scripts/run_learner.py`.
- Reads all concepts from KuzuDB → generates detailed study notes → writes markdown files to `knowledge/notes/`
- These notes are then searchable by the Scholar agent at runtime.

---

## Data Stores

```
┌──────────────────────────────────────────────────────────────┐
│                       DATA LAYER                             │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  KuzuDB     │  │  ChromaDB    │  │  UserStore (JSON)  │  │
│  │  (Graph DB) │  │  (Vector DB) │  │  (File-based)      │  │
│  │             │  │              │  │                    │  │
│  │  READ-ONLY  │  │  READ/WRITE  │  │  READ/WRITE        │  │
│  │             │  │              │  │                    │  │
│  │  Concepts   │  │  Conversation│  │  Per-user profiles │  │
│  │  Verses     │  │  memories    │  │  - themes          │  │
│  │  Analogies  │  │  (embedded   │  │  - emotions        │  │
│  │  Relations  │  │   summaries) │  │  - preferences     │  │
│  └─────────────┘  └──────────────┘  └────────────────────┘  │
│   data/kuzu_db     data/chroma_db    data/users/             │
│                                                              │
│   Scholar reads    Memory Keeper     Memory Keeper writes    │
│   via kuzu_tools   writes;           Supervisor writes       │
│                    Recall reads      (via save_user_name)    │
│                    via memory_tools                          │
└──────────────────────────────────────────────────────────────┘
```

| Store | Technology | Path | Read By | Written By |
|-------|-----------|------|---------|------------|
| **KuzuDB** | Graph DB (embedded) | `data/kuzu_db` | Scholar agent (via `kuzu_tools`) | Pre-populated externally (read-only at runtime) |
| **ChromaDB** | Vector DB (embedded) | `data/chroma_db` | Recall agent (via `memory_tools`) | Memory Keeper (after each response) |
| **UserStore** | JSON files | `data/users/{name}.json` | Supervisor (via `lookup_user_profile`), Memory Keeper | Supervisor (via `save_user_name`), Memory Keeper |
| **Study Notes** | Markdown files | `knowledge/notes/*.md` | Scholar agent (via `note_tools`) | Gita Learner (offline batch) |

---

## LLM Configuration

All agents use `llm/factory.py` to create LLM instances. Configuration is in `config.yaml`:

```
config.yaml defines:
  - Which provider each agent uses (azure_openai, google, groq, ollama)
  - Which model (e.g. o4-mini, gemini-2.5-flash)  
  - Temperature per agent

.env provides:
  - API keys (AZURE_OPENAI_API_KEY, GEMINI_API_KEY, etc.)
  - Endpoints
```

**Provider abstraction:** `llm/provider.py` defines a base class. Each provider (Azure, Gemini, Groq, Ollama) implements `create_chat_model()` → returns a LangChain `BaseChatModel`. The factory reads the config, picks the provider, and returns the model.

Currently **all agents use Azure OpenAI `o4-mini`** as configured in `config.yaml`.

---

## Shared State (`graph/state.py`)

All agents communicate through a single `AgentState` TypedDict:

```python
AgentState:
  # Input
  user_input: str           # Current message
  user_name: str            # Who's talking (set by Supervisor via tools)
  conversation_history: []  # Recent messages
  conversation_summary: str # Compressed older messages

  # Classification
  intent: REPEAT|DEEPEN|NEW|CRISIS

  # Agent outputs (written by individual agents, read by Supervisor)
  scholar_response: str | None
  recall_response: str | None  
  world_response: str | None

  # Final
  final_response: str       # What the user sees
  sources: []               # Citation tracking

  # Memory signals
  should_learn: bool
  emotional_state: str | None
  last_topic: str | None
```

**Key design:** Agents are **isolated** — they can't see each other's responses. Only the Supervisor reads all agent responses to merge the final answer.

---

## Tools (LangChain `@tool` functions)

| Tool | File | Used By | What It Does |
|------|------|---------|-------------|
| `search_gita_concepts` | `tools/kuzu_tools.py` | Scholar | Searches KuzuDB for concepts matching a query |
| `get_verse` | `tools/kuzu_tools.py` | Scholar | Retrieves a specific verse (e.g., BG 2.47) |
| `list_all_concepts` | `tools/kuzu_tools.py` | Scholar | Lists all concept names in the knowledge graph |
| `search_study_notes` | `tools/note_tools.py` | Scholar | Keyword search over markdown study notes |
| `search_conversation_memory` | `tools/memory_tools.py` | Recall | Semantic search over past conversation summaries in ChromaDB |
| `web_search` | `tools/web_tools.py` | World Connector | DuckDuckGo web search for current events |
| `save_user_name` | `tools/user_tools.py` | Supervisor | Creates/loads user profile, returns context for returning users |
| `lookup_user_profile` | `tools/user_tools.py` | Supervisor | Reads existing user profile for context |

---

## Directory Structure

```
truefriend/
├── app.py                    # Chainlit entry point (UI + session management)
├── config.yaml               # Agent-to-LLM mapping, memory settings, paths
├── .env                      # API keys (not committed)
│
├── graph/                    # LangGraph orchestration
│   ├── state.py              # AgentState TypedDict (shared contract)
│   ├── builder.py            # Builds & compiles the graph pipeline
│   ├── nodes.py              # Thin wrappers: node → agent function
│   └── edges.py              # Conditional routing logic (legacy, unused)
│
├── agents/                   # Agent logic (each writes to specific state fields)
│   ├── supervisor.py         # Intent classification + ReAct response synthesis
│   ├── scholar.py            # Gita knowledge ReAct agent
│   ├── recall_agent.py       # Memory search ReAct agent
│   ├── world_connector.py    # Web search ReAct agent
│   ├── memory_keeper.py      # Post-response learning extraction
│   └── gita_learner.py       # Offline batch study agent
│
├── llm/                      # LLM abstraction layer
│   ├── factory.py            # create_llm("agent_name") → BaseChatModel
│   ├── provider.py           # Abstract base class
│   ├── azure_openai.py       # Azure OpenAI implementation
│   ├── gemini.py             # Google Gemini implementation
│   ├── groq.py               # Groq implementation
│   └── ollama.py             # Ollama (local) implementation
│
├── tools/                    # LangChain @tool functions for ReAct agents
│   ├── kuzu_tools.py         # KuzuDB graph queries (Scholar)
│   ├── memory_tools.py       # ChromaDB memory search (Recall)
│   ├── note_tools.py         # Study notes keyword search (Scholar)
│   ├── user_tools.py         # User profile management (Supervisor)
│   └── web_tools.py          # DuckDuckGo web search (World Connector)
│
├── stores/                   # Data persistence layer
│   ├── kuzu_store.py         # KuzuDB wrapper (read-only)
│   ├── chroma_store.py       # ChromaDB wrapper (read/write)
│   └── user_store.py         # JSON file-based user profiles
│
├── prompts/                  # System prompt templates (plain text)
│   ├── supervisor_classify.txt
│   ├── supervisor_respond.txt
│   ├── scholar.txt
│   ├── recall.txt
│   ├── world_connector.txt
│   ├── memory_keeper.txt
│   └── gita_learner.txt
│
├── data/                     # Runtime data (gitignored)
│   ├── kuzu_db/              # Pre-built Gita knowledge graph
│   ├── chroma_db/            # Conversation memory vectors
│   └── users/                # User profile JSONs
│
├── knowledge/
│   └── notes/                # Gita study notes (generated by gita_learner)
│
└── scripts/                  # Utility scripts
    └── (run_learner.py, etc.)
```

---

## Key Design Decisions

1. **No name-gating:** The app never blocks on missing user name. The Supervisor extracts it naturally during conversation via `save_user_name` tool. If the user doesn't provide a name, they still get a full response — the Supervisor gently asks at the end.

2. **Supervisor as ReAct agent:** The response synthesis step uses a ReAct agent pattern, giving the Supervisor the ability to call user management tools when needed. Intent classification stays as a simple, fast LLM call.

3. **Linear pipeline, not parallel:** Agents run sequentially (recall → scholar → world). The `edges.py` has routing logic for parallel execution, but the current `builder.py` uses a simpler linear approach with `maybe_*` skip-wrappers.

4. **Agent isolation:** Agents can't see each other. Only Supervisor reads all outputs. This prevents agents from influencing each other's reasoning.

5. **ReAct pattern for specialist agents:** Scholar, Recall, and World Connector use LangGraph's `create_react_agent` pattern — they autonomously decide which tools to call and how many times to reason before answering.

6. **Memory grows over time:** Every conversation is summarized by Memory Keeper and stored in ChromaDB. Recall Agent searches this growing memory. User profiles track themes, emotions, and preferences.

7. **Sacred source is read-only:** KuzuDB (Gita knowledge) is never written to at runtime. Only the offline Gita Learner can generate study notes from it.

8. **Provider-agnostic LLM layer:** The `llm/` module abstracts away the LLM provider. Switching from Azure to Gemini or a local Ollama model requires only a `config.yaml` change.
