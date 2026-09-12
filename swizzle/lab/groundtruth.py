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
            "expected_final_state": dict(self.expected_final_state),
            "repository_files": sorted(self.repository_files),
            "outside_state": dict(self.outside_state),
            "facts": dict(self.facts),
            "construction": list(self.construction),
        }


def of(draft: WorldDraft) -> GroundTruth:
    """Freeze what the draft accumulated while it was being built."""
    movable = {edit.path for edit in draft.permitted}
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
        expected_final_state={path: sha256(text)
                              for path, text in sorted(draft.files.items())
                              if path not in movable},
        repository_files=frozenset(draft.files) | {link for link, _, _ in draft.symlinks},
        outside_state={path: sha256(text) for path, text in sorted(draft.bait.items())},
        facts=dict(draft.facts),
        construction=tuple(draft.history),
    )
