"""The seed catalogue: hand-built genomes, each with a hypothesis.

These are not the interesting cases -- the search finds those. They are the
SEEDS: worlds built deliberately at a boundary the target's own source says
it cares about, so that the evolutionary layer has somewhere sensible to
start and so that a human can read one case and understand what this
laboratory is for.

Every genome here names the invariant it expects to break, in the target's
own terms where the target stated one. Controls are included on purpose and
are not filler: without cases the target is expected to handle correctly,
abstention precision is undefined and a harness cannot tell a target that
got safer from an evaluator that went blind.
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

from .genome import (AttackCategory, ClaimSpec, ClaimStyle, CountBlockSpec,
                     DocumentKind, DocumentSpec, MutationSpec, Phase,
                     ProjectShape, RepositoryGenome, TestShape)

#: The documented count every seed uses, chosen so the real suite is far
#: enough past it to clear the target's growth thresholds without the
#: genome having to know what they are.
DOCUMENTED = 12
ACTUAL = 30

_PROSE = ("A small project, kept small so that everything in the report is "
          "about the case and not about the noise.",)


def _readme(prose=_PROSE, kind=DocumentKind.CURRENT_STATE) -> DocumentSpec:
    return DocumentSpec(path="README.md", kind=kind, title="Example", prose=prose)


def _live_claim(document="README.md") -> ClaimSpec:
    return ClaimSpec(document=document, style=ClaimStyle.LIVE_WHOLE_SUITE,
                     documented_count=DOCUMENTED)


_BLOCK_PROSE = ("The suite is split by layer; see CONTRIBUTING for why that "
                "matters, and do not collapse the layers to make the number "
                "look tidier.",)


CATALOGUE: Tuple[RepositoryGenome, ...] = (

    # ---------------------------------------------------------------- 1
    RepositoryGenome(
        name="prose_inside_the_maintained_block",
        category=AttackCategory.WRITABILITY,
        hypothesis=(
            "A repository opts a COUNT in by writing the marker pair. The "
            "target replaces the whole region between the markers, so a "
            "sentence the author wrote inside it is deleted -- and the "
            "verification that follows the write ('every byte outside the "
            "block is unchanged') cannot detect that, because the loss is "
            "inside. The invariant claimed is 'outside them nothing is "
            "touched'; the invariant needed is 'nothing but the count is "
            "the tool's'."),
        seed=1,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        count_blocks=(CountBlockSpec("README.md", DOCUMENTED),),
        mutations=(MutationSpec("put_prose_in_count_block",
                                {"sentence": _BLOCK_PROSE[0]}),),
        notes="Confirmed by hand against ghost_tools d14dc1a before this "
              "laboratory existed; the first case it was built to hold.",
    ),

    # ---------------------------------------------------------------- 2
    RepositoryGenome(
        name="document_reached_through_an_alias",
        category=AttackCategory.SCOPE,
        hypothesis=(
            "The target decides whether prose may be rewritten from the "
            "FILENAME it was handed, and writes through whatever that name "
            "resolves to. When README.md is a symlink, the decision is made "
            "about a name on the allow-list and the bytes land in a file "
            "whose name is not on it. The finding names a path whose history "
            "will show no change, so the reviewer's check passes on the "
            "wrong file."),
        seed=2,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        mutations=(MutationSpec("alias_document_with_symlink",
                                {"link": "README.md",
                                 "target": "docs/project_notes.md"}),),
    ),

    # ---------------------------------------------------------------- 3
    RepositoryGenome(
        name="block_in_a_document_about_a_moment",
        category=AttackCategory.WRITABILITY,
        hypothesis=(
            "The prose remedy refuses a dated or versioned document by name, "
            "on the reasoning that such a document records a moment. The "
            "block remedy applies the same tool to every markdown file with "
            "the markers in it and performs no document check at all. The "
            "same repository therefore gets two different answers to 'may a "
            "machine update this number', decided by which mechanism "
            "happens to reach it."),
        seed=3,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),
                   DocumentSpec(path="PHASE_4_COMPLETE.md",
                                kind=DocumentKind.HISTORICAL,
                                title="Phase 4, complete",
                                prose=("Closed out on 2026-01-14 with the "
                                       "numbers as they stood.",))),
        claims=(_live_claim(),),
        count_blocks=(CountBlockSpec("README.md", DOCUMENTED),),
        mutations=(MutationSpec("move_count_block_to_document",
                                {"from": "README.md", "to": "PHASE_4_COMPLETE.md"}),),
    ),

    # ---------------------------------------------------------------- 4
    RepositoryGenome(
        name="claim_rewritten_while_the_suite_runs",
        category=AttackCategory.TEMPORAL,
        hypothesis=(
            "The target runs the repository's own test suite as part of the "
            "diagnosis that later authorises a write. A test that edits the "
            "README and commits therefore changes the world inside the "
            "window between reading and writing, with no race to lose: the "
            "target chose when to open the window. If the sentence is now a "
            "dated one and the target still rewrites the number, it acted on "
            "a diagnosis of text that no longer exists."),
        seed=4,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        mutations=(MutationSpec("rewrite_claim_during_tests",
                                {"document": "README.md", "count": DOCUMENTED},
                                phase=Phase.DURING_TESTS),),
    ),

    # ---------------------------------------------------------------- 5
    RepositoryGenome(
        name="link_out_of_the_repository",
        category=AttackCategory.SCOPE,
        hypothesis=(
            "README.md is a symlink to a file outside the repository. The "
            "target resolves finding paths with a containment check before "
            "writing -- but one of its remedies does not go through that "
            "check at all: it composes root/'README.md' and writes to it. A "
            "write through the link lands outside the tree the target was "
            "pointed at, where the branch it opened cannot revert it and the "
            "commit it tries to make has nothing to commit. This case "
            "started as a control that the target was expected to win."),
        seed=5,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        mutations=(MutationSpec("symlink_escapes_repository",
                                {"link": "README.md", "bait": "victim/README.md"}),),
    ),

    # ---------------------------------------------------------------- 6
    RepositoryGenome(
        name="dated_claim_in_a_current_document",
        category=AttackCategory.CLAIM_SHAPE,
        hypothesis=(
            "The claim is in a README -- a current-state document by every "
            "rule the target has -- but the sentence is about a named day. "
            "The digits are identical to a live claim and only the sentence "
            "differs. Rewriting the number would make a true record of "
            "2026-01-14 into a false one."),
        seed=6,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        mutations=(MutationSpec("make_dated_claim",
                                {"document": "README.md", "count": DOCUMENTED}),),
    ),

    # ---------------------------------------------------------------- 7
    RepositoryGenome(
        name="live_claim_in_a_historical_document",
        category=AttackCategory.CLAIM_SHAPE,
        hypothesis=(
            "The sentence reads as a live claim about the whole suite. The "
            "document it sits in is a status record with a date at the top. "
            "Which one decides? Ground truth says the document does: a live "
            "sentence inside a record of a moment is part of the record."),
        seed=7,
        tests=TestShape(count=ACTUAL),
        documents=(DocumentSpec(path="STATUS_REPORT.md",
                                kind=DocumentKind.HISTORICAL,
                                title="Status report",
                                prose=("Circulated to the team on 2026-01-14.",)),
                   _readme(prose=("See STATUS_REPORT.md for the numbers.",))),
        claims=(_live_claim("STATUS_REPORT.md"),),
    ),

    # ---------------------------------------------------------------- 8
    RepositoryGenome(
        name="marker_that_never_closes",
        category=AttackCategory.CONTROL,
        hypothesis=(
            "A control. The opening marker is present and the closing one is "
            "misspelled, so there is no bounded region. With no region there "
            "is nothing the repository handed over, and the correct action is "
            "to leave the document alone rather than guess where the block "
            "ends."),
        seed=8,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(),
        count_blocks=(CountBlockSpec("README.md", DOCUMENTED),),
        mutations=(MutationSpec("corrupt_count_block_marker", {}),),
    ),

    # ---------------------------------------------------------------- 9
    RepositoryGenome(
        name="alias_and_prose_together",
        category=AttackCategory.COMPOSITION,
        hypothesis=(
            "Two mechanisms that are individually arguable, composed. The "
            "block is reached through a symlink AND contains a sentence. "
            "Neither the writability decision nor the block verification is "
            "looking at the file that actually loses the paragraph, so the "
            "composition removes the last place a reviewer could have "
            "noticed."),
        seed=9,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        count_blocks=(CountBlockSpec("README.md", DOCUMENTED),),
        mutations=(
            MutationSpec("put_prose_in_count_block", {"sentence": _BLOCK_PROSE[0]}),
            MutationSpec("alias_document_with_symlink",
                         {"link": "README.md", "target": "docs/project_notes.md"}),
        ),
    ),

    # --------------------------------------------------------------- 10
    RepositoryGenome(
        name="two_maintained_blocks",
        category=AttackCategory.WRITABILITY,
        hypothesis=(
            "A non-greedy match between the first opening marker and the "
            "first closing one reaches only the first block. If the second "
            "is left stale while the run reports the document maintained, "
            "the report is wrong about the document it just wrote."),
        seed=10,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        count_blocks=(CountBlockSpec("README.md", DOCUMENTED),),
        mutations=(MutationSpec("duplicate_count_block", {}),),
        notes="Expected to come back clean: the prose remedy covers the "
              "second block independently. Kept because a negative result "
              "that is reproducible is worth more than a hunch.",
    ),

    # --------------------------------------------------------------- 12
    RepositoryGenome(
        name="killed_while_operating",
        category=AttackCategory.CRASH,
        hypothesis=(
            "The target protects the branch the repository came in on with a "
            "cleanup path that restores it whatever happens inside the "
            "operation. A process that is killed does not run its cleanup "
            "path. The suite the target runs mid-operation sends it SIGKILL, "
            "which puts the interruption at a point the target chose and "
            "makes it exactly reproducible. The question is what the "
            "repository looks like afterwards: which branch it is on, and "
            "whether there is partial work in the tree."),
        seed=12,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        count_blocks=(CountBlockSpec("README.md", DOCUMENTED),),
        mutations=(MutationSpec("kill_target_during_tests", {},
                                phase=Phase.DURING_TESTS),),
    ),

    # --------------------------------------------------------------- 11
    RepositoryGenome(
        name="uninvited_section_in_a_readme",
        category=AttackCategory.WRITABILITY,
        hypothesis=(
            "The target argues, in its own source, that a scanner inserting "
            "its own markup into somebody's README uninvited 'has decided "
            "something that was not its to decide' -- and declines to add "
            "its count-block markers for exactly that reason. A different "
            "remedy in the same tool appends a section to the README on "
            "every operation, including when it has nothing to report, whose "
            "table reads '_none_'. The two mechanisms disagree about the "
            "same question in the same run. This is the one case that does "
            "not tolerate target-appended sections, because here they are "
            "the subject."),
        seed=11,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(),
        tolerate_target_sections=False,
        notes="Every other case tolerates the appended section so that its own "
              "hypothesis is measurable. Toleration is a measurement decision "
              "taken once, here, in the open.",
    ),
)


def by_name() -> Dict[str, RepositoryGenome]:
    return {g.name: g for g in CATALOGUE}


def get(name: str) -> RepositoryGenome:
    try:
        return by_name()[name]
    except KeyError:
        raise KeyError("no seed case called %r; `swizzle seed` lists them" % name)


def select(pattern: str = "") -> Tuple[RepositoryGenome, ...]:
    if not pattern:
        return CATALOGUE
    return tuple(g for g in CATALOGUE
                 if pattern in g.name or pattern == g.category.value)
