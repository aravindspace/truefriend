"""P1.9 unit tests — Thyroid node, table-driven (§6.2 step 2, §9.2)."""

import pytest

from arjun.graph.state import GutRead, TierDecision
from arjun.harness.budgets import get_budget
from arjun.organs.thyroid import select_profile, thyroid

# (description, gut_read, expected_profile) — every combination the rules name.
TABLE = [
    ("benign greeting", GutRead(emotional_temperature=0.1), "small_talk"),
    ("perfectly cold turn", GutRead(emotional_temperature=0.0), "small_talk"),
    ("boundary temperature 0.2 still trivial", GutRead(emotional_temperature=0.2), "small_talk"),
    ("just past boundary resolves upward", GutRead(emotional_temperature=0.21), "counseling"),
    ("clear emotional signal", GutRead(emotional_temperature=0.6), "counseling"),
    ("problem domain with zero temperature", GutRead(problem_domain_guess=["career"]), "counseling"),
    ("self-harm flag alone", GutRead(self_harm_flag=True), "counseling"),
    (
        "self-harm flag with otherwise trivial read (floor lock)",
        GutRead(self_harm_flag=True, emotional_temperature=0.0),
        "counseling",
    ),
    ("injection attempt", GutRead(injection_attempt=True), "counseling"),
    ("off-mission request", GutRead(off_mission=True), "counseling"),
    ("no gut read at all (ambiguity)", None, "counseling"),
    (
        "everything at once stays locked",
        GutRead(self_harm_flag=True, injection_attempt=True, emotional_temperature=1.0),
        "counseling",
    ),
]


class TestSelectProfile:
    @pytest.mark.parametrize("desc,read,expected", TABLE, ids=[t[0] for t in TABLE])
    def test_table(self, desc, read, expected):
        assert select_profile(read) == expected

    def test_doubt_resolves_upward_is_the_default_shape(self):
        # Only ONE path leads to small_talk; every field's "bad" value alone
        # forces counseling — asserted field by field.
        upward_reads = [
            GutRead(self_harm_flag=True),
            GutRead(injection_attempt=True),
            GutRead(off_mission=True),
            GutRead(problem_domain_guess=["purpose"]),
            GutRead(emotional_temperature=0.3),
        ]
        for read in upward_reads:
            assert select_profile(read) == "counseling"


class TestThyroidNode:
    def test_writes_tier_decision_only(self):
        update = thyroid({"gut_read": GutRead(emotional_temperature=0.1)})
        assert set(update) == {"tier"}
        assert isinstance(update["tier"], TierDecision)

    def test_small_talk_budget_values_from_config(self):
        tier = thyroid({"gut_read": GutRead()})["tier"]
        assert tier == get_budget("small_talk")  # config is the ceiling — no invention
        assert tier.compose_tier == "fast"
        assert tier.recursion_limit == 8

    def test_counseling_budget_values_from_config(self):
        tier = thyroid({"gut_read": GutRead(self_harm_flag=True)})["tier"]
        assert tier == get_budget("counseling")
        assert tier.compose_tier == "voice"
        assert tier.recursion_limit == 25

    def test_missing_gut_read_key(self):
        assert thyroid({})["tier"].profile == "counseling"
