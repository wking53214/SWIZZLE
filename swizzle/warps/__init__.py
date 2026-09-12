"""The catalogue: every warp SWIZZLE knows how to build.

Warps are grouped by the detector family they are written against, one
module each, because the interesting thing about a family is the pattern
across its members -- four ways a query stays quiet says something that
four unrelated tricks do not.
"""

from __future__ import annotations

from typing import Tuple

from ..schema import Warp
from . import deadcode, decoys, handlers, hollow, insecure, sql

_MODULES = (sql, handlers, hollow, deadcode, insecure, decoys)


def catalogue() -> Tuple[Warp, ...]:
    """Every warp, in a stable order, with names checked unique.

    A duplicate name would mean two warps summoning into the same directory
    and one result overwriting the other, silently. Stopping here is the
    cheaper failure.
    """
    out = []
    seen = set()
    for module in _MODULES:
        for warp in module.WARPS:
            if warp.name in seen:
                raise ValueError("duplicate warp name: %s" % warp.name)
            seen.add(warp.name)
            out.append(warp)
    return tuple(out)


def by_name(name: str) -> Warp:
    for warp in catalogue():
        if warp.name == name:
            return warp
    raise KeyError(name)
