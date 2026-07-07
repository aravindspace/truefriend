"""User management tools — for the Supervisor ReAct agent.

Wraps UserStore methods so the Supervisor can save and look up
user profiles during natural conversation.
"""
import logging
from langchain_core.tools import tool

from stores import UserStore

logger = logging.getLogger(__name__)


@tool
def save_user_name(name: str) -> str:
    """Save the user's name and create or load their profile.

    Call this tool when the user tells you their name during conversation.
    Returns the user's profile summary — if they're a returning user,
    you'll see their past topics and preferences.

    Args:
        name: The user's name as they provided it (e.g. 'Aravind')
    """
    if not name or not name.strip():
        return "No name provided. Ask the user for their name."

    name = name.strip()

    try:
        user_store = UserStore()

        if user_store.user_exists(name):
            profile = user_store.get_profile(name)
            parts = [f"Welcome back, {name}! (returning user)"]
            if profile:
                if profile.get("last_topic"):
                    parts.append(f"Last topic discussed: {profile['last_topic']}")
                if profile.get("recurring_themes"):
                    parts.append(
                        f"Recurring themes: {', '.join(profile['recurring_themes'])}"
                    )
                if profile.get("preferred_style"):
                    parts.append(
                        f"Preferred style: {profile['preferred_style']}"
                    )
                count = profile.get("conversation_count", 0)
                parts.append(f"Past conversations: {count}")
            return "\n".join(parts)
        else:
            user_store.create_profile(name)
            return f"New user '{name}' — profile created. This is their first visit."

    except ValueError as e:
        logger.warning(f"Invalid user name '{name}': {e}")
        return f"Could not save name: {e}"
    except Exception as e:
        logger.warning(f"User profile operation failed: {e}")
        return f"Profile save failed: {e}"


@tool
def lookup_user_profile(name: str) -> str:
    """Look up an existing user's profile to get context about them.

    Use this tool when you want to check if a user has talked to you
    before and what topics or themes they've discussed.

    Args:
        name: The user's name to look up
    """
    if not name or not name.strip():
        return "No name provided."

    name = name.strip()

    try:
        user_store = UserStore()

        if not user_store.user_exists(name):
            return f"No profile found for '{name}'. They are a new user."

        profile = user_store.get_profile(name)
        if not profile:
            return f"Profile exists for '{name}' but is empty."

        parts = [f"Profile for {name}:"]
        parts.append(f"  First seen: {profile.get('first_seen', 'unknown')}")
        parts.append(f"  Last seen: {profile.get('last_seen', 'unknown')}")
        parts.append(
            f"  Conversations: {profile.get('conversation_count', 0)}"
        )

        if profile.get("last_topic"):
            parts.append(f"  Last topic: {profile['last_topic']}")
        if profile.get("recurring_themes"):
            parts.append(
                f"  Themes: {', '.join(profile['recurring_themes'])}"
            )
        if profile.get("preferred_style"):
            parts.append(f"  Preferred style: {profile['preferred_style']}")
        if profile.get("emotional_history"):
            recent = profile["emotional_history"][-3:]
            emotions = [e.get("state", "?") for e in recent]
            parts.append(f"  Recent emotions: {', '.join(emotions)}")

        return "\n".join(parts)

    except ValueError as e:
        logger.warning(f"Invalid user name '{name}': {e}")
        return f"Lookup failed: {e}"
    except Exception as e:
        logger.warning(f"User profile lookup failed: {e}")
        return f"Lookup failed: {e}"
