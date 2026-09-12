"""The attack report: one for a person, one for a machine, from the same facts.

A report that cannot be acted on is not a finding. Each report answers, in
order, the questions a reader actually has: what was attacked, what was
expected, what happened instead, what the evidence is, how small the case
is, and what to type to see it again.
"""

from __future__ import annotations

import json
import textwrap
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .attack import CaseResult
from .fitness import corroboration
from .minimize import Minimisation
from .signals import Judgement, Severity, failure_class

WIDTH = 74


def attack_report(result: CaseResult,
                  minimisation: Optional[Minimisation] = None,
                  corpus_path: str = "") -> str:
    """The human report for one case."""
    genome = result.genome
    lines: List[str] = []
    lines.append("SWIZZLE ATTACK REPORT")
    lines.append("=" * WIDTH)
    lines.append("")
    lines.append(_field("Target", "%s %s at %s"
                        % (result.target_version.get("target", "?"),
                           result.target_version.get("package_version", "?"),
                           result.target_version.get("commit", "?")[:10])))
    lines.append(_field("Case", genome.name))
    lines.append(_field("Category", genome.category.value))
    lines.append(_field("Genome", genome.digest() + "  (seed %d)" % genome.seed))
    lines.append("")

    if result.broken:
        lines.append(_field("Result", "NOT MEASURED"))
        lines.append(_field("Why", result.broken))
        lines.append("")
        lines.append("A run that could not be completed is never reported as an "
                     "attack.")
        return "\n".join(lines)

    top = result.fitness.top
    lines.append(_field("Severity", top.name if result.fitness.interesting else "none"))
    lines.append(_field("Expected", "ABSTAIN" if result.ground_truth.expected_abstention
                        else "act only within %d authorised edit(s)"
                             % len(result.ground_truth.permitted_edits)))
    acted = result.evidence.target_acted
    lines.append(_field("Observed", "MUTATE (%d path(s))" % len(result.evidence.changed()
                                                                or result.evidence.changed(working=True))
                        if acted else "ABSTAIN"))
    lines.append(_field("Verdict", "the target violated an invariant it states"
                        if result.fitness.interesting
                        else "no violation: the target handled this case"))
    lines.append("")

    lines.append("Hypothesis")
    lines.append("-" * WIDTH)
    lines.append(_wrap(genome.hypothesis, 2))
    lines.append("")

    lines.append("Construction")
    lines.append("-" * WIDTH)
    for step in result.ground_truth.construction or ("(no mutations; the base "
                                                     "world is the case)",):
        lines.append("  %s" % step)
    lines.append("")

    if result.violations:
        lines.append("Evidence")
        lines.append("-" * WIDTH)
        for signal in sorted(result.violations, key=lambda s: -int(s.severity)):
            lines.append("  [%s] %s  (%s oracle)"
                         % (signal.severity.name, signal.kind, signal.oracle))
            lines.append(_wrap(signal.summary, 6))
            if signal.detail:
                lines.append(_wrap(signal.detail, 6))
            lines.append("")
        agreement = corroboration(result.signals)
        lines.append("  Corroboration")
        for name, count in agreement.items():
            mark = "confirmed" if count >= 2 else "single oracle"
            lines.append("    %-26s %d oracle(s)  %s" % (name, count, mark))
        lines.append("")

    if result.inconclusive:
        lines.append("Inconclusive")
        lines.append("-" * WIDTH)
        for signal in result.inconclusive:
            lines.append("  %s (%s): %s" % (signal.kind, signal.oracle, signal.summary))
        lines.append("")

    changed = result.evidence.changed() or result.evidence.changed(working=True)
    if changed:
        lines.append("What moved")
        lines.append("-" * WIDTH)
        for path, verb in sorted(changed.items()):
            lines.append("  %-8s %s" % (verb, path))
        if result.evidence.act and result.evidence.act.claimed_changes:
            lines.append("")
            lines.append("  The target's own account:")
            for claim in result.evidence.act.claimed_changes:
                lines.append("    %s" % claim)
        lines.append("")

    if minimisation is not None:
        lines.append("Minimised case")
        lines.append("-" * WIDTH)
        lines.append("  %d of %d reductions held; size %d -> %d (ratio %.2f)%s"
                     % (minimisation.steps_kept, minimisation.steps_tried,
                        _size(minimisation.original), _size(minimisation.minimal),
                        minimisation.ratio,
                        "; budget exhausted" if minimisation.exhausted else ""))
        for step in minimisation.removed:
            lines.append("    removed: %s" % step)
        lines.append("")
        lines.append("  This is LOCALLY minimal: every single reduction the "
                     "minimiser knows")
        lines.append("  how to make was tried and each one destroyed the failure.")
        lines.append("")

    if corpus_path:
        lines.append(_field("Archived", corpus_path))
    lines.append(_field("Reproduce", "swizzle reproduce %s" % genome.name))
    lines.append("")
    return "\n".join(lines)


def summary_table(results: Sequence[CaseResult]) -> str:
    lines = ["%-38s %-9s %-20s %s" % ("case", "severity", "signals", "corroborated"),
             "-" * WIDTH]
    for result in results:
        if result.broken:
            lines.append("%-38s %-9s %s" % (result.genome.name[:38], "BROKEN",
                                            result.broken[:40]))
            continue
        lines.append("%-38s %-9s %-20s %s"
                     % (result.genome.name[:38],
                        result.fitness.top.name if result.fitness.interesting else "pass",
                        result.fitness.render(),
                        ", ".join(result.corroborated) or "-"))
    return "\n".join(lines)


def machine_report(results: Sequence[CaseResult],
                   minimisations: Mapping[str, Minimisation] = (),
                   scorecard: Optional[Mapping[str, Any]] = None) -> str:
    """Stable JSON. The key set does not change between runs."""
    minimisations = dict(minimisations or {})
    payload = {
        "schema": "swizzle.attack-report.v1",
        "cases": [_case_json(r, minimisations.get(r.genome.name)) for r in results],
        "scorecard": dict(scorecard) if scorecard else None,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _case_json(result: CaseResult, minimisation: Optional[Minimisation]) -> Dict[str, Any]:
    out = dict(result.to_dict())
    out["minimisation"] = minimisation.to_dict() if minimisation else None
    return out


def _field(name: str, value: str) -> str:
    return "%-11s %s" % (name + ":", value)


def _wrap(text: str, indent: int) -> str:
    pad = " " * indent
    return "\n".join(textwrap.fill(paragraph, width=WIDTH - indent,
                                   initial_indent=pad, subsequent_indent=pad)
                     for paragraph in (text or "").split("\n\n"))


def _size(genome) -> int:
    from .minimize import _size as measure
    return measure(genome)
