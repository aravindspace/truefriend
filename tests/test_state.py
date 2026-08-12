"""P1.4 unit tests — graph state schema (§6.1)."""

import pytest
from pydantic import ValidationError

from arjun.graph import (
    GUT_BASELINE,
    Feeling,
    GunaBalance,
    GutRead,
    LimbicState,
    Person,
    initial_state,
)


class TestGunaBalance:
    def test_valid_sum_accepted(self):
        gb = GunaBalance(sattva=0.5, rajas=0.3, tamas=0.2)
        assert gb.sattva == 0.5

    def test_sum_above_one_rejected(self):
        with pytest.raises(ValidationError, match="sum to 1"):
            GunaBalance(sattva=0.8, rajas=0.5, tamas=0.2)

    def test_sum_below_one_rejected(self):
        with pytest.raises(ValidationError, match="sum to 1"):
            GunaBalance(sattva=0.1, rajas=0.1, tamas=0.1)

    def test_negative_component_rejected(self):
        with pytest.raises(ValidationError):
            GunaBalance(sattva=1.2, rajas=-0.3, tamas=0.1)

    def test_baseline_is_valid_and_sattvic(self):
        assert GUT_BASELINE.sattva > GUT_BASELINE.rajas > GUT_BASELINE.tamas


class TestDefaults:
    def test_initial_state_construction(self):
        state = initial_state(Person(id="guest_abc123"))
        assert state["messages"] == []
        assert state["retrieved"] == []
        assert state["world_context"] == []
        assert state["gut_read"] is None
        assert state["turn_plan"] is None
        assert state["memory_recall"] is None
        assert state["tier"] is None

    def test_self_harm_flag_defaults_false(self):
        state = initial_state(Person(id="guest_abc123"))
        assert state["self_harm_flag"] is False
        assert GutRead().self_harm_flag is False

    def test_limbic_defaults_to_gut_baseline(self):
        limbic = LimbicState()
        assert limbic.guna_balance == GUT_BASELINE
        assert limbic.active_feelings == []

    def test_baseline_copy_is_independent(self):
        a, b = LimbicState(), LimbicState()
        assert a.guna_balance is not b.guna_balance

    def test_person_defaults_to_unpromoted_guest(self):
        p = Person(id="guest_abc123")
        assert p.is_guest is True
        assert p.uniquename_set is False


class TestFeeling:
    def test_intensity_bounded(self):
        with pytest.raises(ValidationError):
            Feeling(name="compassion", intensity=1.5, cause="test")

    def test_valid_feeling(self):
        f = Feeling(name="compassion", intensity=0.8, cause="person's grief")
        assert f.intensity == 0.8
