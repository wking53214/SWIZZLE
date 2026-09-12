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
