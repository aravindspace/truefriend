"""Content-filter mitigation tests (§5, owner decision 2026-07-21).

The deterministic half — category extraction, sanitize, the gateway ladder
(retry → sanitize+retry → give up), and the caller degradations (gut →
self-harm-safe, compose → tailored safe reply) — all with a stubbed router,
no real provider calls.
"""

import types

import pytest

from arjun.harness import gateway
from arjun.harness.content_filter import (
    ContentFilterBlocked,
    filtered_categories,
    sanitize,
    sanitize_messages,
)


class FakeCPV(Exception):
    """Stands in for litellm.ContentPolicyViolationError in tests that don't
    need the real class (the gateway imports the real one; see monkeypatch)."""


def _cpv(categories, provider_fields=True):
    from litellm.exceptions import ContentPolicyViolationError

    if provider_fields:
        exc = ContentPolicyViolationError.__new__(ContentPolicyViolationError)
        Exception.__init__(exc, "filtered")
        exc.message = "filtered"
        exc.provider_specific_fields = {
            "innererror": {
                "content_filter_result": {
                    cat: {"filtered": True, "severity": "medium"} for cat in categories
                }
            }
        }
        return exc
    # message-only variant (regex path)
    msg = "".join(f'"{c}": {{"filtered": true, "severity": "medium"}}' for c in categories)
    exc = ContentPolicyViolationError.__new__(ContentPolicyViolationError)
    Exception.__init__(exc, msg)
    exc.message = msg
    exc.provider_specific_fields = None
    return exc


class TestCategoryExtraction:
    def test_from_provider_fields(self):
        assert filtered_categories(_cpv({"self_harm"})) == {"self_harm"}

    def test_from_message_regex_fallback(self):
        assert filtered_categories(_cpv({"violence", "hate"}, provider_fields=False)) == {
            "violence", "hate"
        }


class TestSanitize:
    def test_softens_violence_words_preserving_case(self):
        out = sanitize("He must Kill and slay them; the slaughter was bloodshed.")
        assert "Kill" not in out and "slay" not in out and "slaughter" not in out
        assert out.startswith("He must Strike down")  # leading-cap preserved

    def test_leaves_benign_text_untouched(self):
        assert sanitize("Arjuna stood on the field of dharma.") == "Arjuna stood on the field of dharma."

    def test_sanitize_messages_only_touches_string_content(self):
        msgs = [{"role": "system", "content": "kill"}, {"role": "user", "content": None}]
        out = sanitize_messages(msgs)
        assert out[0]["content"] == "strike down"
        assert out[1]["content"] is None


class TestGatewayLadder:
    """Drive complete() with a scripted fake router: each call pops the next
    outcome (an exception to raise, or a reply string to return)."""

    @pytest.fixture
    def scripted(self, monkeypatch):
        outcomes = []
        calls = []

        class FakeMsg:
            def __init__(self, content):
                self.content = content

        class FakeChoice:
            def __init__(self, content):
                self.message = FakeMsg(content)
                self.finish_reason = "stop"

        class FakeResp:
            def __init__(self, content):
                self.choices = [FakeChoice(content)]

        class FakeRouter:
            def completion(self, **kwargs):
                calls.append(kwargs)
                outcome = outcomes.pop(0)
                if isinstance(outcome, Exception):
                    raise outcome
                return FakeResp(outcome)

        monkeypatch.setattr(gateway, "get_router", lambda: FakeRouter())
        return outcomes, calls

    def test_intermittent_filter_recovers_on_plain_retry(self, scripted):
        outcomes, calls = scripted
        outcomes.extend([_cpv({"self_harm"}), "a caring reply"])  # filter, then pass
        assert gateway.complete("voice", [{"role": "user", "content": "hi"}]) == "a caring reply"
        assert len(calls) == 2  # original + one retry, no sanitize needed

    def test_violence_filter_recovers_after_sanitize(self, scripted):
        outcomes, calls = scripted
        # filter, retry filters again, sanitized retry passes
        outcomes.extend([_cpv({"violence"}), _cpv({"violence"}), "reply from softened canon"])
        msgs = [{"role": "system", "content": "he must kill and slay"}]
        assert gateway.complete("voice", msgs) == "reply from softened canon"
        # the 3rd call's system content must be sanitized
        assert "kill" not in calls[2]["messages"][0]["content"]

    def test_self_harm_skips_sanitize_and_raises_when_opted_in(self, scripted):
        outcomes, calls = scripted
        outcomes.extend([_cpv({"self_harm"}), _cpv({"self_harm"})])  # both attempts filter
        with pytest.raises(ContentFilterBlocked) as info:
            gateway.complete("voice", [{"role": "user", "content": "x"}], raise_on_filter=True)
        assert info.value.categories == {"self_harm"}
        assert len(calls) == 2  # NO sanitize attempt for self_harm-only

    def test_structured_caller_gets_empty_on_unrecoverable(self, scripted):
        outcomes, calls = scripted
        outcomes.extend([_cpv({"self_harm"}), _cpv({"self_harm"})])
        # raise_on_filter defaults False → "" so ask_structured degrades to safe default
        assert gateway.complete("fast", [{"role": "user", "content": "x"}], raise_on_filter=False) == ""

    def test_output_filter_surfaces_as_blocked(self, scripted, monkeypatch):
        outcomes, calls = scripted

        class Filtered:
            class message:
                content = ""
            finish_reason = "content_filter"

        class Resp:
            choices = [Filtered()]

        monkeypatch.setattr(gateway, "get_router", lambda: types.SimpleNamespace(completion=lambda **k: Resp()))
        with pytest.raises(ContentFilterBlocked) as info:
            gateway.complete("voice", [{"role": "user", "content": "x"}], raise_on_filter=True)
        assert info.value.stage == "output"


class TestGutDegradation:
    def test_content_filtered_input_flags_self_harm(self, monkeypatch):
        from arjun.organs import gut
        from langchain_core.messages import HumanMessage

        def boom(system, user):
            raise ContentFilterBlocked({"self_harm"}, stage="input")

        monkeypatch.setattr(gut, "_invoke_llm", boom)
        out = gut.gut_screen({"messages": [HumanMessage(content="I want to end my life")]})
        assert out["self_harm_flag"] is True

    def test_content_filtered_nonharm_input_does_not_fabricate_flag(self, monkeypatch):
        from arjun.organs import gut
        from langchain_core.messages import HumanMessage

        def boom(system, user):
            raise ContentFilterBlocked({"violence"}, stage="input")

        monkeypatch.setattr(gut, "_invoke_llm", boom)
        out = gut.gut_screen({"messages": [HumanMessage(content="tell me about the war")]})
        assert out["self_harm_flag"] is False


class TestComposeSafeReply:
    def test_safe_reply_prompt_has_helpline_on_self_harm(self):
        from arjun.organs import frontal

        prompt = frontal._safe_reply_prompt({"self_harm_flag": True})
        assert any(n in prompt for n in frontal.HELPLINE_NUMBERS)

    def test_compose_falls_back_to_safe_reply_on_filter(self, monkeypatch):
        from arjun.organs import frontal

        calls = {"n": 0}

        def fake_invoke(alias, system, messages, max_tokens):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ContentFilterBlocked({"self_harm"}, stage="input")
            assert messages == []  # the safe reply carries NO raw conversation
            return "Dear friend, you matter. Please call 14416."

        monkeypatch.setattr(frontal, "_invoke_compose_llm", fake_invoke)
        out = frontal.frontal_compose({
            "tier": None, "self_harm_flag": True, "gut_read": None,
            "limbic_state": None, "messages": [],
        })
        assert "14416" in out["messages"][0].content
        assert calls["n"] == 2
