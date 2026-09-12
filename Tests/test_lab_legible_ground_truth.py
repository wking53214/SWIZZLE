"""Ground truth may only protect on grounds the world actually carries.

THE FAILURE THIS FILE EXISTS TO STOP

`DocumentKind.CHANGELOG` rendered exactly like `CURRENT_STATE`: a title,
some prose, a `## Tests` heading, a live claim. Ground truth protected the
claim on the grounds that a changelog entry is about the past by
definition, and **nothing in the file said it was a changelog**. No marker,
no heading, no date.

So the world handed the target a live whole-suite claim in a file named
`README.md`, the target rewrote it -- which is correct -- and the harness
reported CRITICAL `protected_text_destroyed`, corroborated by two
independent oracles. Eight of them in one search, all filed to the corpus.

No oracle can catch this. Every oracle here judges the target against
ground truth, and the thing that was wrong WAS ground truth. It was found
by building the world and reading the file.

THE INVARIANT

If a property of the genome makes ground truth refuse a rewrite, that
property must be visible in the bytes the target is given. Otherwise the
case is asking the target to know something nobody told it, and a failure
proves only that the harness knows a secret.

This is a test about the LABORATORY, not about any target. It runs against
no target at all.
"""
from __future__ import annotations

import pytest

from swizzle.lab import world
from swizzle.lab.draft import TargetDialect
from swizzle.lab.genome import (AttackCategory, ClaimSpec, ClaimStyle,
                                DocumentKind, DocumentSpec, RepositoryGenome,
                                TestShape)

DIALECT = TargetDialect(name="none", count_block_open="<!--o-->",
                        count_block_close="<!--c-->",
                        writable_document_names=("readme.md",))


def _world(kind: DocumentKind):
    genome = RepositoryGenome(
        name="legibility_%s" % kind.value,
        hypothesis="A fixture for the legibility invariant.",
        category=AttackCategory.CLAIM_SHAPE, seed=3,
        tests=TestShape(count=12),
        documents=(DocumentSpec("README.md", kind=kind, title="Example",
                                prose=("A sentence the author wrote.",)),),
        claims=(ClaimSpec("README.md", ClaimStyle.LIVE_WHOLE_SUITE, 12),),
    )
    return world.build(genome, DIALECT)


def _protects_the_claim(draft) -> bool:
    return any(c.document == "README.md" and not c.may_be_rewritten
               for c in draft.claims)


@pytest.mark.parametrize("kind", list(DocumentKind))
def test_a_kind_that_forbids_a_rewrite_is_visible_in_the_file(kind):
    """THE REGRESSION.

    Whatever makes a claim unrewritable has to be readable in the document.
    Compared against the CURRENT_STATE rendering of the same genome, so the
    test asks "is there a difference a reader could notice", not "did
    somebody remember to add a marker I already know about".
    """
    draft = _world(kind)
    text = draft.files["README.md"]
    plain = _world(DocumentKind.CURRENT_STATE).files["README.md"]
    if not _protects_the_claim(draft):
        return                       # nothing is being asserted about it
    assert text != plain, (
        "%s makes ground truth refuse the rewrite, and renders a file "
        "indistinguishable from an ordinary current-state document. The "
        "target is being asked to know something nobody told it." % kind.value)


@pytest.mark.parametrize("kind", list(DocumentKind))
def test_the_difference_is_near_the_claim_not_only_in_the_header(kind):
    """A marker the analyser's window cannot reach is a marker that is not
    there, for any target with a bounded lookback.

    Asserted at 240 characters, which is the widest window this
    laboratory's own target reads. A case that wants to test the WINDOW
    should say so and be built for it -- `push_the_trigger_out_of_the_window`
    is that case -- rather than arriving by accident in a case about
    document kinds.
    """
    draft = _world(kind)
    if not _protects_the_claim(draft):
        return
    text = draft.files["README.md"]
    plain = _world(DocumentKind.CURRENT_STATE).files["README.md"]
    claim = "The test suite has 12 tests"
    assert claim in text
    before = text[max(0, text.index(claim) - 240):text.index(claim)]
    novel = [line.strip() for line in before.splitlines()
             if line.strip() and line.strip() not in plain]
    assert novel, (
        "%s renders its distinguishing mark outside the 240 characters "
        "before the claim, so a bounded reader never sees it. Either move "
        "it next to the claim or build a window case on purpose." % kind.value)


def test_current_state_is_the_one_kind_that_permits_a_rewrite():
    """The control. If this stops holding, the two tests above pass by
    protecting nothing."""
    assert not _protects_the_claim(_world(DocumentKind.CURRENT_STATE))
    protected = [k for k in DocumentKind if _protects_the_claim(_world(k))]
    assert len(protected) == len(list(DocumentKind)) - 1


def test_every_protected_claim_states_its_reason():
    for kind in DocumentKind:
        draft = _world(kind)
        for claim in draft.claims:
            if not claim.may_be_rewritten:
                assert claim.rationale.strip(), kind.value
