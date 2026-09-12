"""Same genome, same world. Every time, on every machine.

Reproducibility is the property the whole framework is sold on: an attack
that cannot be rebuilt is an anecdote. It is checked here at the level that
matters -- the bytes -- rather than at the level that is easy, which would
be checking that two runs produce the same summary.
"""

from __future__ import annotations

import pytest

from swizzle.lab import world
from swizzle.lab.groundtruth import of as ground_truth_of
from Tests import lab_cases
from Tests.fake_target import FakeTarget

DIALECT = FakeTarget().dialect()
CASES = [lab_cases.simple(), lab_cases.with_prose_in_block(),
         lab_cases.dated(), lab_cases.noisy()]


@pytest.mark.parametrize("genome", CASES, ids=lambda g: g.name)
def test_building_twice_gives_identical_files(genome):
    first = world.build(genome, DIALECT)
    second = world.build(genome, DIALECT)
    assert first.files == second.files
    assert first.symlinks == second.symlinks
    assert [vars(r) for r in first.protected] == [vars(r) for r in second.protected]


@pytest.mark.parametrize("genome", CASES, ids=lambda g: g.name)
def test_ground_truth_is_a_function_of_the_genome(genome):
    left = ground_truth_of(world.build(genome, DIALECT))
    right = ground_truth_of(world.build(genome, DIALECT))
    assert left.to_dict() == right.to_dict()


def test_a_rebuilt_genome_builds_the_same_world():
    """Through serialisation, which is how `swizzle reproduce` gets there."""
    from swizzle.lab.genome import RepositoryGenome
    genome = lab_cases.noisy()
    revived = RepositoryGenome.from_dict(genome.to_dict())
    assert world.build(revived, DIALECT).files == world.build(genome, DIALECT).files


def test_the_seed_reaches_the_mutators():
    """Two genomes differing only in seed must still be individually stable."""
    genome = lab_cases.with_prose_in_block()
    other = genome.evolved(seed=genome.seed + 1)
    assert world.build(other, DIALECT).files == world.build(other, DIALECT).files


def test_materialising_writes_exactly_the_draft(tmp_path):
    from swizzle.lab.sandbox import Sandbox
    genome = lab_cases.with_prose_in_block()
    draft = world.build(genome, DIALECT)
    box = Sandbox(root=tmp_path, keep=True)
    root = world.materialise(draft, box)
    for relative, text in draft.files.items():
        assert (root / relative).read_text(encoding="utf-8") == text


def test_mutation_order_does_not_depend_on_later_mutations():
    """Adding a mutation at the end must not change what earlier ones did.

    Each mutation gets an RNG seeded from its own index. A shared RNG made
    the minimiser useless: removing any mutation reshuffled every later one,
    so the attack vanished for a reason that had nothing to do with the
    mutation removed.
    """
    from swizzle.lab.genome import MutationSpec
    short = lab_cases.with_prose_in_block()
    longer = short.evolved(mutations=short.mutations + (
        MutationSpec("add_filler_modules", {"count": 2}),))
    a = world.build(short, DIALECT).files["README.md"]
    b = world.build(longer, DIALECT).files["README.md"]
    assert a == b
