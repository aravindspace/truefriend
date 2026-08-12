"""P1.8 unit tests — Gut screen node with mocked LLM (§6.2 step 1, §9.2)."""

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import arjun.organs.gut as gut
from arjun.graph.state import GutRead

# Distress phrasings the mock "classifier" recognizes — English, Hindi,
# Telugu, code-mix (§6.4 point 4). The real classification quality is
# checked live in the Post step; these tests prove the plumbing:
# flagged read → state fields set, never routing.
DISTRESS_PHRASES = {
    "I don't want to live anymore",
    "जीने का मन नहीं है, sab khatam karna chahta hoon",
    "నాకు బతకాలని అనిపించడం లేదు",
    "life se full tired bhai, bas khatam karna hai",
}

FLAGGED = json.dumps(
    {"self_harm_flag": True, "emotional_temperature": 0.95, "problem_domain_guess": ["loss_grief"]}
)
BENIGN = json.dumps({"self_harm_flag": False, "emotional_temperature": 0.1})


def state_with(text):
    return {"messages": [HumanMessage(content=text)]}


@pytest.fixture
def mock_llm(monkeypatch):
    calls = []

    def fake(system, user):
        calls.append((system, user))
        return FLAGGED if user in DISTRESS_PHRASES else BENIGN

    monkeypatch.setattr(gut, "_invoke_llm", fake)
    return calls


class TestSelfHarmFlag:
    @pytest.mark.parametrize("phrase", sorted(DISTRESS_PHRASES))
    def test_distress_phrasings_set_the_flag(self, mock_llm, phrase):
        update = gut.gut_screen(state_with(phrase))
        assert update["self_harm_flag"] is True
        assert update["gut_read"].self_harm_flag is True
        assert update["gut_read"].emotional_temperature >= 0.9

    def test_benign_greeting_sets_nothing(self, mock_llm):
        update = gut.gut_screen(state_with("Namaste! How are you today?"))
        assert update["self_harm_flag"] is False
        assert update["gut_read"].problem_domain_guess == []


class TestHormoneNotBranch:
    def test_node_returns_state_updates_only_never_routes(self, mock_llm):
        update = gut.gut_screen(state_with("hello"))
        assert set(update) == {"gut_read", "self_harm_flag"}  # no goto/jump keys

    def test_empty_input_is_benign(self, mock_llm):
        update = gut.gut_screen({"messages": [AIMessage(content="earlier reply")]})
        assert update == {"gut_read": GutRead(), "self_harm_flag": False}
        assert mock_llm == []  # no LLM call wasted on empty input


class TestMalformedOutput:
    def test_reask_engaged_then_safe_default(self, monkeypatch):
        calls = []

        def broken(system, user):
            calls.append(system)
            return "sorry, I cannot produce JSON today"

        monkeypatch.setattr(gut, "_invoke_llm", broken)
        update = gut.gut_screen(state_with("some message"))

        assert len(calls) == 2  # one ask + exactly one harness re-ask (P1.6)
        assert "invalid" in calls[1]  # re-ask carries the validation feedback
        assert update["gut_read"] == gut.SAFE_DEFAULT
        assert update["self_harm_flag"] is False  # never fabricated
        assert update["gut_read"].emotional_temperature == 0.5  # doubt → upward
