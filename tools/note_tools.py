"""Study notes tools — search markdown knowledge files.

Used by the Scholar agent to read pre-written study notes
from the knowledge/notes directory.
"""
import logging
from pathlib import Path
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_NOTES_DIR = Path(__file__).parent.parent / "knowledge" / "notes"


@tool
def search_study_notes(keywords: str) -> str:
    """Search study notes for Gita insights matching the given keywords.

    Study notes are markdown files containing detailed concept explanations,
    real-world examples, and practical applications of Gita teachings.

    Args:
        keywords: Space-separated keywords to match against note filenames
            (e.g. 'karma yoga detachment')
    """
    if not _NOTES_DIR.exists():
        return "No study notes directory found."

    terms = [t.strip().lower() for t in keywords.split() if len(t.strip()) > 2]
    if not terms:
        return "Please provide meaningful keywords (at least 3 characters each)."

    matched_notes = []
    for md_file in _NOTES_DIR.glob("*.md"):
        fname = md_file.stem.lower()
        if any(term in fname for term in terms):
            content = md_file.read_text()
            # Truncate very long notes to avoid token overflow
            if len(content) > 3000:
                content = content[:3000] + "\n...(truncated)"
            matched_notes.append(f"--- {md_file.stem} ---\n{content}")

    if not matched_notes:
        # List available notes so the agent can try different keywords
        available = [f.stem for f in _NOTES_DIR.glob("*.md")]
        if available:
            return f"No notes matched '{keywords}'. Available notes: {', '.join(available)}"
        return "No study notes available."

    return "\n\n".join(matched_notes)
