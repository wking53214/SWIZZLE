"""Test the canonical counterexample: factually correct, semantically overclaimed.

This is WIZZLE's core scientific artifact:

Ghost observes: "Member removed from production"
Ghost concludes: "MAJOR regression"

WIZZLE verifies:
- Factual: CORRECT (member really was removed)
- Semantic: OVERCLAIMED (evidence does not justify MAJOR severity)
- Action: NOT_ENTITLED (should not autonomously modify based on this)

This test demonstrates that observation ≠ interpretation ≠ conclusion ≠ action entitlement.
"""

import pytest
import tempfile
from pathlib import Path
from .ghost_invoker import GhostInvoker, GhostFinding, GhostAnalysis
from .evaluator import Evaluator
from .epistemic_model import (
    IntentKind, SemanticCorrectness, FactualCorrectness, GhostObservation
)
from .evidence_entitlement import EvidenceEntitlementEvaluator, EvidenceCategory
from .action_entitlement import ActionEntitlementOracle, ActionEntitlementVerdict


def test_canonical_counterexample_overclaim():
    """WIZZLE's core case: factually correct but semantically overclaimed conclusion.

    Scenario: An enum member is intentionally removed during refactoring.
    - Member existed in production (historical fact)
    - Member was removed intentionally (intent signal in commit message)
    - Member remains in tests (only for backwards-compatible import)
    - No evidence of regression, unintended removal, or semantic breakage

    Ghost's finding:
    - Category: REMOVED_FROM_LIBRARY
    - Severity: MAJOR
    - Confidence: 0.7

    WIZZLE's assessment:
    - Factual correctness: CORRECT (member really was removed)
    - Semantic correctness: OVERCLAIMED (MAJOR not justified for intentional refactor)
    - Action entitlement: NOT_ENTITLED (should not autonomously act)
    """

    # Simulate Ghost finding
    ghost_finding = GhostFinding(
        member_name="LegacyStatus",
        file_path="enums.py",
        severity="MAJOR",
        category="REMOVED_FROM_LIBRARY",
        message="LegacyStatus removed from production code but remains in test imports",
        metadata={
            "confidence": 0.7,
            "removed_in_commit": "abc1234",
            "still_in_tests": True
        }
    )

    # Simulate oracle assessment (independent of Ghost)
    oracle_results = {
        "history": {
            "oracle": "HistoryOracle",
            "inferred_intent": IntentKind.INTENTIONAL_REFACTOR.name,
            "confidence": 0.8,
            "evidence": {
                "commit_messages": ["refactor: remove legacy status enum"]
            }
        },
        "current_state": {
            "oracle": "CurrentStateOracle",
            "members_in_production": [],  # Member gone from production
            "members_in_tests": ["LegacyStatus"],  # But remains in tests
            "members_in_both": []
        }
    }

    # Convert to Ghost observation
    ghost_obs = GhostObservation(
        member_name=ghost_finding.member_name,
        provenance_class=ghost_finding.category,
        severity=ghost_finding.severity,
        evidence_cited=[ghost_finding.message]
    )

    # Evaluate factual correctness
    # Member is absent from production (factual claim is correct)
    members_in_prod = oracle_results["current_state"]["members_in_production"]
    factual_correctness = (
        FactualCorrectness.CORRECT
        if ghost_obs.member_name not in members_in_prod
        else FactualCorrectness.INCORRECT
    )
    assert factual_correctness == FactualCorrectness.CORRECT

    # Evaluate semantic correctness using Evidence Entitlement
    # The key: MAJOR severity is NOT justified for intentional refactoring
    present_evidence = {
        EvidenceCategory.MEMBER_PRODUCTION_HISTORY,    # Was used in production
        EvidenceCategory.MEMBER_REMOVAL_HISTORY,       # Was removed
        EvidenceCategory.MEMBER_CURRENT_STATE,         # Currently absent
        EvidenceCategory.INTENTIONAL_SIGNAL            # Intent signal (commit message)
    }
    absent_evidence = set()  # No evidence of accidental removal, no evidence of regression

    verdict = EvidenceEntitlementEvaluator.evaluate_entitlement(
        conclusion="REMOVED_FROM_LIBRARY",
        intent_kind=IntentKind.INTENTIONAL_REFACTOR,
        evidence_present=present_evidence,
        evidence_absent=absent_evidence,
        evidence_weak=set(),
        evidence_contradicting=set(),
        ghost_severity="MAJOR"
    )

    # The semantic verdict should be OVERCLAIMED
    assert verdict.semantic_correctness == SemanticCorrectness.OVERCLAIMED
    assert verdict.maximum_justified_severity == "MINOR"
    assert ghost_finding.severity == "MAJOR"  # Ghost claimed more than justified

    # Evaluate action entitlement
    # Even if factually correct and semantically justified (hypothetically),
    # action requires more conditions
    action_detail = ActionEntitlementOracle.assess(
        semantic_correctness=verdict.semantic_correctness,
        confidence=ghost_finding.metadata["confidence"],
        has_replacement_test=False,  # Not verified
        has_behavioral_verification=False,  # Not verified
        has_explicit_policy=False  # No policy
    )

    assert action_detail.verdict == ActionEntitlementVerdict.NOT_ENTITLED

    # Summary of the counterexample
    print("\n" + "="*60)
    print("CANONICAL COUNTEREXAMPLE: Overclaim Detection")
    print("="*60)
    print(f"Member: {ghost_finding.member_name}")
    print(f"\nGhost's observation: {ghost_finding.message}")
    print(f"Ghost's severity claim: {ghost_finding.severity} (confidence: {ghost_finding.metadata['confidence']})")
    print(f"\nWIZZLE's assessment:")
    print(f"  Factual: {factual_correctness.name} ✓")
    print(f"  Semantic: {verdict.semantic_correctness.name} ✗")
    print(f"  Max justified severity: {verdict.maximum_justified_severity}")
    print(f"  Action entitled: {action_detail.verdict.name} ✗")
    print(f"\nConclusion: Ghost's MAJOR severity claim EXCEEDS evidence entitlement")
    print("="*60)


def test_canonical_counterexample_factual_then_semantic():
    """Ensure factual correctness alone does not imply action entitlement.

    This tests the core epistemic independence:
    - Factual correctness (did Ghost observe correctly?)
    - Semantic correctness (does the interpretation match available evidence?)
    - Action entitlement (is autonomous action justified?)

    These are three separate questions.
    """

    # Case: Member was removed (factual truth)
    # But we can't determine intent (semantic uncertainty)
    # Therefore action not entitled (epistemic principle)

    ghost_obs = GhostObservation(
        member_name="UnknownRemoval",
        provenance_class="REMOVED_FROM_LIBRARY",
        severity="MAJOR",
        evidence_cited=["Member exists in history, absent in current"]
    )

    # Evidence: member was removed, but intent unclear
    present_evidence = {EvidenceCategory.MEMBER_REMOVAL_HISTORY}
    absent_evidence = {
        EvidenceCategory.INTENTIONAL_SIGNAL,
        EvidenceCategory.UNINTENDED_SIGNAL,
        EvidenceCategory.SECURITY_SIGNAL
    }

    verdict = EvidenceEntitlementEvaluator.evaluate_entitlement(
        conclusion="REMOVED_FROM_LIBRARY",
        intent_kind=IntentKind.UNKNOWN_INTENT,
        evidence_present=present_evidence,
        evidence_absent=absent_evidence,
        evidence_weak=set(),
        evidence_contradicting=set(),
        ghost_severity="MAJOR"
    )

    # Semantic correctness should be INCONCLUSIVE (intent unclear)
    assert verdict.semantic_correctness == SemanticCorrectness.INCONCLUSIVE

    # Action cannot be entitled on inconclusive evidence
    action_detail = ActionEntitlementOracle.assess(
        semantic_correctness=verdict.semantic_correctness,
        confidence=0.3  # Low confidence
    )

    assert action_detail.verdict == ActionEntitlementVerdict.NOT_ENTITLED

    print("\nCase 2: Factual does not imply action")
    print(f"  Factual: Member was removed (observable fact)")
    print(f"  Semantic: {verdict.semantic_correctness.name} (cannot determine intent)")
    print(f"  Action: {action_detail.verdict.name} (insufficient evidence)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
