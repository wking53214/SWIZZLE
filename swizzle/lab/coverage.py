"""Which of the target's mechanisms are actually being attacked.

A mutation count is not coverage. Thirty mutations that all land on one
predicate tell you about one predicate. This matrix maps the target's
SURFACES -- the mechanisms a repository-level modification system has to
get right -- against the mutators aimed at each and the attacks actually
found there, so an empty row is visible.

An empty row is the useful output. It says "nothing in this laboratory has
ever tested that", which is the one thing a coverage report can tell you
that a pass rate cannot.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from .attack import CaseResult
from .genome import AttackCategory
from .mutators import registry
from .signals import Severity, failure_class

#: The mechanisms under attack, described in terms any autonomous
#: modification system has rather than in Ghost's vocabulary.
SURFACES: Dict[str, str] = {
    "claim shape": "deciding what a sentence asserts, and about what",
    "writability": "deciding whether a machine may rewrite a piece of text",
    "identity": "deciding that two findings are or are not the same finding",
    "ledger": "the record the tool keeps of what it did",
    "annotation": "text the tool writes into the repository on its own account",
    "baseline": "what the tool remembers between runs",
    "temporal": "whether a diagnosis is still valid when it is acted on",
    "scope": "which files are inside the thing being modified",
    "verification": "the check that the write did what was intended",
}

#: Which surface each attack category exercises. A category may touch more
#: than one; composition touches whatever its members touch.
_CATEGORY_SURFACES: Dict[str, Tuple[str, ...]] = {
    AttackCategory.CLAIM_SHAPE.value: ("claim shape", "writability"),
    AttackCategory.WRITABILITY.value: ("writability", "verification", "annotation"),
    AttackCategory.IDENTITY.value: ("identity", "baseline"),
    AttackCategory.BASELINE.value: ("baseline", "ledger"),
    AttackCategory.TEMPORAL.value: ("temporal", "verification"),
    AttackCategory.SCOPE.value: ("scope", "annotation"),
    AttackCategory.VERIFICATION.value: ("verification",),
    AttackCategory.COMPOSITION.value: ("writability", "scope", "verification"),
    AttackCategory.CRASH.value: ("ledger", "verification"),
    AttackCategory.CONCURRENCY.value: ("temporal",),
    AttackCategory.CONTROL.value: (),
}

_FAILURE_SURFACES: Dict[str, str] = {
    "identity_drift": "identity",
    "false_memory": "baseline",
    "unauthorised_mutation": "writability",
    "escape": "scope",
    "unattributable_change": "scope",
    "stale_action": "temporal",
    "record_mismatch": "ledger",
    "collateral_damage": "verification",
    "over_caution": "writability",
    "stray_output": "annotation",
}


def surfaces_of(mutator_name: str) -> Tuple[str, ...]:
    """Which of the target's mechanisms this mutator can reach."""
    mutator = registry().get(mutator_name)
    if mutator is None:
        return ()
    return _CATEGORY_SURFACES.get(mutator.category.value, ())


def unexercised(table: Mapping[str, Mapping[str, Any]]) -> Tuple[str, ...]:
    """Surfaces no case has landed on.

    Not "surfaces that scored badly". A surface with no cases has no
    measurement at all, which is the same kind of ignorance `knowledge.py`
    labels ZERO_BASE and must be reached the same way -- by spending budget
    on it BECAUSE it is unknown, not by giving it an invented weight.
    """
    return tuple(surface for surface, row in table.items()
                 if not row.get("cases"))


def matrix(results: Sequence[CaseResult] = ()) -> Dict[str, Dict[str, Any]]:
    """Surface -> mutators aimed at it, cases run, attacks found."""
    out: Dict[str, Dict[str, Any]] = {
        surface: {"description": description, "mutators": [], "cases": 0,
                  "attacks": 0, "critical": 0}
        for surface, description in SURFACES.items()
    }
    for name, mutator in sorted(registry().items()):
        for surface in _CATEGORY_SURFACES.get(mutator.category.value, ()):
            out[surface]["mutators"].append(name)

    for result in results:
        surfaces = set(_CATEGORY_SURFACES.get(result.genome.category.value, ()))
        for signal in result.violations:
            surface = _FAILURE_SURFACES.get(failure_class(signal.kind))
            if surface:
                surfaces.add(surface)
        for surface in surfaces:
            row = out.setdefault(surface, {"description": "", "mutators": [],
                                           "cases": 0, "attacks": 0, "critical": 0})
            row["cases"] += 1
            row["attacks"] += int(result.fitness.interesting)
            row["critical"] += int(result.fitness.top is Severity.CRITICAL)
    return out


def render(table: Mapping[str, Mapping[str, Any]]) -> str:
    lines = ["SWIZZLE MUTATION COVERAGE", "=" * 78, "",
             "%-14s %-9s %-7s %-9s %s" % ("surface", "mutators", "cases",
                                          "attacks", "what it is"),
             "-" * 78]
    for surface, row in table.items():
        lines.append("%-14s %-9d %-7d %-9d %s"
                     % (surface, len(row["mutators"]), row["cases"],
                        row["attacks"], row["description"][:34]))
    untested = [s for s, row in table.items() if row["cases"] == 0]
    lines.append("")
    if untested:
        lines.append("Never exercised: " + ", ".join(untested))
        lines.append("An empty row is the point of this table. It is the one "
                     "thing a pass rate")
        lines.append("cannot tell you: that nothing here has ever been tested.")
    else:
        lines.append("Every surface has been exercised at least once.")
    lines.append("")
    return "\n".join(lines)
