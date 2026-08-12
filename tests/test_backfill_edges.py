"""P1.20 unit tests — the DETERMINISTIC half of step 07 (§8.3).

The LLM half (proposals) is exercised by the real staged run and read by the
owner in the validation report; what must be tested here is the code that
decides what actually touches the graph: the confidence gate, the caps, id
validation, duplicate suppression, and the master staying untouched.

Every test runs against a throwaway clone in tmp_path — never the live clone.
"""

import importlib.util
import json
import shutil
from pathlib import Path

import kuzu
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MASTER = PROJECT_ROOT / "graphdb" / "gita_graph"


def _load_module():
    """Step scripts are named `07_…` — not importable by name."""
    path = PROJECT_ROOT / "preprocessing" / "07_backfill_edges.py"
    spec = importlib.util.spec_from_file_location("backfill_edges", path)
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.path.insert(0, str(PROJECT_ROOT / "preprocessing"))  # its `from config import …`
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


backfill = _load_module()


@pytest.fixture
def staging(tmp_path, monkeypatch):
    """A private clone of the canon master, wired in as the staging path."""
    clone = tmp_path / "clone"
    # The Kuzu master is a single file (not a directory) — mirror clone_master.
    shutil.copytree(MASTER, clone) if MASTER.is_dir() else shutil.copy2(MASTER, clone)
    monkeypatch.setattr(backfill, "STAGING_DB", clone)
    monkeypatch.setattr(backfill, "PROPOSALS_PATH", tmp_path / "proposals.jsonl")
    return clone


def _write_proposals(records):
    with open(backfill.PROPOSALS_PATH, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def _counts(clone):
    conn = kuzu.Connection(kuzu.Database(str(clone), read_only=True))
    counts = backfill.edge_counts(conn)
    conn.close()
    return counts


def _insert(clone):
    conn = kuzu.Connection(kuzu.Database(str(clone)))
    stats = backfill.insert_edges(conn)
    conn.close()
    return stats


class TestConfidenceGate:
    def test_below_threshold_is_dropped(self):
        links = [{"chunk_id": "chunk_0001", "confidence": 0.59}]
        assert backfill._accepted(links, cap=3) == []

    def test_threshold_itself_is_accepted(self):
        links = [{"chunk_id": "chunk_0001", "confidence": backfill.MIN_CONFIDENCE}]
        assert len(backfill._accepted(links, cap=3)) == 1

    def test_cap_keeps_the_strongest(self):
        links = [
            {"chunk_id": "a", "confidence": 0.7},
            {"chunk_id": "b", "confidence": 0.95},
            {"chunk_id": "c", "confidence": 0.8},
        ]
        assert [l["chunk_id"] for l in backfill._accepted(links, cap=2)] == ["b", "c"]


class TestInsertion:
    def test_accepted_proposal_becomes_an_edge(self, staging):
        incident = "chunk_0010"
        _write_proposals([{
            "kind": "incident",
            "source": incident,
            "anarthas": [{"anartha": "Kama", "confidence": 0.9, "reason": "x"}],
            "teachings": [{"chunk_id": "chunk_0407", "confidence": 0.9, "reason": "x"}],
        }])
        before = _counts(staging)
        stats = _insert(staging)
        after = _counts(staging)

        assert stats["PRESENT_IN"]["inserted"] == 1
        assert stats["RESOLVED_BY"]["inserted"] == 1
        assert after["PRESENT_IN"] == before["PRESENT_IN"] + 1
        assert after["RESOLVED_BY"] == before["RESOLVED_BY"] + 1

    def test_low_confidence_never_reaches_the_graph(self, staging):
        _write_proposals([{
            "kind": "incident",
            "source": "chunk_0010",
            "anarthas": [{"anartha": "Kama", "confidence": 0.3, "reason": "x"}],
            "teachings": [{"chunk_id": "chunk_0407", "confidence": 0.2, "reason": "x"}],
        }])
        before = _counts(staging)
        _insert(staging)
        assert _counts(staging) == before

    def test_hallucinated_chunk_id_is_rejected_not_inserted(self, staging):
        _write_proposals([{
            "kind": "incident",
            "source": "chunk_0010",
            "anarthas": [],
            "teachings": [{"chunk_id": "chunk_9999", "confidence": 1.0, "reason": "x"}],
        }])
        before = _counts(staging)
        stats = _insert(staging)
        assert stats["RESOLVED_BY"]["unknown_id"] == 1
        assert _counts(staging) == before

    def test_invalid_anartha_name_is_rejected(self, staging):
        _write_proposals([{
            "kind": "incident",
            "source": "chunk_0010",
            "anarthas": [{"anartha": "Anger", "confidence": 1.0, "reason": "x"}],
            "teachings": [],
        }])
        before = _counts(staging)
        stats = _insert(staging)
        assert stats["PRESENT_IN"]["unknown_id"] == 1
        assert _counts(staging) == before

    def test_second_run_is_idempotent(self, staging):
        _write_proposals([{
            "kind": "incident",
            "source": "chunk_0010",
            "anarthas": [{"anartha": "Kama", "confidence": 0.9, "reason": "x"}],
            "teachings": [],
        }])
        _insert(staging)
        after_first = _counts(staging)
        stats = _insert(staging)
        assert stats["PRESENT_IN"]["duplicate"] == 1
        assert stats["PRESENT_IN"]["inserted"] == 0
        assert _counts(staging) == after_first

    def test_analogy_edge_from_a_teaching_proposal(self, staging):
        conn = kuzu.Connection(kuzu.Database(str(staging), read_only=True))
        result = conn.execute("MATCH (n:NatureAnalogy) RETURN n.chunk_id LIMIT 1")
        analogy_id = result.get_next()[0]
        conn.close()

        _write_proposals([{
            "kind": "teaching",
            "source": "chunk_0407",
            "analogies": [{"chunk_id": analogy_id, "confidence": 0.9, "reason": "x"}],
        }])
        before = _counts(staging)
        _insert(staging)
        assert _counts(staging)["ILLUSTRATED_BY"] == before["ILLUSTRATED_BY"] + 1


class TestWriteBoundary:
    def test_master_is_never_the_write_target(self, staging):
        """§8.1: the canon master is never opened for writing by this step."""
        assert backfill.STAGING_DB != backfill.GRAPHDB_DIR
        assert backfill.STAGING_DB != backfill.LIVE_DB
        assert backfill.LIVE_DB.name == "self_learning_db"

    def test_master_edge_counts_unchanged_by_a_staged_insert(self, staging):
        conn = kuzu.Connection(kuzu.Database(str(MASTER), read_only=True))
        master_before = backfill.edge_counts(conn)
        conn.close()

        _write_proposals([{
            "kind": "incident",
            "source": "chunk_0010",
            "anarthas": [{"anartha": "Kama", "confidence": 0.9, "reason": "x"}],
            "teachings": [],
        }])
        _insert(staging)

        conn = kuzu.Connection(kuzu.Database(str(MASTER), read_only=True))
        assert backfill.edge_counts(conn) == master_before
        conn.close()
