"""The two SQLite stores — §7.1 (short-term) + §7.2 (long-term).

Both files live in arjun_action/memory/ (inside the write boundary,
ADR 0004). WAL is enabled on both connections (§11 belt-and-braces).
"""

import sqlite3
from pathlib import Path
from typing import Callable, Optional

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.sqlite import SqliteStore

from arjun.graph.state import STATE_MSGPACK_ALLOWLIST
from arjun.memory.embeddings import DIMS, embed_texts

MEMORY_DIR = Path(__file__).resolve().parents[2] / "arjun_action" / "memory"
SHORT_TERM_DB = MEMORY_DIR / "short_term_history.db"
LONG_TERM_DB = MEMORY_DIR / "long_term_store.db"


def thread_id(person_id: str, session: str) -> str:
    """§7.1 — checkpointer thread id = ``{person_id}:{session}``."""
    return f"{person_id}:{session}"


def _connect(path: Path, *, autocommit: bool) -> sqlite3.Connection:
    # isolation_level mirrors each class's own from_conn_string factory:
    # SqliteStore requires autocommit (it issues explicit BEGIN internally);
    # SqliteSaver manages transactions itself on a default connection.
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(path),
        check_same_thread=False,
        isolation_level=None if autocommit else "",
    )
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def make_checkpointer(path: Optional[Path] = None) -> SqliteSaver:
    """Short-term memory: thread-scoped conversation checkpoints (§7.1).

    Serde allow-lists exactly our state models (§5 checkpoint security) —
    with LANGGRAPH_STRICT_MSGPACK=true anything else is blocked."""
    saver = SqliteSaver(
        _connect(path or SHORT_TERM_DB, autocommit=False),
        serde=JsonPlusSerializer(allowed_msgpack_modules=list(STATE_MSGPACK_ALLOWLIST)),
    )
    saver.setup()
    return saver


def make_store(path: Optional[Path] = None, embed: Optional[Callable] = None) -> SqliteStore:
    """Long-term memory: cross-thread store with semantic search (§7.2)."""
    store = SqliteStore(
        _connect(path or LONG_TERM_DB, autocommit=True),
        index={"dims": DIMS, "embed": embed or embed_texts},
    )
    store.setup()
    return store
