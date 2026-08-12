"""
Step 07 — Edge backfill (P1.20, architecture §8.3)

Fixes the thin Canon graph: 3 RESOLVED_BY / 3 ILLUSTRATED_BY edges against
68 incidents / 876 teachings / 84 analogies, and PRESENT_IN edges that leave
Kama with zero incidents.

Procedure (§8.3), in order:

    1. Fresh clone:  graphdb/gita_graph  →  arjun_action/self_learning_db__staging
    2. Candidates:   Qdrant nearest neighbours (deterministic, no LLM, no cost).
                     The chunks are already embedded, so their stored vectors are
                     reused directly — no embedding model is loaded.
    3. Proposals:    the LLM sees ONE incident + its candidate teachings and emits
                     Pydantic structured output — chunk-id pairs with confidence.
                     It never writes Cypher and never sees the database.
    4. Insertion:    deterministic code validates both ids exist in the clone,
                     skips duplicates, and inserts via fixed parameterized
                     statements into the STAGING clone only.
    5. Report:       edge counts before/after, confidence distribution, random
                     samples for human reading.
    6. STOP:         the owner reads the report and approves.  Only then does
                     ``--promote`` swap the staging clone into place (the current
                     clone is kept as a timestamped backup).

Worst case is a discarded clone — the master `graphdb/` is opened read-only and
the live `arjun_action/self_learning_db` is untouched until `--promote`.

Usage
-----
    python preprocessing/07_backfill_edges.py --stage            # full run
    python preprocessing/07_backfill_edges.py --stage --limit 3  # cheap dry run
    python preprocessing/07_backfill_edges.py --report           # re-render report
    python preprocessing/07_backfill_edges.py --promote          # AFTER approval
"""

import argparse
import json
import random
import shutil
import uuid
import warnings
from datetime import datetime
from pathlib import Path

import kuzu
from pydantic import BaseModel, Field

from config import (
    PROJECT_ROOT,
    GRAPHDB_DIR,
    VECTORDB_DIR,
    DATA_PROCESSED,
    get_azure_llm,
    get_logger,
    processing_pause,
    retry_with_backoff,
)

logger = get_logger("07_backfill_edges")

# LangChain re-serializes the parsed model inside the raw response; harmless.
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic.main")

# ── Paths & constants ────────────────────────────────────────────────

LIVE_DB = PROJECT_ROOT / "arjun_action" / "self_learning_db"
STAGING_DB = PROJECT_ROOT / "arjun_action" / "self_learning_db__staging"
PROPOSALS_PATH = DATA_PROCESSED / "edge_proposals.jsonl"
REPORTS_DIR = PROJECT_ROOT / "preprocessing" / "reports"

UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # same as step 04

ANARTHAS = ("Kama", "Krodha", "Lobha", "Moha", "Mada", "Matsarya")

TEACHING_CANDIDATES = 12   # nearest teachings offered per incident
ANALOGY_CANDIDATES = 8     # nearest analogies offered per teaching
MIN_CONFIDENCE = 0.6       # below this a proposal is recorded but NOT inserted
MAX_TEACHINGS_PER_INCIDENT = 3
MAX_ANALOGIES_PER_TEACHING = 2
MAX_ANARTHAS_PER_INCIDENT = 4


# ── Structured output models (the LLM only ever emits these) ─────────

class AnarthaLink(BaseModel):
    """One anartha judged to be at work in an incident."""
    anartha: str = Field(description=f"exactly one of: {', '.join(ANARTHAS)}")
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(description="one short sentence")


class ChunkLink(BaseModel):
    """One candidate chunk judged to be genuinely related."""
    chunk_id: str = Field(description="a chunk_id copied EXACTLY from the candidates")
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(description="one short sentence")


class IncidentReading(BaseModel):
    """LLM verdict for one GitaIncident."""
    anarthas: list[AnarthaLink] = Field(default_factory=list)
    teachings: list[ChunkLink] = Field(default_factory=list)


class TeachingIllustration(BaseModel):
    """LLM verdict for one YogaTeaching."""
    analogies: list[ChunkLink] = Field(default_factory=list)


INCIDENT_SYSTEM_PROMPT = """You are a Bhagavad Gita scholar working in the disciplic
tradition (parampara). Kurukshetra, Arjuna, Krishna and the Kuru dynasty are real
historical places, persons and events — never "characters" or "stories".

You are given ONE recorded incident from the Gita discourse, and a list of candidate
teaching passages retrieved by semantic similarity. Two judgements are asked of you:

1. ANARTHAS — which of the six anarthas are at work in this incident?
   Kama (unbridled desire) · Krodha (anger when desire is blocked) ·
   Lobha (greed, hoarding) · Moha (delusion, misidentification with the body) ·
   Mada (pride, intoxication of ego) · Matsarya (envy of others' fortune).
   A real life situation usually carries SEVERAL braided together. Name the ones
   genuinely present; do not force all six.

2. TEACHINGS — which candidate teachings actually RESOLVE this incident? A teaching
   resolves an incident when applying it would dissolve the anartha at work, not
   merely when it shares vocabulary. Be strict: choose at most three, and it is
   correct to choose none.

Rules:
- Copy chunk_ids EXACTLY from the candidate list. Never invent one.
- Confidence is your honest strength of judgement (0.0–1.0).
- Reasons are one short sentence each."""

ANALOGY_SYSTEM_PROMPT = """You are a Bhagavad Gita scholar working in the disciplic
tradition (parampara).

You are given ONE teaching from the Gita discourse and candidate nature analogies
that Lord Krishna uses (moth and fire, iron rod in fire, lotus leaf, banyan tree …).

Decide which candidate analogies genuinely ILLUSTRATE this teaching — the analogy
must picture the very principle the teaching states. Choose at most two; choosing
none is correct when nothing fits.

Rules:
- Copy chunk_ids EXACTLY from the candidate list. Never invent one.
- Confidence is your honest strength of judgement (0.0–1.0).
- Reasons are one short sentence each."""


# ── Step 1: clone ────────────────────────────────────────────────────

def clone_master() -> None:
    """Fresh copy of the canon master into the staging path (§8.3)."""
    if not GRAPHDB_DIR.exists():
        raise SystemExit(f"Canon master not found: {GRAPHDB_DIR}")
    if STAGING_DB.exists():
        logger.info("Removing previous staging clone %s", STAGING_DB)
        _remove(STAGING_DB)
    logger.info("Cloning %s → %s", GRAPHDB_DIR, STAGING_DB)
    if GRAPHDB_DIR.is_dir():
        shutil.copytree(GRAPHDB_DIR, STAGING_DB)
    else:
        shutil.copy2(GRAPHDB_DIR, STAGING_DB)


def _remove(path: Path) -> None:
    shutil.rmtree(path) if path.is_dir() else path.unlink()


# ── Step 2: candidates from Qdrant (deterministic, no LLM) ───────────

class Candidates:
    """Nearest-neighbour lookup over the Canon collections.

    The chunks were embedded in step 04 with deterministic point ids
    (uuid5 of the chunk_id), so a chunk's own vector can be fetched and
    re-queried against another collection — no embedding model needed.
    """

    def __init__(self) -> None:
        from qdrant_client import QdrantClient

        self.client = QdrantClient(path=str(VECTORDB_DIR))

    def close(self) -> None:
        self.client.close()

    def _vector(self, collection: str, chunk_id: str) -> list[float] | None:
        points = self.client.retrieve(
            collection_name=collection,
            ids=[str(uuid.uuid5(UUID_NAMESPACE, chunk_id))],
            with_vectors=True,
        )
        return points[0].vector if points else None

    def neighbours(
        self, source_collection: str, chunk_id: str, target_collection: str, limit: int
    ) -> list[dict]:
        """Nearest chunks in ``target_collection`` to the given chunk."""
        vector = self._vector(source_collection, chunk_id)
        if vector is None:
            logger.warning("No vector for %s in %s", chunk_id, source_collection)
            return []
        response = self.client.query_points(
            collection_name=target_collection,
            query=vector,
            limit=limit,
            with_payload=True,
        )
        return [
            {
                "chunk_id": point.payload["chunk_id"],
                "summary": point.payload.get("brief_summary", ""),
                "context": point.payload.get("context_prefix", "")[:300],
            }
            for point in response.points
        ]


# ── Step 3: proposals (LLM, one node at a time) ──────────────────────

def _load_nodes(conn: kuzu.Connection, table: str, extra: str) -> list[dict]:
    result = conn.execute(
        f"MATCH (n:{table}) RETURN n.chunk_id, n.name, {extra} ORDER BY n.chunk_id"
    )
    rows = []
    while result.has_next():
        chunk_id, name, extra_value = result.get_next()
        rows.append({"chunk_id": chunk_id, "name": name, "extra": extra_value})
    return rows


@retry_with_backoff()
def _read_incident(llm, incident: dict, candidates: list[dict]) -> IncidentReading:
    prompt = (
        f"## Incident {incident['chunk_id']}\n{incident['name']}\n\n"
        f"Personalities / emotions: {incident['extra']}\n\n"
        f"## Candidate teachings\n{json.dumps(candidates, indent=2, ensure_ascii=False)}"
    )
    return llm.with_structured_output(IncidentReading).invoke(
        [{"role": "system", "content": INCIDENT_SYSTEM_PROMPT},
         {"role": "user", "content": prompt}]
    )


@retry_with_backoff()
def _read_teaching(llm, teaching: dict, candidates: list[dict]) -> TeachingIllustration:
    prompt = (
        f"## Teaching {teaching['chunk_id']}\n{teaching['name']}\n\n"
        f"Core principle: {teaching['extra']}\n\n"
        f"## Candidate analogies\n{json.dumps(candidates, indent=2, ensure_ascii=False)}"
    )
    return llm.with_structured_output(TeachingIllustration).invoke(
        [{"role": "system", "content": ANALOGY_SYSTEM_PROMPT},
         {"role": "user", "content": prompt}]
    )


def _append_proposal(record: dict) -> None:
    PROPOSALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROPOSALS_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_proposals() -> list[dict]:
    if not PROPOSALS_PATH.exists():
        return []
    with open(PROPOSALS_PATH, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def propose(conn: kuzu.Connection, limit: int | None) -> None:
    """Walk incidents (then their accepted teachings) and record proposals.

    Checkpointed: an already-proposed source id is skipped, so an interrupted
    run resumes where it stopped (same pattern as steps 01/02).
    """
    llm = get_azure_llm()
    candidates = Candidates()
    done = {(record["kind"], record["source"]) for record in load_proposals()}

    incidents = _load_nodes(conn, "GitaIncident", "n.personality + ' | ' + n.emotional_state")
    if limit:
        incidents = incidents[:limit]

    for index, incident in enumerate(incidents, start=1):
        if ("incident", incident["chunk_id"]) in done:
            continue
        neighbours = candidates.neighbours(
            "historical_account", incident["chunk_id"], "teaching", TEACHING_CANDIDATES
        )
        if not neighbours:
            continue
        reading = _read_incident(llm, incident, neighbours)
        _append_proposal({
            "kind": "incident",
            "source": incident["chunk_id"],
            "anarthas": [link.model_dump() for link in reading.anarthas],
            "teachings": [link.model_dump() for link in reading.teachings],
        })
        logger.info(
            "[%d/%d] %s → %d anarthas, %d teachings",
            index, len(incidents), incident["chunk_id"],
            len(reading.anarthas), len(reading.teachings),
        )
        processing_pause()

    # Analogies are only worth judging for teachings that an incident reaches —
    # those are the ones a graph walk will ever arrive at.
    teachings = {row["chunk_id"]: row for row in _load_nodes(
        conn, "YogaTeaching", "n.core_principle")}
    wanted = sorted({
        link["chunk_id"]
        for record in load_proposals() if record["kind"] == "incident"
        for link in record["teachings"]
        if link["confidence"] >= MIN_CONFIDENCE and link["chunk_id"] in teachings
    })

    for index, chunk_id in enumerate(wanted, start=1):
        if ("teaching", chunk_id) in done:
            continue
        neighbours = candidates.neighbours(
            "teaching", chunk_id, "analogy", ANALOGY_CANDIDATES
        )
        if not neighbours:
            continue
        illustration = _read_teaching(llm, teachings[chunk_id], neighbours)
        _append_proposal({
            "kind": "teaching",
            "source": chunk_id,
            "analogies": [link.model_dump() for link in illustration.analogies],
        })
        logger.info(
            "[%d/%d] %s → %d analogies",
            index, len(wanted), chunk_id, len(illustration.analogies),
        )
        processing_pause()

    candidates.close()


# ── Step 4: deterministic validation + insertion ─────────────────────

EDGE_SQL = {
    "PRESENT_IN": (
        "MATCH (a:Anartha {name: $fid}), (i:GitaIncident {chunk_id: $tid}) "
        "CREATE (a)-[:PRESENT_IN]->(i)",
        "MATCH (a:Anartha {name: $fid})-[:PRESENT_IN]->(i:GitaIncident {chunk_id: $tid}) "
        "RETURN 1 LIMIT 1",
    ),
    "RESOLVED_BY": (
        "MATCH (i:GitaIncident {chunk_id: $fid}), (t:YogaTeaching {chunk_id: $tid}) "
        "CREATE (i)-[:RESOLVED_BY]->(t)",
        "MATCH (i:GitaIncident {chunk_id: $fid})-[:RESOLVED_BY]->(t:YogaTeaching {chunk_id: $tid}) "
        "RETURN 1 LIMIT 1",
    ),
    "ILLUSTRATED_BY": (
        "MATCH (t:YogaTeaching {chunk_id: $fid}), (n:NatureAnalogy {chunk_id: $tid}) "
        "CREATE (t)-[:ILLUSTRATED_BY]->(n)",
        "MATCH (t:YogaTeaching {chunk_id: $fid})-[:ILLUSTRATED_BY]->(n:NatureAnalogy {chunk_id: $tid}) "
        "RETURN 1 LIMIT 1",
    ),
}


def _node_exists(conn: kuzu.Connection, table: str, key: str, value: str) -> bool:
    result = conn.execute(
        f"MATCH (n:{table} {{{key}: $value}}) RETURN 1 LIMIT 1", parameters={"value": value}
    )
    return result.has_next()


def _edge_exists(conn: kuzu.Connection, rel: str, fid: str, tid: str) -> bool:
    _, check = EDGE_SQL[rel]
    return conn.execute(check, parameters={"fid": fid, "tid": tid}).has_next()


def _accepted(links: list[dict], cap: int) -> list[dict]:
    """Confidence gate + cap, strongest first."""
    keep = [link for link in links if link.get("confidence", 0) >= MIN_CONFIDENCE]
    return sorted(keep, key=lambda link: -link["confidence"])[:cap]


def insert_edges(conn: kuzu.Connection) -> dict:
    """Insert every accepted proposal into the staging clone.

    Deterministic throughout: ids must exist as nodes, the relationship must
    not already be present, and every write is a fixed parameterized statement.
    """
    stats = {
        rel: {"inserted": 0, "duplicate": 0, "unknown_id": 0}
        for rel in EDGE_SQL
    }

    def write(rel: str, fid: str, tid: str, from_table: str, from_key: str,
              to_table: str) -> None:
        if not _node_exists(conn, from_table, from_key, fid) or not _node_exists(
            conn, to_table, "chunk_id", tid
        ):
            stats[rel]["unknown_id"] += 1
            logger.warning("%s: unknown id %s → %s — skipped", rel, fid, tid)
            return
        if _edge_exists(conn, rel, fid, tid):
            stats[rel]["duplicate"] += 1
            return
        conn.execute(EDGE_SQL[rel][0], parameters={"fid": fid, "tid": tid})
        stats[rel]["inserted"] += 1

    for record in load_proposals():
        if record["kind"] == "incident":
            for link in _accepted(record["anarthas"], MAX_ANARTHAS_PER_INCIDENT):
                if link["anartha"] not in ANARTHAS:
                    stats["PRESENT_IN"]["unknown_id"] += 1
                    continue
                write("PRESENT_IN", link["anartha"], record["source"],
                      "Anartha", "name", "GitaIncident")
            for link in _accepted(record["teachings"], MAX_TEACHINGS_PER_INCIDENT):
                write("RESOLVED_BY", record["source"], link["chunk_id"],
                      "GitaIncident", "chunk_id", "YogaTeaching")
        elif record["kind"] == "teaching":
            for link in _accepted(record["analogies"], MAX_ANALOGIES_PER_TEACHING):
                write("ILLUSTRATED_BY", record["source"], link["chunk_id"],
                      "YogaTeaching", "chunk_id", "NatureAnalogy")

    return stats


# ── Step 5: validation report ────────────────────────────────────────

def edge_counts(conn: kuzu.Connection) -> dict[str, int]:
    counts = {}
    for rel in ("PRESENT_IN", "RESOLVED_BY", "ILLUSTRATED_BY", "CAUSES", "MAPS_TO"):
        result = conn.execute(f"MATCH ()-[r:{rel}]->() RETURN count(r)")
        counts[rel] = result.get_next()[0]
    return counts


def _per_anartha(conn: kuzu.Connection) -> dict[str, int]:
    per = {name: 0 for name in ANARTHAS}
    result = conn.execute(
        "MATCH (a:Anartha)-[:PRESENT_IN]->(i:GitaIncident) RETURN a.name, count(i)"
    )
    while result.has_next():
        name, count = result.get_next()
        per[name] = count
    return per


def _chain_coverage(conn: kuzu.Connection) -> dict[str, int]:
    """How many full anartha → incident → teaching → analogy chains exist per
    anartha — this is exactly what `anartha_chain` (P1.12) returns at runtime."""
    coverage = {}
    for name in ANARTHAS:
        result = conn.execute(
            "MATCH (a:Anartha {name: $anartha})-[:PRESENT_IN]->(i:GitaIncident)"
            "-[:RESOLVED_BY]->(t:YogaTeaching)-[:ILLUSTRATED_BY]->(n:NatureAnalogy) "
            "RETURN count(*)",
            parameters={"anartha": name},
        )
        coverage[name] = result.get_next()[0]
    return coverage


def _histogram(values: list[float]) -> str:
    buckets = {"0.0–0.2": 0, "0.2–0.4": 0, "0.4–0.6": 0, "0.6–0.8": 0, "0.8–1.0": 0}
    for value in values:
        index = min(int(value * 5), 4)
        buckets[list(buckets)[index]] += 1
    return "\n".join(
        f"| {label} | {count} | {'█' * min(count // 2, 40)} |"
        for label, count in buckets.items()
    )


def _samples(conn: kuzu.Connection, count: int = 8) -> str:
    result = conn.execute(
        "MATCH (a:Anartha)-[:PRESENT_IN]->(i:GitaIncident)-[:RESOLVED_BY]->(t:YogaTeaching) "
        "OPTIONAL MATCH (t)-[:ILLUSTRATED_BY]->(n:NatureAnalogy) "
        "RETURN a.name, i.chunk_id, i.name, t.chunk_id, t.name, n.name LIMIT 300"
    )
    rows = []
    while result.has_next():
        rows.append(result.get_next())
    random.seed(7)
    lines = []
    for row in random.sample(rows, min(count, len(rows))):
        anartha, incident_id, incident_name, teaching_id, teaching_name, analogy = row
        lines.append(
            f"**{anartha}** → `{incident_id}` {incident_name}\n\n"
            f"→ resolved by `{teaching_id}` {teaching_name}\n\n"
            f"→ illustrated by {analogy or '_(no analogy)_'}\n\n---\n"
        )
    return "\n".join(lines) if lines else "_No chains found._"


def write_report(before: dict, stats: dict | None) -> Path:
    conn = kuzu.Connection(kuzu.Database(str(STAGING_DB), read_only=True))
    after = edge_counts(conn)
    proposals = load_proposals()

    confidences = [
        link["confidence"]
        for record in proposals
        for key in ("anarthas", "teachings", "analogies")
        for link in record.get(key, [])
    ]
    accepted = [value for value in confidences if value >= MIN_CONFIDENCE]

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORTS_DIR / f"07_backfill_{stamp}.md"

    lines = [
        "# Step 07 — Edge backfill validation report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Staging clone: `{STAGING_DB.relative_to(PROJECT_ROOT)}`  ",
        f"Master (read-only): `{GRAPHDB_DIR.relative_to(PROJECT_ROOT)}`  ",
        f"Confidence threshold: **{MIN_CONFIDENCE}**  ",
        f"Caps: {MAX_ANARTHAS_PER_INCIDENT} anarthas/incident · "
        f"{MAX_TEACHINGS_PER_INCIDENT} teachings/incident · "
        f"{MAX_ANALOGIES_PER_TEACHING} analogies/teaching",
        "",
        "## 1. Edge counts",
        "",
        "| Relationship | Before | After | Δ |",
        "|---|---|---|---|",
    ]
    for rel in after:
        delta = after[rel] - before.get(rel, 0)
        lines.append(f"| {rel} | {before.get(rel, 0)} | {after[rel]} | +{delta} |")

    lines += ["", "## 2. Insertion outcome", "",
              "| Relationship | Inserted | Duplicate (skipped) | Unknown id (rejected) |",
              "|---|---|---|---|"]
    for rel, values in (stats or {}).items():
        lines.append(
            f"| {rel} | {values['inserted']} | {values['duplicate']} | {values['unknown_id']} |"
        )
    if not stats:
        lines.append("| _(report-only run — no insertion this pass)_ | | | |")

    lines += ["", "## 3. Anartha coverage (PRESENT_IN incidents)", "",
              "| Anartha | Incidents | Full chains |", "|---|---|---|"]
    per = _per_anartha(conn)
    chains = _chain_coverage(conn)
    for name in ANARTHAS:
        lines.append(f"| {name} | {per[name]} | {chains[name]} |")

    lines += [
        "", "## 4. Confidence distribution", "",
        f"{len(confidences)} proposals · {len(accepted)} accepted "
        f"({len(confidences) - len(accepted)} below threshold, recorded but not inserted)",
        "", "| Bucket | Count | |", "|---|---|---|", _histogram(confidences),
        "", "## 5. Random samples for human reading", "", _samples(conn),
        "", "## 6. Owner decision", "",
        "- [ ] APPROVED — run `python preprocessing/07_backfill_edges.py --promote`",
        "- [ ] REJECTED — delete the staging clone; nothing else changes.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    conn.close()
    return path


# ── Step 6: promotion (only after the owner approves) ────────────────

def promote() -> None:
    if not STAGING_DB.exists():
        raise SystemExit(f"No staging clone at {STAGING_DB} — run --stage first.")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if LIVE_DB.exists():
        backup = LIVE_DB.with_name(f"{LIVE_DB.name}__prebackfill_{stamp}")
        logger.info("Backing up live clone → %s", backup)
        shutil.move(str(LIVE_DB), str(backup))
    # A Kuzu single-file DB may leave a .wal sidecar; move it with its database.
    for stale in (LIVE_DB.with_suffix(LIVE_DB.suffix + ".wal"),):
        if stale.exists():
            stale.unlink()
    shutil.move(str(STAGING_DB), str(LIVE_DB))
    staging_wal = STAGING_DB.with_suffix(STAGING_DB.suffix + ".wal")
    if staging_wal.exists():
        shutil.move(str(staging_wal), str(LIVE_DB) + ".wal")
    logger.info("Staging clone is now live at %s", LIVE_DB)
    print(f"\nPromoted. Previous clone kept as a backup alongside it.\n")


# ── Entry point ──────────────────────────────────────────────────────

def stage(limit: int | None, keep_proposals: bool) -> None:
    if not keep_proposals and PROPOSALS_PATH.exists():
        PROPOSALS_PATH.unlink()

    clone_master()

    read_conn = kuzu.Connection(kuzu.Database(str(STAGING_DB), read_only=True))
    before = edge_counts(read_conn)
    logger.info("Edges before: %s", before)
    propose(read_conn, limit)
    read_conn.close()

    write_conn = kuzu.Connection(kuzu.Database(str(STAGING_DB)))
    stats = insert_edges(write_conn)
    logger.info("Insertion: %s", stats)
    write_conn.close()

    path = write_report(before, stats)
    print(f"\nValidation report: {path}")
    print("STOP — the owner reads and approves this report before --promote.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--stage", action="store_true", help="clone, propose, insert, report")
    group.add_argument("--report", action="store_true", help="re-render the report only")
    group.add_argument("--promote", action="store_true", help="AFTER approval: go live")
    parser.add_argument("--limit", type=int, help="only process the first N incidents")
    parser.add_argument("--keep-proposals", action="store_true",
                        help="resume from an existing edge_proposals.jsonl")
    args = parser.parse_args()

    if args.stage:
        stage(args.limit, args.keep_proposals)
    elif args.report:
        master = kuzu.Connection(kuzu.Database(str(GRAPHDB_DIR), read_only=True))
        before = edge_counts(master)
        master.close()
        print(f"\nValidation report: {write_report(before, None)}\n")
    else:
        promote()


if __name__ == "__main__":
    main()
