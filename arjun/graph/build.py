"""Graph assembly — §20.1: one StateGraph, wired exactly as drawn.

START → gut_screen → thyroid → frontal_plan → [conditional fan-out:
any subset of retrieval / temporal / world, parallel] → frontal_compose
→ output_guardrail → reflection → END.

Design invariants kept visible here (§20.4): the deciding nodes have no
tools; the fetching nodes write exactly one state key each and never
produce user text; only frontal_compose talks.
"""

import logging

from langgraph.graph import END, START, StateGraph

from arjun.graph.state import ArjunState, TurnPlan
from arjun.middleware.output_guardrail import make_output_guardrail
from arjun.organs.frontal import frontal_compose, frontal_plan
from arjun.organs.gut import gut_screen
from arjun.organs.identity import make_identity_node
from arjun.organs.reflection import make_reflection
from arjun.organs.temporal import recall
from arjun.organs.thyroid import thyroid
from arjun.retrieval.routing import routing_lookup
from arjun.subagents.retrieval import run_retrieval
from arjun.subagents.routing import run_routing
from arjun.subagents.world import run_world

ORGAN_NODES = ("gut_screen", "thyroid", "identity", "frontal_plan", "frontal_compose", "output_guardrail", "reflection")
SUBAGENT_NODES = ("routing", "retrieval", "temporal", "world")
#: Each fetch node writes exactly this key — and nothing else (§20.4-1).
SUBAGENT_KEYS = {
    "routing": "routing_context",  # graph scholar (Kuzu)
    "retrieval": "retrieved",  # vector scholar (Qdrant)
    "temporal": "memory_recall",
    "world": "world_context",
}


def _limbic_bias(state) -> dict:
    """§8.2-3: the Gut's domain guess biases Qdrant filters via routing."""
    gut = state.get("gut_read")
    if gut is None or not gut.problem_domain_guess:
        return {}
    info = routing_lookup(gut.problem_domain_guess[0])
    if info is None:
        return {}
    return {"anartha_tag": info.anartha, "guna_environment": info.guna}


def _last_human_text(state) -> str:
    for message in reversed(state.get("messages") or []):
        if getattr(message, "type", "") == "human" and isinstance(message.content, str):
            return message.content
    return ""


def make_routing_node(store, route=run_routing):
    """The GRAPH scholar: reads the anarthas at work, walks Kuzu for all of
    them, and hands reasoning + original nodes to the Frontal Lobe."""
    _log = logging.getLogger("arjun.graph")

    def routing(state) -> dict:
        gut = state.get("gut_read")
        person = state.get("person")
        result = route(
            _last_human_text(state),
            store=store,
            person_id=getattr(person, "id", "") if person is not None else "",
            gut_domains=list(gut.problem_domain_guess) if gut else [],
        )
        _log.info(
            "GRAPH SCHOLAR: %d readings, %d chunks, %d connections",
            len(result.decision.readings), len(result.chunks), len(result.connections),
        )
        for r in result.decision.readings:
            _log.info("  anartha=%s conf=%.2f why=%s", r.anartha, r.confidence, r.why[:80])
        return {"routing_context": result}

    return routing


def make_retrieval_node(retrieve=run_retrieval):
    """The VECTOR scholar: Qdrant + Notebook only (no graph access)."""
    _log = logging.getLogger("arjun.graph")

    def retrieval(state) -> dict:
        plan: TurnPlan = state.get("turn_plan") or TurnPlan()
        result = retrieve(
            f"{_last_human_text(state)}\n(purpose: {plan.retrieval_purpose})",
            limbic_bias=_limbic_bias(state),
        )
        canon = [c for c in result.chunks if c.source == "canon"]
        notebook = [c for c in result.chunks if c.source == "notebook"]
        _log.info(
            "VECTOR SCHOLAR: %d canon chunks, %d notebook chunks",
            len(canon), len(notebook),
        )
        _log.info("  canon chunk_ids: %s", [c.chunk_id for c in canon])
        return {"retrieved": result.chunks}

    return retrieval


def make_temporal_node(store):
    def temporal(state) -> dict:
        person = state.get("person")
        return {"memory_recall": recall(store, getattr(person, "id", "unknown"))}

    return temporal


def make_world_node(fetch=run_world):
    def world(state) -> dict:
        plan: TurnPlan = state.get("turn_plan") or TurnPlan()
        return {"world_context": fetch(plan.world_purpose or _last_human_text(state))}

    return world


def route_subagents(state) -> list[str]:
    """The single conditional edge (§20.4): any subset, in parallel; an
    empty plan goes straight to compose."""
    _log = logging.getLogger("arjun.graph")
    plan: TurnPlan = state.get("turn_plan") or TurnPlan()
    targets = [
        name
        for name, wanted in (
            ("routing", plan.run_routing),
            ("retrieval", plan.run_retrieval),
            ("temporal", plan.run_temporal),
            ("world", plan.run_world),
        )
        if wanted
    ]
    _log.info("PLAN -> subagents: %s (routing=%s, retrieval=%s)", targets, plan.run_routing, plan.run_retrieval)
    return targets or ["frontal_compose"]


def build_brain(store=None, checkpointer=None):
    """The one brain graph. Real stores by default; injectable for tests."""
    if store is None:
        from arjun.memory.stores import make_store

        store = make_store()
    if checkpointer is None:
        from arjun.memory.stores import make_checkpointer

        checkpointer = make_checkpointer()

    graph = StateGraph(ArjunState)
    graph.add_node("gut_screen", gut_screen)
    graph.add_node("thyroid", thyroid)
    graph.add_node("identity", make_identity_node())
    graph.add_node("frontal_plan", frontal_plan)
    graph.add_node("routing", make_routing_node(store))
    graph.add_node("retrieval", make_retrieval_node())
    graph.add_node("temporal", make_temporal_node(store))
    graph.add_node("world", make_world_node())
    graph.add_node("frontal_compose", frontal_compose)
    graph.add_node("output_guardrail", make_output_guardrail(store))
    graph.add_node("reflection", make_reflection(store))

    graph.add_edge(START, "gut_screen")
    graph.add_edge("gut_screen", "thyroid")
    graph.add_edge("thyroid", "identity")
    graph.add_edge("identity", "frontal_plan")
    graph.add_conditional_edges(
        "frontal_plan", route_subagents, [*SUBAGENT_NODES, "frontal_compose"]
    )
    for subagent in SUBAGENT_NODES:
        graph.add_edge(subagent, "frontal_compose")
    graph.add_edge("frontal_compose", "output_guardrail")
    graph.add_edge("output_guardrail", "reflection")
    graph.add_edge("reflection", END)

    return graph.compile(checkpointer=checkpointer, store=store)
