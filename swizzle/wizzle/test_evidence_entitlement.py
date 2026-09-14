"""Tests for evidence entitlement evaluator."""

import pytest
from .evidence_entitlement import (
    EvidenceCategory, EvidenceEntitlementEvaluator, EntitlementVerdictDetail,
    classify_evidence_from_oracle_results
)
from .epistemic_model import IntentKind, SemanticCorrectness


def test_removed_from_library_with_required_evidence():
    """Test REMOVED_FROM_LIBRARY is justified with all evidence."""
    verdict = EvidenceEntitlementEvaluator.evaluate_entitlement(
        conclusion="REMOVED_FROM_LIBRARY",
        intent_kind=IntentKind.INTENTIONAL_REFACTOR,
        evidence_present={
            EvidenceCategory.MEMBER_PRODUCTION_HISTORY,
            EvidenceCategory.MEMBER_REMOVAL_HISTORY,
            EvidenceCategory.MEMBER_CURRENT_STATE,
        },
        evidence_absent=set(),
        evidence_weak=set(),
        evidence_contradicting=set(),
        ghost_severity="MINOR"
    )

    assert verdict.is_entitled is True
    assert verdict.severity_justified is True
    assert verdict.semantic_correctness == SemanticCorrectness.JUSTIFIED


def test_removed_from_library_missing_evidence():
    """Test REMOVED_FROM_LIBRARY is inconclusive without evidence."""
    verdict = EvidenceEntitlementEvaluator.evaluate_entitlement(
        conclusion="REMOVED_FROM_LIBRARY",
        intent_kind=IntentKind.UNKNOWN_INTENT,
        evidence_present={
            EvidenceCategory.MEMBER_CURRENT_STATE,  # Only have current state
        },
        evidence_absent={
            EvidenceCategory.MEMBER_PRODUCTION_HISTORY,
            EvidenceCategory.MEMBER_REMOVAL_HISTORY,
        },
        evidence_weak=set(),
        evidence_contradicting=set(),
        ghost_severity="MAJOR"
    )

    assert verdict.is_entitled is False
    assert verdict.semantic_correctness == SemanticCorrectness.INCONCLUSIVE
    assert len(verdict.missing_evidence) > 0


def test_overclaimed_major_on_intentional_refactor():
    """Test MAJOR severity is overclaimed for intentional refactor."""
    verdict = EvidenceEntitlementEvaluator.evaluate_entitlement(
        conclusion="REMOVED_FROM_LIBRARY",
        intent_kind=IntentKind.INTENTIONAL_REFACTOR,
        evidence_present={
            EvidenceCategory.MEMBER_PRODUCTION_HISTORY,
            EvidenceCategory.MEMBER_REMOVAL_HISTORY,
            EvidenceCategory.MEMBER_CURRENT_STATE,
            EvidenceCategory.INTENTIONAL_SIGNAL,
        },
        evidence_absent=set(),
        evidence_weak=set(),
        evidence_contradicting=set(),
        ghost_severity="MAJOR"  # Too strong for intentional refactor
    )

    assert verdict.semantic_correctness == SemanticCorrectness.OVERCLAIMED
    assert verdict.severity_justified is False
    assert verdict.maximum_justified_severity == "MINOR"


def test_major_justified_for_accidental_removal():
    """Test MAJOR severity IS justified for accidental removal."""
    verdict = EvidenceEntitlementEvaluator.evaluate_entitlement(
        conclusion="REMOVED_FROM_LIBRARY",
        intent_kind=IntentKind.ACCIDENTAL_REMOVAL,
        evidence_present={
            EvidenceCategory.MEMBER_PRODUCTION_HISTORY,
            EvidenceCategory.MEMBER_REMOVAL_HISTORY,
            EvidenceCategory.MEMBER_CURRENT_STATE,
            EvidenceCategory.UNINTENDED_SIGNAL,
        },
        evidence_absent=set(),
        evidence_weak=set(),
        evidence_contradicting=set(),
        ghost_severity="MAJOR"
    )

    assert verdict.semantic_correctness == SemanticCorrectness.JUSTIFIED
    assert verdict.severity_justified is True
    assert verdict.maximum_justified_severity == "MAJOR"


def test_contradicted_by_disconfirming_evidence():
    """Test CONTRADICTED when evidence directly conflicts."""
    verdict = EvidenceEntitlementEvaluator.evaluate_entitlement(
        conclusion="DEAD_CODE_CLEANUP",
        intent_kind=IntentKind.ACCIDENTAL_REMOVAL,
        evidence_present={
            EvidenceCategory.MEMBER_REMOVAL_HISTORY,
        },
        evidence_absent=set(),
        evidence_weak=set(),
        evidence_contradicting={
            EvidenceCategory.UNINTENDED_SIGNAL,  # Contradicts "dead code"
        },
        ghost_severity="MINOR"
    )

    assert verdict.semantic_correctness == SemanticCorrectness.CONTRADICTED
    assert verdict.is_entitled is False


def test_test_only_migration_safe_entitlement():
    """Test TEST_ONLY_MIGRATION gets low severity entitlement."""
    verdict = EvidenceEntitlementEvaluator.evaluate_entitlement(
        conclusion="TEST_ONLY_MIGRATION",
        intent_kind=IntentKind.TEST_ONLY_MIGRATION,
        evidence_present={
            EvidenceCategory.MEMBER_PRODUCTION_HISTORY,
            EvidenceCategory.MEMBER_REMOVAL_HISTORY,
            EvidenceCategory.MEMBER_TEST_USAGE,
            EvidenceCategory.INTENTIONAL_SIGNAL,
        },
        evidence_absent=set(),
        evidence_weak=set(),
        evidence_contradicting=set(),
        ghost_severity="MAJOR"
    )

    assert verdict.semantic_correctness == SemanticCorrectness.OVERCLAIMED
    assert verdict.maximum_justified_severity == "INFORMATIONAL"


def test_unknown_conclusion_unaskable():
    """Test unknown conclusions return UNASKABLE."""
    verdict = EvidenceEntitlementEvaluator.evaluate_entitlement(
        conclusion="UNKNOWN_CONCLUSION",
        intent_kind=IntentKind.UNKNOWN_INTENT,
        evidence_present=set(),
        evidence_absent=set(),
        evidence_weak=set(),
        evidence_contradicting=set(),
        ghost_severity="MAJOR"
    )

    assert verdict.semantic_correctness == SemanticCorrectness.UNASKABLE
    assert len(verdict.what_would_change_mind) > 0


def test_classify_evidence_from_oracle_results():
    """Test conversion of oracle results to evidence categories."""
    oracle_results = {
        "current_state": {
            "members_in_production": [],
            "members_in_tests": ["PHANTOM"],
        },
        "history": {
            "inferred_intent": "INTENTIONAL_REFACTOR",
        }
    }

    present, absent = classify_evidence_from_oracle_results(
        oracle_results,
        test_imports_member=True
    )

    assert EvidenceCategory.MEMBER_PRODUCTION_HISTORY in present
    assert EvidenceCategory.MEMBER_CURRENT_STATE in present
    assert EvidenceCategory.MEMBER_TEST_USAGE in present
    assert EvidenceCategory.INTENTIONAL_SIGNAL in present


def test_what_would_change_mind_included():
    """Test that what_would_change_mind field is populated."""
    verdict = EvidenceEntitlementEvaluator.evaluate_entitlement(
        conclusion="REMOVED_FROM_LIBRARY",
        intent_kind=IntentKind.UNKNOWN_INTENT,
        evidence_present=set(),
        evidence_absent={
            EvidenceCategory.MEMBER_PRODUCTION_HISTORY,
            EvidenceCategory.MEMBER_REMOVAL_HISTORY,
        },
        evidence_weak=set(),
        evidence_contradicting=set(),
        ghost_severity="MAJOR"
    )

    assert len(verdict.what_would_change_mind) > 0
    assert any("provide" in str(w).lower() or "evidence" in str(w).lower() for w in verdict.what_would_change_mind)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
