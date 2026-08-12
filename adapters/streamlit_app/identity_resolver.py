"""Identity Resolver — thin adapter shim over the Identity organ (§4).

All identity BRAIN logic (promotion, re-link, Uniquename recording, the
ask-directive) now lives in ``arjun/organs/identity.py`` (owner decision
2026-07-18). This adapter module keeps only what's genuinely adapter-level:
new guest ids, the lazy Session-End check, and mapping the organ's pure
``resolve_step`` onto the Streamlit session object. Swappable — a future
robot embodiment replaces this shim, the brain is untouched.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from arjun.graph.state import Person
from arjun.memory.namespaces import ReadScope
# Re-exported so the resolver's public surface (and existing callers/tests)
# stay stable while the logic itself lives in the Identity organ.
from arjun.organs.identity import (  # noqa: F401
    build_directive,
    names_matching,
    promote,
    record_uniquename,
    resolve,
    resolve_step,
)
from arjun.organs.reflection import distill_session
from arjun.organs.temporal import build_tools

#: §4 Session End — a fixed period of silence, checked lazily on next wake-up.
SESSION_SILENCE_MINUTES = 30


def new_guest_id() -> str:
    return f"guest_{uuid.uuid4().hex[:12]}"


def apply_gut_identity(store, state, gut) -> Optional[str]:
    """Run the Identity organ's ``resolve_step`` against the current session
    and write the outcome back onto the Streamlit ``state`` object. Returns a
    UI status string, or None if nothing changed."""
    if gut is None:
        return None
    person = Person(
        id=state.person_id,
        display_name=state.display_name or None,
        is_guest=state.person_id.startswith("guest_"),
        uniquename_set=state.uniquename_set,
    )
    new_person, new_pending, status = resolve_step(
        store, person, getattr(state, "pending_name", "") or "", gut
    )
    state.person_id = new_person.id
    state.display_name = new_person.display_name or ""
    state.uniquename_set = new_person.uniquename_set
    state.pending_name = new_pending
    return status


def session_expired(last_activity: Optional[datetime], now: Optional[datetime] = None) -> bool:
    if last_activity is None:
        return False
    now = now or datetime.now(timezone.utc)
    return now - last_activity >= timedelta(minutes=SESSION_SILENCE_MINUTES)


def end_session(store, person_id: str, messages, uniquename_set: bool) -> str:
    """Session End (§4): empty Uniquename slot → Forgetting; a completed
    Person Key → distillation into long-term memory (§7.3)."""
    if person_id.startswith("guest_") or not uniquename_set:
        belt = {t.name: t for t in build_tools(store, ReadScope(person_id))}
        return belt["forget_guest"].invoke({})
    distill_session(store, person_id, messages)
    return f"session distilled for {person_id}"


#: Ledger of already-distilled conversation threads (idempotency).
_DISTILLED_NS = ("arjun", "sessions")
_DISTILLED_KEY = "distilled_threads"


def _has_real_exchange(messages) -> bool:
    """At least one substantive human message — skip trivial 'hi' chats."""
    return any(
        getattr(m, "type", "") == "human" and isinstance(m.content, str) and len(m.content.strip()) > 15
        for m in (messages or [])
    )


def _load_done(store) -> set:
    ledger = store.get(_DISTILLED_NS, _DISTILLED_KEY)
    return set(ledger.value.get("ids", [])) if ledger else set()


def _save_done(store, done: set) -> None:
    # index=False → bookkeeping, never embedded (embedding it would load the
    # llama.cpp model and cost seconds on every ledger write).
    store.put(_DISTILLED_NS, _DISTILLED_KEY, {"ids": sorted(done)}, index=False)


def plan_distillation(brain, store, active_session_id: str) -> list[str]:
    """CHEAP scan (no LLM): which FINISHED conversations still need distilling?

    The web adapter can't reliably fire Session-End (a browser refresh wipes
    st.session_state), so we sweep the checkpointer — it already holds each
    conversation's transcript, and each thread's state carries its person.
    Threads that need no LLM work (guests, trivial chats, the live session) are
    marked done here, so the caller gets an accurate to-do list to show a
    progress bar against."""
    done = _load_done(store)
    todo: list[str] = []

    # Materialise the thread ids FIRST. Calling get_state() while the list()
    # cursor is still open issues nested queries on the same SQLite connection
    # and blocks indefinitely.
    thread_ids: list[str] = []
    seen = set()
    for ct in brain.checkpointer.list(None):
        tid = ct.config["configurable"]["thread_id"]
        if tid not in seen:
            seen.add(tid)
            thread_ids.append(tid)

    for tid in thread_ids:
        if tid == active_session_id or tid in done:
            continue  # live conversation, or already handled

        snap = brain.get_state({"configurable": {"thread_id": tid}})
        person = snap.values.get("person")
        pid = getattr(person, "id", "") if person is not None else ""
        if pid and not pid.startswith("guest_") and _has_real_exchange(snap.values.get("messages", [])):
            todo.append(tid)
        else:
            done.add(tid)  # nothing to distill — never look at it again

    _save_done(store, done)
    return todo


def distill_thread(brain, store, thread_id: str) -> bool:
    """Distill ONE finished conversation (one LLM call, ~20s on the reasoning
    model) and mark it done. Returns True if an episode was written."""
    try:
        snap = brain.get_state({"configurable": {"thread_id": thread_id}})
        person = snap.values.get("person")
        pid = getattr(person, "id", "") if person is not None else ""
        messages = snap.values.get("messages", [])
        if pid and not pid.startswith("guest_"):
            # session_key=thread_id → upserts, so re-distilling never duplicates.
            distill_session(store, pid, messages, session_key=thread_id)
            written = True
        else:
            written = False
    except Exception:
        written = False  # a bad thread must never break startup
    done = _load_done(store)
    done.add(thread_id)
    _save_done(store, done)
    return written


def distill_finished_sessions(brain, store, active_session_id: str) -> int:
    """Distill every finished conversation in one go (non-UI callers)."""
    return sum(distill_thread(brain, store, tid) for tid in plan_distillation(brain, store, active_session_id))


def distill_current_session(brain, store, person_id: str, session_id: str) -> bool:
    """Distill the LIVE conversation into long-term memory right now — called
    the moment a person becomes known (name + Uniquename set, or a re-link).

    This is the "store immediately" guarantee (owner decision 2026-07-18): the
    raw transcript is already safe in short-term (the checkpointer saves every
    turn), and this promotes it into long-term episodes without waiting for an
    unreliable browser Session-End. Idempotent via ``session_key``."""
    if not person_id or person_id.startswith("guest_"):
        return False
    snap = brain.get_state({"configurable": {"thread_id": session_id}})
    messages = snap.values.get("messages", [])
    if not _has_real_exchange(messages):
        return False
    try:
        distill_session(store, person_id, messages, session_key=session_id)
        return True
    except Exception:
        return False
