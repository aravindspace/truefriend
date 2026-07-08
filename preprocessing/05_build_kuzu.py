"""
Step 05 — Build Kuzu Knowledge Graph

Reads chunks_tagged.jsonl and routing/ministructure.json, then populates a
Kuzu embedded graph database with typed nodes and LLM-discovered edges.

Node tables: Anartha, GitaIncident, YogaTeaching, NatureAnalogy, UserProblemDomain
Rel  tables: CAUSES, PRESENT_IN, RESOLVED_BY, ILLUSTRATED_BY, MAPS_TO
"""

import json
from pathlib import Path

import kuzu
from pydantic import BaseModel

from config import (
    get_azure_llm,
    retry_with_backoff,
    processing_pause,
    get_logger,
    CHUNKS_TAGGED_PATH,
    ROUTING_JSON_PATH,
    GRAPHDB_DIR,
    MINISTRUCTURE_PATH,
    KURU_FAMILY_PATH,
)

logger = get_logger("05_build_kuzu")

# ---------------------------------------------------------------------------
# Pydantic models for LLM edge-discovery
# ---------------------------------------------------------------------------

class Edge(BaseModel):
    from_id: str  # chunk_id or name
    to_id: str    # chunk_id or name


class EdgeDiscoveryResponse(BaseModel):
    present_in: list[Edge]       # Anartha -> GitaIncident
    resolved_by: list[Edge]      # GitaIncident -> YogaTeaching
    illustrated_by: list[Edge]   # YogaTeaching -> NatureAnalogy
    causes: list[Edge]           # Anartha -> Anartha


# ---------------------------------------------------------------------------
# Fixed Anartha definitions (the 6 enemies of the mind)
# ---------------------------------------------------------------------------

ANARTHAS = [
    {
        "name": "Kama",
        "description": "Lust or unbridled desire; the craving for sensory gratification that pulls the mind toward objects of pleasure.",
        "symptoms": "Restlessness, obsessive attachment, inability to focus on duty, fantasizing about sense objects",
        "guna": "Rajas",
    },
    {
        "name": "Krodha",
        "description": "Anger; the explosive reaction when desire is frustrated or obstructed.",
        "symptoms": "Loss of temper, harsh speech, irrational decisions, violence, clouded judgement",
        "guna": "Rajas",
    },
    {
        "name": "Lobha",
        "description": "Greed; the insatiable hunger to acquire and hoard beyond genuine need.",
        "symptoms": "Hoarding, exploitation of others, chronic dissatisfaction, inability to give or share",
        "guna": "Rajas",
    },
    {
        "name": "Moha",
        "description": "Delusion or bewilderment; the inability to distinguish the real from the unreal, the self from the body.",
        "symptoms": "Confusion about duty, misidentification with the body, attachment to impermanent things, grief without cause",
        "guna": "Tamas",
    },
    {
        "name": "Mada",
        "description": "Pride or intoxication of ego; the inflated sense of superiority based on power, beauty, lineage, or knowledge.",
        "symptoms": "Arrogance, disrespect toward elders and teachers, dismissiveness of others, overconfidence",
        "guna": "Rajas",
    },
    {
        "name": "Matsarya",
        "description": "Envy or jealousy; the inability to tolerate the prosperity, virtue, or happiness of others.",
        "symptoms": "Resentment at others' success, scheming to undermine others, chronic comparison, bitterness",
        "guna": "Tamas",
    },
]

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

NODE_TABLE_DDL = [
    """CREATE NODE TABLE IF NOT EXISTS Anartha(
        name STRING,
        description STRING,
        symptoms STRING,
        guna STRING,
        PRIMARY KEY(name)
    )""",
    """CREATE NODE TABLE IF NOT EXISTS GitaIncident(
        chunk_id STRING,
        name STRING,
        chapter STRING,
        personality STRING,
        emotional_state STRING,
        full_text STRING,
        problem_domain STRING,
        PRIMARY KEY(chunk_id)
    )""",
    """CREATE NODE TABLE IF NOT EXISTS YogaTeaching(
        chunk_id STRING,
        name STRING,
        section INT64,
        full_text STRING,
        core_principle STRING,
        PRIMARY KEY(chunk_id)
    )""",
    """CREATE NODE TABLE IF NOT EXISTS NatureAnalogy(
        chunk_id STRING,
        name STRING,
        full_text STRING,
        maps_concept STRING,
        natural_element STRING,
        PRIMARY KEY(chunk_id)
    )""",
    """CREATE NODE TABLE IF NOT EXISTS UserProblemDomain(
        name STRING,
        PRIMARY KEY(name)
    )""",
]

REL_TABLE_DDL = [
    "CREATE REL TABLE IF NOT EXISTS CAUSES(FROM Anartha TO Anartha)",
    "CREATE REL TABLE IF NOT EXISTS PRESENT_IN(FROM Anartha TO GitaIncident)",
    "CREATE REL TABLE IF NOT EXISTS RESOLVED_BY(FROM GitaIncident TO YogaTeaching)",
    "CREATE REL TABLE IF NOT EXISTS ILLUSTRATED_BY(FROM YogaTeaching TO NatureAnalogy)",
    "CREATE REL TABLE IF NOT EXISTS MAPS_TO(FROM UserProblemDomain TO Anartha)",
]

# ---------------------------------------------------------------------------
# LLM system prompt for edge discovery
# ---------------------------------------------------------------------------

# Load Kuru dynasty family info for edge discovery context
_kuru_family_text = KURU_FAMILY_PATH.read_text(encoding="utf-8").strip()

EDGE_DISCOVERY_SYSTEM_PROMPT = f"""\
You are a Vedic scholar building a knowledge graph of the Bhagavad Gita teachings.

You are given lists of nodes from a Gita discourse:
- Anartha nodes: The 6 enemies of the mind (Kama, Krodha, Lobha, Moha, Mada, Matsarya)
- GitaIncident nodes: Real historical incidents from the discourse (with chunk_id and summary)
- YogaTeaching nodes: Teaching explanations (with chunk_id and summary)
- NatureAnalogy nodes: Nature metaphors and illustrations (with chunk_id and summary)

KURU DYNASTY FAMILY CONTEXT (use this to understand family relationships in incidents):
{_kuru_family_text}

Your task: Identify the RELATIONSHIPS between these nodes.

1. PRESENT_IN: Which Anartha is demonstrated/present in which GitaIncident? An incident \
about Arjuna's grief shows Moha. An incident about Duryodhana's calculation shows Mada and Lobha.

2. RESOLVED_BY: Which GitaIncident is resolved/addressed by which YogaTeaching? \
Arjuna's grief is resolved by Sankhya knowledge and ultimately Bhakti Yoga.

3. ILLUSTRATED_BY: Which YogaTeaching is illustrated by which NatureAnalogy? \
The teaching of Bhakti Yoga is illustrated by the iron rod in fire analogy.

4. CAUSES: Which Anartha causes/leads to which other Anartha? \
Kama (lust) when frustrated causes Krodha (anger). Lobha (greed) feeds Matsarya (envy).

Rules:
- Use the chunk_ids exactly as provided for from_id and to_id.
- For Anartha nodes, use the name (e.g., 'Kama', 'Krodha').
- One node can have MULTIPLE relationships.
- Be thorough — capture every genuine relationship visible in the data.
- Only create relationships that are philosophically sound per the Gita teachings.\
"""


# ---------------------------------------------------------------------------
# Helper: load data files
# ---------------------------------------------------------------------------

def _load_chunks_tagged() -> list[dict]:
    """Load chunks_tagged.jsonl into a list of dicts."""
    chunks = []
    with open(CHUNKS_TAGGED_PATH, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    logger.info("Loaded %d tagged chunks from %s", len(chunks), CHUNKS_TAGGED_PATH)
    return chunks


def _load_routing_json() -> dict:
    """Load routing/ministructure.json."""
    with open(ROUTING_JSON_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    logger.info("Loaded routing JSON from %s", ROUTING_JSON_PATH)
    return data


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

def _create_schema(conn: kuzu.Connection) -> None:
    """Create all node and relationship tables."""
    for ddl in NODE_TABLE_DDL:
        conn.execute(ddl)
        logger.info("Executed: %s", ddl.split("(")[0].strip())
    for ddl in REL_TABLE_DDL:
        conn.execute(ddl)
        logger.info("Executed: %s", ddl.strip())


# ---------------------------------------------------------------------------
# Node insertion
# ---------------------------------------------------------------------------

def _insert_anartha_nodes(conn: kuzu.Connection) -> int:
    """Insert the 6 Anartha nodes."""
    for a in ANARTHAS:
        conn.execute(
            "CREATE (n:Anartha {name: $name, description: $description, symptoms: $sym, guna: $guna})",
            parameters={
                "name": a["name"],
                "description": a["description"],
                "sym": a["symptoms"],
                "guna": a["guna"],
            },
        )
    logger.info("Inserted %d Anartha nodes", len(ANARTHAS))
    return len(ANARTHAS)


def _safe_join(val) -> str:
    """Join a list into a comma-separated string, or return as-is if already a string."""
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    if val is None:
        return ""
    return str(val)


def _insert_chunk_nodes(conn: kuzu.Connection, chunks: list[dict]) -> dict[str, int]:
    """
    Insert chunk nodes into their respective tables based on chunk_type.

    Returns a dict of {table_name: count}.
    """
    counts = {"GitaIncident": 0, "YogaTeaching": 0, "NatureAnalogy": 0}

    for chunk in chunks:
        chunk_type = chunk.get("chunk_type", "").upper()
        chunk_id = chunk.get("chunk_id", "")
        name = chunk.get("brief_summary", "")
        full_text = chunk.get("text", "")

        if chunk_type == "HISTORICAL_ACCOUNT":
            conn.execute(
                """CREATE (n:GitaIncident {
                    chunk_id: $cid, name: $name, chapter: $chapter,
                    personality: $personality, emotional_state: $emotional,
                    full_text: $text, problem_domain: $domain
                })""",
                parameters={
                    "cid": chunk_id,
                    "name": name,
                    "chapter": _safe_join(chunk.get("chapter_ref", "")),
                    "personality": _safe_join(chunk.get("personality", "")),
                    "emotional": _safe_join(chunk.get("emotional_state", "")),
                    "text": full_text,
                    "domain": _safe_join(chunk.get("problem_domain", "")),
                },
            )
            counts["GitaIncident"] += 1

        elif chunk_type == "TEACHING":
            section_val = chunk.get("section", [0])
            if isinstance(section_val, list):
                section_val = section_val[0] if section_val else 0
            if isinstance(section_val, str):
                try:
                    section_val = int(section_val)
                except ValueError:
                    section_val = 0
            conn.execute(
                """CREATE (n:YogaTeaching {
                    chunk_id: $cid, name: $name, section: $section,
                    full_text: $text, core_principle: $principle
                })""",
                parameters={
                    "cid": chunk_id,
                    "name": name,
                    "section": section_val,
                    "text": full_text,
                    "principle": _safe_join(chunk.get("core_principle", "")),
                },
            )
            counts["YogaTeaching"] += 1

        elif chunk_type == "ANALOGY":
            conn.execute(
                """CREATE (n:NatureAnalogy {
                    chunk_id: $cid, name: $name, full_text: $text,
                    maps_concept: $concept, natural_element: $element
                })""",
                parameters={
                    "cid": chunk_id,
                    "name": name,
                    "text": full_text,
                    "concept": _safe_join(chunk.get("maps_concept", "")),
                    "element": _safe_join(chunk.get("natural_element", "")),
                },
            )
            counts["NatureAnalogy"] += 1
        else:
            logger.debug("Skipping chunk %s with unknown type: %s", chunk_id, chunk_type)

    for table, count in counts.items():
        logger.info("Inserted %d %s nodes", count, table)

    return counts


def _insert_problem_domain_nodes(conn: kuzu.Connection, routing_data: dict) -> int:
    """Insert UserProblemDomain nodes from routing_table keys."""
    routing_table = routing_data.get("routing_table", routing_data)
    count = 0
    for domain_name in routing_table:
        conn.execute(
            "CREATE (n:UserProblemDomain {name: $name})",
            parameters={"name": domain_name},
        )
        count += 1
    logger.info("Inserted %d UserProblemDomain nodes", count)
    return count


# ---------------------------------------------------------------------------
# MAPS_TO edges from routing table
# ---------------------------------------------------------------------------

def _insert_maps_to_edges(conn: kuzu.Connection, routing_data: dict) -> int:
    """Create MAPS_TO edges from UserProblemDomain → Anartha based on routing_table."""
    routing_table = routing_data.get("routing_table", routing_data)
    anartha_names = {a["name"].lower(): a["name"] for a in ANARTHAS}
    count = 0

    for domain_name, entry in routing_table.items():
        # Try to find associated anarthas from the routing entry
        anarthas_for_domain = entry.get("anarthas", []) if isinstance(entry, dict) else []

        if not anarthas_for_domain:
            # Fallback: try to infer from the routing entry structure
            if isinstance(entry, dict):
                # Check if there's an anartha field or mapped values
                for key, val in entry.items():
                    if isinstance(val, str) and val.lower() in anartha_names:
                        anarthas_for_domain.append(val)
                    elif isinstance(val, list):
                        for v in val:
                            if isinstance(v, str) and v.lower() in anartha_names:
                                anarthas_for_domain.append(v)

        for anartha in anarthas_for_domain:
            anartha_proper = anartha_names.get(anartha.lower(), anartha)
            try:
                conn.execute(
                    """MATCH (u:UserProblemDomain), (a:Anartha)
                       WHERE u.name = $domain AND a.name = $anartha
                       CREATE (u)-[:MAPS_TO]->(a)""",
                    parameters={"domain": domain_name, "anartha": anartha_proper},
                )
                count += 1
            except Exception as exc:
                logger.warning("Failed MAPS_TO edge %s -> %s: %s", domain_name, anartha_proper, exc)

    logger.info("Inserted %d MAPS_TO edges", count)
    return count


# ---------------------------------------------------------------------------
# LLM-based edge discovery
# ---------------------------------------------------------------------------

def _build_node_summaries(chunks: list[dict]) -> dict[str, list[dict]]:
    """Build compact node summary lists for the LLM prompt."""
    summaries: dict[str, list[dict]] = {
        "anartha": [{"name": a["name"], "description": a["description"]} for a in ANARTHAS],
        "incidents": [],
        "teachings": [],
        "analogies": [],
    }

    for chunk in chunks:
        ct = chunk.get("chunk_type", "").upper()
        entry = {
            "chunk_id": chunk.get("chunk_id", ""),
            "summary": chunk.get("brief_summary", ""),
        }
        if ct == "HISTORICAL_ACCOUNT":
            # Include extra context for better edge discovery
            entry["personality"] = _safe_join(chunk.get("personality", ""))
            entry["emotional_state"] = _safe_join(chunk.get("emotional_state", ""))
            summaries["incidents"].append(entry)
        elif ct == "TEACHING":
            entry["core_principle"] = _safe_join(chunk.get("core_principle", ""))
            summaries["teachings"].append(entry)
        elif ct == "ANALOGY":
            entry["maps_concept"] = _safe_join(chunk.get("maps_concept", ""))
            entry["natural_element"] = _safe_join(chunk.get("natural_element", ""))
            summaries["analogies"].append(entry)

    return summaries


@retry_with_backoff()
def _discover_edges_llm(llm, summaries: dict[str, list[dict]]) -> EdgeDiscoveryResponse:
    """
    Send node summaries to Azure o4-mini and get structured edge lists back.

    If the data is large, split into batched calls.
    """
    # Build the user prompt with all node data
    user_prompt_parts = [
        "Here are the nodes in the Gita knowledge graph. Identify ALL relationships.\n",
        "## Anartha Nodes\n",
        json.dumps(summaries["anartha"], indent=2),
        "\n## GitaIncident Nodes\n",
        json.dumps(summaries["incidents"], indent=2),
        "\n## YogaTeaching Nodes\n",
        json.dumps(summaries["teachings"], indent=2),
        "\n## NatureAnalogy Nodes\n",
        json.dumps(summaries["analogies"], indent=2),
    ]
    user_prompt = "\n".join(user_prompt_parts)

    # Check if we need to batch (rough token estimate: ~4 chars per token)
    estimated_tokens = len(user_prompt) // 4
    if estimated_tokens > 80_000:
        return _discover_edges_batched(llm, summaries)

    structured_llm = llm.with_structured_output(EdgeDiscoveryResponse)
    response = structured_llm.invoke([
        {"role": "system", "content": EDGE_DISCOVERY_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ])
    return response


@retry_with_backoff()
def _discover_present_in(llm, summaries: dict) -> list[Edge]:
    """Batch call: discover PRESENT_IN edges (Anartha -> GitaIncident)."""
    user_prompt = (
        "Identify which Anarthas are PRESENT_IN which GitaIncidents.\n\n"
        "## Anartha Nodes\n" + json.dumps(summaries["anartha"], indent=2) +
        "\n\n## GitaIncident Nodes\n" + json.dumps(summaries["incidents"], indent=2)
    )

    class PresInResponse(BaseModel):
        present_in: list[Edge]

    structured_llm = llm.with_structured_output(PresInResponse)
    response = structured_llm.invoke([
        {"role": "system", "content": EDGE_DISCOVERY_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ])
    return response.present_in


@retry_with_backoff()
def _discover_resolved_by(llm, summaries: dict) -> list[Edge]:
    """Batch call: discover RESOLVED_BY edges (GitaIncident -> YogaTeaching)."""
    user_prompt = (
        "Identify which GitaIncidents are RESOLVED_BY which YogaTeachings.\n\n"
        "## GitaIncident Nodes\n" + json.dumps(summaries["incidents"], indent=2) +
        "\n\n## YogaTeaching Nodes\n" + json.dumps(summaries["teachings"], indent=2)
    )

    class ResolvedResponse(BaseModel):
        resolved_by: list[Edge]

    structured_llm = llm.with_structured_output(ResolvedResponse)
    response = structured_llm.invoke([
        {"role": "system", "content": EDGE_DISCOVERY_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ])
    return response.resolved_by


@retry_with_backoff()
def _discover_illustrated_by(llm, summaries: dict) -> list[Edge]:
    """Batch call: discover ILLUSTRATED_BY edges (YogaTeaching -> NatureAnalogy)."""
    user_prompt = (
        "Identify which YogaTeachings are ILLUSTRATED_BY which NatureAnalogies.\n\n"
        "## YogaTeaching Nodes\n" + json.dumps(summaries["teachings"], indent=2) +
        "\n\n## NatureAnalogy Nodes\n" + json.dumps(summaries["analogies"], indent=2)
    )

    class IllustratedResponse(BaseModel):
        illustrated_by: list[Edge]

    structured_llm = llm.with_structured_output(IllustratedResponse)
    response = structured_llm.invoke([
        {"role": "system", "content": EDGE_DISCOVERY_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ])
    return response.illustrated_by


@retry_with_backoff()
def _discover_causes(llm, summaries: dict) -> list[Edge]:
    """Batch call: discover CAUSES edges (Anartha -> Anartha)."""
    user_prompt = (
        "Identify which Anarthas CAUSE which other Anarthas.\n\n"
        "## Anartha Nodes\n" + json.dumps(summaries["anartha"], indent=2)
    )

    class CausesResponse(BaseModel):
        causes: list[Edge]

    structured_llm = llm.with_structured_output(CausesResponse)
    response = structured_llm.invoke([
        {"role": "system", "content": EDGE_DISCOVERY_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ])
    return response.causes


def _discover_edges_batched(llm, summaries: dict) -> EdgeDiscoveryResponse:
    """Discover edges in separate batched LLM calls when data is too large."""
    logger.info("Data too large for single call — batching edge discovery …")

    present_in = _discover_present_in(llm, summaries)
    processing_pause()

    resolved_by = _discover_resolved_by(llm, summaries)
    processing_pause()

    illustrated_by = _discover_illustrated_by(llm, summaries)
    processing_pause()

    causes = _discover_causes(llm, summaries)

    return EdgeDiscoveryResponse(
        present_in=present_in,
        resolved_by=resolved_by,
        illustrated_by=illustrated_by,
        causes=causes,
    )


# ---------------------------------------------------------------------------
# Edge insertion
# ---------------------------------------------------------------------------

def _insert_edge(conn: kuzu.Connection, cypher: str, params: dict, label: str) -> bool:
    """Execute an edge creation query; return True on success."""
    try:
        conn.execute(cypher, parameters=params)
        return True
    except Exception as exc:
        logger.warning("Failed %s edge %s -> %s: %s", label, params.get("fid", "?"), params.get("tid", "?"), exc)
        return False


def _insert_discovered_edges(conn: kuzu.Connection, edges: EdgeDiscoveryResponse) -> dict[str, int]:
    """Insert all LLM-discovered edges into the graph."""
    counts = {"PRESENT_IN": 0, "RESOLVED_BY": 0, "ILLUSTRATED_BY": 0, "CAUSES": 0}

    # PRESENT_IN: Anartha -> GitaIncident
    for edge in edges.present_in:
        ok = _insert_edge(
            conn,
            """MATCH (a:Anartha), (g:GitaIncident)
               WHERE a.name = $fid AND g.chunk_id = $tid
               CREATE (a)-[:PRESENT_IN]->(g)""",
            {"fid": edge.from_id, "tid": edge.to_id},
            "PRESENT_IN",
        )
        if ok:
            counts["PRESENT_IN"] += 1

    # RESOLVED_BY: GitaIncident -> YogaTeaching
    for edge in edges.resolved_by:
        ok = _insert_edge(
            conn,
            """MATCH (g:GitaIncident), (y:YogaTeaching)
               WHERE g.chunk_id = $fid AND y.chunk_id = $tid
               CREATE (g)-[:RESOLVED_BY]->(y)""",
            {"fid": edge.from_id, "tid": edge.to_id},
            "RESOLVED_BY",
        )
        if ok:
            counts["RESOLVED_BY"] += 1

    # ILLUSTRATED_BY: YogaTeaching -> NatureAnalogy
    for edge in edges.illustrated_by:
        ok = _insert_edge(
            conn,
            """MATCH (y:YogaTeaching), (n:NatureAnalogy)
               WHERE y.chunk_id = $fid AND n.chunk_id = $tid
               CREATE (y)-[:ILLUSTRATED_BY]->(n)""",
            {"fid": edge.from_id, "tid": edge.to_id},
            "ILLUSTRATED_BY",
        )
        if ok:
            counts["ILLUSTRATED_BY"] += 1

    # CAUSES: Anartha -> Anartha
    for edge in edges.causes:
        ok = _insert_edge(
            conn,
            """MATCH (a1:Anartha), (a2:Anartha)
               WHERE a1.name = $fid AND a2.name = $tid
               CREATE (a1)-[:CAUSES]->(a2)""",
            {"fid": edge.from_id, "tid": edge.to_id},
            "CAUSES",
        )
        if ok:
            counts["CAUSES"] += 1

    for rel, count in counts.items():
        logger.info("Inserted %d %s edges", count, rel)

    return counts


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _print_summary(conn: kuzu.Connection) -> None:
    """Query and print node/edge counts per type."""
    print("\n" + "=" * 60)
    print("KUZU GRAPH SUMMARY")
    print("=" * 60)

    node_tables = ["Anartha", "GitaIncident", "YogaTeaching", "NatureAnalogy", "UserProblemDomain"]
    for table in node_tables:
        try:
            result = conn.execute(f"MATCH (n:{table}) RETURN count(n) AS cnt")
            while result.has_next():
                row = result.get_next()
                print(f"  {table:30s}: {row[0]:>5d} nodes")
        except Exception as exc:
            print(f"  {table:30s}: ERROR ({exc})")

    rel_tables = ["CAUSES", "PRESENT_IN", "RESOLVED_BY", "ILLUSTRATED_BY", "MAPS_TO"]
    for table in rel_tables:
        try:
            result = conn.execute(f"MATCH ()-[r:{table}]->() RETURN count(r) AS cnt")
            while result.has_next():
                row = result.get_next()
                print(f"  {table:30s}: {row[0]:>5d} edges")
        except Exception as exc:
            print(f"  {table:30s}: ERROR ({exc})")

    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Build the Kuzu knowledge graph."""
    logger.info("Starting Kuzu graph build …")

    # Load data
    chunks = _load_chunks_tagged()
    routing_data = _load_routing_json()

    # Open / create Kuzu DB
    logger.info("Opening Kuzu DB at %s", GRAPHDB_DIR)
    db = kuzu.Database(str(GRAPHDB_DIR))
    conn = kuzu.Connection(db)

    # Create schema
    logger.info("Creating schema …")
    _create_schema(conn)

    # Insert nodes
    logger.info("Inserting Anartha nodes …")
    _insert_anartha_nodes(conn)

    logger.info("Inserting chunk nodes …")
    _insert_chunk_nodes(conn, chunks)

    logger.info("Inserting UserProblemDomain nodes …")
    _insert_problem_domain_nodes(conn, routing_data)

    # Insert MAPS_TO edges from routing table
    logger.info("Inserting MAPS_TO edges from routing table …")
    _insert_maps_to_edges(conn, routing_data)

    # LLM edge discovery
    logger.info("Discovering edges via LLM …")
    llm = get_azure_llm()
    summaries = _build_node_summaries(chunks)

    logger.info(
        "Node summaries — Anarthas: %d, Incidents: %d, Teachings: %d, Analogies: %d",
        len(summaries["anartha"]),
        len(summaries["incidents"]),
        len(summaries["teachings"]),
        len(summaries["analogies"]),
    )

    edge_response = _discover_edges_llm(llm, summaries)
    processing_pause()

    logger.info("Inserting discovered edges …")
    _insert_discovered_edges(conn, edge_response)

    # Print summary
    _print_summary(conn)

    logger.info("Kuzu graph build complete.")


if __name__ == "__main__":
    main()
