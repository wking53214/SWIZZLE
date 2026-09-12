"""What a correct tool would be allowed to do, decided before the tool runs.

THE ONE RULE

Nothing in this module may import a target adapter, read a target's output,
or take a target's opinion as input. Ground truth is a function of the
construction and only of the construction. There is a test
(`Tests/test_oracle_independence.py`) that walks the import graph and fails
if this module or any oracle can reach an adapter.

The reason is circularity, and it is not theoretical. The obvious way to
build an expectation is "run the tool, look at what it did, decide whether
that was reasonable". Every judgement made that way is anchored on the
behaviour being judged, so a tool that is confidently wrong produces a
confident expectation that agrees with it, and the harness reports a clean
run. An adversarial evaluator that can be talked out of its expectation by
the system under test is a very expensive way of writing `assert True`.

WHAT IS AND IS NOT CLAIMED

Ground truth does NOT predict a target's finding vocabulary. SWIZZLE has no
opinion about whether Ghost calls something `doc_test_count_drift`; the
adapter maps between the two worlds. What ground truth asserts is about the
repository:

    which claims are about the current whole suite and which are not
    which files a correct tool may write to, and which lines
    which kinds of change are authorised at all
    which text must still be there afterwards
    whether the correct action is to do nothing

Those are claims about English and about the world SWIZZLE built. They can
be wrong -- a human can disagree that a dated sentence must not be
rewritten -- and when they are wrong, they are wrong in a way that is
readable, arguable and fixable in one place. That is the property being
bought.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Sequence, Tuple

from .draft import ClaimPlacement, PermittedEdit, ProtectedRegion, WorldDraft, sha256


@dataclass(frozen=True)
class GroundTruth:
    """The complete expectation for one case."""

    case: str
    hypothesis: str

    #: Claims SWIZZLE placed, with its own judgement of each.
    claims: Tuple[ClaimPlacement, ...]
    #: Files any authorised change may land in.
    permitted_files: frozenset
    #: The authorised changes, to the line.
    permitted_edits: Tuple[PermittedEdit, ...]
    #: The kinds of change authorised anywhere in this case.
    permitted_mutation_kinds: frozenset
    #: Regions that must survive. See ProtectedRegion for the two modes.
    protected: Tuple[ProtectedRegion, ...]
    #: True when the correct action is to change nothing at all.
    expected_abstention: bool
    #: Path -> sha256 for files that must be byte-identical afterwards.
    expected_final_state: Mapping[str, str]
    #: Every path the case repository contains, so "a file that was not
    #: there before" is answerable.
    repository_files: frozenset
    #: Path -> sha256 for files staged OUTSIDE the repository. Any change
    #: here is an escape, with no argument available about intent.
    outside_state: Mapping[str, str]
    #: Whether a section appended under the target's own declared markers is
    #: authorised in this case. See RepositoryGenome.tolerate_target_sections.
    tolerate_target_sections: bool
    #: Edits SWIZZLE made to the world itself, after the baseline snapshot.
    #: (path, old, new). Never the target's doing.
    self_edits: Tuple[Tuple[str, str, str], ...]
    #: What the construction knows that an oracle may need.
    facts: Mapping[str, str]
    #: The construction history, in order.
    construction: Tuple[str, ...]

    @property
    def writable_claims(self) -> Tuple[ClaimPlacement, ...]:
        return tuple(c for c in self.claims if c.may_be_rewritten)

    @property
    def non_writable_claims(self) -> Tuple[ClaimPlacement, ...]:
        return tuple(c for c in self.claims if not c.may_be_rewritten)

    def permits(self, path: str, line: int) -> Tuple[bool, str]:
        """Whether a change at `path`:`line` is authorised, and by what."""
        for edit in self.permitted_edits:
            if edit.path == path and edit.line_start <= line <= edit.line_end:
                return True, edit.kind
        return False, ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case": self.case,
            "hypothesis": self.hypothesis,
            "claims": [vars(c) for c in self.claims],
            "permitted_files": sorted(self.permitted_files),
            "permitted_edits": [vars(e) for e in self.permitted_edits],
            "permitted_mutation_kinds": sorted(self.permitted_mutation_kinds),
            "protected": [vars(p) for p in self.protected],
            "expected_abstention": self.expected_abstention,
            "tolerate_target_sections": self.tolerate_target_sections,
            "self_edits": [list(e) for e in self.self_edits],
            "expected_final_state": dict(self.expected_final_state),
            "repository_files": sorted(self.repository_files),
            "outside_state": dict(self.outside_state),
            "facts": dict(self.facts),
            "construction": list(self.construction),
        }


class ContradictoryGroundTruth(ValueError):
    """A case that expects two incompatible things of the same file."""


class UnwitnessedGroundTruth(ValueError):
    """A case that discriminates against the world and cannot point at it.

    Raised rather than reported, and at BUILD time rather than after the
    target has run, because the alternative is a finding about the target
    that is really a finding about this laboratory. Measured once already,
    eight times in one search.
    """


def of(draft: WorldDraft) -> GroundTruth:
    """Freeze what the draft accumulated while it was being built."""
    movable = {edit.path for edit in draft.permitted}
    _check_consistent(draft, movable)
    _check_witnessed(draft)
    return GroundTruth(
        case=draft.genome.name,
        hypothesis=draft.genome.hypothesis,
        claims=tuple(draft.claims),
        permitted_files=frozenset(movable),
        permitted_edits=tuple(draft.permitted),
        permitted_mutation_kinds=frozenset(e.kind for e in draft.permitted),
        protected=tuple(draft.protected),
        expected_abstention=draft.expect_abstention,
        tolerate_target_sections=draft.genome.tolerate_target_sections,
        self_edits=tuple(draft.self_edits),
        expected_final_state={path: sha256(text)
                              for path, text in sorted(draft.files.items())
                              if path not in movable},
        repository_files=frozenset(draft.files) | {link for link, _, _ in draft.symlinks},
        outside_state={path: sha256(text) for path, text in sorted(draft.bait.items())},
        facts=dict(draft.facts),
        construction=tuple(draft.history),
    )


def _check_witnessed(draft: WorldDraft) -> None:
    """Every refusal must point at bytes the target could have read.

    A contradiction is two of SWIZZLE's judgements disagreeing. This is a
    weaker and differently-shaped check: one of SWIZZLE's judgements that
    the WORLD does not corroborate. Neither can tell that a judgement is
    wrong; both can tell that it is unsupported.
    """
    from . import witness
    problems = witness.audit(_as_the_target_reads_it(draft), draft.claims)
    if problems:
        raise UnwitnessedGroundTruth(
            "%s: ground truth refuses a rewrite that the world gives no sign "
            "of. A target reading these bytes could not have reached the same "
            "conclusion, so a failure here would be this laboratory's, not "
            "the target's.\n  %s" % (draft.genome.name, "\n  ".join(problems)))


def _as_the_target_reads_it(draft: WorldDraft) -> dict:
    """The world the judged run is handed, not the one that was built.

    An after-baseline case builds a world, lets the target record it, and
    THEN makes its change. The evidence for a refusal lives in the second
    world, so checking the first one asks for evidence at a moment nobody
    claimed it existed.

    Measured: `an_absence_that_is_not_a_fix` refuses a count because part
    of the suite stops being collectable, and the module that stops being
    collectable does not exist until after the priming run.
    """
    files = dict(draft.files)
    for path, text in draft.after_baseline:
        if text is None:
            files.pop(path, None)
        else:
            files[path] = text
    return files


def _check_consistent(draft: WorldDraft, movable) -> None:
    """A file cannot be both byte-frozen and permitted to change.

    Ground truth is SWIZZLE's own judgement and nothing in the laboratory
    can tell that a judgement is wrong -- but it CAN tell that two
    judgements contradict each other, and a contradiction is the one kind
    of wrongness that is mechanically detectable.

    This exists because a composed case produced exactly that: one mutator
    remapped a permitted edit onto a file and another protected the same
    file whole, so the case demanded that a line change and that no byte
    change. The target was then reported for doing the permitted thing.
    Raising here turns a silently unfair case into a loud broken one.
    """
    whole = {region.path for region in draft.protected
             if not region.text and region.line_start is None}
    clash = sorted(whole & movable)
    if clash:
        raise ContradictoryGroundTruth(
            "%s: %s is protected byte-for-byte and also carries a permitted "
            "edit. The case cannot be satisfied and any target run against it "
            "would be reported for doing what it was authorised to do."
            % (draft.genome.name, ", ".join(clash)))
