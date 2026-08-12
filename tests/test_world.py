"""P1.14 unit tests — world subagent with mocked fetchers (§6.3 row 3)."""

from datetime import datetime

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

import arjun.subagents.world as world
from arjun.subagents.world import build_world_tools, make_world_agent


@pytest.fixture
def mocked_fetchers(monkeypatch):
    monkeypatch.setattr(
        world,
        "_search_text",
        lambda q, n: [{"title": "T1", "body": "fact one", "href": "https://ex.com/1"}],
    )
    monkeypatch.setattr(
        world,
        "_search_news",
        lambda t, n: [
            {"date": "2026-07-17", "title": "N1", "body": "news body", "source": "PTI", "url": "https://ex.com/n"}
        ],
    )
    monkeypatch.setattr(
        world,
        "_fetch_weather",
        lambda p: {"place": "Hyderabad", "temperature_2m": 31.2, "wind_speed_10m": 8.0, "weather_code": 2},
    )


def belt_and_collector():
    collector = []
    return {t.name: t for t in build_world_tools(collector)}, collector


class TestOutputShape:
    def test_every_item_timestamped_and_sourced(self, mocked_fetchers):
        belt, collector = belt_and_collector()
        belt["web_search"].invoke({"query": "current affairs India"})
        belt["weather"].invoke({"place": "Hyderabad"})
        belt["news"].invoke({"topic": "monsoon"})

        assert len(collector) == 3
        for item in collector:
            assert item.content and item.source
            datetime.fromisoformat(item.timestamp)  # valid ISO 8601 or raises

    def test_sources_are_real_origins(self, mocked_fetchers):
        belt, collector = belt_and_collector()
        belt["web_search"].invoke({"query": "q"})
        belt["weather"].invoke({"place": "Hyderabad"})
        belt["news"].invoke({"topic": "t"})
        assert {i.source for i in collector} == {"https://ex.com/1", "open-meteo.com", "PTI"}


class TestDegradation:
    def test_broken_fetcher_degrades_never_raises(self, monkeypatch):
        def boom(q, n):
            raise RuntimeError("network down")

        monkeypatch.setattr(world, "_search_text", boom)
        belt, collector = belt_and_collector()
        out = belt["web_search"].invoke({"query": "x"})
        assert "unavailable" in out and collector == []

    def test_unknown_place(self, monkeypatch):
        monkeypatch.setattr(world, "_fetch_weather", lambda p: None)
        belt, collector = belt_and_collector()
        assert "unknown place" in belt["weather"].invoke({"place": "Xyzzy"})
        assert collector == []


class TestQuarantine:
    def test_tool_belt_is_exactly_three_no_store_tools(self):
        belt, _ = belt_and_collector()
        assert set(belt) == {"web_search", "weather", "news"}

    def test_agent_carries_no_store_tools(self):
        agent = make_world_agent(
            [],
            model=FakeListChatModel(responses=["ok"]),
            summarizer_model=FakeListChatModel(responses=["s"]),
        )
        names = set(agent.nodes["tools"].bound._tools_by_name)
        assert names == {"web_search", "weather", "news"}
        assert not any(n.startswith("store_") or "put" in n for n in names)

    def test_run_world_returns_collector_even_on_agent_failure(self, mocked_fetchers):
        # A model that cannot tool-call → empty collector, but never an exception.
        items = world.run_world(
            "weather in Hyderabad",
            model=FakeListChatModel(responses=["cannot call tools"]),
            summarizer_model=FakeListChatModel(responses=["s"]),
            fallback_models=[],  # hermetic: no real Groq/Gemini fallback in this test
        )
        assert items == []
