"""P1.19 logic tests — identity resolver + session-end (§4). The browser
walkthrough itself is the owner's manual script (workbook Post)."""

from datetime import datetime, timedelta, timezone

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import adapters.streamlit_app.identity_resolver as ids
from arjun.memory.namespaces import ReadScope
from arjun.memory.stores import make_store
from arjun.organs.reflection import Distillation

FAKE_EMBED = lambda texts: [[0.0] * 512 for _ in texts]  # noqa: E731


@pytest.fixture
def store(tmp_path):
    return make_store(path=tmp_path / "lt.db", embed=FAKE_EMBED)


class TestGuestAndPromotion:
    def test_new_guest_ids_unique(self):
        a, b = ids.new_guest_id(), ids.new_guest_id()
        assert a != b and a.startswith("guest_")

    def test_promote_returns_new_person_id(self, store):
        guest = ids.new_guest_id()
        store.put(ReadScope(guest).person("episodes"), "e1", {"text": "first talk"})
        new_id = ids.promote(store, guest, "Ravi")
        assert new_id and new_id.startswith("ravi_")
        assert store.get(ReadScope(new_id).person("episodes"), "e1") is not None

    def test_promote_non_guest_refused(self, store):
        assert ids.promote(store, "ravi_a1", "Someone") is None

    def test_record_uniquename_completes_key(self, store):
        guest = ids.new_guest_id()
        new_id = ids.promote(store, guest, "Sita")
        ids.record_uniquename(store, new_id, "lotus")
        assert ids.resolve(store, "Sita", "lotus") == new_id


class TestReLinking:
    def test_resolve_needs_both_and_matches_case_insensitively(self, store):
        new_id = ids.promote(store, ids.new_guest_id(), "Ravi", uniquename="banyan")
        assert ids.resolve(store, "RAVI", "Banyan") == new_id
        assert ids.resolve(store, "Ravi", "") is None
        assert ids.resolve(store, "Ravi", "wrong") is None  # never guessed

    def test_no_match_returns_none_never_merges(self, store):
        ids.promote(store, ids.new_guest_id(), "Ravi", uniquename="banyan")
        assert ids.resolve(store, "Unknown", "banyan") is None


class TestSessionEnd:
    def test_expiry_boundary(self):
        now = datetime.now(timezone.utc)
        assert ids.session_expired(now - timedelta(minutes=31), now) is True
        assert ids.session_expired(now - timedelta(minutes=29), now) is False
        assert ids.session_expired(None, now) is False

    def test_unnamed_guest_forgotten(self, store):
        guest = ids.new_guest_id()
        store.put(ReadScope(guest).person("episodes"), "e1", {"text": "talk"})
        outcome = ids.end_session(store, guest, [], uniquename_set=False)
        assert "deleted" in outcome
        assert store.search(ReadScope(guest).person("episodes"), limit=5) == []

    def test_named_but_no_uniquename_forgotten(self, store):
        new_id = ids.promote(store, ids.new_guest_id(), "Arun")
        outcome = ids.end_session(store, new_id, [], uniquename_set=False)
        assert "deleted" in outcome
        assert store.search(ReadScope(new_id).person("profile"), limit=5) == []

    def test_complete_person_key_distilled_not_deleted(self, store, monkeypatch):
        import arjun.organs.reflection as refl

        new_id = ids.promote(store, ids.new_guest_id(), "Sita", uniquename="lotus")
        distilled = Distillation(episode="Talked about exam fear; breathing helped.")
        monkeypatch.setattr(refl, "_invoke_distill_llm", lambda s, t: distilled.model_dump_json())

        messages = [HumanMessage(content="exam fear"), AIMessage(content="breathe, friend")]
        outcome = ids.end_session(store, new_id, messages, uniquename_set=True)
        assert "distilled" in outcome
        assert store.get(ReadScope(new_id).person("profile"), "name") is not None  # kept
        assert store.search(ReadScope(new_id).person("episodes"), limit=5)  # distilled in


class _GutStub:
    def __init__(self, shared_name="", chosen_uniquename="", temp=0.1, flag=False):
        self.shared_name = shared_name
        self.chosen_uniquename = chosen_uniquename
        self.emotional_temperature = temp
        self.self_harm_flag = flag


class _StateStub:
    def __init__(self, person_id):
        self.person_id = person_id
        self.uniquename_set = False
        self.display_name = ""
        self.pending_name = ""


class TestConversationalIdentity:
    """§4 owner decision 2026-07-17 — promotion/Uniquename/re-link from what
    the person SAID (gut_read), never a form; returning people re-link."""

    def test_brand_new_name_promotes_and_awaits_uniquename(self, store):
        state = _StateStub(ids.new_guest_id())
        status = ids.apply_gut_identity(store, state, _GutStub(shared_name="Ravi"))
        assert "promoted to ravi_" in status and "awaiting Uniquename" in status
        assert not state.person_id.startswith("guest_") and state.display_name == "Ravi"
        assert state.uniquename_set is False

    def test_existing_name_holds_pending_not_duplicated(self, store):
        # An Ashok already exists → a new guest saying "ashok" must NOT fork.
        ids.promote(store, ids.new_guest_id(), "Ashok", uniquename="lotus")
        state = _StateStub(ids.new_guest_id())
        status = ids.apply_gut_identity(store, state, _GutStub(shared_name="Ashok"))
        assert "may be returning" in status
        assert state.person_id.startswith("guest_")  # held, not promoted
        assert state.pending_name == "Ashok"

    def test_returning_person_relinks_after_uniquename(self, store):
        old = ids.promote(store, ids.new_guest_id(), "Ashok", uniquename="lotus")
        state = _StateStub(ids.new_guest_id())
        ids.apply_gut_identity(store, state, _GutStub(shared_name="Ashok"))  # turn 1: held
        status = ids.apply_gut_identity(store, state, _GutStub(chosen_uniquename="lotus"))
        assert "re-linked" in status and state.person_id == old
        assert state.uniquename_set is True and state.pending_name == ""

    def test_wrong_uniquename_forks_fresh_profile(self, store):
        ids.promote(store, ids.new_guest_id(), "Ashok", uniquename="lotus")
        state = _StateStub(ids.new_guest_id())
        ids.apply_gut_identity(store, state, _GutStub(shared_name="Ashok"))
        status = ids.apply_gut_identity(store, state, _GutStub(chosen_uniquename="banyan"))
        assert "no earlier match" in status and state.uniquename_set is True

    def test_name_and_uniquename_same_turn_relinks(self, store):
        old = ids.promote(store, ids.new_guest_id(), "Ravi", uniquename="banyan")
        state = _StateStub(ids.new_guest_id())
        status = ids.apply_gut_identity(
            store, state, _GutStub(shared_name="Ravi", chosen_uniquename="banyan")
        )
        assert "re-linked" in status and state.person_id == old

    def test_uniquename_completes_key_for_named_person(self, store):
        named = ids.promote(store, ids.new_guest_id(), "Arun")
        state = _StateStub(named)
        state.display_name = "Arun"
        status = ids.apply_gut_identity(store, state, _GutStub(chosen_uniquename="river"))
        assert status == "Person Key complete" and state.uniquename_set is True

    def test_word_misclassified_as_name_still_completes_key(self, store):
        # Gut put the Uniquename word in shared_name (single word looks like a
        # name). A named-unkeyed person's word must still complete the key.
        named = ids.promote(store, ids.new_guest_id(), "Yogesh")
        state = _StateStub(named)
        state.display_name = "Yogesh"
        status = ids.apply_gut_identity(store, state, _GutStub(shared_name="yogi"))
        assert status == "Person Key complete" and state.uniquename_set is True
        assert ids.resolve(store, "Yogesh", "yogi") == named  # saved + re-linkable

    def test_repeated_name_not_taken_as_uniquename(self, store):
        named = ids.promote(store, ids.new_guest_id(), "Arun")
        state = _StateStub(named)
        state.display_name = "Arun"
        assert ids.apply_gut_identity(store, state, _GutStub(shared_name="Arun")) is None
        assert state.uniquename_set is False

    def test_relink_word_misclassified_as_name(self, store):
        old = ids.promote(store, ids.new_guest_id(), "Yogesh", uniquename="yogi")
        state = _StateStub(ids.new_guest_id())
        ids.apply_gut_identity(store, state, _GutStub(shared_name="Yogesh"))  # held
        # user answers "yogi" — Gut put it in shared_name again
        status = ids.apply_gut_identity(store, state, _GutStub(shared_name="yogi"))
        assert "re-linked" in status and state.person_id == old

    def test_nothing_said_no_change(self, store):
        state = _StateStub(ids.new_guest_id())
        assert ids.apply_gut_identity(store, state, _GutStub()) is None
        assert state.person_id.startswith("guest_")

# The calm-gate for asking name/Uniquename now lives in the Identity organ's
# build_directive (see tests/test_identity.py::TestDirective).
