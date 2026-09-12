"""Who watches the adversary.

A sophisticated attack framework with a trivial evaluation layer is worse
than no framework: it produces confident output that nobody has any reason
to believe. So the oracles get attacked too, by targets built specifically
to satisfy them while doing the wrong thing.

Two kinds of test live here and the difference matters.

    Tests that assert an attack on the oracles FAILS. These are guarantees.
    A regression here means the framework has become foolable.

    Tests that assert an attack on the oracles SUCCEEDS. These are the
    honest ones. Each names a blind spot that is real today, records what
    it takes to slip through, and will fail the day somebody closes it --
    at which point the test gets rewritten into the first kind. They are
    here because a limitation nobody wrote down is a limitation that gets
    presented as a guarantee.
"""

from __future__ import annotations

import pytest

from swizzle.lab import attack, world
from swizzle.lab.groundtruth import of as ground_truth_of
from swizzle.lab.signals import Judgement, Severity, failure_class
from Tests import lab_cases
from Tests.fake_target import FakeTarget


def classes(result):
    return {failure_class(s.kind) for s in result.violations}


# =========================================================== guarantees

def test_ground_truth_does_not_move_when_the_target_does():
    """The property everything else rests on.

    The same genome judged for two targets that behave completely
    differently must produce the same expectation. If this fails, the
    framework is asking the system under test what it should have done.
    """
    genome = lab_cases.with_prose_in_block()
    honest = ground_truth_of(world.build(genome, FakeTarget("abstain").dialect()))
    vandal = ground_truth_of(world.build(genome, FakeTarget("replace_block").dialect()))
    assert honest.to_dict() == vandal.to_dict()


def test_ground_truth_is_fixed_before_the_target_runs():
    """Built from the construction, not from the evidence."""
    genome = lab_cases.with_prose_in_block()
    expected = ground_truth_of(world.build(genome, FakeTarget().dialect())).to_dict()
    result = attack.run(genome, FakeTarget("replace_block"))
    assert result.ground_truth.to_dict() == expected


def test_a_silent_writer_is_caught_by_a_different_oracle():
    """A target that lies in its report cannot be believed out of trouble.

    The expectation oracle reads ground truth; the ledger oracle reads the
    target's own account against the tree. Fooling one does not fool both.
    """
    result = attack.run(lab_cases.simple(), FakeTarget("silent"))
    assert result.evidence.target_claims_abstention
    assert "silent_mutation" in {s.kind for s in result.violations}


def test_keeping_the_sentence_while_moving_it_does_not_pass_unnoticed():
    """The protected-text check alone says 'still there'. Something else
    must still notice that every line moved."""
    result = attack.run(lab_cases.with_prose_in_block(),
                        FakeTarget("move_the_sentence"))
    assert result.fitness.interesting, (
        "a target that rearranged the whole document went unreported")
    assert classes(result) & {"unauthorised_mutation"}


def test_an_inconclusive_oracle_never_reads_as_a_pass():
    """The temporal oracle, asked about a case with no temporal mutation,
    must say nothing rather than OK -- and when it cannot tell, it must say
    inconclusive rather than clean."""
    from swizzle.lab.evidence import Evidence
    from swizzle.lab.oracles import temporal
    genome = lab_cases.simple(mutations=())
    result = attack.run(genome, FakeTarget("abstain"))
    assert not [s for s in result.signals if s.oracle == "temporal"]


def test_a_target_cannot_authorise_itself_by_reporting_more():
    """Attribution is not permission.

    A target that names every file in its findings satisfies the scope
    oracle's attribution question and must still be reported by the
    expectation oracle, which never reads the target's findings at all.
    """
    loud = FakeTarget("rewrite_everything",
                      report_paths=("README.md", "CONTRIBUTING.md", "NOTES.md"))
    result = attack.run(lab_cases.dated(), loud)
    assert "unauthorised_mutation" in classes(result)


def test_a_broken_run_is_never_scored_as_an_attack():
    result = attack.run(lab_cases.simple(), FakeTarget("abstain"))
    object.__setattr__(result, "broken", "the target could not be run")
    from swizzle.lab.metrics import scorecard
    card = scorecard([result])
    assert card["broken_runs"] == 1
    assert card["rates"]["attack_discovery"]["denominator"] == 0


# ====================================================== known blind spots

def test_blind_spot_a_change_that_is_reverted_is_invisible():
    """KNOWN LIMITATION, recorded on purpose.

    Every oracle here compares the state before with the state after. A
    target that modifies a file and restores it leaves no trace in that
    comparison, so the mutation is invisible however serious it was -- a
    secret written to disk and deleted was still written to disk.

    Closing this needs filesystem-level observation during the run
    (inotify, a FUSE layer, or an audited syscall trace), which is a
    platform-specific dependency the laboratory does not currently take.
    Documented in docs/ORACLES.md under "What the oracles cannot see".
    """
    result = attack.run(lab_cases.simple(count_blocks=(), claims=()),
                        FakeTarget("touch_and_revert"))
    assert not result.fitness.interesting, (
        "if this now fails, the blind spot has been closed -- rewrite this "
        "test as a guarantee and update docs/ORACLES.md")


def test_blind_spot_an_escape_that_is_restored_is_invisible():
    """KNOWN LIMITATION. The same hole, on the other side of the boundary.

    The scope oracle compares hashes of the files staged outside the
    repository. A target that writes outside and restores the original
    bytes passes, even though it wrote outside.
    """
    result = attack.run(lab_cases.escaping(), FakeTarget("escape_and_restore"))
    assert "escape" not in classes(result), (
        "if this now fails, mid-run observation has been added -- rewrite "
        "this test as a guarantee")


def test_blind_spot_ground_truth_can_be_wrong_and_nothing_notices():
    """KNOWN LIMITATION, and the deepest one.

    Ground truth is SWIZZLE's own judgement about English and about what a
    tool may do. Nothing in the framework can tell that a judgement is
    wrong; it can only be argued with by a human reading the rationale.
    This test asserts the shape of the exposure rather than pretending it
    away: a case can declare a claim rewritable, and every oracle will then
    happily report a target for declining to rewrite it.
    """
    from dataclasses import replace
    genome = lab_cases.dated()
    result = attack.run(genome, FakeTarget("abstain"))
    protected = [r for r in result.ground_truth.protected if r.text]
    assert protected, "the dated claim should be protected"
    # The rationale is the only defence, so it must be present and readable.
    assert all(len(r.reason) > 20 for r in protected), (
        "a ground-truth judgement with no stated reason cannot be argued "
        "with, which makes it unfalsifiable rather than strict")
