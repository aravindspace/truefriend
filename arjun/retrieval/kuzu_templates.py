"""Whitelisted Kuzu query templates — §8.2 step 2: traverse.

The LLM NEVER writes Cypher. It picks a template name and supplies
parameters; every parameter is validated against enums (6 anarthas) or
strict patterns (chunk ids, personality names). A bad parameter or a
failed query yields an empty result — never an error, never a write.

Opens ONLY the working clone ``arjun_action/self_learning_db`` (read-only
Kuzu mode); the master path is not imported here (§8.1).
"""

import logging
import re
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "arjun_action" / "self_learning_db"

logger = logging.getLogger("arjun.retrieval")

ANARTHAS = frozenset({"Kama", "Krodha", "Lobha", "Moha", "Mada", "Matsarya"})
_CHUNK_RE = re.compile(r"^chunk_\d+$")
_NAME_RE = re.compile(r"^[^\W\d_](?:[^\W\d_]|[ '’-])*$", re.UNICODE)  # letters/spaces only


def _is_anartha(v) -> bool:
    return v in ANARTHAS


def _is_chunk_id(v) -> bool:
    return isinstance(v, str) and bool(_CHUNK_RE.match(v))


def _is_name(v) -> bool:
    return isinstance(v, str) and 0 < len(v) < 60 and bool(_NAME_RE.match(v))


#: template name → (cypher, {param: validator}). The whitelist IS the API.
TEMPLATES: dict[str, tuple[str, dict]] = {
    "anartha_incidents": (
        "MATCH (a:Anartha {name: $anartha})-[:PRESENT_IN]->(i:GitaIncident) "
        "RETURN i.chunk_id AS chunk_id, i.name AS name, i.full_text AS full_text LIMIT 10",
        {"anartha": _is_anartha},
    ),
    "anartha_chain": (
        "MATCH (a:Anartha {name: $anartha})-[:PRESENT_IN]->(i:GitaIncident)"
        "-[:RESOLVED_BY]->(t:YogaTeaching)-[:ILLUSTRATED_BY]->(n:NatureAnalogy) "
        "RETURN i.chunk_id AS incident_id, i.full_text AS incident_text, "
        "t.chunk_id AS teaching_id, t.full_text AS teaching_text, "
        "n.chunk_id AS analogy_id, n.full_text AS analogy_text LIMIT 5",
        {"anartha": _is_anartha},
    ),
    "incident_teachings": (
        "MATCH (i:GitaIncident {chunk_id: $chunk_id})-[:RESOLVED_BY]->(t:YogaTeaching) "
        "RETURN t.chunk_id AS chunk_id, t.name AS name, t.full_text AS full_text LIMIT 5",
        {"chunk_id": _is_chunk_id},
    ),
    "teaching_analogies": (
        "MATCH (t:YogaTeaching {chunk_id: $chunk_id})-[:ILLUSTRATED_BY]->(n:NatureAnalogy) "
        "RETURN n.chunk_id AS chunk_id, n.name AS name, n.full_text AS full_text LIMIT 5",
        {"chunk_id": _is_chunk_id},
    ),
    "personality_incidents": (
        "MATCH (p:HistoricalPersonality {name: $personality})-[:APPEARS_IN]->(i:GitaIncident) "
        "RETURN i.chunk_id AS chunk_id, i.name AS name, i.full_text AS full_text, "
        "p.role AS role LIMIT 10",
        {"personality": _is_name},
    ),
    "personality_relatives": (
        "MATCH (p:HistoricalPersonality {name: $personality})-[:PARENT_OF|MARRIED_TO]-"
        "(rel:HistoricalPersonality) "
        "RETURN rel.name AS name, rel.role AS role, rel.dynasty AS dynasty LIMIT 20",
        {"personality": _is_name},
    ),
}

_db = None


def _connection():
    global _db
    import kuzu

    if _db is None:
        _db = kuzu.Database(str(DB_PATH), read_only=True)
    return kuzu.Connection(_db)


def run_template(name: str, **params) -> list[dict]:
    """Execute one whitelisted template. Anything invalid → [] (never an
    error, never a write)."""
    if name not in TEMPLATES:
        return []
    cypher, validators = TEMPLATES[name]
    if set(params) != set(validators) or not all(
        validators[key](value) for key, value in params.items()
    ):
        return []
    try:
        conn = _connection()
        result = conn.execute(cypher, parameters=params)
        columns = result.get_column_names()
        rows = []
        while result.has_next():
            rows.append(dict(zip(columns, result.get_next())))
        conn.close()
        return rows
    except Exception as exc:
        logger.warning("kuzu template %r failed (%s) — empty result", name, exc)
        return []


def chunk_exists(chunk_id: str) -> bool:
    """Deterministic Canon traceability check (used by the output guardrail,
    P1.16): does this chunk_id exist on any Canon node type?"""
    if not _is_chunk_id(chunk_id):
        return False
    for table in ("GitaIncident", "YogaTeaching", "NatureAnalogy"):
        try:
            conn = _connection()
            result = conn.execute(
                f"MATCH (n:{table} {{chunk_id: $chunk_id}}) RETURN n.chunk_id LIMIT 1",
                parameters={"chunk_id": chunk_id},
            )
            found = result.has_next()
            conn.close()
            if found:
                return True
        except Exception as exc:
            logger.warning("chunk_exists(%s) on %s failed: %s", chunk_id, table, exc)
    return False
