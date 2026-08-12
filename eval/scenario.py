"""P1.21 — golden scenario schema + loader (§15 layer 1).

A scenario is one message through the full brain plus declared expectations.
Files in ``eval/golden/*.yaml`` each hold a list of scenarios; ids must be
globally unique (they key the resume checkpoint and the report).
"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


class SeededPerson(BaseModel):
    """A person pre-written into long-term memory before the turn runs —
    privacy probes assert none of this ever reaches another person's reply."""

    person_id: str  # e.g. "ravi_evalseed01" (people/{id}/ namespaces)
    name: str
    uniquename: str
    episode: str  # the private content that must never leak


class Expected(BaseModel):
    """Deterministic expectations — every set field is asserted (§15)."""

    profile: Optional[str] = None  # small_talk | counseling (Thyroid)
    anarthas: list[str] = Field(default_factory=list)  # ⊆ routing readings
    self_harm: Optional[bool] = None  # the Gut's flag


class Scenario(BaseModel):
    id: str
    category: str
    message: str
    seed_other_person: Optional[SeededPerson] = None
    expected: Expected = Field(default_factory=Expected)
    required: list[str] = Field(default_factory=list)  # behavior checks that must PASS
    forbidden: list[str] = Field(default_factory=list)  # behavior checks that must NOT fire
    allow_fallback: bool = False  # privacy probes: the safe fallback is a valid outcome
    judge_focus: Optional[str] = None  # extra context handed to the LLM judge


def load_scenarios(directory: Path = GOLDEN_DIR) -> list[Scenario]:
    scenarios: list[Scenario] = []
    for path in sorted(directory.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        for item in raw:
            scenarios.append(Scenario(**item))
    ids = [s.id for s in scenarios]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"duplicate scenario ids: {duplicates}")
    return scenarios
