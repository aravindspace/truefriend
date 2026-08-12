#!/usr/bin/env python3
"""P1.1 preflight — dev tooling, outside the write boundary (ADR 0004 exempt).

Checks the machine and repo are provably ready for Phase 1:
  - unprivileged user namespaces available (needed for Phase 3 bwrap)
  - bwrap --version runs
  - SQLite WAL mode can be enabled
  - graphdb/ master readable (Kuzu opens it read-only)
  - Python deps importable

Prints a PASS/FAIL table; exits non-zero on any FAIL.
"""

import importlib
import os
import sqlite3
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH_MASTER = os.path.join(REPO_ROOT, "graphdb", "gita_graph")

REQUIRED_IMPORTS = [
    "kuzu",
    "langgraph",
    "langchain",
    "langgraph.checkpoint.sqlite",
    "litellm",
    "langfuse",
    "apscheduler",
    "streamlit",
    "qdrant_client",
    "llama_cpp",
    "pydantic",
    "yaml",
    "dotenv",
]

results = []  # (name, passed, detail)


def check(name):
    def deco(fn):
        try:
            detail = fn() or ""
            results.append((name, True, detail))
        except Exception as exc:
            results.append((name, False, f"{type(exc).__name__}: {exc}"))
    return deco


@check("unprivileged userns")
def _():
    proc = subprocess.run(
        ["unshare", "--user", "--map-root-user", "true"],
        capture_output=True, text=True, timeout=10,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "unshare --user failed")
    return "unshare --user works"


@check("bwrap available")
def _():
    proc = subprocess.run(["bwrap", "--version"], capture_output=True, text=True, timeout=10)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "bwrap --version failed")
    return proc.stdout.strip()


@check("SQLite WAL mode")
def _():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        path = tmp.name
    try:
        conn = sqlite3.connect(path)
        mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        conn.close()
        if mode.lower() != "wal":
            raise RuntimeError(f"journal_mode came back as {mode!r}")
        return "journal_mode=wal"
    finally:
        for p in (path, path + "-wal", path + "-shm"):
            if os.path.exists(p):
                os.unlink(p)


@check("graphdb master readable (Kuzu read-only)")
def _():
    import kuzu
    if not os.path.isfile(GRAPH_MASTER):
        raise FileNotFoundError(GRAPH_MASTER)
    db = kuzu.Database(GRAPH_MASTER, read_only=True)
    conn = kuzu.Connection(db)
    res = conn.execute("MATCH (a:Anartha) RETURN count(a)")
    count = res.get_next()[0]
    conn.close()
    db.close()
    return f"{count} Anartha nodes"


for mod in REQUIRED_IMPORTS:
    @check(f"import {mod}")
    def _(mod=mod):
        m = importlib.import_module(mod)
        return getattr(m, "__version__", "")


def main():
    width = max(len(name) for name, _, _ in results)
    failed = False
    print(f"\n{'CHECK'.ljust(width)}  RESULT  DETAIL")
    print("-" * (width + 40))
    for name, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        if not ok:
            failed = True
        print(f"{name.ljust(width)}  {status}    {detail}")
    print()
    if failed:
        print("PREFLIGHT FAILED — fix the FAIL rows above before building.")
        sys.exit(1)
    print("PREFLIGHT PASSED — all checks green.")


if __name__ == "__main__":
    main()
