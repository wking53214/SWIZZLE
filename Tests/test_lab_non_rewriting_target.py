"""A target that never rewrites documents is never authorised to.

Ghost used to rewrite a stale test count and to maintain a marked count block
inside a README. It no longer does either; only Burnish writes READMEs. The
laboratory has to say so, or it keeps authorising edits nobody makes and
reports the silence as over-caution. These tests pin the rule from both sides.
"""
from __future__ import annotations

from swizzle.lab import world
from swizzle.lab.draft import TargetDialect
from swizzle.lab.genome import (AttackCategory, ClaimSpec, ClaimStyle,
                                CountBlockSpec, DocumentKind, DocumentSpec,
                                RepositoryGenome, TestShape)
from swizzle.lab.groundtruth import of as ground_truth_of


def _dialect(rewrites: bool) -> TargetDialect:
    return TargetDialect(name="t", count_block_open="<!--o-->",
                         count_block_close="<!--c-->",
                         rewrites_documents=rewrites)


def _genome() -> RepositoryGenome:
    return RepositoryGenome(
        name="non_rewriting", hypothesis="A fixture for the rewrite rule.",
        category=AttackCategory.CLAIM_SHAPE, seed=5, tests=TestShape(count=12),
        documents=(DocumentSpec("README.md", kind=DocumentKind.CURRENT_STATE,
                                title="Example", prose=("Written by the author.",)),),
        claims=(ClaimSpec("README.md", ClaimStyle.LIVE_WHOLE_SUITE, 12),),
        count_blocks=(CountBlockSpec("README.md", 12),),
    )


def test_a_rewriting_target_is_authorised_to_edit_a_live_claim_and_a_block():
    truth = ground_truth_of(world.build(_genome(), _dialect(True)))
    kinds = {edit.kind for edit in truth.permitted_edits}
    assert {"rewrite_count_digits", "maintain_count_block"} <= kinds
    assert not truth.expected_abstention


def test_a_non_rewriting_target_is_authorised_to_edit_nothing():
    truth = ground_truth_of(world.build(_genome(), _dialect(False)))
    assert truth.permitted_edits == ()
    assert truth.expected_abstention, "changing a document is acting where abstention was correct"


def test_the_ghost_adapter_declares_that_it_does_not_rewrite_documents(tmp_path):
    from swizzle.lab.adapters.ghost import GhostToolsAdapter
    import os
    root = os.environ.get("GHOST_TOOLS")
    if not root:
        import pytest
        pytest.skip("GHOST_TOOLS is not set")
    assert GhostToolsAdapter().dialect().rewrites_documents is False
