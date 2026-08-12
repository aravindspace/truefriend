"""§7.2 namespace layout + the structural privacy wall (§7.4).

The wall is construction, not convention: a ``ReadScope`` is built for ONE
person and can only ever express that person's namespaces plus ``arjun/*``.
There is no API on it that accepts another person id — person A's memories
are unreachable in person B's turn because B's scope cannot even name them.
"""

from dataclasses import dataclass

PERSON_SECTIONS = ("profile", "episodes", "diagnoses", "commitments")
SELF_SECTIONS = ("mood_history", "learnings", "observations")

Namespace = tuple[str, ...]


def _validated(section: str, allowed: tuple[str, ...]) -> str:
    if section not in allowed:
        raise ValueError(f"unknown section {section!r} — allowed: {allowed}")
    return section


@dataclass(frozen=True)
class ReadScope:
    """Everything the current turn may read: this person + arjun/*."""

    person_id: str

    def person(self, section: str) -> Namespace:
        """people/{person_id}/{profile|episodes|diagnoses|commitments}"""
        return ("people", self.person_id, _validated(section, PERSON_SECTIONS))

    def arjun_self(self, section: str) -> Namespace:
        """arjun/self/{mood_history|learnings|observations}"""
        return ("arjun", "self", _validated(section, SELF_SECTIONS))

    def world(self) -> Namespace:
        """arjun/world/facts — timestamped, sourced, expiring web facts."""
        return ("arjun", "world", "facts")

    def all_namespaces(self) -> tuple[Namespace, ...]:
        """Every namespace this scope can express — the wall, enumerated."""
        return (
            *(self.person(s) for s in PERSON_SECTIONS),
            *(self.arjun_self(s) for s in SELF_SECTIONS),
            self.world(),
        )

    def allows(self, namespace: Namespace) -> bool:
        """True iff a namespace lies inside the wall (leakage tripwire helper)."""
        return tuple(namespace) in self.all_namespaces()
