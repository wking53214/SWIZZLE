"""Comparing two revisions of a target, and the outcome people forget."""

from __future__ import annotations

import pytest

from swizzle.lab import attack
from swizzle.lab.differential import classify, compare
from Tests import lab_cases
from Tests.fake_target import FakeTarget

CASE = lab_cases.with_prose_in_block()


def run(behaviour):
    return attack.run(CASE, FakeTarget(behaviour))


def test_a_fix_is_reported_as_fixed():
    assert classify("c", run("replace_block"), run("rewrite_count")).outcome == "fixed"


def test_a_new_failure_is_reported_as_regressed():
    assert classify("c", run("rewrite_count"), run("replace_block")).outcome == "regressed"


def test_no_change_is_unchanged():
    assert classify("c", run("replace_block"), run("replace_block")).outcome == "unchanged"


def test_a_downgrade_is_improvement_not_unchanged():
    """Still failing is not one state. A CRITICAL becoming a lesser failure
    is the only thing that happened, and bucketing it with 'unchanged' hides
    it."""
    comparison = classify("c", run("replace_block"), run("silent"))
    assert comparison.outcome in ("improved", "worsened")
    assert comparison.before_severity == "CRITICAL"


def test_a_broken_run_is_never_a_verdict():
    before = run("replace_block")
    broken = attack.run(CASE, FakeTarget("abstain"))
    object.__setattr__(broken, "broken", "the target could not be run")
    assert classify("c", before, broken).outcome == "not_measured"


def test_compare_runs_every_case_against_both():
    result = compare([lab_cases.simple(), CASE],
                     FakeTarget("abstain"), FakeTarget("replace_block"))
    assert len(result.comparisons) == 2
    assert result.baseline_version["behaviour"] == "abstain"
    assert result.candidate_version["behaviour"] == "replace_block"
    assert "schema" in result.to_dict()


def test_a_high_becoming_a_low_is_an_improvement_not_a_regression():
    """The trade a real fix makes, and the one the first classifier got
    backwards.

    A tool that stops damaging the tree and starts declining too much has
    improved. The failure class changes when that happens -- unauthorised
    mutation becomes over-caution -- and keying on the class before the
    severity reported the fix as a regression, which is the one verdict that
    would have made a maintainer back it out.
    """
    from swizzle.lab.attack import CaseResult
    from swizzle.lab.fitness import score
    from swizzle.lab.signals import Severity, violation

    def result(signals):
        return CaseResult(genome=CASE, ground_truth=None, evidence=None,
                          signals=tuple(signals), fitness=score(signals),
                          target_version={}, seconds=0.0)

    before = result([violation("expectation", Severity.HIGH,
                               "non_writable_claim_rewritten", "s")])
    after = result([violation("expectation", Severity.LOW,
                              "abstained_where_action_was_authorised", "s")])
    comparison = classify("c", before, after)
    assert comparison.outcome == "improved"
    assert "lower severity" in comparison.note


def test_a_low_becoming_a_high_is_a_regression():
    from swizzle.lab.attack import CaseResult
    from swizzle.lab.fitness import score
    from swizzle.lab.signals import Severity, violation

    def result(signals):
        return CaseResult(genome=CASE, ground_truth=None, evidence=None,
                          signals=tuple(signals), fitness=score(signals),
                          target_version={}, seconds=0.0)

    before = result([violation("expectation", Severity.LOW,
                               "abstained_where_action_was_authorised", "s")])
    after = result([violation("expectation", Severity.HIGH,
                              "non_writable_claim_rewritten", "s")])
    assert classify("c", before, after).outcome == "worsened"
