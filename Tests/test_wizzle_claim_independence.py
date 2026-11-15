"""The target's claimed severity may change the verdict, never the ceiling.

The ceiling (maximum justified severity) is the warrant. If the claim could
move it, the claim would be establishing its own justification.
"""

import pytest

from swizzle.wizzle.epistemic_model import IntentKind, SemanticCorrectness
from swizzle.wizzle.evidence_entitlement import (
    EvidenceCategory,
    EvidenceEntitlementEvaluator,
)

SEVERITIES = ["INFORMATIONAL", "MINOR", "MAJOR", "CRITICAL"]
ORDER = {s: i for i, s in enumerate(SEVERITIES, start=1)}

PRESENT = {
    EvidenceCategory.MEMBER_PRODUCTION_HISTORY,
    EvidenceCategory.MEMBER_REMOVAL_HISTORY,
    EvidenceCategory.MEMBER_CURRENT_STATE,
}


def _evaluate(intent: IntentKind, claim: str):
    return EvidenceEntitlementEvaluator.evaluate_entitlement(
        conclusion="REMOVED_FROM_LIBRARY",
        intent_kind=intent,
        evidence_present=set(PRESENT),
        evidence_absent=set(),
        evidence_weak=set(),
        evidence_contradicting=set(),
        ghost_severity=claim,
    )


@pytest.mark.parametrize(
    "intent",
    [
        IntentKind.INTENTIONAL_REFACTOR,
        IntentKind.ACCIDENTAL_REMOVAL,
        IntentKind.SECURITY_FIX,
        IntentKind.UNKNOWN_INTENT,
    ],
)
def test_ceiling_and_entitlement_do_not_depend_on_the_claim(intent):
    verdicts = [_evaluate(intent, claim) for claim in SEVERITIES]

    assert len({v.maximum_justified_severity for v in verdicts}) == 1
    assert len({v.is_entitled for v in verdicts}) == 1
    assert len({frozenset(v.supporting_evidence) for v in verdicts}) == 1


@pytest.mark.parametrize(
    "intent",
    [
        IntentKind.INTENTIONAL_REFACTOR,
        IntentKind.ACCIDENTAL_REMOVAL,
        IntentKind.UNKNOWN_INTENT,
    ],
)
def test_overclaim_is_exactly_the_claims_that_exceed_the_ceiling(intent):
    ceiling = _evaluate(intent, "INFORMATIONAL").maximum_justified_severity

    for claim in SEVERITIES:
        verdict = _evaluate(intent, claim)
        exceeds = ORDER[claim] > ORDER[ceiling]
        overclaimed = verdict.semantic_correctness == SemanticCorrectness.OVERCLAIMED
        assert overclaimed == exceeds, (intent.name, claim, ceiling)


def test_an_inflated_claim_cannot_raise_its_own_ceiling():
    honest = _evaluate(IntentKind.INTENTIONAL_REFACTOR, "MINOR")
    inflated = _evaluate(IntentKind.INTENTIONAL_REFACTOR, "CRITICAL")

    assert inflated.maximum_justified_severity == honest.maximum_justified_severity
    assert honest.semantic_correctness != SemanticCorrectness.OVERCLAIMED
    assert inflated.semantic_correctness == SemanticCorrectness.OVERCLAIMED
