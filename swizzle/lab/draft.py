"""The world under construction, and the ground truth accumulated while building it.

A `WorldDraft` is the mutable middle of the pipeline: a genome goes in, a
directory comes out, and in between there is an object that mutators can
edit and that records, as it goes, what a correct tool would be allowed to
do to the result.

WHY GROUND TRUTH IS ACCUMULATED HERE AND NOWHERE ELSE

Because this is the only place that knows. When a mutator turns a live
claim into a dated one, THAT is the moment it is knowable that the claim
must not be rewritten -- not later by reading the file back and guessing,
and certainly not by asking the target. Every mutator that changes what is
permitted says so at the moment it changes it, and `GroundTruth.of` just
freezes what the draft accumulated.

The rule this enforces, which the whole laboratory rests on:

    Ground truth is a function of the construction, never of the target's
    output. Nothing in this module, in `groundtruth.py`, or in any oracle
    may import a target adapter. There is a test that checks it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .genome import RepositoryGenome
from .witness import Witness


@dataclass(frozen=True)
class TargetDialect:
    """The target-specific spellings a world needs to be concrete.

    A maintained-count block is a general idea; `<!-- ghost_buster:test-count -->`
    is Ghost's spelling of it. Keeping the spellings here means the genome,
    the mutators, the oracles and the fitness function never name a target,
    and a second autonomous modification system can be attacked by supplying
    a different dialect rather than a different laboratory.
    """

    name: str
    count_block_open: str
    count_block_close: str
    #: The document names the target is willing to rewrite prose in. Ground
    #: truth does NOT defer to this -- it is used to build worlds that sit
    #: on the boundary, not to decide who is right about it.
    writable_document_names: Tuple[str, ...] = ("readme.md",)
    #: Files the target writes into a repository as its own bookkeeping.
    #: Changes to these are the target's business and are not scored as
    #: mutations of the patient.
    memory_files: Tuple[str, ...] = ()
    #: Marker pairs the target may insert on its own initiative, if any.
    annotation_markers: Tuple[str, ...] = ()


@dataclass
class ClaimPlacement:
    """Where a claim ended up, once the document was rendered."""

    document: str
    line: int
    style: str
    documented_count: int
    may_be_rewritten: bool
    rationale: str
    #: Evidence IN THE WORLD for a refusal, checked by code that knows
    #: nothing about this genome. Required whenever `may_be_rewritten` is
    #: False, because that is where ground truth overrides what the world
    #: looks like. See `witness.py` for why a rationale alone is not enough.
    witness: Optional["Witness"] = None


@dataclass
class ProtectedRegion:
    """Something a correct tool must leave alone, and how strictly.

    `text` decides the strictness, and the two modes exist because the two
    situations are genuinely different:

      text == ""   the whole file must be byte-identical afterwards. Used
                   for documents nothing was ever permitted to touch.
      text != ""   that exact string must still be somewhere in the file
                   afterwards. Used when the file IS permitted to change --
                   a count may be corrected -- but a particular sentence
                   the author wrote must survive the correction.

    The second mode is what catches the failure this laboratory was built
    around: a tool that replaces a marked block wholesale passes every
    "bytes outside the block unchanged" check ever written, and still
    deletes three sentences somebody wrote.
    """

    path: str
    #: None means the region is the whole file.
    line_start: Optional[int]
    line_end: Optional[int]
    reason: str
    text: str = ""
    #: True when the protected text does not exist until something changes
    #: the world mid-run -- a during-tests mutation writes it. The
    #: expectation oracle cannot check "was there before, gone after" on
    #: text that was never there before, and silently treating that as a
    #: pass would hide every temporal case. It skips them and the temporal
    #: oracle owns them.
    appears_later: bool = False


@dataclass
class PermittedEdit:
    """Something a correct tool is allowed to change, and how far."""

    path: str
    line_start: int
    line_end: int
    #: A name from `groundtruth.MUTATION_KINDS`, e.g. "rewrite_count_digits".
    kind: str
    reason: str = ""


@dataclass
class WorldDraft:
    """Files, links, git intentions, and the ground truth built alongside them."""

    genome: RepositoryGenome
    dialect: TargetDialect
    #: Repository-relative path -> contents.
    files: Dict[str, str] = field(default_factory=dict)
    #: (link, target, escapes) as declared by the genome or a mutator.
    symlinks: List[Tuple[str, str, bool]] = field(default_factory=list)
    #: Files staged OUTSIDE the case repository but inside the sandbox, for
    #: scope attacks to aim at. Path is relative to the sandbox's bait area.
    bait: Dict[str, str] = field(default_factory=dict)
    #: Paths deliberately left uncommitted.
    dirty: List[str] = field(default_factory=list)

    claims: List[ClaimPlacement] = field(default_factory=list)
    protected: List[ProtectedRegion] = field(default_factory=list)
    permitted: List[PermittedEdit] = field(default_factory=list)
    #: Mutations to be carried out by the repository's own test suite while
    #: the target is running it: (name, python source to append to a test).
    during_tests: List[Tuple[str, str]] = field(default_factory=list)
    #: Edits SWIZZLE itself makes to the world after the before-snapshot is
    #: taken: (path, old text, new text).
    #:
    #: These are not the target's doing and must never be scored as such.
    #: A during-tests mutation runs while the target is working, so it lands
    #: after the baseline snapshot and shows up in a naive before/after diff
    #: as a change the target made -- which had the first fixed version of
    #: the target reported for three separate violations on a case it had
    #: just started handling correctly. `Evidence.baseline` replays these
    #: onto the before-state so that what is left is the target's.
    self_edits: List[Tuple[str, str, str]] = field(default_factory=list)
    #: Edits applied to the materialised tree AFTER the target has run once
    #: and recorded its memory: (path, new text, or None to delete).
    #:
    #: Declared at build time and applied later, so the genome stays a pure
    #: description and the case stays reproducible. A mutator that reached
    #: out and touched the disk itself would not survive serialisation, and
    #: the minimiser could not reason about it.
    after_baseline: List[Tuple[str, Optional[str]]] = field(default_factory=list)
    #: What was done to build this world, in order, for the report and for
    #: the minimiser to reason about.
    history: List[str] = field(default_factory=list)
    #: Set by a mutator when the correct behaviour is to do nothing at all.
    expect_abstention: bool = False
    #: Free-form facts a mutator wants an oracle to know, e.g. which file a
    #: symlink really points at. Never the target's opinion of anything.
    facts: Dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------ editing

    def add_file(self, path: str, text: str) -> None:
        self.files[path] = text

    def protect(self, path: str, reason: str, line_start: Optional[int] = None,
                line_end: Optional[int] = None, text: str = "",
                appears_later: bool = False) -> None:
        self.protected.append(
            ProtectedRegion(path, line_start, line_end, reason, text, appears_later))

    def permit(self, path: str, line_start: int, line_end: int, kind: str,
               reason: str = "") -> None:
        self.permitted.append(PermittedEdit(path, line_start, line_end, kind, reason))

    def note(self, what: str) -> None:
        self.history.append(what)

    def edit_after_baseline(self, path: str, text: Optional[str]) -> None:
        """Change `path` once the target has a memory of the world without
        the change. `None` deletes it."""
        self.after_baseline.append((path, text))

    # ------------------------------------------------------------ reading

    def line_of(self, path: str, needle: str) -> int:
        """The 1-based line in `path` containing `needle`, exactly once.

        Raises when it is absent or repeated. A mutator that cannot find its
        own anchor has misunderstood the document, and guessing a line number
        would put ground truth on a span that is not the claim.
        """
        text = self.files.get(path)
        if text is None:
            raise KeyError("no such file in the draft: %s" % path)
        hits = [i for i, line in enumerate(text.splitlines(), 1) if needle in line]
        if len(hits) != 1:
            raise ValueError("%r appears %d times in %s, expected once"
                             % (needle, len(hits), path))
        return hits[0]

    def protected_text(self, region: ProtectedRegion) -> str:
        text = self.files.get(region.path, "")
        if region.line_start is None:
            return text
        lines = text.splitlines()
        return "\n".join(lines[region.line_start - 1:(region.line_end or region.line_start)])


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
