"""Thyroid — §6.2 step 2: deterministic tier/budget selection. NO LLM.

Pure function from the Gut read to a named profile declared in
config/models.yaml. Config tiers are each agent's default AND maximum —
the Thyroid may only downgrade for a turn, never upgrade past config, so
cost stays capped by a readable file (§14).

Quality floor (§9.2): downgrade ONLY on a high-confidence trivial read;
any emotional signal, problem domain, flag, or ambiguity → counseling.
Doubt resolves upward.
"""

from typing import Optional

from arjun.graph.state import GutRead
from arjun.harness.budgets import get_budget

#: A turn is "trivial" only at or below this emotional temperature.
TRIVIAL_MAX_TEMPERATURE = 0.2


def select_profile(read: Optional[GutRead]) -> str:
    """Named profile for this turn. Every rule here downgrades or holds —
    nothing upgrades past config."""
    if read is None:
        return "counseling"  # no Gut read = ambiguity → upward
    if read.self_harm_flag:
        return "counseling"  # §9.2 floor lock — no exceptions, checked first
    if read.problem_domain_guess:
        return "counseling"  # a detected problem is never small talk
    if read.emotional_temperature > TRIVIAL_MAX_TEMPERATURE:
        return "counseling"  # any emotional signal → upward
    if read.injection_attempt or read.off_mission:
        return "counseling"  # declines are composed with full care
    return "small_talk"  # high-confidence trivial turn — the only downgrade


def thyroid(state) -> dict:
    """Graph node: writes the §6.1 ``tier`` decision into state. Nothing else."""
    return {"tier": get_budget(select_profile(state.get("gut_read")))}
