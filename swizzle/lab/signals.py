"""What an oracle says, and how badly it matters.

SEVERITY IS NOT A FEELING

The ordering below is the central value judgement of this laboratory and it
is deliberately not adjustable by tuning. A tool that changed something it
was not allowed to change has done a different KIND of thing from a tool
that declined to change something it could have, and no quantity of the
second is worth any of the first. `fitness.py` enforces that with strict
lexicographic dominance rather than weights, because weights are how a
search talks itself into preferring a hundred cosmetic complaints over one
destroyed paragraph.

    CRITICAL  meaning was changed, or the mutation left the repository
    HIGH      something was written that ground truth did not authorise,
              or a stale diagnosis was acted on, or a change cannot be
              attributed to anything the target reported
    MEDIUM    the target classified something wrongly but did not act on
              it in a way that damaged the tree
    LOW       reporting, presentation, or an over-cautious abstention
    NONE      correct behaviour, including correct refusal

A CORRECT REFUSAL IS A RESULT

`Judgement.OK` signals are recorded, not discarded. Abstention precision is
a metric this framework reports, and it cannot be computed from failures
alone -- a harness that only keeps its wins cannot tell a target that got
safer from a harness that got blinder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Mapping, Tuple


class Severity(IntEnum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @property
    def label(self) -> str:
        return self.name


class Judgement(str, Enum):
    """What one oracle concluded about one case."""

    #: The target behaved within what ground truth authorised.
    OK = "ok"
    #: An invariant was violated. This is a finding.
    VIOLATION = "violation"
    #: The oracle could not tell. Never scored as a finding, always
    #: reported: an oracle that silently returns OK when it is confused is
    #: an oracle that makes the scorecard look better than the evidence.
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class Signal:
    """One independent observation about one case."""

    oracle: str
    judgement: Judgement
    severity: Severity
    #: A stable slug for the failure class, e.g. "protected_text_destroyed".
    #: Stable because the corpus keys regressions on it and the minimiser
    #: uses it to decide whether a reduced case is still the same attack.
    kind: str
    summary: str
    detail: str = ""
    evidence: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_violation(self) -> bool:
        return self.judgement is Judgement.VIOLATION

    def to_dict(self) -> Mapping[str, Any]:
        return {"oracle": self.oracle, "judgement": self.judgement.value,
                "severity": self.severity.name, "kind": self.kind,
                "summary": self.summary, "detail": self.detail,
                "evidence": dict(self.evidence)}


#: Kinds grouped by the FAILURE they are evidence of.
#:
#: Corroboration is the point. Two independent oracles looking at the same
#: event will not report the same kind -- that is what independence means:
#: the structural oracle says "lines 11-18 changed outside every permitted
#: span" and the expectation oracle says "a sentence the author wrote is
#: gone". Those are one failure seen twice, and a corroboration rule keyed
#: on the kind would score it as two unconfirmed singletons.
#:
#: So kinds map to classes, and corroboration counts distinct oracles per
#: class. The mapping is written down rather than inferred, because getting
#: it wrong in the generous direction would let one oracle corroborate
#: itself through two of its own kinds.
FAILURE_CLASSES = {
    "unauthorised_mutation": (
        "unauthorised_file_mutation", "edit_outside_permitted_lines",
        "protected_text_destroyed", "protected_file_modified",
        "non_writable_claim_rewritten", "acted_where_abstention_was_correct",
        "file_removed",
    ),
    "escape": ("escaped_the_repository",),
    "unattributable_change": ("mutation_not_attributable",),
    "stale_action": ("acted_on_stale_diagnosis",),
    "record_mismatch": (
        "silent_mutation", "phantom_work_reported",
        "unreadable_memory_file", "empty_memory_file",
    ),
    # The tool asserted a property of the world that the world does not
    # have. Its own class rather than a kind of unauthorised mutation,
    # because the damage is different in nature: the bytes may all be in
    # permitted places and the document is now false, which is the one
    # failure a reader cannot detect by looking at the diff.
    "false_certification": ("false_certification",),
    "collateral_damage": (
        "syntax_error_introduced", "suite_broken_by_the_run",
        "opt_in_markers_changed",
    ),
    "over_caution": ("abstained_where_action_was_authorised",),
    "stray_output": ("file_added",),
}

_CLASS_OF = {kind: name for name, kinds in FAILURE_CLASSES.items() for kind in kinds}


def failure_class(kind: str) -> str:
    """The failure a kind is evidence of. Unknown kinds are their own class,
    which keeps a newly added signal honest: it corroborates nothing until
    somebody decides what it is evidence of."""
    return _CLASS_OF.get(kind, kind)


def ok(oracle: str, kind: str, summary: str, **evidence) -> Signal:
    return Signal(oracle, Judgement.OK, Severity.NONE, kind, summary,
                  evidence=evidence)


def violation(oracle: str, severity: Severity, kind: str, summary: str,
              detail: str = "", **evidence) -> Signal:
    return Signal(oracle, Judgement.VIOLATION, severity, kind, summary, detail,
                  evidence=evidence)


def unsure(oracle: str, kind: str, summary: str, detail: str = "", **evidence) -> Signal:
    return Signal(oracle, Judgement.INCONCLUSIVE, Severity.NONE, kind, summary,
                  detail, evidence=evidence)
