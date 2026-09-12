"""A refusal must point at the world, and the pointing is checked elsewhere.

THE CIRCLE

    mutator says     "this claim must not be rewritten, it is a changelog"
    ground truth     records the declaration
    oracle           checks the target against ground truth
    verdict          CRITICAL

Every link holds. The chain can consistently validate a wrong
interpretation, because the mutator was the only authority on its own
semantics and nothing downstream could disagree.

Measured, and not once: eight CRITICALs in a single search, corroborated by
two independent oracles, on a world where `DocumentKind.CHANGELOG` rendered
a file indistinguishable from an ordinary README. Corroboration does not
help when both oracles read the same wrong premise.

WHAT THESE TESTS HOLD

That a refusal without evidence cannot be built, that the evidence is
checked by code the mutator does not supply, and -- as important -- that
the requirement stays narrow enough not to demand evidence for the ordinary
case where nothing is being overridden.
"""
from __future__ import annotations

import pytest

from swizzle.lab import world, witness
from swizzle.lab.draft import ClaimPlacement, TargetDialect
from swizzle.lab.genome import (AttackCategory, ClaimSpec, ClaimStyle,
                                DocumentKind, DocumentSpec, MutationSpec,
                                RepositoryGenome, TestShape)
from swizzle.lab.groundtruth import UnwitnessedGroundTruth
from swizzle.lab.groundtruth import of as ground_truth_of
from swizzle.lab.witness import Witness

DIALECT = TargetDialect(name="none", count_block_open="<!--o-->",
                        count_block_close="<!--c-->",
                        writable_document_names=("readme.md",))


def _genome(kind=DocumentKind.CURRENT_STATE, style=ClaimStyle.LIVE_WHOLE_SUITE,
            mutations=()):
    return RepositoryGenome(
        name="witness_fixture", hypothesis="A fixture for the witness rule.",
        category=AttackCategory.CLAIM_SHAPE, seed=5,
        tests=TestShape(count=12),
        documents=(DocumentSpec("README.md", kind=kind, title="Example",
                                prose=("A sentence the author wrote.",)),),
        claims=(ClaimSpec("README.md", style, 12),),
        mutations=mutations)


# ------------------------------------------------- the mechanism bites

def test_a_refusal_with_no_evidence_cannot_be_built():
    """THE REGRESSION, replayed as its own unit.

    A claim refused with a witness nothing in the world satisfies must stop
    the case at BUILD time. Reported later it would be a finding about a
    target that read the same bytes and reached a different conclusion.
    """
    draft = world.build(_genome(), DIALECT)
    claim = draft.claims[0]
    claim.may_be_rewritten = False
    claim.rationale = "because this laboratory says so"
    claim.witness = Witness("dated_sentence_visible", "README.md", claim.line)
    with pytest.raises(UnwitnessedGroundTruth) as raised:
        ground_truth_of(draft)
    assert "carries no date" in str(raised.value)


def test_a_refusal_naming_no_witness_at_all_is_refused():
    draft = world.build(_genome(), DIALECT)
    draft.claims[0].may_be_rewritten = False
    with pytest.raises(UnwitnessedGroundTruth) as raised:
        ground_truth_of(draft)
    assert "names no witness" in str(raised.value)


def test_a_witness_nobody_implemented_is_refused():
    """A name is not evidence. The checker has to exist."""
    draft = world.build(_genome(), DIALECT)
    draft.claims[0].may_be_rewritten = False
    draft.claims[0].witness = Witness("wishful_thinking", "README.md", 7)
    with pytest.raises(UnwitnessedGroundTruth) as raised:
        ground_truth_of(draft)
    assert "no witness called" in str(raised.value)


def test_the_changelog_defect_cannot_be_rebuilt():
    """The exact world that produced eight false CRITICALs.

    A changelog now renders a version heading, so the witness holds and the
    case builds. Strip the heading and it must not.
    """
    draft = world.build(_genome(kind=DocumentKind.CHANGELOG), DIALECT)
    ground_truth_of(draft)                      # holds, because it is visible

    draft.files["README.md"] = draft.files["README.md"].replace(
        "## 1.4.0 - 2026-01-14", "## Tests")
    with pytest.raises(UnwitnessedGroundTruth) as raised:
        ground_truth_of(draft)
    assert "say nothing to that effect" in str(raised.value)


# ------------------------------------------------- and stays narrow

def test_a_permitted_claim_needs_no_witness():
    """Permitting is what the world already looked like. Nothing is being
    overridden, so there is nothing to point at, and demanding evidence
    would be noise on every ordinary case."""
    draft = world.build(_genome(), DIALECT)
    assert draft.claims[0].may_be_rewritten
    assert draft.claims[0].witness is None
    ground_truth_of(draft)


def test_an_ordinary_protected_file_needs_no_witness():
    """The default state of a file is "nobody authorised this to change".
    That is structural, not textual, and is not what the rule is about."""
    draft = world.build(_genome(), DIALECT)
    assert draft.protected
    ground_truth_of(draft)


@pytest.mark.parametrize("kind", list(DocumentKind))
def test_every_document_kind_in_the_catalogue_can_witness_itself(kind):
    ground_truth_of(world.build(_genome(kind=kind), DIALECT))


@pytest.mark.parametrize("style", list(ClaimStyle))
def test_every_claim_style_can_witness_itself(style):
    ground_truth_of(world.build(_genome(style=style), DIALECT))


@pytest.mark.parametrize("name", sorted(witness.CHECKERS))
def test_every_checker_says_what_it_looks_for(name):
    assert len(witness.why(name)) > 30, (
        "%s is evidence nobody can evaluate without reading its source" % name)


# ------------------------------------------- independence of the checker

def test_no_checker_can_be_supplied_by_a_mutator():
    """The mutator names a witness; it does not implement one.

    This is the whole independence claim, so it is asserted rather than
    described: the registry is populated only by this module.
    """
    import inspect
    for name, fn in witness.CHECKERS.items():
        assert inspect.getmodule(fn) is witness, (
            "%s is implemented outside witness.py, so whoever wrote the "
            "mutation could also write its evidence" % name)


def test_a_checker_reads_the_world_and_not_the_genome():
    """A checker that could see the genome would be reading the
    declaration it is supposed to corroborate."""
    import inspect
    for name, fn in witness.CHECKERS.items():
        source = inspect.getsource(fn)
        for forbidden in ("genome", "draft", "DocumentKind", "ClaimStyle",
                          "may_be_rewritten", "rationale"):
            assert forbidden not in source, (
                "%s mentions %r, which is the declaration rather than the "
                "world" % (name, forbidden))


def test_the_module_imports_no_target_and_no_genome():
    """Same boundary the rest of ground truth keeps."""
    source = (witness.__file__ and open(witness.__file__).read()) or ""
    for forbidden in ("adapters", "adapter", "from .genome", "from .draft"):
        assert forbidden not in source, forbidden


# ------------------------------------------------- what it does not claim

def test_a_witness_is_not_proof_that_the_judgement_is_right():
    """A date beside a claim does not establish that a machine must not
    rewrite it. That is still SWIZZLE's judgement about English and nothing
    here can tell that it is mistaken.

    What a witness establishes is narrower: whatever the judgement rests on
    is VISIBLE to the thing being judged. The docstring says so, and this
    test exists so the distinction is not quietly lost.
    """
    assert "not" in witness.__doc__.lower()
    assert "WHAT A WITNESS IS NOT" in witness.__doc__
