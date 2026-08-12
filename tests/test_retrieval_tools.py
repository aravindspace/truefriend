"""P1.12 unit tests — the 4 retrieval tools against the REAL stores (§8.2)."""

import pytest

import arjun.retrieval.notebook as nb
from arjun.retrieval.kuzu_templates import TEMPLATES, chunk_exists, run_template
from arjun.retrieval.qdrant_search import build_filter, qdrant_search
from arjun.retrieval.routing import known_domains, routing_lookup


class TestRouting:
    def test_career_routes_from_real_data(self):
        info = routing_lookup("career")
        assert info.anartha == "Kama" and info.guna == "Rajas" and info.section == 3
        assert info.incident_chunk_ids and all(
            c.startswith("chunk_") for c in info.incident_chunk_ids
        )

    def test_case_and_whitespace_insensitive(self):
        assert routing_lookup("  CAREER ").anartha == "Kama"

    def test_unknown_domain_returns_none(self):
        assert routing_lookup("cryptocurrency") is None

    def test_domains_load(self):
        assert {"career", "family", "purpose", "envy"} <= set(known_domains())


class TestKuzuTemplates:
    def test_anartha_incidents_real_rows(self):
        rows = run_template("anartha_incidents", anartha="Moha")
        assert rows and all(r["chunk_id"].startswith("chunk_") for r in rows)
        assert all(len(r["full_text"]) > 50 for r in rows)  # full text at the node

    def test_known_chunk_id_roundtrips(self):
        chunk_id = run_template("anartha_incidents", anartha="Moha")[0]["chunk_id"]
        assert chunk_exists(chunk_id) is True

    def test_invalid_anartha_empty_never_error(self):
        assert run_template("anartha_incidents", anartha="Anger") == []

    def test_injection_shaped_parameter_rejected(self):
        assert run_template("incident_teachings", chunk_id="chunk_1; DROP TABLE x") == []
        assert chunk_exists("chunk_1 OR 1=1") is False

    def test_unknown_template_and_wrong_params_empty(self):
        assert run_template("free_cypher", query="MATCH (n) RETURN n") == []
        assert run_template("anartha_incidents", anartha="Moha", extra="x") == []

    def test_personality_templates(self):
        rows = run_template("personality_incidents", personality="Arjuna")
        assert rows and rows[0]["role"]
        relatives = run_template("personality_relatives", personality="Arjuna")
        assert any(r["name"] in {"Kunti", "Pandu", "Subhadra", "Abhimanyu"} for r in relatives)

    def test_whitelist_is_the_expected_size(self):
        assert set(TEMPLATES) == {
            "anartha_incidents",
            "anartha_chain",
            "incident_teachings",
            "teaching_analogies",
            "personality_incidents",
            "personality_relatives",
        }


class TestQdrantSearch:
    def test_filtered_search_real_collection(self):
        chunks = qdrant_search(
            "grief and lamentation on the battlefield",
            "historical_account",
            filters={"anartha_tag": "Moha"},
            limit=3,
        )
        assert chunks and all(c.source == "canon" for c in chunks)
        assert all(c.chunk_id.startswith("chunk_") and len(c.text) > 50 for c in chunks)
        assert chunks[0].chunk_type == "HISTORICAL_ACCOUNT"

    def test_bad_collection_empty(self):
        assert qdrant_search("anything", "no_such_collection") == []

    def test_build_filter_merges_bias_without_overriding(self):
        f = build_filter({"anartha_tag": "Krodha"}, {"anartha_tag": "Moha", "guna_environment": "Tamas"})
        by_key = {c.key: c.match.value for c in f.must}
        assert by_key == {"anartha_tag": "Krodha", "guna_environment": "Tamas"}  # explicit wins

    def test_build_filter_drops_unknown_keys(self):
        assert build_filter({"evil_key": "x"}, None) is None


class TestNotebook:
    def test_seeded_note_found_and_tagged(self, tmp_path, monkeypatch):
        monkeypatch.setattr(nb, "NOTEBOOK_DIR", tmp_path)
        (tmp_path / "on_grief.md").write_text(
            "# My study of grief\nMoha binds through attachment to the body."
        )
        (tmp_path / "on_karma.md").write_text("# Karma notes\nAct without claiming fruits.")

        results = nb.notebook_search("grief and attachment")
        assert results[0].chunk_id == "notebook:on_grief"
        assert results[0].source == "notebook"  # Arjun's OWN understanding, not Canon

    def test_empty_notebook_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(nb, "NOTEBOOK_DIR", tmp_path)
        assert nb.notebook_search("anything") == []
