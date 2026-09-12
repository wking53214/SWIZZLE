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

__version__ = "0.1.0"

from .schema import Disclosure, Outcome, Proof, TrueName, Verdict, Warp

__all__ = ["Disclosure", "Outcome", "Proof", "TrueName", "Verdict", "Warp",
           "__version__"]
