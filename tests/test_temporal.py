"""P1.11 unit tests — Temporal Lobe tools, identity ops, write invariant."""

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from arjun.graph.state import MemoryRecall
from arjun.memory.namespaces import ReadScope
from arjun.memory.stores import make_store
from arjun.organs.temporal import build_tools, make_temporal_agent, recall

FAKE_EMBED = lambda texts: [[0.0] * 512 for _ in texts]  # noqa: E731 — plumbing tests


@pytest.fixture
def store(tmp_path):
    return make_store(path=tmp_path / "lt.db", embed=FAKE_EMBED)


def tools_for(store, person_id, **kwargs):
    belt = build_tools(store, ReadScope(person_id), **kwargs)
    return {t.name: t for t in belt}


def seed(store, person_id, section, key, text):
    store.put(ReadScope(person_id).person(section), key, {"text": text})


class TestPromotion:
    def test_promotion_renames_namespace_with_data_intact(self, store):
        guest = "guest_ab12cd"
        seed(store, guest, "episodes", "ep1", "Came in distress about career.")
        seed(store, guest, "diagnoses", "d1", "Krodha rising, Rajas environment.")

        result = tools_for(store, guest)["promote_guest"].invoke({"name": "Ravi"})
        assert "promoted to ravi_ab12cd" in result

        new = ReadScope("ravi_ab12cd")
        assert store.get(new.person("episodes"), "ep1").value["text"] == "Came in distress about career."
        assert store.get(new.person("diagnoses"), "d1") is not None
        assert "Name: Ravi" in store.get(new.person("profile"), "name").value["text"]
        # old guest namespace is empty
        assert store.search(ReadScope(guest).person("episodes"), limit=10) == []

    def test_two_step_uniquename_recorded_when_provided(self, store):
        result = tools_for(store, "guest_x9")["promote_guest"].invoke(
            {"name": "Sita Devi", "uniquename": "lotus"}
        )
        assert "uniquename set" in result
        profile = ReadScope("sita_devi_x9").person("profile")
        assert "lotus" in store.get(profile, "uniquename").value["text"]

    def test_uniquename_pending_when_absent(self, store):
        result = tools_for(store, "guest_y1")["promote_guest"].invoke({"name": "Arun"})
        assert "uniquename pending" in result

    def test_non_guest_cannot_be_promoted(self, store):
        result = tools_for(store, "ravi_ab12cd")["promote_guest"].invoke({"name": "Other"})
        assert result.startswith("REFUSED")


class TestForgetting:
    def test_forgetting_deletes_everything(self, store):
        guest = "guest_gone"
        for section, key in [("profile", "p"), ("episodes", "e"), ("commitments", "c")]:
            seed(store, guest, section, key, "data")

        result = tools_for(store, guest)["forget_guest"].invoke({})
        assert "3 items deleted" in result
        scope = ReadScope(guest)
        for section in ("profile", "episodes", "commitments"):
            assert store.search(scope.person(section), limit=10) == []


class TestRecall:
    def test_recall_returns_four_section_shape(self, store):
        pid = "ravi_r1"
        seed(store, pid, "profile", "p1", "Works in Hyderabad, two kids.")
        seed(store, pid, "episodes", "e1", "Grief session about father.")
        seed(store, pid, "diagnoses", "d1", "Moha, Tamas-heavy.")
        seed(store, pid, "commitments", "c1", "Promised to check on sleep next time.")

        out = recall(store, pid)
        assert isinstance(out, MemoryRecall)
        assert out.profile == ["Works in Hyderabad, two kids."]
        assert out.episodes and out.diagnoses and out.commitments

    def test_recall_empty_person_is_empty_shape(self, store):
        out = recall(store, "stranger_z9")
        assert out == MemoryRecall()


class TestWriteInvariant:
    def test_store_put_refused_mid_turn(self, store):
        result = tools_for(store, "ravi_r1")["store_put"].invoke(
            {"section": "episodes", "key": "e9", "text": "sneaky mid-turn write"}
        )
        assert result.startswith("REFUSED")
        assert store.search(ReadScope("ravi_r1").person("episodes"), limit=10) == []

    def test_store_put_allowed_in_reflection_context(self, store):
        belt = tools_for(store, "ravi_r1", reflection_context=True)
        result = belt["store_put"].invoke({"section": "episodes", "key": "e1", "text": "distilled"})
        assert result == "stored episodes/e1"
        assert store.get(ReadScope("ravi_r1").person("episodes"), "e1") is not None


class TestPrivacyInToolLayer:
    def test_tools_cannot_reach_another_person(self, store):
        seed(store, "person_a", "profile", "secret", "A's private fact")
        belt = tools_for(store, "person_b")
        assert "no item" in belt["store_get"].invoke({"section": "profile", "key": "secret"})
        assert "nothing found" in belt["store_search"].invoke(
            {"section": "profile", "query": "private fact"}
        )

    def test_unknown_section_is_error_string_not_exception(self, store):
        belt = tools_for(store, "person_b")
        assert "unknown section" in belt["store_get"].invoke({"section": "passwords", "key": "x"})


class TestAgentConstruction:
    def test_agent_carries_exactly_five_tools(self, store):
        agent = make_temporal_agent(
            store,
            "guest_t1",
            model=FakeListChatModel(responses=["ok"]),
            summarizer_model=FakeListChatModel(responses=["s"]),
        )
        tool_node = agent.nodes.get("tools")
        assert tool_node is not None
        names = set(tool_node.bound._tools_by_name)  # ToolNode's registry
        assert names == {"store_get", "store_search", "store_put", "promote_guest", "forget_guest"}
