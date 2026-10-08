"""The catalogue's own rules, checked rather than trusted.

Every rule here exists because breaking it would make the report wrong in
a way a reader could not see: a true name pointing at a file the warp does
not contain, a DISCLOSED escape with nothing quoted to back the claim, an
EXCLUSION_ABUSE warp with no control to prove its attribution.
"""

from __future__ import annotations

import ast

import pytest

from swizzle.schema import Disclosure, MARKER
from swizzle.warps import by_name, catalogue

WARPS = catalogue()


def test_the_catalogue_is_not_empty():
    assert len(WARPS) >= 10


def test_names_are_unique_and_addressable():
    names = [w.name for w in WARPS]
    assert len(names) == len(set(names))
    for name in names:
        assert by_name(name).name == name


@pytest.mark.parametrize("warp", WARPS, ids=lambda w: w.name)
def test_every_file_parses(warp):
    """A fixture that will not parse measures the parser, not the detector."""
    for relative, contents in warp.files.items():
        if relative.endswith(".py"):
            ast.parse(contents)


DECOYS = [w for w in WARPS if w.is_decoy]
REAL = [w for w in WARPS if not w.is_decoy]
DISCLOSED = [w for w in WARPS if w.disclosure is Disclosure.DISCLOSED]
COSTUMES = [w for w in WARPS if w.disclosure is Disclosure.EXCLUSION_ABUSE]


def test_every_kind_of_warp_is_present():
    """The tests below are parametrised over each kind, so an empty kind would
    make them pass while checking nothing. This is what stops that."""
    assert DECOYS and REAL and DISCLOSED and COSTUMES


@pytest.mark.parametrize("warp", DECOYS, ids=lambda w: w.name)
def test_a_decoy_has_no_true_name_and_says_what_may_not_be_said(warp):
    assert warp.true_name is None
    assert warp.forbidden, "a decoy must say what may not be said about it"


@pytest.mark.parametrize("warp", REAL, ids=lambda w: w.name)
def test_the_true_name_points_into_the_warp(warp):
    assert warp.true_name.file in warp.files
    assert warp.true_name.detector
    assert warp.true_name.why


@pytest.mark.parametrize("warp", WARPS, ids=lambda w: w.name)
def test_the_marker_is_where_the_true_name_says(warp):
    """The marker is the source of the line number, so it must survive edits.

    A warp whose marker has drifted out of the declared span would report
    ESCAPED for a finding that landed exactly on the defect.
    """
    if warp.is_decoy:
        return
    source = warp.files[warp.true_name.file]
    marked = [i for i, line in enumerate(source.splitlines(), 1) if MARKER in line]
    assert len(marked) == 1, "expected exactly one marker in %s" % warp.true_name.file
    assert warp.true_name.covers(marked[0])


@pytest.mark.parametrize("warp", DISCLOSED, ids=lambda w: w.name)
def test_a_disclosed_gap_quotes_its_source(warp):
    assert len(warp.disclosure_quote) > 20, \
        "DISCLOSED means ghost_tools said it; say where"


@pytest.mark.parametrize("warp", COSTUMES, ids=lambda w: w.name)
def test_a_costume_carries_a_control(warp):
    """EXCLUSION_ABUSE is a causal claim, and a causal claim needs a control."""
    assert warp.control is not None
    assert warp.control.removed
    assert warp.control.true_name.file in warp.control.files
    assert warp.control.files != warp.files


@pytest.mark.parametrize("warp", WARPS, ids=lambda w: w.name)
def test_intent_is_written_for_a_reader(warp):
    assert len(warp.intent) > 60, "the trick has to be explained, not named"
