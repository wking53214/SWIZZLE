"""Two versions of a target, the same worlds, and what changed between them.

The question a maintainer actually has is not "does my tool fail this
case". It is "did the change I just made fix anything, break anything, or
quietly trade one failure for another". That needs the same genomes run
against two revisions and the outcomes compared per case.

FIVE OUTCOMES, AND THE FOURTH IS THE ONE PEOPLE MISS

    fixed        failed before, passes now
    regressed    passed before, fails now
    unchanged    same failure classes, same top severity
    worsened     still fails, and at a higher severity or with a new class
    improved     still fails, but with less of it

`worsened` and `improved` exist because "still failing" is not one state.
A fix that turns a CRITICAL into a MEDIUM is progress and a report that
buckets it with "unchanged" hides the only thing that happened.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from . import attack as attack_module
from .adapter import TargetAdapter
from .attack import CaseResult
from .genome import RepositoryGenome
from .signals import Severity, failure_class

OUTCOMES = ("fixed", "regressed", "unchanged", "worsened", "improved",
            "not_measured")


@dataclass(frozen=True)
class CaseComparison:
    case: str
    outcome: str
    before_severity: str
    after_severity: str
    before_classes: Tuple[str, ...]
    after_classes: Tuple[str, ...]
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"case": self.case, "outcome": self.outcome,
                "before": {"severity": self.before_severity,
                           "classes": list(self.before_classes)},
                "after": {"severity": self.after_severity,
                          "classes": list(self.after_classes)},
                "note": self.note}


@dataclass(frozen=True)
class Differential:
    baseline_version: Mapping[str, str]
    candidate_version: Mapping[str, str]
    comparisons: Tuple[CaseComparison, ...]
    seconds: float

    def counts(self) -> Dict[str, int]:
        out = {name: 0 for name in OUTCOMES}
        for comparison in self.comparisons:
            out[comparison.outcome] = out.get(comparison.outcome, 0) + 1
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": "swizzle.differential.v1",
            "baseline": dict(self.baseline_version),
            "candidate": dict(self.candidate_version),
            "counts": self.counts(),
            "cases": [c.to_dict() for c in self.comparisons],
            "seconds": round(self.seconds, 1),
        }

    def render(self) -> str:
        lines = ["SWIZZLE DIFFERENTIAL", "=" * 66, ""]
        lines.append("  baseline   %s at %s"
                     % (self.baseline_version.get("package_version", "?"),
                        self.baseline_version.get("commit", "?")[:10]))
        lines.append("  candidate  %s at %s"
                     % (self.candidate_version.get("package_version", "?"),
                        self.candidate_version.get("commit", "?")[:10]))
        lines.append("")
        counts = self.counts()
        for name in OUTCOMES:
            if counts.get(name):
                lines.append("  %-12s %d" % (name, counts[name]))
        lines.append("")
        for comparison in self.comparisons:
            if comparison.outcome == "unchanged":
                continue
            lines.append("  %-10s %-34s %s -> %s"
                         % (comparison.outcome, comparison.case[:34],
                            comparison.before_severity, comparison.after_severity))
            if comparison.note:
                lines.append("             %s" % comparison.note)
        lines.append("")
        return "\n".join(lines)


def compare(genomes: Sequence[RepositoryGenome], baseline: TargetAdapter,
            candidate: TargetAdapter, *, timeout: float = 900.0,
            on_case=None) -> Differential:
    """Run every genome against both targets and classify each difference."""
    started = time.perf_counter()
    comparisons: List[CaseComparison] = []
    for genome in genomes:
        before = attack_module.run(genome, baseline, timeout=timeout)
        after = attack_module.run(genome, candidate, timeout=timeout)
        comparison = classify(genome.name, before, after)
        comparisons.append(comparison)
        if on_case:
            on_case(comparison)
    return Differential(baseline_version=dict(baseline.version()),
                        candidate_version=dict(candidate.version()),
                        comparisons=tuple(comparisons),
                        seconds=time.perf_counter() - started)


def classify(name: str, before: CaseResult, after: CaseResult) -> CaseComparison:
    if before.broken or after.broken:
        return CaseComparison(name, "not_measured",
                              before.fitness.top.name, after.fitness.top.name,
                              (), (),
                              note=before.broken or after.broken)
    before_classes = tuple(sorted({failure_class(s.kind) for s in before.violations}))
    after_classes = tuple(sorted({failure_class(s.kind) for s in after.violations}))
    before_top, after_top = before.fitness.top, after.fitness.top

    if before.fitness.interesting and not after.fitness.interesting:
        outcome, note = "fixed", "the candidate no longer violates anything here"
    elif not before.fitness.interesting and after.fitness.interesting:
        outcome, note = "regressed", "new failure: " + ", ".join(after_classes)
    elif not before.fitness.interesting and not after.fitness.interesting:
        outcome, note = "unchanged", ""
    elif after_top > before_top or set(after_classes) - set(before_classes):
        outcome = "worsened"
        new = sorted(set(after_classes) - set(before_classes))
        note = ("higher severity" if after_top > before_top else "") + (
            ("; new class: " + ", ".join(new)) if new else "")
    elif after_top < before_top or set(before_classes) - set(after_classes):
        outcome = "improved"
        gone = sorted(set(before_classes) - set(after_classes))
        note = ("lower severity" if after_top < before_top else "") + (
            ("; no longer: " + ", ".join(gone)) if gone else "")
    else:
        outcome, note = "unchanged", ""
    return CaseComparison(name, outcome, before_top.name, after_top.name,
                          before_classes, after_classes, note)
