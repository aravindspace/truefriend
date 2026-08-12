"""P1.15 unit tests — Frontal Lobe plan + compose with mocked LLM."""

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import arjun.organs.frontal as frontal
from arjun.graph.state import (
    Feeling,
    GunaBalance,
    GutRead,
    LimbicState,
    MemoryRecall,
    Person,
    RetrievedChunk,
    TurnPlan,
    WorldItem,
)
from arjun.harness.budgets import get_budget

COUNSELING = get_budget("counseling")
SMALL_TALK = get_budget("small_talk")


def base_state(**overrides):
    state = {
        "messages": [HumanMessage(content="My brother and I fight over land daily.")],
        "gut_read": GutRead(problem_domain_guess=["family"], emotional_temperature=0.6),
        "tier": COUNSELING,
        "limbic_state": LimbicState(),
        "retrieved": [],
        "memory_recall": None,
        "world_context": [],
        "self_harm_flag": False,
    }
    state.update(overrides)
    return state


class TestPlan:
    def test_plan_output_validates(self, monkeypatch):
        plan = TurnPlan(run_retrieval=True, retrieval_purpose="family conflict teachings")
        monkeypatch.setattr(frontal, "_invoke_plan_llm", lambda a, s, u: plan.model_dump_json())
        update = frontal.frontal_plan(base_state())
        assert update["turn_plan"].run_retrieval is True
        assert update["turn_plan"].retrieval_purpose == "family conflict teachings"

    def test_canon_scholars_run_together(self, monkeypatch):
        """Vector without graph is the bug that made replies teaching-only —
        asking for Canon material must always run BOTH scholars (ADR 0006)."""
        vector_only = TurnPlan(run_retrieval=True, retrieval_purpose="gita")
        monkeypatch.setattr(frontal, "_invoke_plan_llm", lambda a, s, u: vector_only.model_dump_json())
        plan = frontal.frontal_plan(base_state())["turn_plan"]
        assert plan.run_routing is True and plan.run_retrieval is True

    def test_self_harm_forces_both_scholars(self, monkeypatch):
        monkeypatch.setattr(frontal, "_invoke_plan_llm", lambda a, s, u: TurnPlan().model_dump_json())
        plan = frontal.frontal_plan(
            base_state(gut_read=GutRead(self_harm_flag=True, emotional_temperature=0.95))
        )["turn_plan"]
        assert plan.run_retrieval is True and plan.run_routing is True

    def test_malformed_plan_twice_falls_to_default(self, monkeypatch):
        calls = []

        def broken(alias, system, user):
            calls.append(alias)
            return "no json here"

        monkeypatch.setattr(frontal, "_invoke_plan_llm", broken)
        update = frontal.frontal_plan(base_state())
        assert update["turn_plan"] == frontal.DEFAULT_PLAN
        assert len(calls) == 2  # one re-ask (P1.6 discipline)

    def test_small_talk_skips_planning_llm_entirely(self, monkeypatch):
        def fail(*a):
            raise AssertionError("LLM must not be called for small talk")

        monkeypatch.setattr(frontal, "_invoke_plan_llm", fail)
        update = frontal.frontal_plan(base_state(tier=SMALL_TALK))
        assert update["turn_plan"] == frontal.NO_SUBAGENTS  # guest → nothing

    def test_known_person_always_gets_memory_even_on_small_talk(self, monkeypatch):
        """A friend does not forget you because you said something casual."""

        def fail(*a):
            raise AssertionError("LLM must not be called for small talk")

        monkeypatch.setattr(frontal, "_invoke_plan_llm", fail)
        known = Person(id="ganesh_88768be0a57a", display_name="Ganesh", is_guest=False)
        update = frontal.frontal_plan(base_state(tier=SMALL_TALK, person=known))
        assert update["turn_plan"].run_temporal is True
        assert update["turn_plan"].run_retrieval is False  # expensive fetchers stay off

    def test_known_person_memory_forced_when_llm_plan_omits_it(self, monkeypatch):
        lazy = TurnPlan(run_retrieval=True, retrieval_purpose="gita")  # no temporal
        monkeypatch.setattr(frontal, "_invoke_plan_llm", lambda a, s, u: lazy.model_dump_json())
        known = Person(id="ganesh_88768be0a57a", display_name="Ganesh", is_guest=False)
        update = frontal.frontal_plan(base_state(person=known))
        assert update["turn_plan"].run_temporal is True

    def test_flagged_injection_gets_no_subagents(self, monkeypatch):
        monkeypatch.setattr(frontal, "_invoke_plan_llm", lambda *a: "unused")
        update = frontal.frontal_plan(base_state(gut_read=GutRead(injection_attempt=True)))
        assert update["turn_plan"] == frontal.NO_SUBAGENTS

    def test_self_harm_forces_retrieval_even_if_plan_omits_it(self, monkeypatch):
        lazy_plan = TurnPlan()  # LLM said: nothing needed
        monkeypatch.setattr(frontal, "_invoke_plan_llm", lambda a, s, u: lazy_plan.model_dump_json())
        update = frontal.frontal_plan(
            base_state(gut_read=GutRead(self_harm_flag=True, emotional_temperature=0.95))
        )
        assert update["turn_plan"].run_retrieval is True


class TestComposePrompt:
    def test_helpline_present_iff_flag_set(self):
        with_flag = frontal.build_compose_prompt(base_state(self_harm_flag=True))
        without = frontal.build_compose_prompt(base_state())
        for number in frontal.HELPLINE_NUMBERS:
            assert number in with_flag
        assert "Tele-MANAS" in with_flag and "Tele-MANAS" not in without

    def test_chunk_texts_verbatim_in_prompt(self):
        weird = 'Kṛṣṇa said — "na jāyate mriyate vā kadācin…" (verbatim ✓ <>&)'
        state = base_state(
            retrieved=[
                RetrievedChunk(chunk_id="chunk_0042", text=weird, source="canon", chunk_type="TEACHING"),
                RetrievedChunk(chunk_id="notebook:grief", text="My own study note.", source="notebook"),
            ]
        )
        prompt = frontal.build_compose_prompt(state)
        assert weird in prompt and "[chunk_0042]" in prompt
        assert "YOUR understanding, never as Canon" in prompt and "My own study note." in prompt

    def test_memory_world_and_tone_sections(self):
        state = base_state(
            memory_recall=MemoryRecall(profile=["Works in Hyderabad"], commitments=["ask about sleep"]),
            world_context=[WorldItem(content="Rain expected", source="open-meteo.com", timestamp="2026-07-17T09:00:00+00:00")],
            limbic_state=LimbicState(
                guna_balance=GunaBalance(sattva=0.5, rajas=0.4, tamas=0.1),
                active_feelings=[Feeling(name="compassion", intensity=0.8, cause="person's pain")],
            ),
        )
        prompt = frontal.build_compose_prompt(state)
        assert "Works in Hyderabad" in prompt and "ask about sleep" in prompt
        assert "Rain expected" in prompt and "sattva 0.50" in prompt
        assert "compassion (0.8) because person's pain" in prompt

    def test_decline_instruction_on_off_mission(self):
        prompt = frontal.build_compose_prompt(base_state(gut_read=GutRead(off_mission=True)))
        assert "Decline warmly" in prompt and "Never comply" in prompt


class TestCompose:
    def test_reply_is_ai_message_on_tier_alias(self, monkeypatch):
        seen = {}

        def fake(alias, system, messages, max_tokens):
            seen.update(alias=alias, max_tokens=max_tokens, roles=[m["role"] for m in messages])
            return "Namaste, my friend."

        monkeypatch.setattr(frontal, "_invoke_compose_llm", fake)
        update = frontal.frontal_compose(base_state(messages=[
            HumanMessage(content="hi"), AIMessage(content="hello"), HumanMessage(content="listen…"),
        ]))
        assert isinstance(update["messages"][0], AIMessage)
        assert update["messages"][0].content == "Namaste, my friend."
        assert seen["alias"] == "voice" and seen["max_tokens"] == COUNSELING.max_tokens
        assert seen["roles"] == ["user", "assistant", "user"]

    def test_small_talk_composes_on_fast(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(
            frontal, "_invoke_compose_llm",
            lambda alias, s, m, t: seen.update(alias=alias) or "hi!",
        )
        frontal.frontal_compose(base_state(tier=SMALL_TALK))
        assert seen["alias"] == "fast"
