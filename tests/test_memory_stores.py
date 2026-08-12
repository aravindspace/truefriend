"""P1.10 unit tests — stores, real semantic search, privacy wall (§7)."""

import pytest

from arjun.memory.namespaces import ReadScope
from arjun.memory.stores import make_checkpointer, make_store, thread_id


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    """One store with REAL nomic embeddings for the whole module (model
    loads once)."""
    return make_store(path=tmp_path_factory.mktemp("mem") / "long_term.db")


class TestStores:
    def test_wal_enabled_on_both(self, tmp_path):
        saver = make_checkpointer(tmp_path / "st.db")
        assert saver.conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        st = make_store(tmp_path / "lt.db", embed=lambda ts: [[0.0] * 512 for _ in ts])
        assert st.conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"

    def test_thread_id_format(self):
        assert thread_id("guest_ab12", "s1") == "guest_ab12:s1"


class TestSemanticSearch:
    def test_put_search_roundtrip_real_embeddings(self, store):
        scope = ReadScope("ravi_x1")
        ns = scope.person("episodes")
        store.put(ns, "ep_cricket", {"text": "We chatted happily about cricket scores and the IPL final."})
        store.put(ns, "ep_grief", {"text": "He was grieving the loss of his father and could not sleep."})

        results = store.search(ns, query="sadness about losing a parent", limit=2)
        assert len(results) == 2
        assert results[0].key == "ep_grief"  # semantically closer item wins

    def test_search_scoped_to_own_person_only(self, store):
        ns_a = ReadScope("person_a").person("episodes")
        ns_b = ReadScope("person_b").person("episodes")
        store.put(ns_a, "a_secret", {"text": "Person A shared a private family conflict."})
        store.put(ns_b, "b_item", {"text": "Person B talked about exam stress."})

        results = store.search(ns_b, query="family conflict", limit=5)
        assert {r.key for r in results} == {"b_item"}  # A's item unreachable via B's scope


class TestPrivacyWall:
    def test_scope_expresses_exactly_eight_namespaces(self):
        scope = ReadScope("ravi_x1")
        assert len(scope.all_namespaces()) == 8
        assert scope.person("profile") == ("people", "ravi_x1", "profile")
        assert scope.arjun_self("learnings") == ("arjun", "self", "learnings")
        assert scope.world() == ("arjun", "world", "facts")

    def test_cross_person_namespace_is_inexpressible(self):
        scope_b = ReadScope("person_b")
        # No API on scope_b accepts another person id; its full namespace
        # enumeration never contains person_a.
        assert all("person_a" not in ns for ns in scope_b.all_namespaces())
        assert scope_b.allows(("people", "person_a", "profile")) is False

    def test_invalid_sections_rejected(self):
        scope = ReadScope("x")
        with pytest.raises(ValueError):
            scope.person("passwords")
        with pytest.raises(ValueError):
            scope.arjun_self("profile")
