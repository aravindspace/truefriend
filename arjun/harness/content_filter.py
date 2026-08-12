"""Deterministic content-filter mitigation (§5 — owner decision 2026-07-21).

A provider's safety filter (chiefly Azure's, on dense battlefield Canon or a
person's self-harm words) must never kill a turn. Rather than depend on other
providers (whose quotas run dry), the gateway handles a content-policy rejection
with a deterministic ladder — verified empirically, not assumed:

  1. RETRY the same call once. Azure's filter is *intermittent* at the medium-
     severity boundary where our self-harm / battlefield prompts sit (the same
     prompt filters on one call, passes on the next) — a plain retry often clears it.
  2. SANITIZE + retry. Softening the heaviest violence words lowers the aggregate
     severity below the filter threshold (a sanitized compose prompt passes where
     the raw one filtered). Only the displayed quote softens — the chunk_id is
     unchanged, so traceability (§10) still holds.
  3. Give up gracefully. For a plain (structured) call the gateway returns "" so
     the caller degrades to its safe default; for compose it raises
     ``ContentFilterBlocked`` so frontal_compose can voice a tailored safe reply
     (helpline for self-harm, firm decline for off-mission) built WITHOUT the
     triggering text.

Empirical note (2026-07-21): single words ("kill", "suicide") and lone sentences
do NOT trip the filter — Azure scores aggregate contextual severity, so the real
trigger is ~40 dense battlefield/self-harm chunks in one compose prompt. The
category in the error (self_harm vs violence) tells us which branch we are in.
"""

import re

VIOLENCE_CATS = frozenset({"violence", "hate", "sexual"})

#: Heaviest violence words in the battlefield Canon → gentler, meaning-adjacent
#: forms. Applied ONLY on a filter hit, as a severity-reducer of last resort;
#: the chunk_id is preserved so the citation still traces to Canon (§10).
SAFE_SUBSTITUTIONS = {
    "kill": "strike down",
    "kills": "strikes down",
    "killing": "striking down",
    "killed": "struck down",
    "slay": "vanquish",
    "slays": "vanquishes",
    "slaying": "vanquishing",
    "slain": "vanquished",
    "slaughter": "devastation",
    "slaughtered": "devastated",
    "murder": "unlawful killing",
    "murdered": "unlawfully killed",
    "bloodshed": "carnage",
    "corpse": "fallen body",
    "corpses": "fallen bodies",
    "suicide": "self-harm crisis",
}

_SUB_RE = re.compile(r"\b(" + "|".join(SAFE_SUBSTITUTIONS) + r")\b", re.IGNORECASE)
_CATEGORY_RE = re.compile(
    r'"(hate|violence|sexual|self_harm)"\s*:\s*\{[^}]*?"filtered"\s*:\s*true', re.IGNORECASE
)


class ContentFilterBlocked(Exception):
    """Raised to a caller that opted in (``raise_on_filter=True``) when the
    mitigation ladder could not recover a filtered turn. Carries the filtered
    categories and the stage (input prompt vs output completion)."""

    def __init__(self, categories, stage: str = "input"):
        self.categories = set(categories) or {"unknown"}
        self.stage = stage
        super().__init__(f"content filter blocked ({stage}): {sorted(self.categories)}")


def filtered_categories(exc) -> set[str]:
    """The Azure harm categories that were filtered, from the structured
    provider fields if present, else parsed from the error message."""
    cats: set[str] = set()
    fields = getattr(exc, "provider_specific_fields", None)
    if isinstance(fields, dict):
        result = (fields.get("innererror") or {}).get("content_filter_result")
        if isinstance(result, dict):
            cats = {
                name for name, info in result.items()
                if isinstance(info, dict) and info.get("filtered")
            }
    if not cats:
        cats = {m.lower() for m in _CATEGORY_RE.findall(str(getattr(exc, "message", exc)))}
    return cats


def sanitize(text: str) -> str:
    """Soften the heaviest violence words, preserving leading-capital case."""
    def _repl(match: re.Match) -> str:
        word = match.group(0)
        sub = SAFE_SUBSTITUTIONS[word.lower()]
        return sub[0].upper() + sub[1:] if word[:1].isupper() else sub

    return _SUB_RE.sub(_repl, text)


def sanitize_messages(messages: list[dict]) -> list[dict]:
    """Apply :func:`sanitize` to every string message content."""
    return [
        {**m, "content": sanitize(m["content"])} if isinstance(m.get("content"), str) else m
        for m in messages
    ]
