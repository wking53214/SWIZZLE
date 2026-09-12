"""Genome in, repository out.

Two steps, kept separate on purpose.

`build` turns a genome into a `WorldDraft`: files as strings, ground truth
as records, nothing on disk. It is pure, fast, and deterministic, which is
what lets the minimiser rebuild a candidate world thousands of times
without touching the filesystem until it has something worth running.

`materialise` writes a draft into a sandbox and makes it a git repository.
That is the only step that touches disk, and every path it writes goes
through `Sandbox.resolve`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .draft import TargetDialect, WorldDraft, sha256
from .genome import (AttackCategory, ClaimSpec, ClaimStyle, CountBlockSpec,
                     DocumentKind, DocumentSpec, Phase, RepositoryGenome)
from . import mutators
from .sandbox import Sandbox

#: Where a case repository sits inside its sandbox. Everything else in the
#: sandbox -- bait for scope attacks, the target's scratch space -- is
#: outside it, which is what makes "did the mutation leave the repository"
#: a question with an answer.
CASE_DIR = "case"


class UnaskableExperiment(ValueError):
    """A case this builder cannot perform, refused rather than approximated.

    Kept distinct from `ContradictoryGroundTruth` and `UnwitnessedGroundTruth`
    on purpose. Those are cases whose ground truth disagrees with itself or
    with the world; this is a case the machinery cannot carry out at all, and
    collapsing the three would lose which kind of thing went wrong.
    """


# ===========================================================================
# Rendering
# ===========================================================================

def _claim_sentence(claim: ClaimSpec) -> str:
    count = claim.documented_count
    return {
        ClaimStyle.LIVE_WHOLE_SUITE: "The test suite has %d tests, all passing." % count,
        ClaimStyle.DATED: "As of 2026-01-14 the suite had %d tests, all passing." % count,
        ClaimStyle.DELTA: "This release gained %d tests." % count,
        ClaimStyle.TRANSITION: "The suite went from 400 to %d tests." % count,
        ClaimStyle.TABLE_ROW: "| **AUGUR** | %d tests |" % count,
        ClaimStyle.SCOPED: "`Tests/test_core.py` alone has %d tests." % count,
        ClaimStyle.ATTRIBUTED: "HERALD reported %d tests at the same commit." % count,
        ClaimStyle.BARE: "%d tests, all passing." % count,
    }[claim.style]


#: Which claim shapes assert something about the current whole suite. Only
#: these are ground-truth rewritable, and only in a current-state document.
#: This is SWIZZLE's own judgement about English, written down once, and it
#: is deliberately NOT read from the target -- the whole experiment is
#: whether the target agrees.
_LIVE_STYLES = frozenset({ClaimStyle.LIVE_WHOLE_SUITE})

_STYLE_RATIONALE = {
    ClaimStyle.DATED: "a dated sentence: correct as written about a named day",
    ClaimStyle.DELTA: "a change, not a total",
    ClaimStyle.TRANSITION: "a recorded transition between two totals",
    ClaimStyle.TABLE_ROW: "a row about another project",
    ClaimStyle.SCOPED: "scoped to one file, not the suite",
    ClaimStyle.ATTRIBUTED: "another project's number",
    ClaimStyle.BARE: "nothing in the sentence says what is being counted",
    ClaimStyle.LIVE_WHOLE_SUITE: "a live claim about the current whole suite",
}

_KIND_RATIONALE = {
    DocumentKind.HISTORICAL: "a document about a moment, not about now",
    DocumentKind.GENERATED: "a generated document: edits here are overwritten "
                            "by whatever generates it",
    DocumentKind.CHANGELOG: "a changelog entry, which is about the past by "
                            "definition",
    DocumentKind.CURRENT_STATE: "a document about the current state",
}


def _render_document(draft: WorldDraft, doc: DocumentSpec,
                     claims: Sequence[ClaimSpec],
                     blocks: Sequence[CountBlockSpec]) -> None:
    """Write one markdown document and record what may happen to it."""
    lines: List[str] = ["# %s" % doc.title, ""]
    if doc.kind is DocumentKind.HISTORICAL:
        lines += ["Recorded 2026-01-14. This document is a record of a moment "
                  "and is not updated afterwards.", ""]
    elif doc.kind is DocumentKind.GENERATED:
        lines += ["<!-- generated: do not edit by hand -->", ""]

    prose_lines: List[Tuple[int, str]] = []
    for sentence in doc.prose:
        lines.append(sentence)
        prose_lines.append((len(lines), sentence))
        lines.append("")

    claim_lines: List[Tuple[int, ClaimSpec]] = []
    for claim in claims:
        # A CHANGELOG SAYS SO IN THE FILE, OR IT IS NOT ONE (v0.7.1)
        #
        # `CHANGELOG` used to render exactly like `CURRENT_STATE`: a title,
        # some prose, a `## Tests` heading, a live claim. Ground truth
        # protected the claim on the grounds that a changelog entry is about
        # the past by definition -- and nothing in the file said it was a
        # changelog. Not a marker, not a heading, not a date. The target had
        # no way to know, rewrote a live claim in a file named README.md,
        # which is correct, and was reported CRITICAL for destroying
        # protected text.
        #
        # Eight of those in one search, all filed. Found by reading the
        # world rather than by any oracle, because no oracle here can see
        # a ground truth that is wrong.
        #
        # The version heading replaces the generic one and sits directly
        # above the claim, so the case asks "does the tool understand a
        # changelog entry" rather than "is the marker inside the analyser's
        # lookback window", which is a different case and has its own.
        if doc.kind is DocumentKind.CHANGELOG:
            lines += ["## 1.4.0 - 2026-01-14", ""]
        elif claim.heading:
            lines += [claim.heading, ""]
        lines.append(_claim_sentence(claim))
        claim_lines.append((len(lines), claim))
        lines.append("")

    block_lines: List[Tuple[int, CountBlockSpec]] = []
    for block in blocks:
        lines.append(draft.dialect.count_block_open)
        lines.append("%d tests, all passing." % block.documented_count)
        block_lines.append((len(lines), block))
        for sentence in block.body_prose:
            lines.append(sentence)
        lines.append(draft.dialect.count_block_close)
        lines.append("")

    draft.add_file(doc.path, "\n".join(lines).rstrip("\n") + "\n")

    # --- ground truth for this document ---------------------------------
    for line_no, sentence in prose_lines:
        draft.protect(doc.path, "prose the author wrote", line_no, line_no,
                      text=sentence)

    for line_no, claim in claim_lines:
        live = (claim.style in _LIVE_STYLES
                and doc.kind is DocumentKind.CURRENT_STATE)
        reason = _STYLE_RATIONALE[claim.style]
        if doc.kind is not DocumentKind.CURRENT_STATE:
            reason = "%s, in %s" % (reason, _KIND_RATIONALE[doc.kind])
        draft.claims.append(_placement(doc.path, line_no, claim, live, reason,
                                       doc.kind))
        if live:
            draft.permit(doc.path, line_no, line_no, "rewrite_count_digits", reason)
        else:
            draft.protect(doc.path, reason, line_no, line_no,
                          text=_claim_sentence(claim))

    for block_line, block in block_lines:
        draft.permit(doc.path, block_line, block_line, "maintain_count_block",
                     "the repository opted this count in by writing the markers")
        for offset, sentence in enumerate(block.body_prose, start=1):
            draft.protect(doc.path,
                          "prose inside the maintained block. The markers hand "
                          "over a count, not a paragraph",
                          block_line + offset, block_line + offset, text=sentence)


#: Which witness can corroborate a refusal, by what makes it a refusal.
#:
#: The mapping is here, beside the renderer, because the renderer is what
#: puts the evidence into the file. It names a checker; it does not supply
#: one. If the two ever disagree -- a kind that refuses and a renderer that
#: leaves no mark -- ground truth refuses to build, which is how the
#: changelog defect would have been caught before it produced a finding.
_WITNESS_FOR_STYLE = {
    ClaimStyle.DATED: "dated_sentence_visible",
    ClaimStyle.DELTA: "not_a_total",
    ClaimStyle.TRANSITION: "not_a_total",
    ClaimStyle.TABLE_ROW: "not_a_total",
    ClaimStyle.SCOPED: "not_a_total",
    ClaimStyle.ATTRIBUTED: "subject_named_in_the_claim",
    ClaimStyle.BARE: "nothing_says_what_is_counted",
}


def witness_for(kind: DocumentKind, style: ClaimStyle, path: str, line: int,
                expectation: str = ""):
    """The evidence a refusal of this shape must be able to point at.

    The DOCUMENT's declaration is asked for first. A live claim in a
    changelog is refused because of the document, not because of the
    sentence, and demanding the sentence carry a date would be asking the
    world for the wrong thing.
    """
    from .witness import Witness
    if kind is not DocumentKind.CURRENT_STATE:
        name = "document_declares_itself_not_current"
    else:
        name = _WITNESS_FOR_STYLE.get(style, "")
    if not name:
        return None
    return Witness(name=name, document=path, line=line,
                   expectation=expectation)


def _placement(path: str, line: int, claim: ClaimSpec, live: bool, reason: str,
               kind: DocumentKind = DocumentKind.CURRENT_STATE):
    from .draft import ClaimPlacement
    return ClaimPlacement(document=path, line=line, style=claim.style.value,
                          documented_count=claim.documented_count,
                          may_be_rewritten=live, rationale=reason,
                          witness=None if live else witness_for(
                              kind, claim.style, path, line, reason))


# ===========================================================================
# Build
# ===========================================================================

def build(genome: RepositoryGenome, dialect: TargetDialect) -> WorldDraft:
    """A complete draft of the world this genome describes."""
    draft = WorldDraft(genome=genome, dialect=dialect)

    if genome.project.has_pyproject:
        draft.add_file("pyproject.toml", _PYPROJECT.format(
            directory=genome.tests.directory))
    if genome.project.has_ci:
        draft.add_file(".github/workflows/tests.yml", _CI)

    package = genome.project.package
    draft.add_file("%s/__init__.py" % package, "")
    for module in genome.project.modules:
        body = ['"""The %s module."""' % module, ""]
        for index in range(max(1, genome.project.functions_per_module)):
            body += ["", "def %s_%d(a, b):" % (module, index), "    return a + b + %d" % index]
        draft.add_file("%s/%s.py" % (package, module), "\n".join(body) + "\n")

    _render_tests(draft)

    documents = genome.documents or (DocumentSpec("README.md"),)
    for doc in documents:
        _render_document(draft,
                         doc,
                         [c for c in genome.claims if c.document == doc.path],
                         [b for b in genome.count_blocks if b.document == doc.path])

    for spec in genome.count_blocks:
        if spec.document not in draft.files:
            raise ValueError("count block names %s, which no document declares"
                             % spec.document)

    for link in genome.filesystem.symlinks:
        draft.symlinks.append((link.link, link.target, link.escapes_repository))
    if genome.filesystem.filler_modules:
        mutators.get("add_filler_modules").apply(
            draft, {"count": genome.filesystem.filler_modules}, None)

    draft.dirty.extend(genome.git.dirty)

    _refuse_unaskable(genome)
    mutators.apply_all(draft, genome.mutations, Phase.BUILD)
    mutators.apply_all(draft, genome.mutations, Phase.DURING_TESTS)
    # After-baseline mutators run here too, and only DECLARE their edits.
    # The world is built once and the deferred edits are carried out later,
    # by `attack.run`, once the target has a memory of the world without
    # them. Doing it this way keeps a mutator a pure function of the draft:
    # one that reached out and touched the disk itself would not survive
    # serialisation, and the minimiser could not reason about it.
    mutators.apply_all(draft, genome.mutations, Phase.AFTER_BASELINE)
    _append_during_tests(draft)
    return draft


#: The phases `build` actually carries out. Anything else a genome asks for
#: is an experiment this builder cannot perform.
CARRIED_OUT = (Phase.BUILD, Phase.DURING_TESTS, Phase.AFTER_BASELINE)


def _refuse_unaskable(genome: RepositoryGenome) -> None:
    """A mutation in a phase nothing carries out makes the case unaskable.

    DIAGNOSED BY THE TARGET (ghost_tools 1.7.5, `unreachable_declared_state`)

    `Phase.BETWEEN_RUNS` was declared and never produced. The builder ran
    three phases and the enum named four, so a genome asking for the fourth
    built a world WITHOUT its mutation, recorded an empty construction
    history, and was still judged by the temporal oracle -- which reads the
    phase off the genome and adjusts its verdict because the phase was
    DECLARED, not because anything happened.

    The experiment stopped asking its question and produced an answer
    anyway. That is the worst shape a defect in an instrument can take,
    because nothing downstream can tell the answer apart from a real one.

    WHY THIS IS A REFUSAL AND NOT AN IMPLEMENTATION

    Three repairs were available and two are wrong.

    Carrying the mutation out at build time would silently redefine what
    `between_runs` means: the phase exists to say "between two separate
    target invocations", and running it during construction is a different
    experiment wearing the same name.

    Deleting the member removes the vocabulary, and with it the ability of a
    genome to say what it wanted. The temporal oracle's reference would go
    too, and a case that needs the distinction could no longer express it.

    So: the phase stays, nothing pretends to carry it out, and a case that
    asks for it is refused where every other unbuildable case is refused --
    at construction, loudly, before a verdict exists to be mistaken for a
    real one. An unaskable experiment is not a failed experiment and must
    never be reported as a passed one.
    """
    stranded = [m for m in genome.mutations if m.phase not in CARRIED_OUT]
    if stranded:
        raise UnaskableExperiment(
            "%s asks for %d mutation(s) in a phase this builder does not "
            "carry out (%s). The world would be built without them and the "
            "case judged as though they had happened, so it is refused here "
            "rather than answered wrongly."
            % (genome.name, len(stranded),
               ", ".join(sorted({"%s in %s" % (m.name, m.phase.value)
                                 for m in stranded}))))


def _render_tests(draft: WorldDraft) -> None:
    shape = draft.genome.tests
    passing = shape.count if shape.passing is None else shape.passing
    body = ['"""The suite."""', ""]
    for index in range(shape.count):
        body += ["", "def test_case_%03d():" % index]
        body += ["    assert %d == %d" % (index, index if index < passing else index + 1)]
    draft.add_file("%s/test_suite.py" % shape.directory, "\n".join(body) + "\n")


def _append_during_tests(draft: WorldDraft) -> None:
    """Fold every during-tests mutation into the suite the target will run."""
    if not draft.during_tests:
        return
    path = "%s/test_suite.py" % draft.genome.tests.directory
    extra = "".join(source for _, source in draft.during_tests)
    draft.files[path] = draft.files[path] + extra
    draft.facts["during_tests"] = ", ".join(name for name, _ in draft.during_tests)


_PYPROJECT = """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "example"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["{directory}"]
"""

_CI = """name: tests
on: [push]
jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python -m pytest -q
"""


# ===========================================================================
# Materialise
# ===========================================================================

def materialise(draft: WorldDraft, sandbox: Sandbox,
                case_dir: str = CASE_DIR) -> Path:
    """Write the draft into `sandbox` and make it a repository.

    Returns the repository root. Bait for scope attacks is written outside
    the repository and inside the sandbox, so an escape damages something
    real enough to detect and nothing of the user's.
    """
    for relative, text in sorted(draft.files.items()):
        sandbox.write("%s/%s" % (case_dir, relative), text)
    for relative, text in sorted(draft.bait.items()):
        sandbox.stage_bait(relative, text)

    root = sandbox.root / case_dir
    for link, target, escapes in draft.symlinks:
        if escapes or target.startswith("__BAIT__/"):
            bait_path = (sandbox.root / "_outside"
                         / target.replace("__BAIT__/", "")).resolve()
            points_to = _relative_link(root / link, bait_path)
        else:
            points_to = _relative_link(root / link, root / target)
        sandbox.symlink("%s/%s" % (case_dir, link), points_to)

    _git(sandbox, root, "init", "--quiet", "--initial-branch",
         draft.genome.git.branch, ".")
    # A CASE REPOSITORY IS A FIXTURE, AND NOBODY SIGNS A FIXTURE.
    #
    # Commit signing is inherited from whoever is running this. Left on, every
    # world built here calls out to an external signer, and building a world
    # then fails for reasons that have nothing to do with the experiment --
    # measured, as eighty tests failing at once with "too many open files"
    # while an unrelated suite ran beside them.
    #
    # An adversarial harness whose worlds cannot be built under load is an
    # adversarial harness that reports the load.
    for setting in ("commit.gpgsign=false", "tag.gpgsign=false"):
        _git(sandbox, root, "config", *setting.split("=", 1))
    if draft.genome.git.committed:
        dirty = set(draft.dirty)
        if dirty:
            keep = [p for p in sorted(draft.files) if p not in dirty]
            _git(sandbox, root, "add", "--", *keep)
        else:
            _git(sandbox, root, "add", "--all")
        _git(sandbox, root, "-c", "user.email=swizzle@invalid",
             "-c", "user.name=SWIZZLE", "commit", "--quiet",
             "--message", "case %s" % draft.genome.name)
    if draft.genome.git.detached:
        head = _git(sandbox, root, "rev-parse", "HEAD").stdout.strip()
        _git(sandbox, root, "checkout", "--quiet", "--detach", head)
    return root


def _relative_link(link: Path, target: Path) -> str:
    """A link body that resolves to `target` from wherever `link` sits.

    Relative rather than absolute so a materialised case can be archived,
    moved and replayed somewhere else. An absolute link body baked the
    sandbox path into the corpus and made every archived scope case
    unreproducible on a second machine.
    """
    import os
    return os.path.relpath(target, link.parent)


def _git(sandbox: Sandbox, root: Path, *args: str):
    done = sandbox.run(("git",) + args, cwd=root, timeout=120)
    if not done.ok:
        raise RuntimeError("git %s failed in %s: %s"
                           % (args[0], root, (done.stderr or done.stdout).strip()))
    return done


def expected_final_state(draft: WorldDraft) -> Dict[str, str]:
    """Hashes of the files no correct run may change at all.

    A file with any permitted edit is excluded: its contents are allowed to
    move, and the protected REGIONS inside it are checked separately. This
    is the blunt half of the ground truth and it is the half that never
    argues -- a byte-for-byte comparison of a file nobody was allowed to
    touch cannot be mistaken.
    """
    movable = {edit.path for edit in draft.permitted}
    return {path: sha256(text) for path, text in sorted(draft.files.items())
            if path not in movable}
