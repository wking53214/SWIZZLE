"""The genome contract: round-trips exactly, hashes stably, refuses strangers.

A genome that loses a field in serialisation turns every archived attack
into a different experiment, silently. That is the one failure a regression
corpus cannot survive, so it is checked field by field rather than by
eyeballing a dict.
"""

from __future__ import annotations

import json

import pytest

from swizzle.lab.genome import (SCHEMA_VERSION, AttackCategory, ClaimSpec,
                                ClaimStyle, CountBlockSpec, DocumentKind,
                                DocumentSpec, MutationSpec, Phase,
                                RepositoryGenome)
from Tests import lab_cases


ALL = [lab_cases.simple(), lab_cases.with_prose_in_block(), lab_cases.dated(),
       lab_cases.escaping(), lab_cases.noisy()]


@pytest.mark.parametrize("genome", ALL, ids=lambda g: g.name)
def test_round_trip_is_exact(genome):
    assert RepositoryGenome.from_dict(genome.to_dict()) == genome


@pytest.mark.parametrize("genome", ALL, ids=lambda g: g.name)
def test_round_trip_survives_json(genome):
    """Through a string, which is how the corpus actually stores it."""
    revived = RepositoryGenome.from_dict(json.loads(json.dumps(genome.to_dict())))
    assert revived == genome
    assert revived.digest() == genome.digest()


def test_digest_is_stable_across_field_order():
    left = lab_cases.simple()
    right = RepositoryGenome.from_dict(
        dict(reversed(list(left.to_dict().items()))))
    assert left.digest() == right.digest()


def test_digest_changes_when_the_world_changes():
    before = lab_cases.simple()
    after = before.evolved(tests=before.tests.__class__(count=13))
    assert before.digest() != after.digest()


def test_a_foreign_schema_version_is_refused():
    """Reproducing an archived case under a different schema would silently
    run a different experiment, so it stops instead."""
    raw = lab_cases.simple().to_dict()
    raw["schema_version"] = SCHEMA_VERSION + 1
    with pytest.raises(ValueError, match="schema version"):
        RepositoryGenome.from_dict(raw)


def test_lists_come_back_as_tuples():
    """JSON has no tuples. A field that came back as a list would compare
    unequal and hash differently for a world that is the same."""
    revived = RepositoryGenome.from_dict(lab_cases.noisy().to_dict())
    assert isinstance(revived.documents[0].prose, tuple)
    assert isinstance(revived.project.modules, tuple)
    assert isinstance(revived.count_blocks[0].body_prose, tuple)


def test_mutation_phase_survives():
    genome = lab_cases.simple(mutations=(
        MutationSpec("rewrite_claim_during_tests", {"count": 4},
                     phase=Phase.DURING_TESTS),))
    assert RepositoryGenome.from_dict(genome.to_dict()).mutations[0].phase \
        is Phase.DURING_TESTS
