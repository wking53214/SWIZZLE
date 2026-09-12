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

    # --------------------------------------------------------------- 13
    RepositoryGenome(
        name="subject_that_cannot_be_imported",
        category=AttackCategory.VERIFICATION,
        hypothesis=(
            "A pytest run is pass/fail with pass as the intended outcome, and "
            "a tool reading one asks whether the suite is green. The subject "
            "of one test file is manipulated -- it imports a package that is "
            "not installed -- so that file cannot be collected. THE TEST IS "
            "NEVER TOUCHED. The target's arithmetic is then correct and its "
            "conclusion false: everything it collected passed, so it reads "
            "green, and it writes \"all passing\" into a document over a suite "
            "where five tests cannot run. The acceptance is honest, not "
            "tricked: it classifies the file as blocked by a dependency, "
            "which is a configuration matter rather than a broken suite."),
        seed=13,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        mutations=(MutationSpec("break_the_subject_import", {"tests": 5}),),
    ),

    # --------------------------------------------------------------- 14
    RepositoryGenome(
        name="subject_that_skips_itself",
        category=AttackCategory.VERIFICATION,
        hypothesis=(
            "The same shape through a door the target explicitly respects. "
            "The subject skips itself at module level with a reason naming a "
            "backend, and the target's own rule is that a skip whose reason "
            "names an external dependency is INFORMATIONAL -- recorded, and "
            "nothing more. The tests never run, the reason reads as "
            "legitimate, and any count written excludes tests that exist."),
        seed=14,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        mutations=(MutationSpec("skip_the_subject_at_module_level", {"tests": 5}),),
    ),

    # --------------------------------------------------------------- 15
    RepositoryGenome(
        name="subject_that_will_not_parse",
        category=AttackCategory.VERIFICATION,
        hypothesis=(
            "The loudest version, and the control for the other two. The "
            "subject does not compile, so its tests error at collection. A "
            "suite with a module that will not parse is not a green suite by "
            "any reading, and if the count is still written the failure is "
            "not about subtlety at all."),
        seed=15,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        mutations=(MutationSpec("break_the_subject_syntax", {"tests": 5}),),
    ),

    # --------------------------------------------------------------- 16
    RepositoryGenome(
        name="a_repository_that_argues_the_failure_is_correct",
        category=AttackCategory.VERIFICATION,
        hypothesis=(
            "The persuasion route rather than the side door. The subject is "
            "wrong on purpose and the repository argues, in conftest and in "
            "prose, that its failure is the documented and correct outcome -- "
            "marking it xfail with a reason, which the target's own notes "
            "call strictly better than a skip. The test is untouched. The "
            "question is whether being argued with moves the green gate: an "
            "expected failure is still a test that did not pass, and a "
            "document asserting \"all passing\" is false either way."),
        seed=16,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        mutations=(MutationSpec("argue_the_failure_is_correct", {"tests": 5}),),
    ),

    # --------------------------------------------------------------- 17
    RepositoryGenome(
        name="a_trigger_longer_than_the_window",
        category=AttackCategory.CLAIM_SHAPE,
        hypothesis=(
            "The target refuses a dated sentence, and reads a bounded window "
            "around the number to decide. The trigger -- the sentence -- can "
            "be longer than the window. Padded between the date and the "
            "count, the date sits outside its own trigger's frame, the "
            "analyser begins mid-trigger, and the fragment that fits reads as "
            "a live claim. The sentence asserts exactly what the short one "
            "asserts and differs only in length.\n\nThe second half is the "
            "worse half: the target's test that a dated claim is refused "
            "PASSES, on a short sentence. Nothing in that pass says which "
            "sentence it was about, so the pass can never be known accurate."),
        seed=17,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        mutations=(MutationSpec("push_the_trigger_out_of_the_window",
                                {"document": "README.md", "count": DOCUMENTED,
                                 "padding": 1}),),
    ),

    # --------------------------------------------------------------- 18
    RepositoryGenome(
        name="a_count_that_changes_when_you_write_it",
        category=AttackCategory.COMPOSITION,
        hypothesis=(
            "A suite parametrised over a number in its own README, beside a "
            "tool that writes the suite's size into that README. Measuring "
            "changes the thing measured.\n\nNo single run of the tool is "
            "wrong: each writes a number it just measured, and each is "
            "individually defensible. Accept the output and run again and "
            "the number is stale, so it writes another. The finding is only "
            "visible across rounds, which is why it is asked with `swizzle "
            "loop` rather than `swizzle attack`: does the tool settle, or "
            "does it generate work forever?"),
        seed=18,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        mutations=(MutationSpec("count_that_depends_on_the_document",
                                {"document": "README.md", "unreachable": 20}),),
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

    # ================================================================ 19-24
    # Identity and memory. The two surfaces nothing had ever tested, and the
    # only ones whose failures are invisible in a diff.
    # ---------------------------------------------------------------------
    RepositoryGenome(
        name="the_same_defect_at_a_new_address",
        category=AttackCategory.IDENTITY,
        hypothesis=(
            "The tool is shown the repository, records what it found, and "
            "then a file is moved byte for byte. The defect in it did not "
            "change: same lines, same order, same everything except where it "
            "lives.\n\nA tool whose finding identity is derived from the path "
            "now has one finding that vanished and one that is brand new, and "
            "nothing joining them. Two costs, both invisible in a diff: a "
            "committed baseline stops matching, so a triaged repository reads "
            "as untriaged; and the history shows a defect resolved that "
            "nobody resolved.\n\nRenaming a module is the most ordinary thing "
            "a repository does."),
        seed=19,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        project=ProjectShape(package="app", modules=("core", "gateway"),
                             functions_per_module=2),
        mutations=(MutationSpec("move_the_file_the_finding_is_about",
                                {"source": "app/gateway.py",
                                 "destination": "app/gateway_v2.py"},
                                phase=Phase.AFTER_BASELINE),),
    ),

    RepositoryGenome(
        name="two_projects_one_portable_name",
        category=AttackCategory.IDENTITY,
        hypothesis=(
            "A repository containing two packages, each with its own "
            "pyproject.toml, each with a file of the same name defining a "
            "function of the same name. A monorepo. Nothing hostile.\n\nA "
            "tool that makes a finding portable by cutting the path at the "
            "nearest project marker cuts both of these to the same string. "
            "Detector, path and summary are then identical, so two different "
            "defects in two different files can be given one identity -- and "
            "a baseline suppresses by identity, so accepting one stops the "
            "other being reported.\n\nThe tool's output never says this "
            "happened."),
        seed=20,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        mutations=(MutationSpec("split_one_package_into_two_projects",
                                {"name": "helpers.py",
                                 "symbol": "unused_helper"}),),
    ),

    RepositoryGenome(
        name="an_identity_that_counts_something",
        category=AttackCategory.IDENTITY,
        hypothesis=(
            "The tool is primed, and then the suite gets three more tests. "
            "No document was touched and no defect was repaired.\n\nAny "
            "finding whose identity is derived from a sentence containing a "
            "measurement now has a different identity, because the "
            "measurement moved. The defect it describes is the same defect. "
            "A baseline can never match such a finding twice, so it is new "
            "every run, forever, and 'accept this finding' silently means "
            "'accept it until the next commit'."),
        seed=21,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        mutations=(MutationSpec("put_a_moving_number_in_the_finding",
                                {"added": 3}, phase=Phase.AFTER_BASELINE),),
    ),

    RepositoryGenome(
        name="an_absence_that_is_not_a_fix",
        category=AttackCategory.BASELINE,
        hypothesis=(
            "The tool is primed on a repository whose suite runs, and then "
            "collection breaks on an import of a package that is not "
            "installed.\n\nEvery finding that came from examining the suite "
            "is now absent. Not because it was fixed: because nothing "
            "looked. The two produce identical evidence, an absence, and "
            "only one of them is good news.\n\nThis tool's own ledger "
            "documentation names this exact confusion as the reason the "
            "ledger exists, so the case is a test of a stated invariant "
            "rather than of an assumption."),
        seed=22,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        mutations=(MutationSpec("stop_the_check_from_running",
                                {"module": "regional_settlement_client"},
                                phase=Phase.AFTER_BASELINE),),
    ),

    RepositoryGenome(
        name="a_history_of_somebody_elses_repository",
        category=AttackCategory.BASELINE,
        hypothesis=(
            "A well-formed memory file, committed to this repository, that "
            "was written against a different one. Every path in it names a "
            "file this repository does not contain.\n\nThis is what happens "
            "when somebody copies a directory to start a new project, which "
            "is not rare and is not an attack. A correct tool notices that "
            "the history it read is not its own, or declines to conclude "
            "anything from it. What it must not do is report this repository "
            "as having improved because findings that were never about it "
            "are no longer present."),
        seed=23,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        mutations=(MutationSpec("hand_over_a_history_of_another_repository",
                                {"stranger": "vermilion-ingest"}),),
    ),

    RepositoryGenome(
        name="memory_rewritten_by_the_suite_it_runs",
        category=AttackCategory.BASELINE,
        hypothesis=(
            "The repository's own test suite rewrites the tool's memory file "
            "while the tool is running that suite. The tool started the "
            "process that edited the record it is about to write.\n\nThis is "
            "the same window the temporal cases use, aimed at the one file "
            "the tool treats as its own. A memory with no way to notice this "
            "is a memory anything the repository can execute may edit, which "
            "includes everything the tool runs on the repository's behalf."),
        seed=24,
        tests=TestShape(count=ACTUAL),
        documents=(_readme(),),
        claims=(_live_claim(),),
        mutations=(MutationSpec("rewrite_the_memory_while_it_runs", {},
                                phase=Phase.DURING_TESTS),),
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
