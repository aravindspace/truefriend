"""Per-turn budgets from config/models.yaml — §5 (budgets), §6.2 step 2.

The named profiles (small_talk, counseling) are the Thyroid's vocabulary;
the harness enforces them. Config is the ceiling — nothing here upgrades.
"""

from functools import lru_cache
from pathlib import Path

import yaml

from arjun.graph.state import TierDecision

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "models.yaml"


@lru_cache(maxsize=1)
def _config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def profile_names() -> list[str]:
    return list(_config()["profiles"])


def get_budget(profile: str) -> TierDecision:
    """The §6.1 ``tier`` object for a named profile. KeyError on unknown name."""
    spec = _config()["profiles"][profile]
    return TierDecision(
        profile=profile,
        compose_tier=spec["compose_tier"],
        max_tokens=spec["max_tokens"],
        max_tool_calls_per_subagent=spec["max_tool_calls_per_subagent"],
        recursion_limit=spec["recursion_limit"],
    )


def agent_tier(agent_name: str) -> str:
    """Which tier alias an agent calls through (§14 ``agents:`` map)."""
    return _config()["agents"][agent_name]


def tier_primary(tier_name: str) -> str:
    """A tier's primary deployment string, e.g. ``groq/openai/gpt-oss-120b``."""
    return _config()["tiers"][tier_name]["primary"]
