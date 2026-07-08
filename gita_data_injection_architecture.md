# Gita RAG — Data Injection Architecture
## (Preprocessing Only — Not RAG Orchestration)

---

## IMPORTANT FRAMING NOTE

The Bhagavad Gita is the recorded discourse spoken by Lord Krishna to Arjuna on the
battlefield of Kurukshetra, embedded within the historical narrative of the
Mahabharata. Per the source material (`gita_text.txt`), Kurukshetra is affirmed as an
actual, geographically real place of pilgrimage (`dharmakshetra kurukshetra`), and
the events, dialogues, and persons described (Arjuna, Krishna, Bhishma, Drona,
Duryodhana, Prahlada, Bharat Maharaj, the Kuru dynasty, etc.) are treated as
**real historical personalities and real historical/scriptural events** — not
literary devices, not allegory, and not fictional "characters" in a story.

This is explicitly stated in the source: commentators who treat Kurukshetra as a
metaphor for the human body and the Pandavas/Kauravas as symbols for senses/vices
are described as holding "a very wrong understanding." Accordingly, this
architecture avoids fiction-oriented vocabulary (`character`, `story`, `narrative`
as literary constructs) and instead uses vocabulary appropriate to historical
accounts, recorded incidents, and real personalities, consistent with disciplic
tradition (parampara).


---

## PROJECT FOLDER STRUCTURE

```
gita-rag/
│
├── data/
│   ├── raw/
│   │   ├── gita_text.txt              ← source discourse (YouTube transcript, plain text)
│   │   ├── ministructure.txt          ← routing schema source (Gunas, Anarthas, Karma, Yoga ladder)
│   │   └── kuru_family.txt            ← Kuru dynasty lineage (Mahabharata genealogy)
│   └── processed/
│       ├── chunks_raw.jsonl           ← output of Step 01 (semantic chunks)
│       └── chunks_tagged.jsonl        ← output of Step 02 (tagged chunks)
│
├── models/                             ← GGUF model files (not committed)
│   └── nomic-embed-text-v1.5.Q8_0.gguf ← embedding model for llama.cpp
│
├── vectordb/                          ← Qdrant local persistence folder
│   ├── historical_account/            ← collection 1
│   ├── teaching/                      ← collection 2
│   └── analogy/                       ← collection 3
│
├── graphdb/                           ← Kuzu local persistence folder
│   └── gita_graph                     ← single Kuzu DB database file
│
├── routing/
│   └── ministructure.json             ← expanded routing schema (flat file)
│
└── preprocessing/
    ├── config.py                      ← shared clients (Azure LLM, llama.cpp embed), paths, retry
    ├── preflight.py                   ← diagnostic check for files, API keys, and model pings
    ├── 01_extract_chunks.py           ← LLM semantic chunking (sliding window)
    ├── 02_tag_chunks.py               ← LLM metadata tagging (all fields)
    ├── 03_build_routing_json.py       ← LLM expands ministructure → routing JSON
    ├── 04_load_qdrant.py              ← nomic embed (llama.cpp) + store in vectordb/
    ├── 05_build_kuzu.py               ← build graph with full text in graphdb/
    ├── 06_build_lineage.py            ← Family doc → Kuru dynasty genealogy nodes/edges
    └── run_pipeline.py                ← orchestrator with --start-from
```

---

## KEY ARCHITECTURAL DECISIONS

| Decision | Resolution |
|----------|------------|
| Vector DB | **Qdrant** (local mode, no server, `qdrant-client`) |
| Chunk classification | **LLM-only** — no regex/keyword heuristics |
| Chunking strategy | **LLM-guided semantic chunking** — sliding window → Azure o4-mini identifies natural boundaries |
| LLM provider | **Azure OpenAI o4-mini** deployment (reasoning model, no temperature) |
| Embedding model | **nomic-embed-text-v1.5** via llama.cpp (768-dim native, Matryoshka-truncated to 512, task prefix `search_document:`) |
| LLM output format | **Pydantic + json_schema** structured output via `.with_structured_output()` |
| Embedding input | `search_document:` prefix + concatenated `context_prefix + "\n\n" + text` |
| Metadata enums | **Strict** for anartha_tag (6), guna_environment (3), yoga_solution (4), chunk_type (3); **open** for personality, emotional_state, problem_domain |
| Metadata cardinality | **List of values** for all metadata fields |
| Processing strategy | **Sequential** with 1s delay + **retry with exponential backoff** on 429 |
| Checkpointing | **Append-mode** output in Steps 01 and 02; resume on restart |
| Routing JSON (Step 03) | **LLM-assisted** — cross-references ministructure.txt + chunks_tagged.jsonl |
| Lineage parsing (Step 06) | **LLM-assisted** — structured output from kuru_family.txt |
| Graph edges (Step 05) | **LLM-discovered** — sends node summaries, gets relationship edges |
| Source file | **gita_text.txt** (YouTube transcript, ~5580 lines, ~1.38MB) |

---

## DATA STORES — WHAT GOES WHERE

---

### STORE 1 — Qdrant (local /vectordb/)

**Purpose:** Semantic similarity search across full gita_text.txt content

**What is saved:**
```
- All chunks from gita_text.txt (LLM-guided semantic boundaries, NOT fixed token windows)
- Each chunk embedded as a 512-dim vector (nomic-embed-text-v1.5 via llama.cpp, Matryoshka truncation)
- Each chunk has metadata payload attached
- Context sentence prepended before embedding
```

**Three Collections:**

| Collection | Chunk Content | Filter Tags Used At Query Time |
|---|---|---|
| `historical_account` | Recorded incidents — Arjuna's grief, Prahlada's persecution, Bharat Maharaj's attachment, the actual events at Kurukshetra | anartha_tag, domain, personality |
| `teaching` | Concept explanations — Karma Yoga, Moha, Gunas, Dharma | yoga_solution, section, guna_environment |
| `analogy` | Nature metaphors used by Krishna to illustrate a point — moth+fire, iron rod+fire, lotus leaf, banyan tree | yoga_solution, analogy_type |

**Chunk Payload Schema (every chunk in all 3 collections):**
```json
{
  "text": "full chunk text here...",
  "context_prefix": "This chunk from the Gita discourse recounts Arjuna's grief on the battlefield...",
  "chunk_type": "HISTORICAL_ACCOUNT | TEACHING | ANALOGY",
  "chunk_id": "chunk_0001",
  "brief_summary": "Arjuna's grief upon seeing relatives on the battlefield",
  "chapter_ref": ["Chapter 1", "Chapter 2"],
  "personality": ["Arjuna", "Krishna", "Bhishma"],
  "emotional_state": ["grief", "confusion"],
  "problem_domain": ["family", "duty", "purpose"],
  "anartha_tag": ["Moha"],
  "yoga_solution": ["Bhakti", "Sankhya"],
  "guna_environment": ["Tamas"],
  "section": [1]
}
```

Note: All metadata fields are **lists** to support multiple values per chunk.
Note: field renamed from `character` → `personality` to reflect that these are
real historical figures being referenced, not fictional characters.

**Storage location:** `/vectordb/` (Qdrant local mode, no server needed)

---

### STORE 2 — Kuzu Graph DB (local /graphdb/)

**Purpose:** Structured traversal from problem → historical incident → teaching →
analogy, with FULL TEXT at every node (no second lookup needed) — and also
genealogical grounding of each personality via the Kuru dynasty lineage.

**What is saved:**
```
- All concept nodes with full descriptive text as node properties
- All relationship edges (LLM-discovered)
- Full incident text inside GitaIncident nodes
- Full teaching text inside YogaTeaching nodes
- Full analogy text inside NatureAnalogy nodes
- Full lineage/genealogy inside HistoricalPersonality nodes (from Family doc)
```

**Node Types and Properties:**

```
(:Anartha)
  - name          → "Krodha"
  - description   → full explanation of what Krodha is, how it arises
  - symptoms      → "anger when desire blocked, loss of reason..."
  - guna          → "Rajas"

(:GitaIncident)                          [renamed from GitaStory]
  - chunk_id      → "chunk_0001"
  - name          → "Arjuna sees relatives on the battlefield and is overwhelmed with grief"
  - chapter       → "Chapter 1"
  - personality   → "Arjuna, Krishna, Bhishma"
  - emotional_state → "grief, confusion"
  - full_text     → complete incident account from gita_text.txt
  - problem_domain → "duty, family, purpose"

(:YogaTeaching)
  - chunk_id      → "chunk_0042"
  - name          → "Karma Yoga — act without attachment to results"
  - section       → 4
  - full_text     → complete teaching explanation from gita_text.txt
  - core_principle → "act without attachment to results"

(:NatureAnalogy)
  - chunk_id      → "chunk_0078"
  - name          → "Iron rod in fire — soul spiritualized by Krishna's contact"
  - full_text     → complete analogy passage from gita_text.txt
  - maps_concept  → "soul spiritualized by constant contact with Krishna"
  - natural_element → "fire"

(:HistoricalPersonality)                 [from kuru_family.txt]
  - name          → "Arjuna"
  - dynasty       → "Kuru"
  - father        → "Pandu"
  - mother        → "Kunti"
  - divine_father → "Indra"
  - generation    → 3
  - role          → "Pandava prince, warrior, disciple of Krishna"
```

**Relationship Types:**

```
(Anartha)              -[:CAUSES]->            (Anartha)
(Anartha)              -[:PRESENT_IN]->        (GitaIncident)
(GitaIncident)         -[:RESOLVED_BY]->       (YogaTeaching)
(YogaTeaching)         -[:ILLUSTRATED_BY]->    (NatureAnalogy)
(UserProblemDomain)    -[:MAPS_TO]->           (Anartha)

(HistoricalPersonality)-[:APPEARS_IN]->        (GitaIncident)
(HistoricalPersonality)-[:PARENT_OF]->         (HistoricalPersonality)
(HistoricalPersonality)-[:MARRIED_TO]->        (HistoricalPersonality)
(HistoricalPersonality)-[:BELONGS_TO_DYNASTY]->(Dynasty)
```

**Kuru Dynasty Lineage (source: `kuru_family.txt`) — loaded as
`HistoricalPersonality` nodes and `PARENT_OF` / `MARRIED_TO` edges:**

```
Shantanu + Ganga        → Bhishma (vowed celibacy)
Shantanu + Satyavati     → Chitrangada, Vichitravirya
Vyasa (Niyoga)           → Dhritarashtra (m. Ambika), Pandu (m. Ambalika), Vidura
Dhritarashtra            → 100 Kauravas (Duryodhana, Dushasana, Vikarna...), Dushala, Yuyutsu
Pandu + Kunti            → Yudhishthira (f. Dharma), Bhima (f. Vayu), Arjuna (f. Indra)
Pandu + Madri            → Nakula, Sahadeva (f. Ashwini Kumaras)
Kunti (pre-marriage)     → Karna (f. Surya, raised by Adhiratha & Radha)
Draupadi + Pandavas      → Upapandavas (Prativindhya, Sutasoma, Srutakarma, Shatanika, Srutasena)
Arjuna + Subhadra        → Abhimanyu
Abhimanyu + Uttara       → Parikshit → Janamejaya
```

**Single Kuzu Query At Runtime (unchanged logic, renamed nodes):**
```cypher
MATCH (a:Anartha {name: $anartha})
      -[:PRESENT_IN]->(i:GitaIncident)
      -[:RESOLVED_BY]->(t:YogaTeaching)
      -[:ILLUSTRATED_BY]->(n:NatureAnalogy)
RETURN i.full_text, t.full_text, n.full_text
```

**Optional lineage-enrichment query:**
```cypher
MATCH (p:HistoricalPersonality {name: $personality})
      -[:APPEARS_IN]->(i:GitaIncident)
OPTIONAL MATCH (p)-[:PARENT_OF|MARRIED_TO|BELONGS_TO_DYNASTY]-(rel:HistoricalPersonality)
RETURN i.full_text, p, collect(rel)
```

**Storage location:** `/graphdb/gita_graph/` (Kuzu embedded, no server needed)

---

### STORE 3 — Routing JSON (flat file /routing/)

**Purpose:** Fast first-step routing before any DB is touched. No gita_text.txt content here.

**What is saved:**
```
- Mapping of problem domains → Anartha
- Mapping of Anartha → Guna environment
- Mapping of section number → which DB collections to query
- Canonical incident names per Anartha (for graph query construction)
- Top 2-3 analogy names per YogaTeaching (fallback if graph traversal misses)
- Canonical personality → dynasty lookup (for lineage enrichment)
```

**Schema:**
```json
{
  "routing_table": {
    "career": { "anartha": "Krodha", "guna": "Rajas", "section": 3 },
    "family_duty": { "anartha": "Moha", "guna": "Tamas", "section": 1 },
    "purpose": { "anartha": "Moha", "guna": "Tamas", "section": 2 },
    "envy": { "anartha": "Matsarya", "guna": "Rajas", "section": 3 },
    "greed": { "anartha": "Lobha", "guna": "Rajas", "section": 3 },
    "attachment": { "anartha": "Kama", "guna": "Rajas", "section": 5 },
    "pride": { "anartha": "Mada", "guna": "Rajas", "section": 2 },
    "loss_grief": { "anartha": "Moha", "guna": "Tamas", "section": 1 }
  },
  "anartha_canonical_incidents": {
    "Krodha": ["chunk_0012", "chunk_0045"],
    "Moha": ["chunk_0003", "chunk_0067"],
    "...": "..."
  },
  "yoga_analogies_fallback": {
    "Karma": ["chunk_0078", "chunk_0091"],
    "Bhakti": ["chunk_0102", "chunk_0115"],
    "...": "..."
  },
  "personality_dynasty_lookup": {
    "Arjuna": "Kuru (Pandava), warrior, disciple of Krishna",
    "Duryodhana": "Kuru (Kaurava), eldest son of Dhritarashtra",
    "Krishna": "Yadu dynasty, Supreme Personality of Godhead"
  }
}
```

**Storage location:** `/routing/ministructure.json` (plain JSON file, loaded into memory at startup)

---

## PREPROCESSING PIPELINE (Run Once)

### Technology Stack
- **LLM calls:** Azure OpenAI `o4-mini` deployment (reasoning model, structured output)
- **Embeddings:** nomic-embed-text-v1.5 via llama.cpp (768-dim native, Matryoshka-truncated to 512, Q8_0 GGUF)
- **Vector DB:** Qdrant (local mode, `qdrant-client`)
- **Graph DB:** Kuzu (embedded, `kuzu` package)
- **Structured output:** Pydantic models + `json_schema` via `.with_structured_output()`

### Execution Order
```
python preprocessing/run_pipeline.py                   # Full pipeline
python preprocessing/run_pipeline.py --start-from 3    # Resume from step 3
```

```
Step 01 — 01_extract_chunks.py
  Input  : data/raw/gita_text.txt
  Process: Split text into paragraphs → group into overlapping windows (~12 paras)
           → send each window to Azure o4-mini for LLM-guided semantic chunking
           → LLM returns paragraph range boundaries + chunk_type + summary
           → reconstruct exact text from original paragraphs (zero text loss)
           → checkpointing: append each chunk as it completes, resume on restart
           → **Hardened filter handling:** catches content filter blocks and falls back
             to treating the window as a single chunk to prevent pipeline crash.
  Output : data/processed/chunks_raw.jsonl

Step 02 — 02_tag_chunks.py
  Input  : data/processed/chunks_raw.jsonl + data/raw/ministructure.txt
  Process: For each chunk, send to Azure o4-mini with structured output
           → fill all metadata fields: context_prefix, chapter_ref, personality,
             emotional_state, problem_domain, anartha_tag, yoga_solution,
             guna_environment, section
           → ministructure.txt embedded in system prompt for section assignment
           → checkpointing: append each tagged chunk, resume on restart
           → **Hardened filter handling:** catches content filter blocks on raw text and
             retries with chunk summary-only; falls back to defaults if that also fails.
  Output : data/processed/chunks_tagged.jsonl

Step 03 — 03_build_routing_json.py
  Input  : data/raw/ministructure.txt + data/processed/chunks_tagged.jsonl
  Process: Send ministructure framework + condensed chunk metadata to Azure o4-mini
           → LLM cross-references to produce routing schema
           → problem_domain → anartha + guna + section mappings
           → canonical incident chunk_ids per anartha
           → analogy fallback chunk_ids per yoga
           → personality dynasty lookup
           → **Schema mapping:** uses `method="function_calling"` and a robust before-validator
             to parse keys and convert verbose section strings (e.g. "Section 3: ...") into integer IDs.
  Output : routing/ministructure.json

Step 04 — 04_load_qdrant.py
  Input  : data/processed/chunks_tagged.jsonl
  Process: For each chunk, concatenate context_prefix + text
           → prepend "search_document: " task prefix
           → embed with nomic-embed-text-v1.5 via llama.cpp (port 9471)
           → Matryoshka-truncate 768-dim output to 512 dims
           → route to correct Qdrant collection by chunk_type
           → upsert with full metadata payload
  Output : vectordb/ (3 Qdrant collections persisted locally)

Step 05 — 05_build_kuzu.py
  Input  : data/processed/chunks_tagged.jsonl + routing/ministructure.json
  Process: Create node table schemas
           → insert ALL chunk nodes as GitaIncident / YogaTeaching / NatureAnalogy
             with full_text (every word preserved)
           → insert 6 Anartha nodes + UserProblemDomain nodes
           → insert MAPS_TO edges from routing table
           → LLM-assisted edge discovery: send node summaries to Azure o4-mini
             to identify PRESENT_IN, RESOLVED_BY, ILLUSTRATED_BY, CAUSES edges
           → batch edge discovery if data too large for single LLM call
           → **Kuzu DB File & Cypher fixes:** Kuzu DB is initialized directly as a file (no folder creation).
             Commas were removed from Cypher `CREATE REL TABLE` queries to match Kuzu DDL specs.
             Renamed parameter placeholder `$desc` to `$description` to resolve reserved Cypher keyword conflict.
  Output : graphdb/gita_graph (Kuzu DB file persisted locally)

Step 06 — 06_build_lineage.py
  Input  : data/raw/kuru_family.txt + existing graphdb/gita_graph
  Process: Send kuru_family.txt to Azure o4-mini with structured output
           → extract HistoricalPersonality nodes + PARENT_OF / MARRIED_TO edges
           → create BELONGS_TO_DYNASTY edges
           → create APPEARS_IN edges linking personalities to GitaIncident nodes
             where the personality name appears in the personality metadata field
           → **Cypher fixes:** Commas were removed from Cypher `CREATE REL TABLE` queries.
  Output : graphdb/gita_graph (lineage nodes/edges added to same Kuzu DB file)
```

---

## WHAT EACH STORE ANSWERS AT QUERY TIME

| Question | Store Used |
|---|---|
| "What is semantically similar to this user problem?" | Qdrant |
| "Which exact Gita incident maps to Krodha?" | Kuzu |
| "What teaching resolves that incident?" | Kuzu |
| "What nature analogy explains that teaching?" | Kuzu |
| "Are there other similar grief situations in different chapters?" | Qdrant |
| "Which domain does this problem belong to?" | routing JSON |
| "Which section should I query?" | routing JSON |
| "Who is this personality actually related to (lineage)?" | Kuzu |

---

## MULTI-AGENT INVENTORY & QUERY DIRECTORY

This section is the canonical reference sheet for the **Multi-Agent System**. It defines exactly where each agent should pick data, what kind of data is present, the exact schema and names available, and their respective counts.

### Source 1: Static Routing Table (JSON)
* **File Path:** `/routing/ministructure.json`
* **Agent Utility:** Used by the **Routing/Classification Agent** as a fast, low-cost static index lookup before querying databases.
* **Fields & Top-Level Keys:**
  1. `routing_table`: Maps a user's everyday problem domain (`career`, `family`, `envy`, etc.) to:
     * `anartha`: Literal enum (`Kama`, `Krodha`, `Lobha`, `Moha`, `Mada`, `Matsarya`)
     * `guna`: Literal enum (`Satva`, `Rajas`, `Tamas`)
     * `section`: Integer (1-5) representing teaching framework section
  2. `anartha_canonical_incidents`: Dictionary mapping Anartha names to lists of canonical chunk IDs representing incident nodes (useful to seed search queries).
  3. `yoga_analogies_fallback`: Dictionary mapping Yoga paths (`Karma`, `Bhakti`, etc.) to analogy chunk IDs for fallback routing.
  4. `personality_dynasty_lookup`: Quick mapping of a personality name to their role and dynasty description.

---

### Source 2: Qdrant Vector DB (Similarity Engine)
* **Storage Location:** `/vectordb/` (Running in local/embedded mode)
* **Agent Utility:** Used by the **Retrieval/Semantic Agent** to run similarity searches across vector space using 512-dimension Nomic embeddings.
* **Collections & Points Count:**
  1. `historical_account` (**68 points**): Chunks detailing battlefield events, family history, and incidents.
  2. `teaching` (**876 points**): Chunks explaining core philosophical teachings and instructions.
  3. `analogy` (**84 points**): Chunks containing metaphors used by Lord Krishna.
* **Point Payload Schema (Available in all 3 collections):**
  * `text` (String): Original chunk text.
  * `context_prefix` (String): Summary sentence prefixed to text.
  * `chunk_type` (String): Class name (`HISTORICAL_ACCOUNT`, `TEACHING`, `ANALOGY`).
  * `chunk_id` (String): Canonical ID (e.g. `chunk_0001`).
  * `brief_summary` (String): Brief summary.
  * `chapter_ref` (List of Strings): Gita chapters (e.g. `["Chapter 1"]`).
  * `personality` (List of Strings): Personalities present.
  * `emotional_state` (List of Strings): Emotions (e.g. `["grief", "envy"]`).
  * `problem_domain` (List of Strings): Domains (e.g. `["career", "family"]`).
  * `anartha_tag` (List of Strings): Associated Anarthas.
  * `yoga_solution` (List of Strings): Paths addressing the chunk.
  * `guna_environment` (List of Strings): Gunas active.
  * `section` (List of Integers): Corresponding sections (1-5).

---

### Source 3: Kuzu Graph DB (Context Traversal Engine)
* **Storage File Path:** `/graphdb/gita_graph` (Single embedded Kuzu database file)
* **Agent Utility:** Used by the **Graph/Context Traversal Agent** to run multi-hop Cypher queries and traverse relationships from problem $\rightarrow$ active Anartha $\rightarrow$ incident $\rightarrow$ teaching $\rightarrow$ analogy $\rightarrow$ lineage.
* **Node Tables & Properties:**
  1. `Anartha` (**6 nodes**):
     * `name` (String, Primary Key) - Kama, Krodha, Lobha, Moha, Mada, Matsarya
     * `description` (String) - Full definition
     * `symptoms` (String) - Behaviors
     * `guna` (String) - Associated mode
  2. `GitaIncident` (**68 nodes**):
     * `chunk_id` (String, Primary Key) - `chunk_XXXX`
     * `name` (String) - Incident summary
     * `chapter` (String) - Chapter references
     * `personality` (String) - Comma-joined personalities
     * `emotional_state` (String) - Comma-joined emotions
     * `full_text` (String) - Complete verbatim transcript passage
     * `problem_domain` (String) - Comma-joined problem domains
  3. `YogaTeaching` (**876 nodes**):
     * `chunk_id` (String, Primary Key)
     * `name` (String) - Core teaching summary
     * `section` (Int64) - Section index (1-5)
     * `full_text` (String) - Complete verbatim transcript passage
     * `core_principle` (String) - The core takeaway
  4. `NatureAnalogy` (**84 nodes**):
     * `chunk_id` (String, Primary Key)
     * `name` (String) - Metaphor summary
     * `full_text` (String) - Complete verbatim transcript passage
     * `maps_concept` (String) - Spiritual concept it illustrates
     * `natural_element` (String) - Element used (e.g. fire, leaf)
  5. `UserProblemDomain` (**21 nodes**):
     * `name` (String, Primary Key) - career, family, duty, purpose, loss, etc.
  6. `HistoricalPersonality` (**52 nodes**):
     * `name` (String, Primary Key) - Arjuna, Krishna, Bhishma, Kunti, etc.
     * `dynasty` (String) - Kuru, Yadu, etc.
     * `father` (String), `mother` (String), `divine_father` (String)
     * `generation` (Int64) - Lineage generation index (1 = Shantanu)
     * `role` (String) - Personal description
  7. `Dynasty` (**1 node**):
     * `name` (String, Primary Key) - `"Kuru"`
* **Relationship Tables & Node Mappings:**
  1. `MAPS_TO` (**21 edges**): `FROM UserProblemDomain TO Anartha`
  2. `PRESENT_IN` (**21 edges**): `FROM Anartha TO GitaIncident`
  3. `RESOLVED_BY` (**3 edges**): `FROM GitaIncident TO YogaTeaching`
  4. `ILLUSTRATED_BY` (**3 edges**): `FROM YogaTeaching TO NatureAnalogy`
  5. `CAUSES` (**2 edges**): `FROM Anartha TO Anartha`
  6. `PARENT_OF` (**52 edges**): `FROM HistoricalPersonality TO HistoricalPersonality`
  7. `MARRIED_TO` (**14 edges**): `FROM HistoricalPersonality TO HistoricalPersonality`
  8. `BELONGS_TO_DYNASTY` (**52 edges**): `FROM HistoricalPersonality TO Dynasty`
  9. `APPEARS_IN` (**115 edges**): `FROM HistoricalPersonality TO GitaIncident`
