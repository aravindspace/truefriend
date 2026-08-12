"""Identity organ — §4: the ONE home for guest → promotion → re-link →
forgetting, plus the in-conversation asks for name and Uniquename.

Consolidated here (owner decision 2026-07-18) so the Frontal Lobe only
COMPOSES: it reads a ready ``identity_directive`` from state, never computes
one. All identity logic — the directive AND the store resolution — lives in
this module; the adapter and the graph node both call in here.

Deterministic (no LLM). Store mutations (promotion / re-link / record) are
the §20.4-2 mid-turn identity write exception, routed through the Temporal
Lobe's identity tools.
"""

from typing import Optional

from arjun.graph.state import GutRead, Person
from arjun.memory.namespaces import ReadScope
from arjun.organs.temporal import build_tools

CALM_TEMPERATURE_MAX = 0.3  # §4: ask the name only at a calm moment


# --------------------------------------------------------------------------
# Store primitives (moved from the adapter's identity_resolver)
# --------------------------------------------------------------------------

def _profile_value(store, person_id: str, key: str) -> str:
    item = store.get(("people", person_id, "profile"), key)
    if item is None:
        return ""
    value = item.value.get("text", "")
    return (value.split(":", 1)[1] if ":" in value else value).strip().lower()


def names_matching(store, name: str) -> list[str]:
    """Person ids whose stored name equals ``name`` (case-insensitive)."""
    wanted = name.strip().lower()
    return [
        ns[1]
        for ns in store.list_namespaces(prefix=("people",))
        if _profile_value(store, ns[1], "name") == wanted
    ]


def resolve(store, name: str, uniquename: str) -> Optional[str]:
    """Re-linking (§4): name + Uniquename → person id, or None. Never guessed,
    never merged."""
    wanted_name, wanted_unique = name.strip().lower(), uniquename.strip().lower()
    if not wanted_name or not wanted_unique:
        return None
    for ns in store.list_namespaces(prefix=("people",)):
        pid = ns[1]
        if _profile_value(store, pid, "name") == wanted_name and _profile_value(store, pid, "uniquename") == wanted_unique:
            return pid
    return None


def promote(store, guest_id: str, name: str, uniquename: str = "") -> Optional[str]:
    """Guest → durable person namespace via temporal's identity tool (§4)."""
    belt = {t.name: t for t in build_tools(store, ReadScope(guest_id))}
    result = belt["promote_guest"].invoke({"name": name, "uniquename": uniquename})
    if result.startswith("REFUSED"):
        return None
    return result.split("promoted to ", 1)[1].split(" ", 1)[0]


def record_uniquename(store, person_id: str, uniquename: str) -> None:
    store.put(("people", person_id, "profile"), "uniquename", {"text": f"Uniquename: {uniquename.strip()}"})


# --------------------------------------------------------------------------
# Resolution — the two-step guest/promotion/re-link decision (pure)
# --------------------------------------------------------------------------

def resolve_step(store, person: Person, pending: str, gut: GutRead) -> tuple[Person, str, Optional[str]]:
    """Act on what the person SAID this turn. Returns (new person, new pending
    name, status | None). A single word looks like both a name and a
    Uniquename, so while awaiting a Uniquename any offered word IS it."""
    name = (gut.shared_name or "").strip()
    unique = (gut.chosen_uniquename or "").strip()
    offered = unique or name

    if person.is_guest:
        if pending and offered:  # waiting for the word → resolve or fork
            found = resolve(store, pending, offered)
            if found:
                return Person(id=found, display_name=pending, is_guest=False, uniquename_set=True), "", f"re-linked to {found} — loading past memory"
            new_id = promote(store, person.id, pending, uniquename=offered)
            return Person(id=new_id, display_name=pending, is_guest=False, uniquename_set=True), "", f"no earlier match — fresh profile {new_id}"

        if name and unique:  # both in one message
            found = resolve(store, name, unique)
            if found:
                return Person(id=found, display_name=name, is_guest=False, uniquename_set=True), "", f"re-linked to {found} — loading past memory"
            new_id = promote(store, person.id, name, uniquename=unique)
            return Person(id=new_id, display_name=name, is_guest=False, uniquename_set=True), "", f"no earlier match — fresh profile {new_id}"

        if name:  # only a name → hold if it might be someone returning
            if names_matching(store, name):
                return person, name, f"'{name}' may be returning — awaiting Uniquename to confirm"
            new_id = promote(store, person.id, name)
            return Person(id=new_id, display_name=name, is_guest=False, uniquename_set=False), "", f"promoted to {new_id} — awaiting Uniquename"
        return person, pending, None

    # Named person, no key yet → complete it with any offered word (not a repeat of the name).
    if not person.uniquename_set and offered and offered.lower() != (person.display_name or "").lower():
        record_uniquename(store, person.id, offered)
        return person.model_copy(update={"uniquename_set": True}), "", "Person Key complete"
    return person, pending, None


# --------------------------------------------------------------------------
# Directive — what to tell Arjun to ask (read by frontal_compose)
# --------------------------------------------------------------------------

def build_directive(person: Optional[Person], gut: GutRead) -> str:
    """The identity guidance string frontal_compose injects verbatim. Empty
    when there's nothing to do."""
    if person is None or gut.self_harm_flag:
        return ""  # never steer identity during a crisis
    header = "## Identity (gentle, in conversation)\n"

    if gut.shared_name:  # just gave name → greet + ask the Uniquename now
        return (
            header
            + f"The person just shared their name: {gut.shared_name}. Warmly greet "
            "them by name. Then, since a name alone isn't enough to be sure it's "
            "them, gently ask them for a special personal word — their Uniquename "
            "(any word they love). Say in one breath that this word lets you "
            "recognize them and reopen your past conversations if you've spoken "
            "before. One warm, optional sentence — never a demand."
        )
    if gut.chosen_uniquename:
        return (
            header
            + "The person just shared their special word (Uniquename). Warmly "
            "acknowledge it and let them know you'll remember them by it."
        )

    calm = gut.emotional_temperature <= CALM_TEMPERATURE_MAX
    if not calm:
        return ""
    if person.is_guest:
        return (
            header
            + "You still don't know this person's name, and this is a calm moment. "
            "Look at the conversation so far. If you have NOT yet asked their name, "
            "warmly ask it now, as a friend naturally would — one short, kind "
            "question (e.g. 'by the way, may I know your name?'). If you already "
            "asked and they moved past it, you may gently ask once more at this "
            "pause — then let it rest. Never nag, never demand; it is always fine "
            "if they'd rather not say."
        )
    if not person.uniquename_set:
        return (
            header
            + f"You know them as {person.display_name or 'a friend'}, but they have "
            "no Uniquename yet. If you have not yet invited one, do so now: ask them "
            "to choose a single personal word so you can recognize them for certain "
            "when they return. One warm sentence; if they decline, accept gracefully."
        )
    return ""


def make_identity_node():
    """§20.1 graph node (no tools): compute the identity directive for the
    Frontal Lobe. The store resolution (promotion / re-link / record) runs
    post-turn in the adapter via ``resolve_step`` — the checkpointer thread is
    conversation-scoped, and person id is adapter-session state (§4). Keeping
    the node side-effect-free keeps the graph replayable."""

    def identity(state) -> dict:
        return {
            "identity_directive": build_directive(
                state.get("person"), state.get("gut_read") or GutRead()
            )
        }

    return identity
