"""Routing JSON lookup — §8.2 step 1: narrow. In-memory, zero cost.

Loads routing/ministructure.json once (read-only canon master; inherently
safe to read in place).
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

ROUTING_PATH = Path(__file__).resolve().parents[2] / "routing" / "ministructure.json"


class RoutingInfo(BaseModel):
    problem_domain: str
    anartha: str
    guna: str
    section: int
    incident_chunk_ids: list[str]


@lru_cache(maxsize=1)
def _routing() -> dict:
    with open(ROUTING_PATH) as f:
        return json.load(f)


def routing_lookup(problem_domain: str) -> Optional[RoutingInfo]:
    """problem_domain → anartha + guna + section + canonical incident
    chunk_ids. Unknown domain → None (the ladder descends, §5)."""
    entry = _routing()["routing_table"].get(problem_domain.strip().lower())
    if entry is None:
        return None
    return RoutingInfo(
        problem_domain=problem_domain.strip().lower(),
        anartha=entry["anartha"],
        guna=entry["guna"],
        section=entry["section"],
        incident_chunk_ids=_routing()["anartha_canonical_incidents"].get(entry["anartha"], []),
    )


def known_domains() -> list[str]:
    return list(_routing()["routing_table"])


def analogy_fallback(yoga: str) -> list[str]:
    """Top analogy chunk_ids per Yoga path — used when graph traversal misses."""
    return _routing()["yoga_analogies_fallback"].get(yoga, [])
