"""P1.19b — Identity organ: directive + resolution consolidated (§4)."""

import pytest

from arjun.graph.state import GutRead, Person
from arjun.memory.stores import make_store
from arjun.organs.identity import build_directive, make_identity_node, resolve_step

FAKE_EMBED = lambda texts: [[0.0] * 512 for _ in texts]  # noqa: E731


@pytest.fixture
def store(tmp_path):
    return make_store(path=tmp_path / "lt.db", embed=FAKE_EMBED)


def guest():
    return Person(id="guest_ab12cd", is_guest=True)


class TestDirective:
    def test_asks_uniquename_right_after_name(self):
        d = build_directive(guest(), GutRead(shared_name="Ravi"))
        assert "Ravi" in d and "Uniquename" in d

    def test_acknowledges_uniquename(self):
        d = build_directive(Person(id="ravi_1", is_guest=False), GutRead(chosen_uniquename="lotus"))
        assert "special word" in d.lower()

    def test_asks_name_when_calm_guest(self):
        d = build_directive(guest(), GutRead(emotional_temperature=0.1))
        assert "name" in d.lower()

    def test_silent_during_distress(self):
        assert build_directive(guest(), GutRead(self_harm_flag=True)) == ""
        assert build_directive(guest(), GutRead(emotional_temperature=0.9)) == ""

    def test_invites_uniquename_for_named_unkeyed(self):
        p = Person(id="arun_1", display_name="Arun", is_guest=False, uniquename_set=False)
        d = build_directive(p, GutRead(emotional_temperature=0.1))
        assert "Uniquename" in d


class TestResolveStep:
    def test_new_name_promotes(self, store):
        p, pending, status = resolve_step(store, guest(), "", GutRead(shared_name="Ravi"))
        assert not p.is_guest and p.display_name == "Ravi" and "promoted" in status

    def test_existing_name_held_pending(self, store):
        resolve_step(store, guest(), "", GutRead(shared_name="Ravi"))  # create a Ravi
        p2, pending, status = resolve_step(store, Person(id="guest_z9", is_guest=True), "", GutRead(shared_name="Ravi"))
        assert p2.is_guest and pending == "Ravi" and "may be returning" in status

    def test_returning_relinks_after_word(self, store):
        first, _, _ = resolve_step(store, guest(), "", GutRead(shared_name="Ravi", chosen_uniquename="banyan"))
        p, pending, status = resolve_step(store, Person(id="guest_z9", is_guest=True), "Ravi", GutRead(chosen_uniquename="banyan"))
        assert p.id == first.id and "re-linked" in status

    def test_word_misclassified_as_name_still_keys(self, store):
        named = Person(id="yogesh_1", display_name="Yogesh", is_guest=False, uniquename_set=False)
        # seed the profile so resolve works afterward
        store.put(("people", "yogesh_1", "profile"), "name", {"text": "Name: Yogesh"})
        p, _, status = resolve_step(store, named, "", GutRead(shared_name="yogi"))
        assert p.uniquename_set and status == "Person Key complete"

    def test_repeated_name_not_taken_as_word(self, store):
        p = Person(id="arun_1", display_name="Arun", is_guest=False, uniquename_set=False)
        _, _, status = resolve_step(store, p, "", GutRead(shared_name="Arun"))
        assert status is None


class TestNode:
    def test_node_sets_directive_only(self):
        node = make_identity_node()
        out = node({"person": guest(), "gut_read": GutRead(shared_name="Ravi")})
        assert set(out) == {"identity_directive"} and "Ravi" in out["identity_directive"]
