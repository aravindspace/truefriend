"""Streamlit chat adapter — §3 (thin transport) + §4 (identity flow).

Run:  streamlit run adapters/streamlit_app/app.py

The adapter owns: the browser transcript, the identity panel, the lazy
Session-End check. The brain owns everything else — this file never
touches Canon, prompts, or memory directly (identity ops go through the
resolver, which uses temporal's tools).
"""

import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

# Show graph scholar and subagent activity in the terminal (owner debug, 2026-08-09).
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adapters.streamlit_app import identity_resolver as ids
from arjun.graph.build import build_brain
from arjun.harness.runner import TurnRequest, run_turn
from arjun.memory.stores import make_store


@st.cache_resource
def boot():
    """One brain + one store per server process (§4 single-human)."""
    store = make_store()
    return build_brain(store=store), store


def fresh_session(state) -> None:
    import uuid

    state.person_id = ids.new_guest_id()
    # Conversation-scoped thread id — stable across a promotion so history
    # survives (§4). Unique per browser session.
    state.session_id = f"conv_{uuid.uuid4().hex[:12]}"
    state.transcript = []
    state.last_activity = None
    state.uniquename_set = False
    state.display_name = ""
    state.pending_name = ""  # a name shared but awaiting Uniquename to re-link/fork
    state.last_temperature = 0.0
    state.last_self_harm = False


def lazy_session_end_check(state, store) -> None:
    """§4: 30 min of silence, checked on next wake-up — may run late,
    always runs. Empty Uniquename slot → Forgetting."""
    if state.last_activity and ids.session_expired(state.last_activity):
        outcome = ids.end_session(
            store, state.person_id, [], uniquename_set=state.uniquename_set
        )
        st.toast(f"Previous session ended: {outcome}")
        fresh_session(state)


def identity_panel(state) -> None:
    """Display only (§4, owner decision 2026-07-17): Arjun asks for name and
    Uniquename IN CONVERSATION. Nothing to type here — this just shows who
    the brain currently thinks it is talking to."""
    with st.sidebar:
        st.subheader("Who Arjun is talking to")
        st.caption(f"id: `{state.person_id}`")
        if state.person_id.startswith("guest_"):
            st.write("🕊️ **Guest** — Arjun will ask their name if a calm moment comes.")
        else:
            st.write(f"🙏 **{state.display_name or 'known person'}**")
            st.write("Uniquename: " + ("✅ set" if state.uniquename_set else "⏳ not yet"))
        st.caption("Names are shared in conversation, never typed here.")


#: Rough seconds per conversation on the reasoning model — refined live.
_SECONDS_PER_CONVERSATION = 20.0


def _eta_text(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds}s" if seconds < 60 else f"{seconds // 60}m {seconds % 60}s"


def run_startup_distillation(brain, store, state) -> bool:
    """One-time startup: fold past conversations into long-term memory, showing
    status + progress + remaining time, with the chat input DISABLED until it
    finishes. Returns True while still working (caller should stop rendering)."""
    todo = state.get("startup_todo")
    if todo is None:  # first pass: cheap scan, no LLM calls
        with st.spinner("Checking Arjun's memory…"):
            todo = ids.plan_distillation(brain, store, state.session_id)
        state.startup_todo = todo
        state.startup_total = len(todo)
        state.startup_secs = _SECONDS_PER_CONVERSATION

    if not todo:
        state.startup_done = True
        return False  # nothing to do — chat normally

    total = state.startup_total
    done_count = total - len(todo)
    st.info(
        f"🪷 Arjun is recalling his past conversations — **{done_count}/{total}** done. "
        f"About **{_eta_text(len(todo) * state.startup_secs)}** left. "
        "You can start chatting as soon as this finishes."
    )
    st.progress(done_count / total if total else 1.0)
    st.chat_input("Please wait — Arjun is recalling…", disabled=True)

    # Distill exactly ONE conversation per rerun, so the page stays responsive
    # and the progress/ETA visibly advances.
    started = time.time()
    ids.distill_thread(brain, store, todo[0])
    elapsed = time.time() - started
    state.startup_secs = (state.startup_secs + elapsed) / 2  # smooth the estimate
    state.startup_todo = todo[1:]

    if not state.startup_todo:
        state.startup_done = True
        st.success("✅ Memory ready — Arjun remembers your past conversations.")
    st.rerun()
    return True


def main() -> None:
    st.set_page_config(page_title="Arjun — TrueFriend", page_icon="🪷")
    state = st.session_state
    brain, store = boot()

    if "person_id" not in state:
        fresh_session(state)
    lazy_session_end_check(state, store)
    identity_panel(state)

    st.title("🪷 Arjun")

    # Continuity startup (§7.3): distill FINISHED conversations into episodes so a
    # returning person's past is recalled. This costs one LLM call per past
    # conversation (~20s on the reasoning model), so it runs ONCE with a visible
    # progress bar and the chat disabled — never silently blocking the UI.
    if not state.get("startup_done") and run_startup_distillation(brain, store, state):
        return  # still working — the rerun below re-enters here

    for role, text in state.transcript:
        st.chat_message(role).write(text)

    if prompt := st.chat_input("Speak to Arjun…"):
        state.transcript.append(("user", prompt))
        st.chat_message("user").write(prompt)
        thread = state.session_id  # conversation-scoped; survives promotion
        try:
            with st.spinner("Arjun is listening…"):
                reply = run_turn(
                    TurnRequest(
                        person_or_guest=state.person_id,
                        message=prompt,
                        uniquename_set=state.uniquename_set,
                        # pending_name carries a just-claimed (not-yet-resolved)
                        # name so the brain knows it's THEIRS (no leakage block).
                        display_name=state.display_name or state.pending_name or None,
                    ),
                    brain,
                    session=state.session_id,
                    step_timeout=180,
                )
        except RuntimeError as exc:  # §4 single-live-conversation assertion
            st.warning(str(exc))
            return
        state.transcript.append(("assistant", reply))
        st.chat_message("assistant").write(reply)
        state.last_activity = datetime.now(timezone.utc)

        # §4 conversational identity: act on what the person said this turn
        # (read from the checkpointed gut_read); promotion/Uniquename here.
        snapshot = brain.get_state({"configurable": {"thread_id": thread}})
        gut = (snapshot.values or {}).get("gut_read")
        if gut is not None:
            state.last_temperature = gut.emotional_temperature
            state.last_self_harm = gut.self_harm_flag
            was_keyed, was_person = state.uniquename_set, state.person_id
            status = ids.apply_gut_identity(store, state, gut)

            # "Store immediately" (owner decision 2026-07-18): the moment this
            # person becomes known — Uniquename just set, or re-linked to an
            # existing profile — promote the live conversation from short-term
            # into long-term episodes. Idempotent; the background sweep later
            # folds in anything said afterwards.
            newly_keyed = state.uniquename_set and not was_keyed
            relinked = state.person_id != was_person and not state.person_id.startswith("guest_")
            if newly_keyed or relinked:
                with st.spinner("Saving our conversation to memory…"):
                    ids.distill_current_session(brain, store, state.person_id, thread)

            if status:
                st.toast(status)


if __name__ == "__main__":
    main()
