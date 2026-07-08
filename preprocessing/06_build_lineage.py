"""
Step 06 — Build Kuru Dynasty Lineage

Parses kuru_family.txt via LLM to extract historical personalities and
family relationships, then creates HistoricalPersonality nodes + family
edges in the existing Kuzu graph DB, and links personalities to
GitaIncident nodes via APPEARS_IN edges.
"""

import json
from typing import Literal

import kuzu
from pydantic import BaseModel

from config import (
    get_azure_llm,
    retry_with_backoff,
    processing_pause,
    get_logger,
    KURU_FAMILY_PATH,
    GRAPHDB_DIR,
)

logger = get_logger("06_build_lineage")

# ---------------------------------------------------------------------------
# Pydantic models for LLM-parsed lineage data
# ---------------------------------------------------------------------------

class HistoricalPersonality(BaseModel):
    name: str
    dynasty: str
    father: str           # empty string if unknown
    mother: str           # empty string if unknown
    divine_father: str    # empty string if not applicable
    generation: int       # 1 = Shantanu, 2 = Dhritarashtra/Pandu, 3 = Pandavas/Kauravas, etc.
    role: str             # brief description


class FamilyRelationship(BaseModel):
    from_person: str
    to_person: str
    relationship: Literal["PARENT_OF", "MARRIED_TO"]


class LineageParseResponse(BaseModel):
    personalities: list[HistoricalPersonality]
    relationships: list[FamilyRelationship]


# ---------------------------------------------------------------------------
# LLM system prompt
# ---------------------------------------------------------------------------

LINEAGE_SYSTEM_PROMPT = """\
You are parsing a Kuru dynasty genealogy document from the Mahabharata.

Extract ALL historical personalities and their family relationships.

For each personality, provide:
- name: The primary name used in the Mahabharata (e.g., "Arjuna", not "Partha")
- dynasty: "Kuru" for all (except note if from another dynasty like Yadu for Krishna)
- father: biological or legal father's name (empty string if not stated)
- mother: mother's name (empty string if not stated)
- divine_father: if the personality has a divine/celestial father (e.g., Indra for Arjuna), \
state it; empty string if not applicable
- generation: generational number (1 = Shantanu/Ganga level, 2 = Dhritarashtra/Pandu/Vidura, \
3 = Pandavas/Kauravas, 4 = Abhimanyu/Upapandavas, 5 = Parikshit)
- role: brief description of their role

For relationships:
- PARENT_OF: from parent to child (father→child OR mother→child)
- MARRIED_TO: between spouses (create one edge per couple, from_person alphabetically first)

Be EXHAUSTIVE — extract every personality mentioned in the document, including minor ones.\
"""

# ---------------------------------------------------------------------------
# Schema DDL for lineage tables
# ---------------------------------------------------------------------------

NODE_TABLE_DDL = [
    """CREATE NODE TABLE IF NOT EXISTS HistoricalPersonality(
        name STRING,
        dynasty STRING,
        father STRING,
        mother STRING,
        divine_father STRING,
        generation INT64,
        role STRING,
        PRIMARY KEY(name)
    )""",
    """CREATE NODE TABLE IF NOT EXISTS Dynasty(
        name STRING,
        PRIMARY KEY(name)
    )""",
]

REL_TABLE_DDL = [
    "CREATE REL TABLE IF NOT EXISTS PARENT_OF(FROM HistoricalPersonality TO HistoricalPersonality)",
    "CREATE REL TABLE IF NOT EXISTS MARRIED_TO(FROM HistoricalPersonality TO HistoricalPersonality)",
    "CREATE REL TABLE IF NOT EXISTS BELONGS_TO_DYNASTY(FROM HistoricalPersonality TO Dynasty)",
    "CREATE REL TABLE IF NOT EXISTS APPEARS_IN(FROM HistoricalPersonality TO GitaIncident)",
]


# ---------------------------------------------------------------------------
# Parse lineage via LLM
# ---------------------------------------------------------------------------

@retry_with_backoff()
def _parse_lineage(llm, family_text: str) -> LineageParseResponse:
    """Send the family text to the LLM and get structured lineage data back."""
    structured_llm = llm.with_structured_output(LineageParseResponse)
    response = structured_llm.invoke([
        {"role": "system", "content": LINEAGE_SYSTEM_PROMPT},
        {"role": "user", "content": f"Parse the following genealogy document:\n\n{family_text}"},
    ])
    return response


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

def _create_schema(conn: kuzu.Connection) -> None:
    """Create lineage-specific node and relationship tables."""
    for ddl in NODE_TABLE_DDL:
        conn.execute(ddl)
        logger.info("Executed: %s", ddl.split("(")[0].strip())
    for ddl in REL_TABLE_DDL:
        conn.execute(ddl)
        logger.info("Executed: %s", ddl.strip())


# ---------------------------------------------------------------------------
# Node insertion
# ---------------------------------------------------------------------------

def _insert_dynasty_node(conn: kuzu.Connection) -> None:
    """Insert the Kuru dynasty node."""
    conn.execute(
        "CREATE (d:Dynasty {name: $name})",
        parameters={"name": "Kuru"},
    )
    logger.info("Inserted Dynasty node: Kuru")


def _insert_personality_nodes(
    conn: kuzu.Connection,
    personalities: list[HistoricalPersonality],
) -> int:
    """Insert all HistoricalPersonality nodes. Returns count of inserted nodes."""
    inserted = 0
    for person in personalities:
        try:
            conn.execute(
                """CREATE (p:HistoricalPersonality {
                    name: $name, dynasty: $dynasty, father: $father,
                    mother: $mother, divine_father: $divine, generation: $gen,
                    role: $role
                })""",
                parameters={
                    "name": person.name,
                    "dynasty": person.dynasty,
                    "father": person.father,
                    "mother": person.mother,
                    "divine": person.divine_father,
                    "gen": person.generation,
                    "role": person.role,
                },
            )
            inserted += 1
        except Exception as exc:
            logger.warning("Failed to insert personality %s: %s", person.name, exc)

    logger.info("Inserted %d / %d HistoricalPersonality nodes", inserted, len(personalities))
    return inserted


# ---------------------------------------------------------------------------
# Edge insertion
# ---------------------------------------------------------------------------

def _insert_family_edges(
    conn: kuzu.Connection,
    relationships: list[FamilyRelationship],
) -> dict[str, int]:
    """Insert PARENT_OF and MARRIED_TO edges. Returns counts per type."""
    counts = {"PARENT_OF": 0, "MARRIED_TO": 0}

    for rel in relationships:
        rel_type = rel.relationship
        try:
            conn.execute(
                f"""MATCH (a:HistoricalPersonality), (b:HistoricalPersonality)
                    WHERE a.name = $from_p AND b.name = $to_p
                    CREATE (a)-[:{rel_type}]->(b)""",
                parameters={"from_p": rel.from_person, "to_p": rel.to_person},
            )
            counts[rel_type] += 1
        except Exception as exc:
            logger.warning(
                "Failed %s edge %s -> %s: %s",
                rel_type, rel.from_person, rel.to_person, exc,
            )

    for rel_type, count in counts.items():
        logger.info("Inserted %d %s edges", count, rel_type)

    return counts


def _insert_belongs_to_dynasty_edges(
    conn: kuzu.Connection,
    personalities: list[HistoricalPersonality],
) -> int:
    """Create BELONGS_TO_DYNASTY edges for all personalities → Kuru dynasty."""
    count = 0
    for person in personalities:
        dynasty_name = person.dynasty if person.dynasty else "Kuru"
        try:
            # Check if the dynasty node exists; if not Kuru, we might need to create it
            if dynasty_name != "Kuru":
                try:
                    conn.execute(
                        "CREATE (d:Dynasty {name: $name})",
                        parameters={"name": dynasty_name},
                    )
                    logger.info("Created additional Dynasty node: %s", dynasty_name)
                except Exception:
                    pass  # Node already exists

            conn.execute(
                """MATCH (p:HistoricalPersonality), (d:Dynasty)
                   WHERE p.name = $person AND d.name = $dynasty
                   CREATE (p)-[:BELONGS_TO_DYNASTY]->(d)""",
                parameters={"person": person.name, "dynasty": dynasty_name},
            )
            count += 1
        except Exception as exc:
            logger.warning(
                "Failed BELONGS_TO_DYNASTY edge %s -> %s: %s",
                person.name, dynasty_name, exc,
            )

    logger.info("Inserted %d BELONGS_TO_DYNASTY edges", count)
    return count


def _insert_appears_in_edges(
    conn: kuzu.Connection,
    personalities: list[HistoricalPersonality],
) -> int:
    """
    Create APPEARS_IN edges: for each HistoricalPersonality, find all
    GitaIncident nodes whose `personality` field contains that person's name.
    """
    count = 0
    for person in personalities:
        try:
            # Query GitaIncident nodes whose personality field contains this name
            result = conn.execute(
                """MATCH (g:GitaIncident)
                   WHERE g.personality CONTAINS $name
                   RETURN g.chunk_id""",
                parameters={"name": person.name},
            )
            incident_ids = []
            while result.has_next():
                row = result.get_next()
                incident_ids.append(row[0])

            for chunk_id in incident_ids:
                try:
                    conn.execute(
                        """MATCH (p:HistoricalPersonality), (g:GitaIncident)
                           WHERE p.name = $person AND g.chunk_id = $cid
                           CREATE (p)-[:APPEARS_IN]->(g)""",
                        parameters={"person": person.name, "cid": chunk_id},
                    )
                    count += 1
                except Exception as exc:
                    logger.warning(
                        "Failed APPEARS_IN edge %s -> %s: %s",
                        person.name, chunk_id, exc,
                    )

            if incident_ids:
                logger.debug(
                    "%s appears in %d GitaIncident(s)", person.name, len(incident_ids),
                )
        except Exception as exc:
            logger.warning("Failed querying incidents for %s: %s", person.name, exc)

    logger.info("Inserted %d APPEARS_IN edges", count)
    return count


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _print_summary(conn: kuzu.Connection) -> None:
    """Print lineage-specific summary."""
    print("\n" + "=" * 60)
    print("LINEAGE GRAPH SUMMARY")
    print("=" * 60)

    tables_to_count = [
        ("HistoricalPersonality", "node"),
        ("Dynasty", "node"),
    ]
    for table, kind in tables_to_count:
        try:
            result = conn.execute(f"MATCH (n:{table}) RETURN count(n) AS cnt")
            while result.has_next():
                row = result.get_next()
                print(f"  {table:30s}: {row[0]:>5d} {kind}s")
        except Exception as exc:
            print(f"  {table:30s}: ERROR ({exc})")

    rel_tables = ["PARENT_OF", "MARRIED_TO", "BELONGS_TO_DYNASTY", "APPEARS_IN"]
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
    """Parse Kuru dynasty lineage and build graph nodes + edges."""
    logger.info("Starting Kuru dynasty lineage build …")

    # Read family text
    family_text = KURU_FAMILY_PATH.read_text(encoding="utf-8")
    logger.info("Read %d characters from %s", len(family_text), KURU_FAMILY_PATH)

    # Parse via LLM
    logger.info("Parsing lineage via Azure o4-mini …")
    llm = get_azure_llm()
    lineage = _parse_lineage(llm, family_text)
    processing_pause()

    logger.info(
        "LLM returned %d personalities, %d relationships",
        len(lineage.personalities),
        len(lineage.relationships),
    )

    # Open existing Kuzu DB (same DB as step 05)
    logger.info("Opening Kuzu DB at %s", GRAPHDB_DIR)
    db = kuzu.Database(str(GRAPHDB_DIR))
    conn = kuzu.Connection(db)

    # Create lineage schema
    logger.info("Creating lineage schema …")
    _create_schema(conn)

    # Insert nodes
    logger.info("Inserting Dynasty node …")
    _insert_dynasty_node(conn)

    logger.info("Inserting HistoricalPersonality nodes …")
    personality_count = _insert_personality_nodes(conn, lineage.personalities)

    # Insert family edges
    logger.info("Inserting family relationship edges …")
    family_edge_counts = _insert_family_edges(conn, lineage.relationships)

    # Insert BELONGS_TO_DYNASTY edges
    logger.info("Inserting BELONGS_TO_DYNASTY edges …")
    dynasty_edge_count = _insert_belongs_to_dynasty_edges(conn, lineage.personalities)

    # Insert APPEARS_IN edges (personality → GitaIncident)
    logger.info("Inserting APPEARS_IN edges …")
    appears_in_count = _insert_appears_in_edges(conn, lineage.personalities)

    # Print summary
    _print_summary(conn)

    total_edges = sum(family_edge_counts.values()) + dynasty_edge_count + appears_in_count
    logger.info(
        "Lineage build complete: %d personalities, %d total edges",
        personality_count,
        total_edges,
    )


if __name__ == "__main__":
    main()
