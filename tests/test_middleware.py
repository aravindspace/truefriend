"""P1.7 unit tests — middleware stack (§20.3, §13)."""

import pytest
from langchain.agents.middleware import AgentMiddleware, SummarizationMiddleware
from langchain_core.messages import AIMessage

import arjun.middleware.prompt_loader as pl
from arjun.middleware.input_guardrail import InputGuardrail
from arjun.middleware.output_guardrail import OutputGuardrail
from arjun.middleware.stack import PROMPT_FILES, standard_stack
from langchain_core.language_models.fake_chat_models import FakeListChatModel


def _FakeModel():
    """Real BaseChatModel stand-in for the summarizer — never invoked here."""
    return FakeListChatModel(responses=["summary"])


@pytest.fixture
def prompts_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(pl, "PROMPTS_DIR", tmp_path)
    (tmp_path / "subagents").mkdir()
    return tmp_path


class TestPromptLoader:
    def test_hot_reload_between_two_calls(self, prompts_dir):
        f = prompts_dir / "subagents" / "retrieval.md"
        f.write_text("version one")
        assert pl.load_prompt("subagents/retrieval.md") == "version one"
        f.write_text("version two — edited on disk")
        assert pl.load_prompt("subagents/retrieval.md") == "version two — edited on disk"

    def test_prompt_loader_returns_middleware(self, prompts_dir):
        (prompts_dir / "subagents" / "retrieval.md").write_text("x")
        assert isinstance(pl.prompt_loader("subagents/retrieval.md"), AgentMiddleware)

    def test_real_prompt_files_all_load(self):
        for rel in PROMPT_FILES.values():
            assert pl.load_prompt(rel).strip()


class TestScaffolds:
    def test_input_guardrail_passes_through_without_screen(self):
        assert InputGuardrail().before_model({"messages": []}, None) is None

    def test_input_screen_update_is_returned(self):
        mw = InputGuardrail(screen=lambda state: {"flagged": True})
        assert mw.before_model({"messages": []}, None) == {"flagged": True}

    def test_broken_screen_fails_open(self):
        def boom(state):
            raise RuntimeError("screen crashed")

        assert InputGuardrail(screen=boom).before_model({"messages": []}, None) is None

    def test_output_guardrail_passes_through_without_layers(self):
        state = {"messages": [AIMessage(content="hi")]}
        assert OutputGuardrail().after_model(state, None) is None

    def test_output_check_runs_deterministic_before_llm(self):
        order = []

        def det(reply, state):
            order.append("deterministic")
            return "violation!"

        def llm(reply, state):
            order.append("llm")
            return None

        g = OutputGuardrail(deterministic=det, llm_verdict=llm)
        assert g.check("reply", {}) == "violation!"
        assert order == ["deterministic"]  # LLM layer never ran — det failed first


class TestStack:
    def test_standard_stack_order(self):
        # fallback_models=[] omits ModelFallbackMiddleware for a hermetic 4-shape.
        stack = standard_stack("retrieval", summarizer_model=_FakeModel(), fallback_models=[])
        assert len(stack) == 4
        assert isinstance(stack[1], InputGuardrail)
        assert isinstance(stack[2], SummarizationMiddleware)
        assert isinstance(stack[3], OutputGuardrail)

    def test_fallback_middleware_appended_when_models_given(self):
        from langchain.agents.middleware import ModelFallbackMiddleware

        stack = standard_stack(
            "world",
            summarizer_model=_FakeModel(),
            fallback_models=[_FakeModel()],
        )
        assert len(stack) == 5
        assert isinstance(stack[4], ModelFallbackMiddleware)

    def test_all_phase1_subagents_have_prompt_files(self):
        assert set(PROMPT_FILES) == {"retrieval", "temporal", "world"}

    def test_unknown_agent_raises(self):
        with pytest.raises(KeyError):
            standard_stack("nonexistent", summarizer_model=_FakeModel(), fallback_models=[])
