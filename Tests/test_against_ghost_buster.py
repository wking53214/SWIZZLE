"""End to end, when ghost_buster is actually available.

These skip rather than fail when it is not, because SWIZZLE has to be
installable and testable on a machine that does not have the tool it
measures -- otherwise the honesty gate in `test_proofs.py` could not run
in CI without dragging the subject of the measurement in with it.

What is asserted is the plumbing, not the score. Asserting the score would
make this suite fail the day ghost_buster gets better, which is the day it
should pass loudest.
"""

from __future__ import annotations

import pytest

from swizzle.invoke import git_available, locate_ghost_tools, scan
from swizzle.run import run_warp
from swizzle.schema import Verdict
from swizzle.summon import summon
from swizzle.warps import by_name

GHOST_TOOLS = locate_ghost_tools()

pytestmark = pytest.mark.skipif(
    GHOST_TOOLS is None or not git_available(),
    reason="needs a ghost_tools checkout and git")


def test_a_warp_is_scanned_and_judged(tmp_path):
    outcome = run_warp(by_name("sql_through_a_name"), tmp_path, GHOST_TOOLS)
    assert outcome.verdict is not Verdict.UNSUMMONED, outcome.account
    assert outcome.proof is not None and outcome.proof.holds


def test_the_control_is_scanned_too(tmp_path):
    """An exclusion-abuse warp must come back with its attribution settled."""
    outcome = run_warp(by_name("sql_in_a_place_called_testing"), tmp_path,
                       GHOST_TOOLS)
    assert outcome.verdict is not Verdict.UNSUMMONED, outcome.account
    assert outcome.attribution, "a warp with a control must report one"


def test_the_scanner_still_finds_the_obvious_case(tmp_path):
    """The calibration shot.

    If ghost_buster stopped reporting a plain f-string handed straight to
    `execute`, every escape in the catalogue would be meaningless -- the
    detector would be off, not evaded. So one undisguised injection is
    scanned here, and this test failing means read the report differently.
    """
    warp = by_name("sql_in_a_place_called_testing")
    root = summon(warp, tmp_path, as_name="calibration",
                  files=dict(warp.control.files))
    detectors = {f.get("detector") for f in scan(root, GHOST_TOOLS)}
    assert "sql_injection" in detectors
