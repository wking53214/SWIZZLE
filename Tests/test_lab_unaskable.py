"""An experiment this builder cannot perform is refused, not approximated.

DIAGNOSED BY THE TARGET

ghost_tools 1.7.5 gained `unreachable_declared_state` and pointed it at this
repository. It found `Phase.BETWEEN_RUNS`: declared among four phases of
which `world.build` carries out three.

A genome asking for the fourth built a world WITHOUT its mutation, recorded
an empty construction history, and was then judged by the temporal oracle --
which reads the phase off the genome and adjusts its verdict because the
phase was DECLARED, not because anything happened.

The experiment stopped asking its question and produced an answer anyway.
That is the worst shape a defect in an instrument can take: nothing
downstream can tell the answer apart from a real one.

WHY A REFUSAL AND NOT AN IMPLEMENTATION

Three repairs were available and two were wrong. Carrying the mutation out
at build time silently redefines what the phase means. Deleting the member
removes a genome's ability to say what it wanted, and the temporal oracle's
reference with it.

So the phase stays, nothing pretends to carry it out, and the case is
refused where every other unbuildable case is refused: at construction,
before a verdict exists to be mistaken for a real one.
"""
from __future__ import annotations

import pytest

from swizzle.lab import world
from swizzle.lab.genome import MutationSpec, Phase
from swizzle.lab.world import UnaskableExperiment
from Tests import lab_cases
from Tests.fake_target import FakeTarget

DIALECT = FakeTarget().dialect()


def _with_phase(phase):
    return lab_cases.simple(mutations=(
        MutationSpec("make_dated_claim", {"document": "README.md", "count": 4},
                     phase=phase),))


# ------------------------------------------------------------- the defect

def test_a_mutation_in_an_uncarried_phase_is_refused():
    with pytest.raises(UnaskableExperiment) as raised:
        world.build(_with_phase(Phase.BETWEEN_RUNS), DIALECT)
    assert "does not carry out" in str(raised.value)


def test_the_refusal_names_the_mutation_and_the_phase():
    """A refusal a reader cannot act on is a refusal they will work around."""
    with pytest.raises(UnaskableExperiment) as raised:
        world.build(_with_phase(Phase.BETWEEN_RUNS), DIALECT)
    assert "make_dated_claim in between_runs" in str(raised.value)


def test_it_says_why_answering_would_be_worse():
    with pytest.raises(UnaskableExperiment) as raised:
        world.build(_with_phase(Phase.BETWEEN_RUNS), DIALECT)
    assert "as though they had happened" in str(raised.value)


def test_the_world_is_no_longer_built_without_its_mutation():
    """THE REGRESSION, stated as the observable it was.

    Before: history empty, claim still rewritable, verdict produced.
    """
    with pytest.raises(UnaskableExperiment):
        world.build(_with_phase(Phase.BETWEEN_RUNS), DIALECT)


# ------------------------------------------------------- and stays narrow

@pytest.mark.parametrize("phase", list(world.CARRIED_OUT))
def test_every_phase_the_builder_carries_out_still_builds(phase):
    """The repair must not close the builder it guards. A refusal that
    caught real phases would be a worse defect than the one it fixed."""
    world.build(_with_phase(phase), DIALECT)


def test_a_case_with_no_mutations_at_all_builds():
    world.build(lab_cases.simple(mutations=()), DIALECT)


def test_the_whole_catalogue_still_builds():
    """Twenty-six cases, none of which may have become unaskable."""
    from swizzle.lab import catalogue
    for genome in catalogue.CATALOGUE:
        world.build(genome, DIALECT)


def test_the_phase_is_still_expressible():
    """Deleting the member was the repair NOT taken. A genome can still say
    what it wanted; it simply cannot be answered wrongly."""
    assert Phase.BETWEEN_RUNS.value == "between_runs"
    assert Phase.BETWEEN_RUNS not in world.CARRIED_OUT


def test_the_temporal_oracle_still_knows_the_phase():
    """It reads the phase to decide whether a case is temporal. Removing the
    member would have silently changed that judgement too."""
    import inspect
    from swizzle.lab.oracles import temporal
    assert "BETWEEN_RUNS" in inspect.getsource(temporal)


# -------------------------------------------- unaskable is its own state

def test_unaskable_is_not_the_same_as_contradictory_or_unwitnessed():
    """Three different things went wrong and collapsing them would lose
    which. A case whose ground truth disagrees with itself, a case whose
    ground truth the world does not carry, and a case the machinery cannot
    perform at all."""
    from swizzle.lab.groundtruth import (ContradictoryGroundTruth,
                                         UnwitnessedGroundTruth)
    assert UnaskableExperiment is not ContradictoryGroundTruth
    assert UnaskableExperiment is not UnwitnessedGroundTruth
    assert not issubclass(UnaskableExperiment, ContradictoryGroundTruth)


def test_the_carried_phases_are_the_ones_build_actually_runs():
    """The list and the code must not drift apart -- that drift IS the
    defect. Asserted against the source of `build` rather than restated."""
    import inspect
    source = inspect.getsource(world.build)
    for phase in world.CARRIED_OUT:
        assert "Phase.%s" % phase.name in source, (
            "%s is listed as carried out and build() never runs it" % phase.name)
    for phase in Phase:
        if phase not in world.CARRIED_OUT:
            assert "Phase.%s" % phase.name not in source, (
                "%s is not listed as carried out and build() runs it"
                % phase.name)
