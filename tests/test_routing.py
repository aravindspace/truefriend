"""Routing subagent — the GRAPH scholar (ADR 0006).

Stage 1 (anartha reading) is mocked; stage 2 (the graph walk) runs against the
REAL Kuzu clone, because the whole point of this agent is that the traverse
actually happens.
"""

import pytest

import arjun.subagents.routing as routing_mod
from arjun.subagents.routing import (
    AnarthaReading,
    RoutingDecision,
    RoutingResult,
    read_situation,
    run_routing,
    walk_graph,
)

JOBLESS = (
    "i am feeling depressed as i haven't got job even trying for three months, "
    "got rejections, i left my job three months ago, feels broken heart"
)

#: The owner's worked example: one situation, many anarthas (§8.2).
MULTI = RoutingDecision(
    readings=[
        AnarthaReading(anartha="Krodha", confidence=0.9, why="anxiety and irritation about the search"),
        AnarthaReading(anartha="Moha", confidence=0.85, why="identity fused with having a job"),
        AnarthaReading(anartha="Kama", confidence=0.7, why="fixed on a specific job and salary"),
        AnarthaReading(anartha="Mada", confidence=0.5, why="pride in his skills, wounded by rejection"),
        AnarthaReading(anartha="Lobha", confidence=0.3, why="wanting a bigger package"),
    ],
    guna_environment="Tamas",
    problem_domains=["career"],
    life_reading="Desire blocked has become anger, resting on the illusion that the job is the self.",
)


class TestReadSituation:
    def test_multi_anartha_reading_kept_and_ranked(self, monkeypatch):
        monkeypatch.setattr(routing_mod, "_invoke_llm", lambda s, u: MULTI.model_dump_json())
        d = read_situation(JOBLESS)
        assert len(d.readings) == 5  # a life incident carries several anarthas
        assert [r.anartha for r in d.readings][:2] == ["Krodha", "Moha"]  # ranked
        assert d.guna_environment == "Tamas"

    def test_low_confidence_noise_dropped(self, monkeypatch):
        noisy = MULTI.model_copy(
            update={
                "readings": MULTI.readings
                + [AnarthaReading(anartha="Matsarya", confidence=0.05, why="faint")]
            }
        )
        monkeypatch.setattr(routing_mod, "_invoke_llm", lambda s, u: noisy.model_dump_json())
        assert "Matsarya" not in [r.anartha for r in read_situation(JOBLESS).readings]

    def test_double_malformed_gives_empty_decision_not_crash(self, monkeypatch):
        monkeypatch.setattr(routing_mod, "_invoke_llm", lambda s, u: "not json")
        d = read_situation(JOBLESS)
        assert d.readings == []

    def test_past_diagnoses_reach_the_prompt(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(
            routing_mod, "_invoke_llm", lambda s, u: seen.update(user=u) or MULTI.model_dump_json()
        )
        read_situation(JOBLESS, past_diagnoses=["Moha strong, Tamas environment"])
        assert "Moha strong" in seen["user"]  # long-term memory informs the reading


class TestWalkGraph:
    """Runs against the REAL graph — this is the regression that matters."""

    def test_walks_every_anartha_and_returns_canon_nodes(self):
        chunks, connections = walk_graph(MULTI)
        assert chunks, "graph walk must return Canon nodes for a multi-anartha reading"
        assert all(c.source == "canon" for c in chunks)
        assert all(c.chunk_id.startswith("chunk_") for c in chunks)
        assert any(c.chunk_type == "HISTORICAL_ACCOUNT" for c in chunks)
        assert connections, "the scholar must connect nodes to the problem"

    def test_moha_alone_reaches_incidents(self):
        chunks, _ = walk_graph(
            RoutingDecision(readings=[AnarthaReading(anartha="Moha", confidence=0.9, why="grief")])
        )
        assert any(c.chunk_type == "HISTORICAL_ACCOUNT" for c in chunks)

    def test_no_readings_returns_nothing(self):
        chunks, connections = walk_graph(RoutingDecision())
        assert chunks == [] and connections == []

    def test_chunks_are_deduplicated(self):
        chunks, _ = walk_graph(MULTI)
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))


class TestRunRouting:
    def test_full_pass_returns_decision_and_nodes(self, monkeypatch):
        monkeypatch.setattr(routing_mod, "_invoke_llm", lambda s, u: MULTI.model_dump_json())
        result = run_routing(JOBLESS)
        assert isinstance(result, RoutingResult)
        assert result.found and result.decision.readings
        assert result.decision.life_reading

    def test_guest_skips_memory_lookup(self, monkeypatch):
        monkeypatch.setattr(routing_mod, "_invoke_llm", lambda s, u: MULTI.model_dump_json())

        class Boom:
            def search(self, *a, **k):
                raise AssertionError("must not read memory for a guest")

        assert run_routing(JOBLESS, store=Boom(), person_id="guest_x").found
