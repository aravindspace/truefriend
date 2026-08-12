"""P1.17 unit tests — limbic renormalization/decay + reflection writes."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import arjun.organs.limbic as limbic_mod
import arjun.organs.reflection as reflection_mod
from arjun.graph.state import GUT_BASELINE, Feeling, GunaBalance, LimbicState, Person
from arjun.memory.namespaces import ReadScope
from arjun.memory.stores import make_store
from arjun.organs.limbic import decay_toward_baseline, limbic_update, renormalize
from arjun.organs.reflection import Distillation, distill_session, make_reflection
from arjun.organs.temporal import build_tools

FAKE_EMBED = lambda texts: [[0.0] * 512 for _ in texts]  # noqa: E731


@pytest.fixture
def store(tmp_path):
    return make_store(path=tmp_path / "lt.db", embed=FAKE_EMBED)


def turn_state(**overrides):
    state = {
        "messages": [
            HumanMessage(content="I lost my father last month."),
            AIMessage(content="I am with you in this grief, friend."),
        ],
        "person": Person(id="ravi_a1", is_guest=False),
        "limbic_state": LimbicState(),
        "self_harm_flag": False,
    }
    state.update(overrides)
    return state


class TestRenormalize:
    def test_weights_normalized_proportionally(self):
        gb = renormalize(0.8, 0.8, 0.4)
        assert gb.sattva == pytest.approx(0.4) and gb.tamas == pytest.approx(0.2)
        assert gb.sattva + gb.rajas + gb.tamas == pytest.approx(1.0)

    def test_all_zero_relaxes_to_baseline(self):
        assert renormalize(0, 0, 0) == GUT_BASELINE


class TestDecay:
    def test_repeated_decay_converges_to_baseline(self):
        state = LimbicState(
            guna_balance=GunaBalance(sattva=0.1, rajas=0.2, tamas=0.7),
            active_feelings=[Feeling(name="sorrow", intensity=0.9, cause="heavy session")],
        )
        for _ in range(6):
            state = decay_toward_baseline(state)
        assert state.guna_balance.sattva == pytest.approx(GUT_BASELINE.sattva, abs=0.02)
        assert state.guna_balance.tamas == pytest.approx(GUT_BASELINE.tamas, abs=0.02)

    def test_feelings_fade_and_dissolve(self):
        state = LimbicState(
            active_feelings=[Feeling(name="sorrow", intensity=0.3, cause="x")]
        )
        once = decay_toward_baseline(state)
        assert once.active_feelings[0].intensity == pytest.approx(0.15)
        twice = decay_toward_baseline(once)
        assert twice.active_feelings == []  # dissolved below the floor


class TestLimbicUpdate:
    def test_proposal_renormalized(self, monkeypatch):
        proposal = limbic_mod.LimbicProposal(
            sattva=2.0, rajas=1.0, tamas=1.0,
            active_feelings=[Feeling(name="compassion", intensity=0.8, cause="grief")],
        )
        monkeypatch.setattr(limbic_mod, "_invoke_llm", lambda s, u: proposal.model_dump_json())
        updated = limbic_update(turn_state())
        assert updated.guna_balance.sattva == pytest.approx(0.5)
        assert updated.active_feelings[0].name == "compassion"

    def test_double_malformed_keeps_current_state(self, monkeypatch):
        monkeypatch.setattr(limbic_mod, "_invoke_llm", lambda s, u: "not json")
        current = LimbicState(guna_balance=GunaBalance(sattva=0.4, rajas=0.4, tamas=0.2))
        updated = limbic_update(turn_state(limbic_state=current))
        assert updated.guna_balance == current.guna_balance  # mood never fabricated

    def test_empty_exchange_short_circuits(self, monkeypatch):
        def fail(*a):
            raise AssertionError("LLM must not run on empty exchange")

        monkeypatch.setattr(limbic_mod, "_invoke_llm", fail)
        assert limbic_update(turn_state(messages=[])) == LimbicState()


class TestReflectionNode:
    @pytest.fixture(autouse=True)
    def calm_limbic(self, monkeypatch):
        proposal = limbic_mod.LimbicProposal(sattva=0.7, rajas=0.2, tamas=0.1)
        monkeypatch.setattr(limbic_mod, "_invoke_llm", lambda s, u: proposal.model_dump_json())

    def test_mood_snapshot_written_every_turn(self, store):
        node = make_reflection(store)
        update = node(turn_state())
        assert "limbic_state" in update
        snaps = store.search(ReadScope("ravi_a1").arjun_self("mood_history"), limit=10)
        assert len(snaps) == 1 and "sattva=0.70" in snaps[0].value["text"]

    def test_self_harm_event_logged_for_seva(self, store):
        node = make_reflection(store)
        node(turn_state(self_harm_flag=True))
        items = store.search(ReadScope("ravi_a1").person("commitments"), limit=10)
        assert any("self-harm" in i.value["text"] for i in items)

    def test_no_self_harm_no_urgent_log(self, store):
        make_reflection(store)(turn_state())
        assert store.search(ReadScope("ravi_a1").person("commitments"), limit=10) == []


class TestDistillation:
    def test_transcript_distilled_into_right_namespaces(self, store, monkeypatch):
        distilled = Distillation(
            episode="Came grieving his father; the deathless-soul teaching helped.",
            diagnoses=["Moha strong, Tamas environment"],
            commitments=["Ask about his sleep next session"],
            learnings=["Grief opens to teaching only after being heard"],
        )
        monkeypatch.setattr(
            reflection_mod, "_invoke_distill_llm", lambda s, t: distilled.model_dump_json()
        )
        out = distill_session(store, "ravi_a1", turn_state()["messages"])
        assert out == distilled

        scope = ReadScope("ravi_a1")
        assert "grieving his father" in store.search(scope.person("episodes"), limit=5)[0].value["text"]
        assert store.search(scope.person("diagnoses"), limit=5)
        assert store.search(scope.person("commitments"), limit=5)
        assert store.search(scope.arjun_self("learnings"), limit=5)

    def test_empty_transcript_writes_nothing(self, store, monkeypatch):
        def fail(*a):
            raise AssertionError("no LLM call on empty transcript")

        monkeypatch.setattr(reflection_mod, "_invoke_distill_llm", fail)
        assert distill_session(store, "ravi_a1", []) == Distillation()

    def test_double_malformed_writes_nothing(self, store, monkeypatch):
        monkeypatch.setattr(reflection_mod, "_invoke_distill_llm", lambda s, t: "broken")
        distill_session(store, "ravi_a1", turn_state()["messages"])
        assert store.search(ReadScope("ravi_a1").person("episodes"), limit=5) == []


class TestOnlyWritePath:
    def test_mid_turn_belt_still_refuses_while_reflection_writes(self, store):
        mid_turn = {t.name: t for t in build_tools(store, ReadScope("ravi_a1"))}
        refused = mid_turn["store_put"].invoke(
            {"section": "episodes", "key": "e", "text": "sneak"}
        )
        assert refused.startswith("REFUSED")
        put = reflection_mod._reflection_put(store, "ravi_a1")
        assert put.invoke({"section": "episodes", "key": "e", "text": "ok"}) == "stored episodes/e"
