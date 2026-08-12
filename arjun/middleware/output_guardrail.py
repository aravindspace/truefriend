"""Output guardrail — §10 item 2, §9.2. Nothing leaves without passing:

  - deterministic layer (always runs, untrickable): chunk_id traceability,
    fiction-vocabulary blacklist, Helpline Rule, leakage tripwire;
  - LLM layer (fast tier, one call): structured pass/fail + reason —
    never rewrites (fails OPEN — the deterministic layer is the hard wall);
  - failure path: ONE re-compose with the violation named → safe fallback.

The ``OutputGuardrail`` middleware class (P1.7) serves subagent stacks; the
brain's checking node is ``make_output_guardrail(store)`` at the bottom.
"""

import logging
import re
from typing import Any, Callable, Optional

from langchain.agents.middleware import AgentMiddleware
from pydantic import BaseModel

logger = logging.getLogger("arjun.middleware")

#: Each layer receives (reply_text, state) and returns a violation reason
#: string, or None when the reply passes.
CheckFn = Callable[[str, dict], Optional[str]]


class OutputGuardrail(AgentMiddleware):
    """Checks the agent's final reply after the model call (§20.3 order:
    last in the stack ⇒ its after_model runs first, straight after the model)."""

    def __init__(
        self,
        deterministic: Optional[CheckFn] = None,
        llm_verdict: Optional[CheckFn] = None,
    ):
        super().__init__()
        self.deterministic = deterministic
        self.llm_verdict = llm_verdict

    def check(self, reply: str, state: dict) -> Optional[str]:
        """First violation found, or None. Deterministic layer always runs
        first — it cannot be tricked and it is free."""
        for layer in (self.deterministic, self.llm_verdict):
            if layer is None:
                continue
            violation = layer(reply, state)
            if violation:
                return violation
        return None

    def after_model(self, state, runtime) -> Optional[dict[str, Any]]:
        if self.deterministic is None and self.llm_verdict is None:
            return None  # subagent stacks run without layers by default
        messages = state.get("messages") or []
        last = messages[-1] if messages else None
        if last is None or getattr(last, "type", "") != "ai":
            return None
        violation = self.check(last.content if isinstance(last.content, str) else "", dict(state))
        if violation:
            logger.warning("output guardrail violation: %s", violation)
        return None


# =========================================================================
# P1.16 — the concrete layers (brain node; §20.1 output_guardrail)
# =========================================================================

_CHUNK_ID_RE = re.compile(r"\bchunk_\d{1,6}\b")
_FICTION_WORDS = re.compile(
    r"\b(character|story|stories|myth|mythical|legend|legendary|fictional|fable|tale)s?\b",
    re.IGNORECASE,
)
#: Historical-framing context: fiction words are violations only when a
#: sentence is about the Gita world (§1 framing).
_GITA_MARKERS = re.compile(
    r"\b(Gita|Kurukshetra|Krishna|Arjuna|Bhishma|Drona|Duryodhana|Pandava|Kaurava|"
    r"Yudhishthira|Bhima|Karna|Prahlada|Mahabharata|Kunti|Draupadi|Abhimanyu)\b",
    re.IGNORECASE,
)


def check_citations(reply: str, state: dict) -> Optional[str]:
    """Every cited chunk_id exists in Canon or arrived via retrieval this
    turn. (Notebook citations use ``notebook:*`` ids — different pattern,
    inherently framed as Arjun's own.)"""
    from arjun.retrieval.kuzu_templates import chunk_exists

    retrieved_ids = {c.chunk_id for c in state.get("retrieved") or []}
    for cited in set(_CHUNK_ID_RE.findall(reply)):
        if cited not in retrieved_ids and not chunk_exists(cited):
            return f"cited {cited} does not exist in Canon"
    return None


def check_fiction_vocabulary(reply: str, state: dict) -> Optional[str]:
    """No 'character/story/myth' talk about Gita personalities (§1, §10)."""
    for sentence in re.split(r"(?<=[.!?])\s+", reply):
        if _FICTION_WORDS.search(sentence) and _GITA_MARKERS.search(sentence):
            return f"fiction vocabulary about Gita personalities: {sentence.strip()[:120]!r}"
    return None


def check_helpline(reply: str, state: dict) -> Optional[str]:
    """Flagged turn ⇒ at least one verified helpline number present (§9.2)."""
    from arjun.organs.frontal import HELPLINE_NUMBERS

    if state.get("self_harm_flag") and not any(n in reply for n in HELPLINE_NUMBERS):
        return "self-harm flagged turn but no helpline number in the reply"
    return None


def known_identities(store, exclude_person_id: str) -> set[str]:
    """Other people's names + Uniquenames — the leakage tripwire wordlist.
    Structural backup on top of the ReadScope wall (§7.4)."""
    identities: set[str] = set()
    for namespace in store.list_namespaces(prefix=("people",)):
        person_id = namespace[1]
        if person_id == exclude_person_id:
            continue
        for key in ("name", "uniquename"):
            item = store.get(("people", person_id, "profile"), key)
            if item is not None:
                value = item.value.get("text", "")
                if ":" in value:
                    identities.add(value.split(":", 1)[1].strip().lower())
    return identities


def _own_identities(store, state) -> set[str]:
    """The current person's OWN name/Uniquename — never a leak, even if some
    OTHER person happens to share the same first name (§4: names are common;
    the structural ReadScope wall is the real privacy guarantee, this tripwire
    is only a backstop against a DIFFERENT person's details)."""
    own: set[str] = set()
    person = state.get("person")
    if person is not None and getattr(person, "display_name", None):
        own.add(person.display_name.strip().lower())
    gut = state.get("gut_read")
    if gut is not None:  # a name/word they claimed THIS turn is theirs
        for value in (getattr(gut, "shared_name", ""), getattr(gut, "chosen_uniquename", "")):
            if value:
                own.add(value.strip().lower())
    current_id = getattr(person, "id", "") if person is not None else ""
    if current_id and not current_id.startswith("guest_"):
        for key in ("name", "uniquename"):
            item = store.get(("people", current_id, "profile"), key)
            if item is not None:
                text = item.value.get("text", "")
                own.add((text.split(":", 1)[1] if ":" in text else text).strip().lower())
    return {v for v in own if v}


def make_leakage_check(store) -> CheckFn:
    def check_leakage(reply: str, state: dict) -> Optional[str]:
        person = state.get("person")
        current_id = getattr(person, "id", "") if person is not None else ""
        own = _own_identities(store, state)
        reply_words = set(re.findall(r"[^\W\d_]+", reply.lower()))
        for identity in known_identities(store, current_id):
            if identity in own:
                continue  # current person's own name — addressing them is fine
            if set(identity.split()) <= reply_words:
                return f"reply mentions another person's identity ({identity!r})"
        return None

    return check_leakage


class Verdict(BaseModel):
    passed: bool
    reason: str = ""


def llm_verdict(reply: str, state: dict) -> Optional[str]:
    """Fast tier, ONE call, pass/fail + reason — never rewrites. Fails OPEN:
    the deterministic layer above is the untrickable wall; a broken verdict
    call must not kill the turn (§5)."""
    from arjun.harness.gateway import complete
    from arjun.harness.retries import ask_structured

    def call(feedback):
        system = (
            "You review Arjun's reply. Arjun is a warm Indian friend and Gita "
            "scholar. A brief greeting, small talk, or simply listening is PERFECTLY "
            "in character — do NOT fail a reply for being short or not quoting the "
            "Gita; he offers scripture only when it fits. FAIL only if the reply "
            "(1) clearly abandons his warm, respectful persona (rude, robotic, or "
            "openly out of character), or (2) gives medical, legal, or financial "
            "prescriptions (dosages, drug names, legal/contract advice, investment "
            "picks). When in doubt, PASS. Verdict JSON only."
            + (f"\n\n{feedback}" if feedback else "")
        )
        return complete(
            "fast",
            [{"role": "system", "content": system}, {"role": "user", "content": reply}],
            response_format=Verdict,
        )

    verdict = ask_structured(call, Verdict, default=Verdict(passed=True))
    return None if verdict.passed else f"LLM verdict: {verdict.reason or 'failed'}"


def make_output_guardrail(store, recompose=None):
    """The brain's output_guardrail node (§20.1). ``recompose(state,
    violation) -> str`` defaults to a compose retry with the violation named;
    injectable for tests."""
    from langchain_core.messages import AIMessage

    from arjun.harness.fallbacks import HONEST_FALLBACK_REPLY

    leakage = make_leakage_check(store)
    deterministic_checks: list[CheckFn] = [
        check_citations,
        check_fiction_vocabulary,
        check_helpline,
        leakage,
    ]

    def run_deterministic(reply: str, state: dict) -> Optional[str]:
        for check in deterministic_checks:
            violation = check(reply, state)
            if violation:
                return violation
        return None

    def default_recompose(state: dict, violation: str) -> str:
        from arjun.organs.frontal import _conversation_messages, build_compose_prompt

        tier = state.get("tier")
        from arjun.harness.gateway import complete

        prompt = (
            build_compose_prompt(state)
            + f"\n\nYour previous reply was rejected: {violation}. "
            "Compose a corrected reply that fixes exactly this."
        )
        return complete(
            tier.compose_tier if tier else "voice",
            [{"role": "system", "content": prompt}, *_conversation_messages(state)],
            max_tokens=tier.max_tokens if tier else 4000,
        )

    recompose_fn = recompose or default_recompose

    def output_guardrail(state) -> dict:
        messages = state.get("messages") or []
        last = messages[-1] if messages else None
        if last is None or getattr(last, "type", "") != "ai":
            return {"messages": [AIMessage(content=HONEST_FALLBACK_REPLY)]}
        reply = last.content if isinstance(last.content, str) else ""

        violation = run_deterministic(reply, state) or llm_verdict(reply, state)
        if violation is None:
            return {}  # clean reply passes untouched

        logger.warning("output guardrail: %s — one re-compose", violation)
        try:
            second = recompose_fn(dict(state), violation)
        except Exception as exc:
            logger.error("re-compose failed (%s) — fallback", exc)
            second = ""
        if second and run_deterministic(second, state) is None:
            return {"messages": [AIMessage(content=second)]}
        logger.warning("re-compose still violating — safe fallback (§5)")
        return {"messages": [AIMessage(content=HONEST_FALLBACK_REPLY)]}

    return output_guardrail
