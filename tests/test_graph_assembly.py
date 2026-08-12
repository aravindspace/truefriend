"""P1.18 structural tests — the graph matches §20.1/§20.4 exactly."""

import pytest
from langchain_core.messages import HumanMessage

from arjun.graph.build import (
    ORGAN_NODES,
    SUBAGENT_KEYS,
    SUBAGENT_NODES,
    build_brain,
    make_retrieval_node,
    make_temporal_node,
    make_world_node,
    route_subagents,
)
from arjun.graph.state import GutRead, Person, TurnPlan
from arjun.memory.stores import make_checkpointer, make_store
from arjun.subagents.retrieval import RetrievalResult

FAKE_EMBED = lambda texts: [[0.0] * 512 for _ in texts]  # noqa: E731


@pytest.fixture
def brain(tmp_path):
    return build_brain(
        store=make_store(tmp_path / "lt.db", embed=FAKE_EMBED),
        checkpointer=make_checkpointer(tmp_path / "st.db"),
    )


class TestTotals:
    def test_seven_organs_four_subagents(self, brain):
        nodes = set(brain.get_graph().nodes) - {"__start__", "__end__"}
        assert nodes == set(ORGAN_NODES) | set(SUBAGENT_NODES)
        # 7 organs (+identity) · 4 subagents (+routing = graph scholar, ADR 0006)
        assert len(ORGAN_NODES) == 7 and len(SUBAGENT_NODES) == 4
        assert "routing" in SUBAGENT_NODES

    def test_exactly_one_conditional_edge(self, brain):
        conditional_sources = {
            e.source for e in brain.get_graph().edges if e.conditional
        }
        assert conditional_sources == {"frontal_plan"}

    def test_wiring_shape(self, brain):
        edges = {(e.source, e.target) for e in brain.get_graph().edges if not e.conditional}
        assert ("__start__", "gut_screen") in edges
        assert ("gut_screen", "thyroid") in edges
        assert ("thyroid", "identity") in edges
        assert ("identity", "frontal_plan") in edges
        for s in SUBAGENT_NODES:
            assert (s, "frontal_compose") in edges
        assert ("frontal_compose", "output_guardrail") in edges
        assert ("output_guardrail", "reflection") in edges
        assert ("reflection", "__end__") in edges

    def test_persistence_attached(self, brain):
        assert brain.checkpointer is not None and brain.store is not None


class TestRouting:
    def test_any_subset_routes(self):
        plan = TurnPlan(run_retrieval=True, run_world=True)
        assert route_subagents({"turn_plan": plan}) == ["retrieval", "world"]

    def test_empty_plan_goes_straight_to_compose(self):
        assert route_subagents({"turn_plan": TurnPlan()}) == ["frontal_compose"]
        assert route_subagents({}) == ["frontal_compose"]


class TestInvariants:
    def test_decide_nodes_are_plain_functions_no_tools(self):
        from arjun.organs import frontal, gut, thyroid

        for fn in (gut.gut_screen, thyroid.thyroid, frontal.frontal_plan, frontal.frontal_compose):
            assert callable(fn) and not hasattr(fn, "tools")

    def test_fetch_nodes_write_exactly_their_key_never_messages(self, tmp_path):
        state = {
            "messages": [HumanMessage(content="my grief")],
            "person": Person(id="ravi_a1"),
            "gut_read": GutRead(problem_domain_guess=["loss"]),
            "turn_plan": TurnPlan(run_retrieval=True, run_temporal=True, run_world=True),
        }
        retrieval = make_retrieval_node(retrieve=lambda *a, **k: RetrievalResult(found=False))
        temporal = make_temporal_node(make_store(tmp_path / "l.db", embed=FAKE_EMBED))
        world = make_world_node(fetch=lambda task: [])

        for name, node in (("retrieval", retrieval), ("temporal", temporal), ("world", world)):
            update = node(state)
            assert set(update) == {SUBAGENT_KEYS[name]}  # one key, no user text
