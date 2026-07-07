"""User profile store — JSON files per user."""
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Strict allowlist for user-name-derived filenames
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _sanitize_username(name: str) -> str:
    """Sanitize username for safe filesystem use.
    
    Only allows alphanumeric, underscore, hyphen.
    Prevents path traversal attacks.
    """
    sanitized = name.lower().strip()
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", sanitized)
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    
    if not sanitized or not _SAFE_NAME_RE.match(sanitized):
        raise ValueError(f"Invalid username after sanitization: '{name}'")
    
    return sanitized


class UserStore:
    """Per-user profile management via JSON files.
    
    Stores: name, recurring themes, preferred style, emotional history,
    conversation count, first/last seen timestamps.
    """

    def __init__(self, profiles_dir: str | Path = "data/users"):
        self._dir = Path(profiles_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"UserStore initialized at {self._dir}")

    def _profile_path(self, user_name: str) -> Path:
        """Get safe file path for user profile."""
        safe_name = _sanitize_username(user_name)
        path = (self._dir / f"{safe_name}.json").resolve()
        # Verify path is within profiles directory (prevent traversal)
        if not str(path).startswith(str(self._dir.resolve()) + "/"):
            raise ValueError(f"Path traversal detected for user: {user_name}")
        return path

    def user_exists(self, user_name: str) -> bool:
        """Check if user profile exists."""
        try:
            return self._profile_path(user_name).exists()
        except ValueError:
            return False

    def get_profile(self, user_name: str) -> dict[str, Any] | None:
        """Load user profile. Returns None if not found."""
        path = self._profile_path(user_name)
        if not path.exists():
            return None
        
        with open(path, "r") as f:
            profile = json.load(f)
        
        logger.info(f"Loaded profile for '{user_name}'")
        return profile

    def create_profile(self, user_name: str) -> dict[str, Any]:
        """Create new user profile."""
        now = datetime.now(timezone.utc).isoformat()
        profile = {
            "name": user_name,
            "first_seen": now,
            "last_seen": now,
            "recurring_themes": [],
            "preferred_style": None,
            "emotional_history": [],
            "conversation_count": 0,
            "last_topic": None,
        }
        self._save_profile(user_name, profile)
        logger.info(f"Created profile for '{user_name}'")
        return profile

    def update_profile(
        self,
        user_name: str,
        concepts: list[str] | None = None,
        emotional_state: str | None = None,
        preferred_style: str | None = None,
        last_topic: str | None = None,
    ) -> dict[str, Any]:
        """Update user profile with new conversation data."""
        profile = self.get_profile(user_name)
        if profile is None:
            profile = self.create_profile(user_name)

        now = datetime.now(timezone.utc).isoformat()
        profile["last_seen"] = now
        profile["conversation_count"] = profile.get("conversation_count", 0) + 1

        if last_topic:
            profile["last_topic"] = last_topic

        if concepts:
            existing = set(profile.get("recurring_themes", []))
            existing.update(concepts)
            profile["recurring_themes"] = sorted(existing)

        if emotional_state:
            history = profile.get("emotional_history", [])
            history.append({"date": now, "state": emotional_state})
            # Keep last 50 entries
            profile["emotional_history"] = history[-50:]

        if preferred_style:
            profile["preferred_style"] = preferred_style

        self._save_profile(user_name, profile)
        return profile

    def get_last_topic(self, user_name: str) -> str | None:
        """Get last discussed topic for returning user greeting."""
        profile = self.get_profile(user_name)
        if profile:
            return profile.get("last_topic")
        return None

    def _save_profile(self, user_name: str, profile: dict[str, Any]) -> None:
        """Save profile to disk."""
        path = self._profile_path(user_name)
        with open(path, "w") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
