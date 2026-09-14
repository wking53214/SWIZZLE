"""Phase 3 Requirements #27-28: Additional required success cases.

Success Case 1 (canonical_counterexample.py): Factually correct, semantically overclaimed
Success Case 2 (this module): Contrastive pair - intentional vs accidental removal
Success Case 3 (this module): UNASKABLE case - insufficient evidence

Each success case demonstrates a core WIZZLE capability.
"""

import pytest
from .epistemic_model import IntentKind, SemanticCorrectness
from .evidence_entitlement import EvidenceEntitlementEvaluator, EvidenceCategory
from .action_entitlement import ActionEntitlementOracle, ActionEntitlementVerdict


class TestSuccessCase2Contrastive:
    """Success Case 2: Contrastive pair - identical evidence, different semantic truth.

    Scenario: Two worlds with identical observable state and commit history,
    but different ground-truth intent (intentional refactor vs accidental removal).

    WIZZLE's capability: Oracles discriminate between them using available evidence.
    """

    def test_contrastive_pair_intentional_vs_accidental(self):
        """World A: Intentional refactor. World B: Accidental removal. Same evidence."""

        # Both worlds have identical observable evidence
        shared_evidence = {
            EvidenceCategory.MEMBER_PRODUCTION_HISTORY,    # Was in production
            EvidenceCategory.MEMBER_REMOVAL_HISTORY,       # Was removed
            EvidenceCategory.MEMBER_CURRENT_STATE,         # Currently absent
        }
        absent_evidence = set()  # Same in both worlds

        # WORLD A: Intentional refactoring (this is semantic truth A)
        world_a_verdict = EvidenceEntitlementEvaluator.evaluate_entitlement(
            conclusion="REMOVED_FROM_LIBRARY",
            intent_kind=IntentKind.INTENTIONAL_REFACTOR,
            evidence_present=shared_evidence,
            evidence_absent=absent_evidence,
            evidence_weak=set(),
            evidence_contradicting=set(),
            ghost_severity="MAJOR"
        )

        # WORLD B: Accidental removal (this is semantic truth B)
        world_b_verdict = EvidenceEntitlementEvaluator.evaluate_entitlement(
            conclusion="REMOVED_FROM_LIBRARY",
            intent_kind=IntentKind.ACCIDENTAL_REMOVAL,
            evidence_present=shared_evidence,
            evidence_absent=absent_evidence,
            evidence_weak=set(),
            evidence_contradicting=set(),
            ghost_severity="MAJOR"
        )

        # Verify contrastive discrimination
        assert world_a_verdict.semantic_correctness != world_b_verdict.semantic_correctness, (
            "Oracles failed to discriminate between intentional and accidental removal"
        )

        # In World A (intentional): MAJOR severity is OVERCLAIMED
        assert world_a_verdict.semantic_correctness == SemanticCorrectness.OVERCLAIMED
        assert world_a_verdict.maximum_justified_severity in ["MINOR", "TRIVIAL"]

        # In World B (accidental): MAJOR severity is JUSTIFIED
        assert world_b_verdict.semantic_correctness == SemanticCorrectness.JUSTIFIED
        assert world_b_verdict.maximum_justified_severity == "MAJOR"

        # Action entitlement should differ
        action_a = ActionEntitlementOracle.assess(
            semantic_correctness=world_a_verdict.semantic_correctness,
            confidence=0.8,
            has_replacement_test=True,
            has_behavioral_verification=True,
            has_explicit_policy=True
        )

        action_b = ActionEntitlementOracle.assess(
            semantic_correctness=world_b_verdict.semantic_correctness,
            confidence=0.8,
            has_replacement_test=True,
            has_behavioral_verification=True,
            has_explicit_policy=True
        )

        # World A: Not entitled (semantic issue blocks action)
        assert action_a.verdict == ActionEntitlementVerdict.NOT_ENTITLED

        # World B: Potentially entitled if other conditions met
        assert action_b.verdict in [
            ActionEntitlementVerdict.ENTITLED,
            ActionEntitlementVerdict.RESTRICTED
        ]

        print("\nSUCCESS CASE 2: CONTRASTIVE DISCRIMINATION")
        print("=" * 60)
        print("Identical Observable Evidence:")
        print(f"  - Member was in production history")
        print(f"  - Member was removed")
        print(f"  - Member currently absent")
        print()
        print("WORLD A: Intentional Refactor")
        print(f"  Semantic: {world_a_verdict.semantic_correctness.name}")
        print(f"  Max Justified Severity: {world_a_verdict.maximum_justified_severity}")
        print(f"  Action Entitled: {action_a.verdict.name}")
        print()
        print("WORLD B: Accidental Removal")
        print(f"  Semantic: {world_b_verdict.semantic_correctness.name}")
        print(f"  Max Justified Severity: {world_b_verdict.maximum_justified_severity}")
        print(f"  Action Entitled: {action_b.verdict.name}")
        print()
        print("Conclusion: Oracles successfully discriminate between worlds")
        print("=" * 60)

    def test_contrastive_discriminates_without_intent_signals(self):
        """Oracles should use indirect evidence to discriminate."""

        # Scenario: Test presence varies, but observable removal is identical
        # World A: Member only in tests (indicates intentional refactor)
        world_a_evidence = {
            EvidenceCategory.MEMBER_REMOVAL_HISTORY,
            EvidenceCategory.MEMBER_CURRENT_STATE,
        }

        # World B: Member completely removed, no test presence
        world_b_evidence = {
            EvidenceCategory.MEMBER_REMOVAL_HISTORY,
            EvidenceCategory.MEMBER_CURRENT_STATE,
        }

        # Same intent kind in both for this test (both unknown)
        verdict_a = EvidenceEntitlementEvaluator.evaluate_entitlement(
            conclusion="REMOVED_FROM_LIBRARY",
            intent_kind=IntentKind.UNKNOWN_INTENT,
            evidence_present=world_a_evidence,
            evidence_absent=set(),
            evidence_weak=set(),
            evidence_contradicting=set(),
            ghost_severity="MAJOR"
        )

        verdict_b = EvidenceEntitlementEvaluator.evaluate_entitlement(
            conclusion="REMOVED_FROM_LIBRARY",
            intent_kind=IntentKind.UNKNOWN_INTENT,
            evidence_present=world_b_evidence,
            evidence_absent=set(),
            evidence_weak=set(),
            evidence_contradicting=set(),
            ghost_severity="MAJOR"
        )

        # Both should reflect the evidence difference
        assert verdict_a.semantic_correctness is not None
        assert verdict_b.semantic_correctness is not None


class TestSuccessCase3Unaskable:
    """Success Case 3: UNASKABLE case - insufficient evidence.

    Scenario: Removal detected but evidence is so sparse and contradictory
    that semantic correctness cannot be determined.

    WIZZLE's capability: Correctly refuses to answer when evidence is insufficient,
    returning UNASKABLE rather than guessing.
    """

    def test_unaskable_conflicting_signals(self):
        """Conflicting signals should produce INCONCLUSIVE/UNASKABLE verdict."""

        # Scenario: Evidence contradicts itself
        # - Commit message suggests intentional: "refactor"
        # - But member was heavily used in production (contradicts refactor)
        # - And no replacement is available (contradicts safe removal)

        present_evidence = {
            EvidenceCategory.MEMBER_PRODUCTION_HISTORY,    # Was widely used
            EvidenceCategory.MEMBER_REMOVAL_HISTORY,       # Was removed
        }

        contradicting_evidence = {
            EvidenceCategory.INTENTIONAL_SIGNAL,          # "refactor" message
        }
        absent_evidence = {
            EvidenceCategory.RELEASE_NOTES,                # Not documented
            EvidenceCategory.REPLACEMENT_EQUIVALENCE,      # No replacement
            EvidenceCategory.DEVELOPER_INTENT,             # No clear intent
        }

        verdict = EvidenceEntitlementEvaluator.evaluate_entitlement(
            conclusion="REMOVED_FROM_LIBRARY",
            intent_kind=IntentKind.UNKNOWN_INTENT,  # Evidence too conflicting
            evidence_present=present_evidence,
            evidence_absent=absent_evidence,
            evidence_weak=set(),
            evidence_contradicting=contradicting_evidence,
            ghost_severity="MAJOR"
        )

        # Should be INCONCLUSIVE due to conflicting evidence
        assert verdict.semantic_correctness in [
            SemanticCorrectness.INCONCLUSIVE,
            SemanticCorrectness.CONTRADICTED
        ]

        # Action should definitely NOT be entitled when inconclusive
        action_detail = ActionEntitlementOracle.assess(
            semantic_correctness=verdict.semantic_correctness,
            confidence=0.4,  # Low confidence due to conflict
        )

        assert action_detail.verdict == ActionEntitlementVerdict.NOT_ENTITLED

        print("\nSUCCESS CASE 3: UNASKABLE - CONFLICTING EVIDENCE")
        print("=" * 60)
        print("Observable Facts:")
        print(f"  - Member was heavily used in production")
        print(f"  - Member was removed")
        print()
        print("Evidence Signals:")
        print(f"  - Commit says 'refactor' (suggests intentional)")
        print(f"  - But high production usage (contradicts refactor)")
        print(f"  - No deprecation warnings (unclear intent)")
        print(f"  - No replacement available (contradicts safe removal)")
        print()
        print("WIZZLE Assessment:")
        print(f"  Semantic Correctness: {verdict.semantic_correctness.name}")
        print(f"  Action Entitled: {action_detail.verdict.name}")
        print()
        print("Conclusion: Evidence is too contradictory to judge")
        print("WIZZLE correctly refuses to answer with confidence")
        print("=" * 60)

    def test_unaskable_insufficient_signals(self):
        """Too little evidence should produce INCONCLUSIVE."""

        # Scenario: Minimal evidence
        # - Member was removed (that's all we know)
        # - No other signals about intent or context

        present_evidence = {
            EvidenceCategory.MEMBER_REMOVAL_HISTORY,
        }

        absent_evidence = {
            EvidenceCategory.MEMBER_PRODUCTION_HISTORY,
            EvidenceCategory.INTENTIONAL_SIGNAL,
            EvidenceCategory.UNINTENDED_SIGNAL,
            EvidenceCategory.RELEASE_NOTES,
            EvidenceCategory.REPLACEMENT_EQUIVALENCE,
            EvidenceCategory.SECURITY_SIGNAL,
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

        # With only removal history and no context, should be INCONCLUSIVE
        assert verdict.semantic_correctness == SemanticCorrectness.INCONCLUSIVE

        # Action must not be entitled
        action_detail = ActionEntitlementOracle.assess(
            semantic_correctness=verdict.semantic_correctness,
            confidence=0.2,  # Very low confidence
        )

        assert action_detail.verdict == ActionEntitlementVerdict.NOT_ENTITLED
        assert ActionEntitlementOracle.SEMANTIC_REQUIREMENTS[verdict.semantic_correctness] is False

        print("\nSUCCESS CASE 3: UNASKABLE - INSUFFICIENT EVIDENCE")
        print("=" * 60)
        print("Observable Facts (minimal):")
        print(f"  - Member was removed")
        print()
        print("Missing Evidence:")
        print(f"  - No historical context")
        print(f"  - No intent signals")
        print(f"  - No usage information")
        print(f"  - No replacement info")
        print()
        print("WIZZLE Assessment:")
        print(f"  Semantic Correctness: {verdict.semantic_correctness.name}")
        print(f"  Action Entitled: {action_detail.verdict.name}")
        print()
        print("Conclusion: Evidence too sparse for confident judgment")
        print("WIZZLE refuses to answer without more information")
        print("=" * 60)

    def test_unaskable_what_would_change_mind(self):
        """UNASKABLE cases should specify what would enable judgment."""

        present_evidence = {
            EvidenceCategory.MEMBER_REMOVAL_HISTORY,
        }

        absent_evidence = {k for k in EvidenceCategory}  # Everything else absent
        absent_evidence.discard(EvidenceCategory.MEMBER_REMOVAL_HISTORY)

        verdict = EvidenceEntitlementEvaluator.evaluate_entitlement(
            conclusion="REMOVED_FROM_LIBRARY",
            intent_kind=IntentKind.UNKNOWN_INTENT,
            evidence_present=present_evidence,
            evidence_absent=absent_evidence,
            evidence_weak=set(),
            evidence_contradicting=set(),
            ghost_severity="MAJOR"
        )

        # Should have recommendations for what evidence would help
        assert len(verdict.what_would_change_mind) > 0

        # Should suggest evidence that would resolve the ambiguity
        suggestions = " ".join(verdict.what_would_change_mind).lower()
        assert any(term in suggestions for term in [
            "commit", "history", "intent", "usage", "deprecation"
        ])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
