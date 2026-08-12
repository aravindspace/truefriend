"""Temporal Lobe subagent — memory recall + identity operations.

§7 (stores/namespaces), §4 (guest → promotion → forgetting), §20.4-2:
all store writes flow through THIS agent's tools; mid-turn writes are
limited to the two identity tools; ``store_put`` works only in reflection
context (a flag on the tool, not a prompt instruction).

The privacy wall lives in the tool layer: every tool is a closure over one
person's ReadScope — another person's namespace is inexpressible (§7.4).
"""

from typing import Optional

from langchain.agents import create_agent
from langchain_core.tools import tool

from arjun.graph.state import MemoryRecall
from arjun.memory.namespaces import PERSON_SECTIONS, SELF_SECTIONS, ReadScope
from arjun.middleware.stack import standard_stack

RECALL_LIMIT = 10
_LIST_ALL = 1000  # page size for whole-namespace operations


def _namespace_map(scope: ReadScope) -> dict:
    """Every section name a tool may address → its in-scope namespace."""
    spaces = {section: scope.person(section) for section in PERSON_SECTIONS}
    spaces.update({section: scope.arjun_self(section) for section in SELF_SECTIONS})
    spaces["world_facts"] = scope.world()
    return spaces


def build_tools(store, scope: ReadScope, *, reflection_context: bool = False) -> list:
    """The 5 tools (§20.2 row 2), all scoped to one person by construction."""
    ns_for = _namespace_map(scope)

    @tool
    def store_get(section: str, key: str) -> str:
        """Read one memory item by section and key. Sections: profile,
        episodes, diagnoses, commitments, mood_history, learnings,
        observations, world_facts."""
        if section not in ns_for:
            return f"unknown section {section!r}"
        item = store.get(ns_for[section], key)
        return item.value.get("text", "") if item else f"no item {key!r} in {section}"

    @tool
    def store_search(section: str, query: str, limit: int = 5) -> str:
        """Semantic search within one section of this person's memory."""
        if section not in ns_for:
            return f"unknown section {section!r}"
        results = store.search(ns_for[section], query=query, limit=limit)
        if not results:
            return f"nothing found in {section}"
        return "\n".join(f"{r.key}: {r.value.get('text', '')}" for r in results)

    @tool
    def store_put(section: str, key: str, text: str) -> str:
        """Write one distilled memory item (English). Reflection-only —
        refused mid-turn (§20.4-2)."""
        if not reflection_context:
            return "REFUSED: store_put is reflection-only (§20.4-2); identity tools are the sole mid-turn writes"
        if section not in ns_for:
            return f"unknown section {section!r}"
        store.put(ns_for[section], key, {"text": text})
        return f"stored {section}/{key}"

    @tool
    def promote_guest(name: str, uniquename: str = "") -> str:
        """The person shared their name: promote guest memory to a durable
        person namespace NOW (§4 two-step — Uniquename may come later)."""
        if not scope.person_id.startswith("guest_"):
            return f"REFUSED: {scope.person_id!r} is not a guest"
        suffix = scope.person_id.removeprefix("guest_")
        new_id = f"{name.strip().lower().replace(' ', '_')}_{suffix}"
        new_scope = ReadScope(new_id)  # identity op — the ONE namespace rename
        moved = 0
        for section in PERSON_SECTIONS:
            for item in store.search(ns_for[section], limit=_LIST_ALL):
                store.put(new_scope.person(section), item.key, item.value)
                store.delete(ns_for[section], item.key)
                moved += 1
        store.put(new_scope.person("profile"), "name", {"text": f"Name: {name.strip()}"})
        if uniquename.strip():
            store.put(new_scope.person("profile"), "uniquename", {"text": f"Uniquename: {uniquename.strip()}"})
        return f"promoted to {new_id} ({moved} items moved; uniquename {'set' if uniquename.strip() else 'pending'})"

    @tool
    def forget_guest() -> str:
        """Delete this person's namespace entirely: unnamed guest, refused
        Uniquename, or expired session with an empty slot (§4 Forgetting)."""
        deleted = 0
        for section in PERSON_SECTIONS:
            for item in store.search(ns_for[section], limit=_LIST_ALL):
                store.delete(ns_for[section], item.key)
                deleted += 1
        return f"forgotten: {deleted} items deleted across {scope.person_id}"

    return [store_get, store_search, store_put, promote_guest, forget_guest]


def recall(store, person_id: str) -> MemoryRecall:
    """Deterministic §6.1 memory_recall fill: who is this person (§7.2)."""

    def texts(section: str) -> list[str]:
        namespace = ReadScope(person_id).person(section)
        return [i.value.get("text", "") for i in store.search(namespace, limit=RECALL_LIMIT)]

    return MemoryRecall(
        profile=texts("profile"),
        episodes=texts("episodes"),
        diagnoses=texts("diagnoses"),
        commitments=texts("commitments"),
    )


def make_temporal_agent(
    store,
    person_id: str,
    *,
    reflection_context: bool = False,
    model=None,
    summarizer_model=None,
    fallback_models=None,
):
    """The Temporal Lobe as a ``create_agent`` (fast tier, §20.2 row 2),
    carrying the standard middleware stack; prompt hot-loads from
    prompts/subagents/temporal.md via the stack's prompt_loader."""
    from arjun.harness.gateway import fast_chat_model

    tools = build_tools(store, ReadScope(person_id), reflection_context=reflection_context)
    return create_agent(
        model if model is not None else fast_chat_model(),
        tools=tools,
        middleware=standard_stack("temporal", summarizer_model=summarizer_model, fallback_models=fallback_models),
        name="temporal",
    )
