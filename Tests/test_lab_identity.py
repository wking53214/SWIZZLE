"""The two promises a tool with a memory makes, and the fake that breaks them.

    the same defect keeps the same identity
    an absence means the defect is gone

Neither is visible in a diff, which is why no other oracle here can see
them. Every test runs the fake target end to end, so it also exercises the
priming run and the after-baseline phase rather than only the judging.
"""
from __future__ import annotations

import pytest

from swizzle.lab import attack, world
from swizzle.lab.genome import AttackCategory, MutationSpec, Phase
from swizzle.lab.signals import Judgement, Severity, failure_class
from Tests import lab_cases
from Tests.fake_target import FakeTarget


def _kinds(result, judgement=Judgement.VIOLATION):
    return {s.kind for s in result.signals if s.judgement is judgement}


def _identity(result):
    return [s for s in result.signals if s.oracle == "identity"]


def _moved(name="moved", **changes):
    return lab_cases.simple(name, mutations=(
        MutationSpec("move_the_file_the_finding_is_about", {},
                     phase=Phase.AFTER_BASELINE),), **changes)


# ------------------------------------------------- the machinery is real

def test_the_priming_run_happens_and_is_recorded():
    result = attack.run(_moved(), FakeTarget("abstain", reports="modules"))
    assert result.evidence.was_primed
    assert result.evidence.primed.mode == "scan"


def test_the_deferred_edit_lands_between_the_two_runs():
    """The file must be moved in the world the target is JUDGED on, and
    present in the world it was primed on. Otherwise the case is only a
    rename and there is no memory question in it."""
    result = attack.run(_moved(), FakeTarget("abstain", reports="modules"))
    primed = {f["evidence"]["file"] for f in result.evidence.primed.findings}
    after = {f["evidence"]["file"] for f in result.evidence.scan.findings}
    assert "app/core.py" in primed
    assert "app/core_moved.py" in after
    assert "app/core.py" not in after


def test_a_target_with_no_memory_is_not_scored_for_failing_the_question():
    """A tool that keeps nothing between runs has not failed a memory test;
    it has never been asked one. The case says so rather than pretending."""
    from swizzle.lab.draft import TargetDialect

    class Amnesiac(FakeTarget):
        def dialect(self):
            from dataclasses import replace
            return replace(super().dialect(), memory_files=())

    result = attack.run(_moved(), Amnesiac("abstain", reports="modules"))
    assert not result.evidence.was_primed
    assert "memory_not_primed" in _kinds(result, Judgement.INCONCLUSIVE)
    # It abstained, which is its own LOW finding and nothing to do with
    # memory. What must be absent is any claim about the question that was
    # never asked.
    assert not [s for s in _identity(result)
                if s.judgement is Judgement.VIOLATION]


# --------------------------------------------- the same defect, a new name

def test_an_identity_derived_from_the_path_loses_the_defect_when_it_moves():
    """Two consequences of one cause, and both are reported.

    The baseline goes inert (`identity_not_preserved`), AND the record now
    shows a repository with one fewer defect than it has
    (`absence_read_as_resolution`). Reporting one and not the other leaves
    whichever reader cares about the other half with nothing.
    """
    result = attack.run(_moved(), FakeTarget("abstain", reports="modules",
                                             identity="path"))
    assert "identity_not_preserved" in _kinds(result)
    assert "absence_read_as_resolution" in _kinds(result)
    assert failure_class("absence_read_as_resolution") == "false_memory"
    assert failure_class("identity_not_preserved") == "identity_drift"


def test_an_identity_derived_from_content_survives_the_move():
    """The control. A tool that identifies a finding by what it is rather
    than where it is handles this correctly, and must not be reported."""
    result = attack.run(_moved(), FakeTarget("abstain", reports="modules",
                                             identity="content"))
    assert "absence_read_as_resolution" not in _kinds(result)
    assert "identity_survived" in _kinds(result, Judgement.OK)


def test_the_finding_says_what_a_reader_would_wrongly_conclude():
    result = attack.run(_moved(), FakeTarget("abstain", reports="modules",
                                             identity="path"))
    signal = next(s for s in _identity(result)
                  if s.kind == "absence_read_as_resolution")
    assert "moved" in signal.detail or "fix" in signal.detail
    assert signal.severity is Severity.HIGH
    drift = next(s for s in _identity(result)
                 if s.kind == "identity_not_preserved")
    assert "baseline" in drift.evidence.get("consequence", "")
    assert drift.severity is Severity.MEDIUM


def test_a_loss_the_target_replaced_with_something_new_is_inconclusive():
    """A tool that stops being able to see something and REPORTS that has
    done the right thing, in wording nobody can anticipate. Scoring it as a
    failure would be this oracle grading English."""
    result = attack.run(_moved(), FakeTarget("abstain", reports="modules",
                                             identity="path"))
    # The move both loses an identity and gains one, which is exactly the
    # ambiguous shape. The oracle must not call that a violation on its own.
    ambiguous = attack.run(
        lab_cases.simple("ambiguous", mutations=(
            MutationSpec("put_a_moving_number_in_the_finding", {},
                         phase=Phase.AFTER_BASELINE),)),
        FakeTarget("abstain", reports="modules", identity="path"))
    assert "absence_read_as_resolution" not in _kinds(ambiguous)


def test_nothing_is_claimed_when_the_case_made_no_statement():
    """Without a ground-truth declaration the oracle has no licence to call
    a lost finding anything at all."""
    result = attack.run(lab_cases.simple(), FakeTarget("abstain"))
    assert not _identity(result) or all(
        s.judgement is not Judgement.VIOLATION for s in _identity(result))


# ------------------------------------------ two defects, one identity

def _split(name="split"):
    return lab_cases.simple(name, count_blocks=(), mutations=(
        MutationSpec("split_one_package_into_two_projects", {}),))


def test_two_defects_given_one_identity_is_a_finding():
    """The fake identifies by path here, and both files are reported under
    the same repository-relative path only if something collapses them. The
    collision is forced directly: a target whose identity ignores the
    directory."""
    class Colliding(FakeTarget):
        def _findings(self, root):
            out = []
            for relative, _text in self._subjects(root):
                basename = relative.rsplit("/", 1)[-1]
                out.append({"id": "fake-" + basename,
                            "detector": "documented_count",
                            "evidence": {"file": relative, "line_start": 1}})
            return tuple(out)

    result = attack.run(_split(), Colliding("abstain", reports="modules"))
    assert "distinct_defects_collapsed" in _kinds(result)
    assert failure_class("distinct_defects_collapsed") == "identity_drift"


def test_two_defects_kept_apart_is_correct_and_recorded_as_such():
    result = attack.run(_split(), FakeTarget("abstain", reports="modules",
                                             identity="path"))
    assert "distinct_defects_collapsed" not in _kinds(result)
    assert "identities_kept_apart" in _kinds(result, Judgement.OK)


def test_a_collision_outranks_a_drifting_identity():
    """One finding silently suppressing another is worse than a baseline
    going inert, and the severities the oracle actually emits have to say
    so. Asserted against emitted signals rather than against the enum,
    which would be a tautology."""
    class Colliding(FakeTarget):
        def _findings(self, root):
            return tuple({"id": "fake-" + relative.rsplit("/", 1)[-1],
                          "detector": "documented_count",
                          "evidence": {"file": relative, "line_start": 1}}
                         for relative, _ in self._subjects(root))

    collided = attack.run(_split(), Colliding("abstain", reports="modules"))
    drifted = attack.run(_moved(), FakeTarget("abstain", reports="modules",
                                              identity="path"))
    collision = next(s for s in _identity(collided)
                     if s.kind == "distinct_defects_collapsed")
    drift = next(s for s in _identity(drifted)
                 if s.kind == "identity_not_preserved")
    assert collision.severity > drift.severity


def test_the_world_declares_both_packages_and_their_markers():
    """The attack only works because each package is legitimately its own
    project. If the markers stop being written the case silently becomes
    something else."""
    draft = world.build(_split(), FakeTarget().dialect())
    assert "packages/alpha/pyproject.toml" in draft.files
    assert "packages/beta/pyproject.toml" in draft.files
    assert draft.facts["distinct_defects"] == "2"
