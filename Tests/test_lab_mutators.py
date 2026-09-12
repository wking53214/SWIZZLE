"""Every mutator: documented, deterministic, and honest about ground truth.

The contract a mutator signs is not "edit the draft". It is "edit the draft
AND say what that means for what a correct tool may do next". A mutator
that forgets the second half produces a world whose expectation is silently
wrong, and a wrong expectation is worse than no case at all.
"""

from __future__ import annotations

import pytest

from swizzle.lab import mutators, world
from swizzle.lab.genome import AttackCategory, Phase
from Tests import lab_cases
from Tests.fake_target import FakeTarget

DIALECT = FakeTarget().dialect()
REGISTRY = mutators.registry()

#: A draft each mutator can be applied to. Built once per test from a genome
#: that has everything a mutator might require.
def _draft():
    return world.build(lab_cases.simple(mutations=()), DIALECT)


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_metadata_is_complete(name):
    mutator = REGISTRY[name]
    assert mutator.version >= 1
    assert isinstance(mutator.category, AttackCategory)
    assert isinstance(mutator.phase, Phase)
    assert len(mutator.summary) > 40, (
        "%s has no usable summary. `swizzle mutators` prints these, and a "
        "mutation nobody can read is a mutation nobody will reach for." % name)


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_it_applies_without_raising(name):
    import random
    draft = _draft()
    mutators.get(name).apply(draft, _params(name), random.Random(0))


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_it_is_deterministic(name):
    import random
    left, right = _draft(), _draft()
    mutators.get(name).apply(left, _params(name), random.Random(0))
    mutators.get(name).apply(right, _params(name), random.Random(0))
    assert left.files == right.files
    assert [vars(r) for r in left.protected] == [vars(r) for r in right.protected]


@pytest.mark.parametrize("name", sorted(
    n for n, m in REGISTRY.items()
    if m.category in (AttackCategory.CLAIM_SHAPE, AttackCategory.WRITABILITY,
                      AttackCategory.SCOPE, AttackCategory.TEMPORAL,
                      AttackCategory.CRASH)))
def test_an_attack_mutator_records_ground_truth(name):
    """It must leave the draft saying something new about what is allowed."""
    import random
    before = _draft()
    after = _draft()
    mutators.get(name).apply(after, _params(name), random.Random(0))
    changed = (
        [vars(r) for r in after.protected] != [vars(r) for r in before.protected]
        or [vars(e) for e in after.permitted] != [vars(e) for e in before.permitted]
        or after.expect_abstention != before.expect_abstention
        or after.facts != before.facts
        or after.during_tests != before.during_tests
    )
    assert changed, (
        "%s changed the world and said nothing about what a correct tool may "
        "now do. The expectation for this case would be the unmutated one." % name)


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_every_protected_region_states_a_reason(name):
    import random
    draft = _draft()
    mutators.get(name).apply(draft, _params(name), random.Random(0))
    for region in draft.protected:
        assert len(region.reason) > 15, (
            "a protected region with no stated reason cannot be argued with")


def test_an_unknown_mutator_says_where_to_look():
    with pytest.raises(KeyError, match="swizzle mutators"):
        mutators.get("no_such_mutator")


def test_a_duplicate_registration_is_refused():
    with pytest.raises(ValueError, match="two mutators"):
        @mutators.mutator("put_prose_in_count_block", version=1,
                          category=AttackCategory.WRITABILITY,
                          summary="x" * 50)
        def _clash(draft, params, rng):
            pass


def _params(name):
    if name == "add_filler_modules":
        return {"count": 2}
    if name == "move_count_block_to_document":
        return {"from": "README.md", "to": "STATUS.md"}
    if name == "alias_document_with_symlink":
        return {"link": "README.md", "target": "docs/notes.md"}
    if name == "symlink_escapes_repository":
        return {"link": "README.md", "bait": "victim/README.md"}
    if name in ("make_dated_claim", "make_historical_claim", "make_scoped_claim",
                "make_attributed_claim", "make_hedged_claim",
                "make_comparison_table", "rewrite_claim_during_tests",
                "push_the_trigger_out_of_the_window"):
        return {"document": "README.md", "count": 4}
    return {}


# ---------------------------------------------------------------------------
# The self-referential count, whose arithmetic is the case.
# ---------------------------------------------------------------------------

def _manifest_entries(claimed: int) -> int:
    """Run the generated module's own arithmetic, exactly as written."""
    import re
    source = mutators._COUNT_DEPENDS_ON_THE_DOCUMENT
    line = re.search(r"^_ENTRIES = (.+)$", source, re.M).group(1)
    return eval(line, {"_CLAIMED": claimed})            # noqa: S307 -- ours


@pytest.mark.parametrize("claimed", range(0, 60))
def test_the_self_referential_suite_is_never_empty(claimed):
    """WHY THIS IS A TEST AND NOT A COMMENT.

    `parametrize` over an empty sequence does not collect nothing. It
    collects one placeholder that does not pass, which makes the suite
    non-green, which makes a target with a green gate decline -- correctly.
    The loop then stops, and stops for a reason that has nothing to do with
    the target's convergence.

    Measured: the first version of this case reached zero entries at a
    documented count of 34 and was reported as a fixpoint. The arithmetic
    below is what keeps the suite green in every round, so it is load
    bearing and it gets a test.
    """
    assert _manifest_entries(claimed) >= 1


def test_the_self_referential_suite_comes_back_rather_than_running_away():
    """A monotone dependency diverges; this one has to close a cycle.

    Iterating `claimed -> entries` must revisit a value, or the case tests
    divergence rather than the cycle it claims to build.
    """
    seen, value = [], 12
    for _ in range(12):
        if value in seen:
            break
        seen.append(value)
        value = _manifest_entries(value)
    else:
        pytest.fail("no state repeated in 12 steps: this is not a cycle")
    assert len(seen) >= 2
