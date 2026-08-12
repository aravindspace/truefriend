"""P1.6 unit tests — harness core with stub graphs (§5, §4)."""

import threading
import time

import pytest
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from arjun.graph.state import ArjunState
from arjun.harness.budgets import get_budget, profile_names
from arjun.harness.fallbacks import HONEST_FALLBACK_REPLY, NoResult, first_nonempty
from arjun.harness.retries import ask_structured
from arjun.harness.runner import TurnRequest, run_turn
from arjun.harness.tracing import tracing_enabled


def compile_stub(node_fn, looping=False):
    g = StateGraph(ArjunState)
    g.add_node("stub", node_fn)
    g.add_edge(START, "stub")
    if looping:
        g.add_conditional_edges("stub", lambda s: "stub")  # never reaches END
    else:
        g.add_edge("stub", END)
    return g.compile()


REQ = TurnRequest(person_or_guest="guest_test", message="hello")


class TestBudgets:
    def test_profiles_exist(self):
        assert set(profile_names()) == {"small_talk", "counseling"}

    def test_counseling_budget_values(self):
        b = get_budget("counseling")
        assert b.compose_tier == "voice"
        assert b.recursion_limit == 25

    def test_unknown_profile_raises(self):
        with pytest.raises(KeyError):
            get_budget("no_such_profile")


class TestRunner:
    def test_normal_turn_returns_reply(self):
        graph = compile_stub(lambda s: {"messages": [AIMessage(content="Hare Krishna!")]})
        assert run_turn(REQ, graph) == "Hare Krishna!"

    def test_budget_exceeded_clean_stop(self):
        graph = compile_stub(lambda s: {}, looping=True)
        assert run_turn(REQ, graph, profile="small_talk") == HONEST_FALLBACK_REPLY

    def test_hung_node_produces_fallback_not_exception(self):
        def hung(state):
            time.sleep(5)
            return {"messages": [AIMessage(content="too late")]}

        graph = compile_stub(hung)
        assert run_turn(REQ, graph, step_timeout=1) == HONEST_FALLBACK_REPLY

    def test_crashing_node_produces_fallback(self):
        def boom(state):
            raise RuntimeError("kaboom")

        graph = compile_stub(boom)
        assert run_turn(REQ, graph) == HONEST_FALLBACK_REPLY

    def test_empty_result_produces_fallback(self):
        graph = compile_stub(lambda s: {})
        assert run_turn(REQ, graph) == HONEST_FALLBACK_REPLY

    def test_single_live_conversation_assertion(self):
        def slow(state):
            time.sleep(1.5)
            return {"messages": [AIMessage(content="done")]}

        graph = compile_stub(slow)
        errors = []

        t = threading.Thread(target=lambda: run_turn(REQ, graph))
        t.start()
        time.sleep(0.3)
        with pytest.raises(RuntimeError, match="single-live-conversation"):
            run_turn(REQ, compile_stub(lambda s: {}))
        t.join()
        assert not errors

    def test_request_contract_exactly_one_payload(self):
        with pytest.raises(ValueError):
            TurnRequest(person_or_guest="g", message="hi", drive_event="seva")
        with pytest.raises(ValueError):
            TurnRequest(person_or_guest="g")


class _Shape(BaseModel):
    mood: str


class TestStructuredReask:
    def test_valid_first_ask(self):
        calls = []

        def call(feedback):
            calls.append(feedback)
            return '{"mood": "sattva"}'

        out = ask_structured(call, _Shape, default=_Shape(mood="fallback"))
        assert out.mood == "sattva" and calls == [None]

    def test_one_reask_then_default(self):
        calls = []

        def call(feedback):
            calls.append(feedback)
            return "not json at all"

        out = ask_structured(call, _Shape, default=_Shape(mood="fallback"))
        assert out.mood == "fallback"
        assert len(calls) == 2  # one ask + exactly one re-ask
        assert calls[1] and "invalid" in calls[1]

    def test_reask_can_succeed(self):
        replies = iter(["broken", '{"mood": "rajas"}'])
        out = ask_structured(lambda f: next(replies), _Shape, default=_Shape(mood="fallback"))
        assert out.mood == "rajas"


class TestFallbackLadder:
    def test_first_nonempty_descends_past_empty_and_errors(self):
        def boom():
            raise RuntimeError("step exploded")

        name, results = first_nonempty(
            [("graph", lambda: []), ("qdrant", boom), ("notebook", lambda: ["note"])]
        )
        assert (name, results) == ("notebook", ["note"])

    def test_exhausted_ladder(self):
        assert first_nonempty([("graph", lambda: [])]) == ("none", [])

    def test_noresult_shape(self):
        nr = NoResult(subagent="retrieval", reason="timeout")
        assert (nr.subagent, nr.reason) == ("retrieval", "timeout")


class TestTracing:
    def test_placeholder_values_disable_tracing(self, monkeypatch):
        monkeypatch.setenv("LANGFUSE_HOST", "https://<your-instance>")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
        assert tracing_enabled() is False

    def test_missing_values_disable_tracing(self, monkeypatch):
        for name in ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
            monkeypatch.delenv(name, raising=False)
        assert tracing_enabled() is False

    def test_real_values_enable_tracing(self, monkeypatch):
        monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example.com")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-1")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-1")
        assert tracing_enabled() is True
