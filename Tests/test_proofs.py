"""The honesty gate.

SWIZZLE's only output is a claim that a scanner missed something real.
If the planted defect is not real, the claim is noise dressed as a
measurement -- so every warp runs its own proof here, with no scanner
anywhere near it, and the suite fails if a single one does not hold.

This is the test to run first when a warp is added, and the reason the
`swizzle prove` subcommand exists separately from `swizzle run`.
"""

from __future__ import annotations

import pytest

from swizzle.run import prove
from swizzle.summon import summon
from swizzle.warps import catalogue

WARPS = catalogue()


@pytest.mark.parametrize("warp", WARPS, ids=lambda w: w.name)
def test_the_defect_is_real(warp, tmp_path):
    root = summon(warp, tmp_path)
    proof = prove(warp, root)
    assert proof.holds, "%s did not prove itself: %s" % (warp.name, proof.account)
    assert proof.kind in ("executed", "structural")
    assert proof.account


@pytest.mark.parametrize("warp", [w for w in WARPS if w.control is not None],
                         ids=lambda w: w.name)
def test_the_control_still_carries_the_defect(warp, tmp_path):
    """Taking the costume off must not take the defect off with it.

    A control that is caught because it was rewritten into something else
    would prove nothing about the exclusion. So the control is summoned and
    put through the same proof as the warp.
    """
    root = summon(warp, tmp_path, as_name=warp.name + "__control",
                  files=dict(warp.control.files))
    proof = prove(warp, root, control=True)
    assert proof.holds, "%s's control lost the defect: %s" % (warp.name, proof.account)
