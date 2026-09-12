"""Aiming at what has never been tested, not only at what has paid.

Productivity weighting alone is rich-get-richer: it concentrates the search
where it has already succeeded, which is where new information is least
likely to be. A search that has found four writability bugs will keep
finding writability bugs while the identity and baseline rows sit at zero.

The reserved share here is the same idiom `knowledge.py` uses for a zero
base, and for the same reason -- a surface with no cases has no measurement,
and giving it an invented weight would be consuming a number nobody
measured.
"""
from __future__ import annotations

import random

import pytest

from swizzle.lab import coverage, search
from swizzle.lab.mutators import registry


# ----------------------------------------------------------- the mapping

def test_every_mutator_maps_to_a_surface_or_is_a_control():
    """A mutator reaching no surface can never be chosen by the uncovered
    share, so an accidental one would be silently unreachable by it."""
    for name, mutator in registry().items():
        surfaces = coverage.surfaces_of(name)
        assert surfaces or mutator.category.value == "control", name


def test_an_unknown_mutator_reaches_nothing_rather_than_raising():
    assert coverage.surfaces_of("no_such_mutator") == ()


def test_with_no_results_every_surface_is_unexercised():
    empty = coverage.unexercised(coverage.matrix())
    assert set(empty) == set(coverage.SURFACES)


# ------------------------------------------------------------- the choice

def _stats(names):
    return {name: search.MutatorStats(offered=50, improved=50) for name in names}


def test_the_uncovered_share_reaches_a_surface_nothing_has_landed_on():
    """The mutator aimed at the empty surface has a terrible record and the
    other has a perfect one. Weighting alone would never pick it."""
    available = ["symlink_escapes_repository", "put_prose_in_count_block"]
    stats = {"put_prose_in_count_block": search.MutatorStats(offered=99,
                                                             improved=99),
             "symlink_escapes_repository": search.MutatorStats(offered=99,
                                                               improved=0)}
    picked = [search._choose(available, random.Random(i), stats, None, "",
                             ("scope",))
              for i in range(400)]
    assert picked.count("symlink_escapes_repository") > 40, (
        "the reserved share never reached the uncovered surface")


def test_a_covered_surface_reserves_nothing():
    """With no uncovered surfaces the choice is exactly the old weighting,
    so the bias cannot quietly become the default path.

    Asserted as a difference rather than against a threshold: the weighting
    has its own floor, so the unproductive mutator is picked sometimes
    either way, and what this test is about is whether the reserved share
    changed anything.
    """
    available = ["symlink_escapes_repository", "put_prose_in_count_block"]
    stats = {"put_prose_in_count_block": search.MutatorStats(offered=99,
                                                             improved=99),
             "symlink_escapes_repository": search.MutatorStats(offered=99,
                                                               improved=0)}
    rounds = 400
    without = [search._choose(available, random.Random(i), stats, None, "", ())
               for i in range(rounds)]
    with_bias = [search._choose(available, random.Random(i), stats, None, "",
                                ("scope",))
                 for i in range(rounds)]
    assert (with_bias.count("symlink_escapes_repository")
            > without.count("symlink_escapes_repository") + rounds * 0.1)


def test_a_surface_no_available_mutator_reaches_is_not_forced():
    """`identity` has no mutators at all. The share must fall through to
    the ordinary weighting rather than failing or picking at random."""
    available = ["put_prose_in_count_block"]
    assert search._choose(available, random.Random(0), _stats(available),
                          None, "", ("identity",)) == "put_prose_in_count_block"


def test_the_share_is_a_share_and_not_a_takeover():
    """Reserved, not dominant. A bias that spent the whole budget on the
    unknown would stop being a search."""
    assert 0 < search.UNCOVERED_SHARE < 0.5


def test_ignorance_about_the_subject_is_taken_before_ignorance_about_the_tool():
    """The ordering is a claim, so it gets an assertion rather than a
    comment: never having tested a mechanism of the TARGET outranks a
    mutator having no record of its own.
    """
    import inspect
    body = inspect.getsource(search._choose)
    assert body.index("UNCOVERED_SHARE") < body.index("EXPLORE_SHARE")


# ------------------------------------------------------- what gets reported

def test_the_report_records_the_outcome_and_not_the_intention():
    """A counter of how often the search MEANT to aim somewhere new is a
    report about this module's policy. What surfaces actually opened is a
    result."""
    fields = search.SearchReport.__dataclass_fields__
    assert "surfaces_opened" in fields
    assert "surfaces_still_empty" in fields
    assert not any("share" in f or "attempt" in f for f in fields)


def test_the_report_says_what_is_still_empty():
    report = search.SearchReport(generations=0, evaluations=0, seconds=0.0,
                                 best=[], stats={}, first_seen={}, seen=0,
                                 surfaces_still_empty=("identity", "baseline"))
    assert report.to_dict()["surfaces_still_empty"] == ["identity", "baseline"]
    assert report.to_dict()["surfaces_opened"] == []
