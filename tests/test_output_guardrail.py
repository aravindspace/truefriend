"""P1.16 unit tests — one test per deterministic rule + the failure path."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import arjun.middleware.output_guardrail as og
from arjun.graph.state import Person, RetrievedChunk
from arjun.memory.namespaces import ReadScope
from arjun.memory.stores import make_store

FAKE_EMBED = lambda texts: [[0.0] * 512 for _ in texts]  # noqa: E731


@pytest.fixture
def store(tmp_path):
    s = make_store(path=tmp_path / "lt.db", embed=FAKE_EMBED)
    s.put(ReadScope("ravi_a1").person("profile"), "name", {"text": "Name: Ravi"})
    s.put(ReadScope("ravi_a1").person("profile"), "uniquename", {"text": "Uniquename: lotus"})
    return s


def state_with(reply, **overrides):
    state = {
        "messages": [HumanMessage(content="..."), AIMessage(content=reply)],
        "person": Person(id="sita_b2", is_guest=False),
        "retrieved": [],
        "self_harm_flag": False,
        "tier": None,
    }
    state.update(overrides)
    return state


class TestDeterministicRules:
    def test_nonexistent_chunk_id_violates(self):
        assert "does not exist" in og.check_citations('As it says (chunk_999999)…', {"retrieved": []})

    def test_retrieved_chunk_id_passes_without_lookup(self):
        state = {"retrieved": [RetrievedChunk(chunk_id="chunk_999999", text="x", source="canon")]}
        assert og.check_citations("Quote (chunk_999999)", state) is None

    def test_real_canon_chunk_id_passes(self):
        from arjun.retrieval.kuzu_templates import run_template

        real = run_template("anartha_incidents", anartha="Moha")[0]["chunk_id"]
        assert og.check_citations(f"As recorded ({real})…", {"retrieved": []}) is None

    def test_fiction_vocabulary_about_personalities_violates(self):
        v = og.check_fiction_vocabulary("Arjuna is a character in this great story.", {})
        assert v and "fiction vocabulary" in v

    def test_fiction_words_without_gita_context_pass(self):
        assert og.check_fiction_vocabulary("He told me a story about his childhood.", {}) is None

    def test_historical_framing_passes(self):
        assert (
            og.check_fiction_vocabulary("At Kurukshetra, Krishna spoke to Arjuna.", {}) is None
        )

    def test_helpline_missing_on_flagged_turn_violates(self):
        v = og.check_helpline("Be strong, friend.", {"self_harm_flag": True})
        assert v and "helpline" in v

    def test_helpline_present_on_flagged_turn_passes(self):
        reply = "Please call Tele-MANAS 14416 — I am with you."
        assert og.check_helpline(reply, {"self_harm_flag": True}) is None

    def test_unflagged_turn_needs_no_helpline(self):
        assert og.check_helpline("A calm reply.", {"self_harm_flag": False}) is None

    def test_leakage_of_other_name_violates(self, store):
        check = og.make_leakage_check(store)
        v = check("Ravi told me something similar last week.", state_with(""))
        assert v and "another person's identity" in v

    def test_leakage_of_other_uniquename_violates(self, store):
        check = og.make_leakage_check(store)
        assert check("Your word reminds me of lotus.", state_with("")) is not None

    def test_own_person_and_clean_words_pass(self, store):
        check = og.make_leakage_check(store)
        own_state = state_with("", person=Person(id="ravi_a1", is_guest=False))
        assert check("Ravi, you are stronger than you know.", own_state) is None
        assert check("The lotus leaf stays dry in water.", own_state) is None


class TestFailurePath:
    def test_clean_reply_passes_untouched(self, store, monkeypatch):
        monkeypatch.setattr(og, "llm_verdict", lambda r, s: None)
        node = og.make_output_guardrail(store, recompose=lambda s, v: pytest.fail("no recompose"))
        assert node(state_with("A clean, warm reply.")) == {}

    def test_recompose_once_then_accept(self, store, monkeypatch):
        monkeypatch.setattr(og, "llm_verdict", lambda r, s: None)
        calls = []

        def recompose(state, violation):
            calls.append(violation)
            return "At Kurukshetra, Krishna guided Arjuna — real counsel for you."

        node = og.make_output_guardrail(store, recompose=recompose)
        update = node(state_with("Arjuna is a character in a myth."))
        assert len(calls) == 1 and "fiction vocabulary" in calls[0]
        assert "Kurukshetra" in update["messages"][0].content

    def test_recompose_still_violating_falls_back(self, store, monkeypatch):
        from arjun.harness.fallbacks import HONEST_FALLBACK_REPLY

        monkeypatch.setattr(og, "llm_verdict", lambda r, s: None)
        node = og.make_output_guardrail(
            store, recompose=lambda s, v: "Still calling Krishna a mythical character."
        )
        update = node(state_with("Arjuna is a character in a myth."))
        assert update["messages"][0].content == HONEST_FALLBACK_REPLY

    def test_missing_ai_reply_falls_back(self, store):
        from arjun.harness.fallbacks import HONEST_FALLBACK_REPLY

        node = og.make_output_guardrail(store, recompose=lambda s, v: "")
        update = node({"messages": [HumanMessage(content="hi")], "person": Person(id="x")})
        assert update["messages"][0].content == HONEST_FALLBACK_REPLY


class TestLLMVerdict:
    def test_verdict_fail_becomes_violation(self, monkeypatch):
        from arjun.middleware.output_guardrail import Verdict

        monkeypatch.setattr(
            "arjun.harness.retries.ask_structured",
            lambda call, schema, default: Verdict(passed=False, reason="medical prescription"),
        )
        v = og.llm_verdict("Take 20mg of sertraline daily.", {})
        assert v and "medical prescription" in v

    def test_verdict_fails_open_on_double_malformed(self, monkeypatch):
        calls = []

        def broken_complete(tier, messages, **kw):
            calls.append(tier)
            return "not json"

        monkeypatch.setattr("arjun.harness.gateway.complete", broken_complete)
        assert og.llm_verdict("Any reply.", {}) is None  # fails OPEN
        assert len(calls) == 2  # one ask + one re-ask
