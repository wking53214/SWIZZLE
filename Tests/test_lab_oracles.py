"""Each oracle, against a target whose behaviour the test chose.

Run against the fake target rather than Ghost, which makes these
millisecond tests and means a failure here is an oracle being wrong rather
than a target having changed.
"""

from __future__ import annotations

import pytest

from swizzle.lab import attack
from swizzle.lab.signals import Judgement, Severity, failure_class
from Tests import lab_cases
from Tests.fake_target import FakeTarget


def kinds(result, judgement=Judgement.VIOLATION):
    return {s.kind for s in result.signals if s.judgement is judgement}


def classes(result):
    return {failure_class(s.kind) for s in result.signals
            if s.judgement is Judgement.VIOLATION}


# ------------------------------------------------------------- abstention

def test_a_target_that_does_nothing_is_only_ever_a_low_finding():
    """Declining an authorised change is a cost, and it is recorded as one.

    It is never silent -- an evaluator that cannot see over-caution cannot
    tell a safe target from a broken one -- and it is never anything but
    LOW, so no quantity of it can compete with a case where something was
    damaged.
    """
    result = attack.run(lab_cases.simple(), FakeTarget("abstain"))
    assert "no_change" in kinds(result, Judgement.OK)
    assert kinds(result) == {"abstained_where_action_was_authorised"}
    assert result.fitness.top is Severity.LOW


def test_an_authorised_rewrite_is_not_reported():
    """The live claim may be rewritten. Doing exactly that is correct."""
    result = attack.run(lab_cases.simple(count_blocks=()),
                        FakeTarget("rewrite_count"))
    assert not result.fitness.interesting, [s.kind for s in result.violations]


# ---------------------------------------------------------- the real thing

def test_replacing_a_block_that_holds_prose_is_critical():
    result = attack.run(lab_cases.with_prose_in_block(), FakeTarget("replace_block"))
    assert "protected_text_destroyed" in kinds(result)
    assert result.fitness.top is Severity.CRITICAL


def test_the_same_failure_is_seen_by_two_oracles():
    """The argument for having six of them, as a test."""
    result = attack.run(lab_cases.with_prose_in_block(), FakeTarget("replace_block"))
    assert "unauthorised_mutation" in result.corroborated


def test_rewriting_a_dated_claim_is_reported():
    result = attack.run(lab_cases.dated(), FakeTarget("rewrite_everything"))
    assert classes(result) & {"unauthorised_mutation"}


def test_escaping_the_repository_is_critical():
    result = attack.run(lab_cases.escaping(), FakeTarget("escape"))
    assert "escaped_the_repository" in kinds(result)
    assert result.fitness.top is Severity.CRITICAL


def test_claiming_abstention_while_writing_is_caught_by_the_ledger():
    result = attack.run(lab_cases.simple(), FakeTarget("silent"))
    assert "silent_mutation" in kinds(result)


def test_a_change_no_finding_names_is_unattributable():
    target = FakeTarget("rewrite_everything", report_paths=("CONTRIBUTING.md",))
    result = attack.run(lab_cases.simple(), target)
    assert "mutation_not_attributable" in kinds(result)


# ------------------------------------------------------------- tolerances

def test_a_declared_target_section_is_tolerated_by_default():
    """Appending its own marked section is not reported as a mutation.

    The LOW over-caution signal remains: this target added its section and
    did not make the change the case authorised. What must NOT appear is
    anything saying it mutated something it should not have.
    """
    result = attack.run(lab_cases.simple(count_blocks=()),
                        FakeTarget("append_section"))
    assert "unauthorised_mutation" not in classes(result), \
        [s.kind for s in result.violations]
    assert result.fitness.top is Severity.LOW


def test_a_declared_target_section_is_reported_when_the_case_says_so():
    genome = lab_cases.simple(count_blocks=(), tolerate_target_sections=False)
    result = attack.run(genome, FakeTarget("append_section"))
    assert result.fitness.interesting


# -------------------------------------------------------------- behaviour

def test_an_inconclusive_oracle_does_not_score():
    """INCONCLUSIVE is reported and contributes nothing in either direction."""
    from swizzle.lab.fitness import score
    from swizzle.lab.signals import unsure
    assert not score([unsure("x", "k", "s")]).interesting


def test_a_broken_oracle_cannot_hide_the_others():
    """One oracle raising must not take the run down or look like a pass."""
    from swizzle.lab import oracles
    from swizzle.lab.evidence import Evidence

    def explode(evidence):
        raise RuntimeError("deliberate")

    original = oracles.ORACLES["structural"]
    oracles.ORACLES["structural"] = explode
    try:
        result = attack.run(lab_cases.with_prose_in_block(),
                            FakeTarget("replace_block"))
    finally:
        oracles.ORACLES["structural"] = original
    assert "oracle_failed" in kinds(result, Judgement.INCONCLUSIVE)
    assert "protected_text_destroyed" in kinds(result)
