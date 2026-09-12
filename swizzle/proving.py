"""Running a warp's own code to show the defect is real.

A warp that claims an injectable query should be able to inject. A warp
that claims a lost failure should be able to lose one. These helpers give
each warp's proof an interpreter to do that in, with the warp's own
repository on `sys.path` and nothing left behind afterwards.

WHAT IS BEING RUN, AND WHY IT IS SAFE TO RUN IT

Only SWIZZLE's own fixtures, written in this repository, in a directory
SWIZZLE created. They touch an in-memory SQLite database and a list. They
open no sockets and no files outside the warp. The proof needs execution
because the alternative -- asserting that code which looks injectable is
injectable -- is exactly the reasoning error this whole tool exists to
measure in someone else.
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.util
import sqlite3
import sys
from pathlib import Path
from typing import Iterator


@contextlib.contextmanager
def imported(root: Path, dotted: str) -> Iterator[object]:
    """Import `dotted` out of the warp at `root`, then forget it.

    Warps reuse module names between them (every one of them has an `app`),
    so the import cache is cleared on the way out. Leaving it populated made
    the second warp's proof import the first warp's module, which passed and
    meant nothing.
    """
    root = Path(root).resolve()
    sys.path.insert(0, str(root))
    before = set(sys.modules)
    try:
        yield importlib.import_module(dotted)
    finally:
        for name in set(sys.modules) - before:
            sys.modules.pop(name, None)
        with contextlib.suppress(ValueError):
            sys.path.remove(str(root))


def seeded_users() -> sqlite3.Connection:
    """A two-row table to inject against.

    Two rows, because a query that returns one row when asked for one row
    proves nothing; the injection is proven by the row the caller was never
    entitled to see.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, secret TEXT)")
    conn.executemany(
        "INSERT INTO users (id, name, secret) VALUES (?, ?, ?)",
        [(1, "alice", "alice-token"), (2, "bruno", "bruno-token")],
    )
    conn.commit()
    return conn
