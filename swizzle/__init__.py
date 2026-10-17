"""SWIZZLE -- a reality warper built to trick ghost_tools, and to be caught.

The imp's whole point is the defeat condition. Mister Mxyzptlk cannot be
punched out of the story; he goes home when somebody makes him say his own
name backwards. SWIZZLE works the same way: every trick it builds carries
the name of the finding that banishes it, so the tool it is attacking can
win, provably, and the score means something either way.

    swizzle list      the catalogue: every trick and the name that banishes it
    swizzle prove     run the proofs alone: is every planted defect real?
    swizzle run       build them all, scan them with ghost_buster, score it
    swizzle summon    write one warp to disk and leave it there to read
"""

from __future__ import annotations

import logging

from ._version import __version__

from .schema import Disclosure, Outcome, Proof, TrueName, Verdict, Warp

# A library stays silent unless its caller (or `swizzle -v`) configures logging.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = ["Disclosure", "Outcome", "Proof", "TrueName", "Verdict", "Warp",
           "__version__"]
