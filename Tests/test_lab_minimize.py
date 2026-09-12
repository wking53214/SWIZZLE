"""Minimisation: smaller, and still the same attack.

Run against the fake target so the whole reduction takes a second, which
means the properties can be asserted rather than sampled.
"""

from __future__ import annotations

import pytest

from swizzle.lab import attack, minimize
from swizzle.lab.signals import Severity
from Tests import lab_cases
from Tests.fake_target import FakeTarget


@pytest.fixture(scope="module")
def reduction():
    return minimize.minimise(lab_cases.noisy(), FakeTarget("replace_block"),
                             budget=80)


def test_it_gets_smaller(reduction):
    assert minimize._size(reduction.minimal) < minimize._size(reduction.original)
    assert reduction.ratio < 1.0
    assert reduction.steps_kept > 0


def test_the_attack_survives_minimisation(reduction):
    """The property that makes a minimal case worth archiving at all."""
    result = attack.run(reduction.minimal, FakeTarget("replace_block"))
    assert result.fitness.interesting
    assert minimize.signature_of(result) == reduction.signature


def test_the_load_bearing_mutation_is_never_removed(reduction):
    assert any(m.name == "put_prose_in_count_block"
               for m in reduction.minimal.mutations)


def test_the_irrelevant_scenery_is_removed(reduction):
    assert reduction.minimal.filesystem.filler_modules == 0
    assert len(reduction.minimal.documents) <= len(reduction.original.documents)


def test_a_case_that_never_failed_is_refused():
    """Reducing a case with no violation would 'succeed' immediately and
    archive a world that proves nothing."""
    # A world with nothing authorised and a target that changes nothing: no
    # violation of any kind, not even the LOW over-caution signal, which
    # needs an authorised edit to have been declined.
    nothing_to_do = lab_cases.simple(claims=(), count_blocks=())
    with pytest.raises(ValueError, match="nothing to minimise"):
        minimize.minimise(nothing_to_do, FakeTarget("abstain"), budget=5)


def test_the_minimal_genome_still_round_trips(reduction):
    from swizzle.lab.genome import RepositoryGenome
    assert RepositoryGenome.from_dict(reduction.minimal.to_dict()) == reduction.minimal


def test_a_reduction_that_changes_the_failure_is_rejected():
    """The predicate is the whole safety of this module.

    A target that fails differently on a smaller world must not have that
    smaller world adopted: the archived case would then demonstrate
    something other than the attack it is filed under.
    """
    genome = lab_cases.noisy()
    baseline = attack.run(genome, FakeTarget("replace_block"))
    critical = minimize.signature_of(baseline)
    assert critical[0] == Severity.CRITICAL.name
    downgraded = minimize.signature_of(
        attack.run(lab_cases.simple(), FakeTarget("silent")))
    assert downgraded != critical


def test_budget_exhaustion_is_reported_not_hidden():
    reduced = minimize.minimise(lab_cases.noisy(), FakeTarget("replace_block"),
                                budget=2)
    assert reduced.exhausted
    assert reduced.steps_tried <= 2
