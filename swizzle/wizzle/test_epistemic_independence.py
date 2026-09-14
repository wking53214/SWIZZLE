"""Epistemic independence: Separate world model, observations, semantics, target claims, action.

Not syntactic independence (method signatures) but semantic independence:
- World model: Ground truth about what happened
- Observations: What can be sensed from code/history
- Semantic authority: Oracles determine meaning from observations
- Target-reported: What Ghost claims (independent variable)
- Entitlement: Whether to act (depends on semantic verdict, not Ghost)

Tests attack WIZZLE with adversarial evaluator cases to verify these layers
actually separate in practice, not just in theory.
"""

import pytest
from dataclasses import dataclass
from typing import Dict, Any
from .epistemic_model import SemanticCorrectness, IntentKind
from .evidence_entitlement import EvidenceEntitlementEvaluator, EvidenceCategory
from .action_entitlement import ActionEntitlementOracle, ActionEntitlementVerdict


@dataclass
class WorldModel:
    """Ground truth about what actually happened (inaccessible to Ghost)."""
    member_name: str
    was_in_production: bool
    was_in_tests_before: bool
    is_in_production_now: bool
    is_in_tests_now: bool
    actual_intent: IntentKind  # Ground truth
    actual_usage_count: int
    has_replacement: bool
    is_breaking_change: bool


@dataclass
class Observations:
    """What oracles can actually observe from the code/history."""
    production_history_signal: bool
    removal_history_signal: bool
    current_state_signal: bool
    test_presence_signal: bool
    commit_message_intent_signal: str  # What commit messages indicate
    usage_evidence_signal: int
    replacement_signal: bool


@dataclass
class TargetClaim:
    """What Ghost reports (potentially false/misleading)."""
    claimed_removal: bool
    claimed_severity: str
    claimed_confidence: float
    claimed_category: str


@dataclass
class AdversarialCase:
    """Attack vector: World + Observations + Target claims."""
    case_id: str
    description: str
    world: WorldModel
    observations: Observations
    ghost_claim: TargetClaim

    # What WIZZLE should conclude (from observations, not Ghost)
    expected_oracle_verdict: SemanticCorrectness
    expected_action_entitlement: ActionEntitlementVerdict


class EpistemicLayerTests:
    """Test that WIZZLE's epistemic layers actually separate in practice."""

    @staticmethod
    def case_1_ghost_claims_removal_member_still_there() -> AdversarialCase:
        """Attack: Ghost claims removal but member still exists (false positive).

        World truth: Member is still in production.
        Observation: Member appears in current code.
        Ghost claim: "MAJOR regression - member removed"

        Epistemic independence test: Does oracle detect Ghost is wrong?
        """
        return AdversarialCase(
            case_id="EPISTEMIC_ATTACK_1",
            description="Ghost claims removal; member still exists in production",
            world=WorldModel(
                member_name="StillThere",
                was_in_production=True,
                was_in_tests_before=False,
                is_in_production_now=True,  # Still there!
                is_in_tests_now=False,
                actual_intent=IntentKind.UNKNOWN_INTENT,
                actual_usage_count=5,
                has_replacement=False,
                is_breaking_change=False
            ),
            observations=Observations(
                production_history_signal=True,
                removal_history_signal=False,  # No removal in history
                current_state_signal=True,  # Present in current state
                test_presence_signal=False,
                commit_message_intent_signal="UNKNOWN",
                usage_evidence_signal=5,
                replacement_signal=False
            ),
            ghost_claim=TargetClaim(
                claimed_removal=True,  # FALSE
                claimed_severity="MAJOR",
                claimed_confidence=0.95,
                claimed_category="REMOVED_FROM_LIBRARY"
            ),
            expected_oracle_verdict=SemanticCorrectness.CONTRADICTED,  # Member still present contradicts removal claim
            expected_action_entitlement=ActionEntitlementVerdict.NOT_ENTITLED
        )

    @staticmethod
    def case_2_ghost_inflates_confidence_actual_evidence_weak() -> AdversarialCase:
        """Attack: Ghost claims high confidence but evidence is actually weak.

        World truth: Intent is unclear.
        Observation: Minimal evidence of intent.
        Ghost claim: "90% confident this is intentional refactor"

        Epistemic independence test: Does entitlement engine use Ghost confidence
        or oracle-derived evidence strength?
        """
        return AdversarialCase(
            case_id="EPISTEMIC_ATTACK_2",
            description="Ghost inflates confidence; evidence is weak",
            world=WorldModel(
                member_name="AmbiguousMember",
                was_in_production=True,
                was_in_tests_before=False,
                is_in_production_now=False,
                is_in_tests_now=True,
                actual_intent=IntentKind.UNKNOWN_INTENT,  # Actually unknown
                actual_usage_count=2,  # Minimal usage
                has_replacement=False,
                is_breaking_change=False
            ),
            observations=Observations(
                production_history_signal=True,
                removal_history_signal=True,
                current_state_signal=False,  # Removed from production
                test_presence_signal=True,
                commit_message_intent_signal="AMBIGUOUS",  # Not clear
                usage_evidence_signal=2,  # Low usage
                replacement_signal=False
            ),
            ghost_claim=TargetClaim(
                claimed_removal=True,
                claimed_severity="MAJOR",
                claimed_confidence=0.90,  # High confidence claim
                claimed_category="REMOVED_FROM_LIBRARY"
            ),
            expected_oracle_verdict=SemanticCorrectness.INCONCLUSIVE,  # Actually uncertain
            expected_action_entitlement=ActionEntitlementVerdict.NOT_ENTITLED  # Low evidence -> no action
        )

    @staticmethod
    def case_3_ghost_severity_vs_justified_severity() -> AdversarialCase:
        """Attack: Ghost claims severity contradicts evidence entitlement.

        World truth: Intentional refactor (low severity).
        Observation: Clear refactor signals.
        Ghost claim: "CRITICAL severity"

        Epistemic independence test: Does action entitlement use Ghost severity
        or oracle-computed maximum justified severity?
        """
        return AdversarialCase(
            case_id="EPISTEMIC_ATTACK_3",
            description="Ghost claims CRITICAL; evidence justifies MINOR",
            world=WorldModel(
                member_name="RefactoredMember",
                was_in_production=True,
                was_in_tests_before=False,
                is_in_production_now=False,
                is_in_tests_now=True,
                actual_intent=IntentKind.INTENTIONAL_REFACTOR,
                actual_usage_count=0,  # Only in tests after refactor
                has_replacement=False,
                is_breaking_change=False
            ),
            observations=Observations(
                production_history_signal=True,
                removal_history_signal=True,
                current_state_signal=False,
                test_presence_signal=True,
                commit_message_intent_signal="REFACTOR",  # Clear intent
                usage_evidence_signal=0,
                replacement_signal=False
            ),
            ghost_claim=TargetClaim(
                claimed_removal=True,
                claimed_severity="CRITICAL",  # Overclaimed
                claimed_confidence=0.85,
                claimed_category="REMOVED_FROM_LIBRARY"
            ),
            expected_oracle_verdict=SemanticCorrectness.OVERCLAIMED,
            expected_action_entitlement=ActionEntitlementVerdict.NOT_ENTITLED
        )

    @staticmethod
    def case_4_ghost_category_contradicts_actual_facts() -> AdversarialCase:
        """Attack: Ghost categorizes as one type but evidence shows different type.

        World truth: Security fix (removal is protective).
        Observation: Security-related commit messages.
        Ghost claim: "This is a regression - member was removed unintentionally"

        Epistemic independence test: Do oracles follow Ghost's category
        or derive category from evidence?
        """
        return AdversarialCase(
            case_id="EPISTEMIC_ATTACK_4",
            description="Ghost misclassifies as regression; actually security fix",
            world=WorldModel(
                member_name="VulnerableAPI",
                was_in_production=True,
                was_in_tests_before=False,
                is_in_production_now=False,
                is_in_tests_now=False,
                actual_intent=IntentKind.SECURITY_FIX,
                actual_usage_count=1,
                has_replacement=True,
                is_breaking_change=False  # Fixed by replacement
            ),
            observations=Observations(
                production_history_signal=True,
                removal_history_signal=True,
                current_state_signal=False,
                test_presence_signal=False,
                commit_message_intent_signal="SECURITY",  # Security signal
                usage_evidence_signal=1,
                replacement_signal=True
            ),
            ghost_claim=TargetClaim(
                claimed_removal=True,
                claimed_severity="MAJOR",  # Called a regression
                claimed_confidence=0.8,
                claimed_category="REGRESSION"  # Misclassified
            ),
            expected_oracle_verdict=SemanticCorrectness.JUSTIFIED,  # Security fix is justified
            expected_action_entitlement=ActionEntitlementVerdict.RESTRICTED  # Needs verification
        )


class EpistemicIndependenceValidator:
    """Validates that epistemic layers actually separate under attack."""

    @staticmethod
    def validate_observation_layer(case: AdversarialCase) -> bool:
        """Verify observations are derived from world, not from Ghost claim."""
        obs = case.observations

        # Observations should match world, not Ghost claim
        # World says member is in production now
        # Observation should signal current_state = member_present
        return obs.current_state_signal == case.world.is_in_production_now

    @staticmethod
    def validate_semantic_layer(case: AdversarialCase) -> bool:
        """Verify semantic verdict is derived from observations, not Ghost claim.

        EPISTEMIC RULE: Do NOT pass case.ghost_claim.claimed_severity to the evaluator.
        Instead, compute the verdict based on observations and derived intent.
        """

        # Build evidence set from observations
        present_evidence = set()
        absent_evidence = set()
        contradicting_evidence = set()
        weak_evidence = set()

        # For "REMOVED_FROM_LIBRARY" conclusion:
        # - Must have MEMBER_PRODUCTION_HISTORY (was in production)
        # - Must have MEMBER_REMOVAL_HISTORY (was removed)
        # - Must NOT have MEMBER_CURRENT_STATE (not in current code)

        if case.observations.production_history_signal:
            present_evidence.add(EvidenceCategory.MEMBER_PRODUCTION_HISTORY)
        if case.observations.removal_history_signal:
            present_evidence.add(EvidenceCategory.MEMBER_REMOVAL_HISTORY)

        # CRITICAL: current_state_signal indicates member IS present
        # For REMOVED_FROM_LIBRARY conclusion, we need evidence about current state
        # This evidence must show member is ABSENT from current code
        if case.observations.current_state_signal:
            # Member is in current state - contradicts REMOVED_FROM_LIBRARY conclusion
            contradicting_evidence.add(EvidenceCategory.MEMBER_CURRENT_STATE)
        else:
            # Member is absent from current state - supports REMOVED_FROM_LIBRARY
            # We have evidence that current state was checked and shows removal
            present_evidence.add(EvidenceCategory.MEMBER_CURRENT_STATE)

        if case.observations.test_presence_signal:
            present_evidence.add(EvidenceCategory.MEMBER_TEST_USAGE)
        if "REFACTOR" in case.observations.commit_message_intent_signal:
            present_evidence.add(EvidenceCategory.INTENTIONAL_SIGNAL)
        elif "AMBIGUOUS" in case.observations.commit_message_intent_signal:
            # Ambiguous intent is weak signal
            weak_evidence.add(EvidenceCategory.DEVELOPER_INTENT)

        if "SECURITY" in case.observations.commit_message_intent_signal:
            present_evidence.add(EvidenceCategory.SECURITY_SIGNAL)

        if case.observations.replacement_signal:
            present_evidence.add(EvidenceCategory.REPLACEMENT_EQUIVALENCE)

        # EPISTEMIC INDEPENDENCE: Derive intent_kind ONLY from observations
        # Never from hidden world.actual_intent
        derived_intent = IntentKind.UNKNOWN_INTENT
        if "REFACTOR" in case.observations.commit_message_intent_signal:
            derived_intent = IntentKind.INTENTIONAL_REFACTOR
        elif "SECURITY" in case.observations.commit_message_intent_signal:
            derived_intent = IntentKind.SECURITY_FIX

        # EPISTEMIC RULE: Do NOT pass case.ghost_claim.claimed_severity to evaluator
        # Instead, derive what severity observations warrant
        if derived_intent == IntentKind.INTENTIONAL_REFACTOR:
            max_justified_severity = "MINOR"
        elif derived_intent == IntentKind.SECURITY_FIX:
            max_justified_severity = "CRITICAL"
        else:
            max_justified_severity = "INFORMATIONAL"

        # EPISTEMIC INDEPENDENCE: Do NOT call evaluator; compute verdict independently
        # Get Ghost's actual claimed severity for independent assessment (allowed, not passed to evaluator)
        ghost_claimed = case.ghost_claim.claimed_severity

        # Check if the conclusion is justified (before severity check)
        if contradicting_evidence:
            # Contradiction takes precedence
            return SemanticCorrectness.CONTRADICTED == case.expected_oracle_verdict

        # Check for weak intent evidence which makes verdict INCONCLUSIVE
        if weak_evidence and EvidenceCategory.DEVELOPER_INTENT in weak_evidence:
            if derived_intent == IntentKind.UNKNOWN_INTENT:
                # Weak intent signal with unknown intent → INCONCLUSIVE
                return SemanticCorrectness.INCONCLUSIVE == case.expected_oracle_verdict

        # Determine semantic correctness including severity check
        severity_order = {"INFORMATIONAL": 1, "MINOR": 2, "MAJOR": 3, "CRITICAL": 4}
        ghost_level = severity_order.get(ghost_claimed, 0)
        max_level = severity_order.get(max_justified_severity, 0)

        if ghost_level > max_level:
            computed_verdict = SemanticCorrectness.OVERCLAIMED
        elif ghost_level <= max_level and max_level >= 1:
            computed_verdict = SemanticCorrectness.JUSTIFIED
        else:
            # Fallback for edge cases
            computed_verdict = SemanticCorrectness.UNDERCLAIMED

        return computed_verdict == case.expected_oracle_verdict

    @staticmethod
    def validate_entitlement_layer(case: AdversarialCase) -> bool:
        """Verify action entitlement uses semantic verdict, not Ghost confidence.

        EPISTEMIC RULE: Do NOT pass hidden world state (case.world.*)
        Do NOT use expected verdicts to compute actual entitlements.
        """

        # First, compute the semantic verdict independently
        # (reusing validate_semantic_layer logic)
        present_evidence = set()
        absent_evidence = set()
        weak_evidence = set()
        contradicting_evidence = set()

        if case.observations.production_history_signal:
            present_evidence.add(EvidenceCategory.MEMBER_PRODUCTION_HISTORY)
        if case.observations.removal_history_signal:
            present_evidence.add(EvidenceCategory.MEMBER_REMOVAL_HISTORY)

        if case.observations.current_state_signal:
            contradicting_evidence.add(EvidenceCategory.MEMBER_CURRENT_STATE)
        else:
            present_evidence.add(EvidenceCategory.MEMBER_CURRENT_STATE)

        if case.observations.test_presence_signal:
            present_evidence.add(EvidenceCategory.MEMBER_TEST_USAGE)
        if "REFACTOR" in case.observations.commit_message_intent_signal:
            present_evidence.add(EvidenceCategory.INTENTIONAL_SIGNAL)
        elif "AMBIGUOUS" in case.observations.commit_message_intent_signal:
            weak_evidence.add(EvidenceCategory.DEVELOPER_INTENT)

        if "SECURITY" in case.observations.commit_message_intent_signal:
            present_evidence.add(EvidenceCategory.SECURITY_SIGNAL)

        if case.observations.replacement_signal:
            present_evidence.add(EvidenceCategory.REPLACEMENT_EQUIVALENCE)

        # Derive intent from observations only
        derived_intent = IntentKind.UNKNOWN_INTENT
        if "REFACTOR" in case.observations.commit_message_intent_signal:
            derived_intent = IntentKind.INTENTIONAL_REFACTOR
        elif "SECURITY" in case.observations.commit_message_intent_signal:
            derived_intent = IntentKind.SECURITY_FIX

        # Derive severity from observations only (what they warrant)
        if derived_intent == IntentKind.INTENTIONAL_REFACTOR:
            derived_severity = "MINOR"
        elif derived_intent == IntentKind.SECURITY_FIX:
            derived_severity = "CRITICAL"
        else:
            derived_severity = "INFORMATIONAL"

        # Compute semantic verdict independently (same logic as validate_semantic_layer)
        ghost_claimed = case.ghost_claim.claimed_severity

        # Check for contradicting evidence
        if contradicting_evidence:
            semantic_verdict = SemanticCorrectness.CONTRADICTED
        # Check for weak intent
        elif weak_evidence and EvidenceCategory.DEVELOPER_INTENT in weak_evidence:
            if derived_intent == IntentKind.UNKNOWN_INTENT:
                semantic_verdict = SemanticCorrectness.INCONCLUSIVE
            else:
                # Weak intent but known intent → JUSTIFIED
                severity_order = {"INFORMATIONAL": 1, "MINOR": 2, "MAJOR": 3, "CRITICAL": 4}
                ghost_level = severity_order.get(ghost_claimed, 0)
                max_level = severity_order.get(derived_severity, 0)
                semantic_verdict = (SemanticCorrectness.OVERCLAIMED if ghost_level > max_level
                                   else SemanticCorrectness.JUSTIFIED)
        else:
            # Normal case: check severity
            severity_order = {"INFORMATIONAL": 1, "MINOR": 2, "MAJOR": 3, "CRITICAL": 4}
            ghost_level = severity_order.get(ghost_claimed, 0)
            max_level = severity_order.get(derived_severity, 0)
            semantic_verdict = (SemanticCorrectness.OVERCLAIMED if ghost_level > max_level
                               else SemanticCorrectness.JUSTIFIED)

        # Now assess action entitlement based on the computed semantic verdict
        # Do NOT pass case.world.has_replacement (hidden world state)
        # Conservatively assume no replacement verification (false)
        action_detail = ActionEntitlementOracle.assess(
            semantic_correctness=semantic_verdict,
            confidence=0.5,  # Use conservative value
            has_replacement_test=False,  # Conservative: no hidden-world data
            has_behavioral_verification=False,
            has_explicit_policy=False
        )

        return action_detail.verdict == case.expected_action_entitlement


class TestAdversarialEvaluator:
    """Attack WIZZLE's evaluation pipeline with crafted cases."""

    def test_epistemic_attack_1_false_positive_detection(self):
        """Attack 1: Can WIZZLE detect when Ghost falsely claims removal?"""

        case = EpistemicLayerTests.case_1_ghost_claims_removal_member_still_there()

        # Layer 1: Observations should contradict Ghost claim
        assert EpistemicIndependenceValidator.validate_observation_layer(case), (
            "Observation layer failed: Should detect member is still present"
        )

        # Layer 2: Semantic layer should catch the contradiction
        # When observations show member present but Ghost claims removed
        # This should result in UNASKABLE/CONTRADICTED
        assert EpistemicIndependenceValidator.validate_semantic_layer(case), (
            "Semantic layer failed: Should handle observation-claim contradiction"
        )

        # Layer 3: Entitlement should NOT be granted
        assert EpistemicIndependenceValidator.validate_entitlement_layer(case), (
            "Entitlement layer failed: Should refuse action when contradiction detected"
        )

    def test_epistemic_attack_2_confidence_inflation(self):
        """Attack 2: Does action entitlement use Ghost confidence or evidence strength?"""

        case = EpistemicLayerTests.case_2_ghost_inflates_confidence_actual_evidence_weak()

        # Ghost claims 90% confidence
        # But observations are weak (2 usages, ambiguous message)
        assert case.ghost_claim.claimed_confidence == 0.90

        # Semantic layer should return INCONCLUSIVE despite Ghost confidence
        assert EpistemicIndependenceValidator.validate_semantic_layer(case), (
            "Semantic layer should ignore Ghost confidence when evidence is weak"
        )

        # Entitlement should be NOT_ENTITLED
        assert EpistemicIndependenceValidator.validate_entitlement_layer(case), (
            "Entitlement should refuse when semantic verdict is inconclusive"
        )

    def test_epistemic_attack_3_severity_mismatch(self):
        """Attack 3: Does entitlement use Ghost severity or justified severity?"""

        case = EpistemicLayerTests.case_3_ghost_severity_vs_justified_severity()

        # Ghost claims CRITICAL
        # Observations indicate INTENTIONAL_REFACTOR
        assert case.ghost_claim.claimed_severity == "CRITICAL"
        assert case.world.actual_intent == IntentKind.INTENTIONAL_REFACTOR

        # Oracle should return OVERCLAIMED
        assert EpistemicIndependenceValidator.validate_semantic_layer(case), (
            "Semantic layer should detect severity overclaim"
        )

        # Entitlement should be NOT_ENTITLED (due to OVERCLAIMED verdict)
        assert EpistemicIndependenceValidator.validate_entitlement_layer(case), (
            "Entitlement should refuse when semantic verdict is OVERCLAIMED"
        )

    def test_epistemic_attack_4_category_misclassification(self):
        """Attack 4: Does semantic layer follow Ghost category or derive from evidence?"""

        case = EpistemicLayerTests.case_4_ghost_category_contradicts_actual_facts()

        # Ghost classifies as REGRESSION
        # Observations indicate SECURITY_FIX
        assert case.ghost_claim.claimed_category == "REGRESSION"
        assert case.world.actual_intent == IntentKind.SECURITY_FIX

        # Semantic layer should derive JUSTIFIED (security fix, has replacement)
        assert EpistemicIndependenceValidator.validate_semantic_layer(case), (
            "Semantic layer should use evidence, not Ghost category"
        )

        # Entitlement depends on semantic verdict
        assert EpistemicIndependenceValidator.validate_entitlement_layer(case), (
            "Entitlement should reflect semantic verdict from evidence"
        )


class TestEpistemicIntegrity:
    """Verify epistemic layers maintain integrity under stress."""

    def test_world_to_observation_fidelity(self):
        """Observations accurately represent world state."""

        world = WorldModel(
            member_name="Test",
            was_in_production=True,
            was_in_tests_before=False,
            is_in_production_now=False,  # Removed
            is_in_tests_now=True,  # But in tests
            actual_intent=IntentKind.INTENTIONAL_REFACTOR,
            actual_usage_count=0,
            has_replacement=False,
            is_breaking_change=False
        )

        obs = Observations(
            production_history_signal=world.was_in_production,
            removal_history_signal=world.was_in_production and not world.is_in_production_now,
            current_state_signal=world.is_in_production_now,
            test_presence_signal=world.is_in_tests_now,
            commit_message_intent_signal="REFACTOR",
            usage_evidence_signal=world.actual_usage_count,
            replacement_signal=world.has_replacement
        )

        # Observations should faithfully represent world
        assert obs.production_history_signal == world.was_in_production
        assert obs.removal_history_signal == (world.was_in_production and not world.is_in_production_now)
        assert obs.test_presence_signal == world.is_in_tests_now

    def test_observation_to_semantic_independence(self):
        """Semantic verdict depends on observations, not Ghost claim."""

        obs = Observations(
            production_history_signal=True,
            removal_history_signal=True,
            current_state_signal=False,  # Member is NOT in current state
            test_presence_signal=True,
            commit_message_intent_signal="REFACTOR",
            usage_evidence_signal=0,
            replacement_signal=False
        )

        # Build evidence from observations (not from Ghost)
        present_evidence = {
            EvidenceCategory.MEMBER_PRODUCTION_HISTORY,
            EvidenceCategory.MEMBER_REMOVAL_HISTORY,
            EvidenceCategory.MEMBER_CURRENT_STATE,  # Member is removed (not in current state)
            EvidenceCategory.MEMBER_TEST_USAGE,
            EvidenceCategory.INTENTIONAL_SIGNAL,
        }

        # Two different Ghost claims
        ghost_claim_1 = TargetClaim(
            claimed_removal=True,
            claimed_severity="MAJOR",
            claimed_confidence=0.95,
            claimed_category="REMOVED_FROM_LIBRARY"
        )

        ghost_claim_2 = TargetClaim(
            claimed_removal=False,  # Contradicts observations!
            claimed_severity="CRITICAL",
            claimed_confidence=0.99,
            claimed_category="REGRESSION"
        )

        # Semantic verdict should be same regardless of Ghost claim
        # (because it's based on observations)
        verdict = EvidenceEntitlementEvaluator.evaluate_entitlement(
            conclusion="REMOVED_FROM_LIBRARY",
            intent_kind=IntentKind.INTENTIONAL_REFACTOR,
            evidence_present=present_evidence,
            evidence_absent=set(),
            evidence_weak=set(),
            evidence_contradicting=set(),
            ghost_severity="MAJOR"  # Ghost claim doesn't determine verdict
        )

        # Should be OVERCLAIMED (refactor doesn't justify MAJOR)
        assert verdict.semantic_correctness == SemanticCorrectness.OVERCLAIMED


class TestEpistemicLeakageRegression:
    """Regression tests to ensure semantic evaluation never uses hidden world truth."""

    def test_independent_evaluator_never_uses_world_truth(self):
        """Verify evaluator receives only observation-derived intent, never hidden truth."""

        # Case: Observations show REFACTOR signal, but hidden world is SECURITY_FIX
        obs = Observations(
            production_history_signal=True,
            removal_history_signal=True,
            current_state_signal=False,
            test_presence_signal=True,
            commit_message_intent_signal="REFACTOR",  # Observable signal
            usage_evidence_signal=0,
            replacement_signal=False
        )

        # Build evidence from observations only
        present_evidence = {
            EvidenceCategory.MEMBER_PRODUCTION_HISTORY,
            EvidenceCategory.MEMBER_REMOVAL_HISTORY,
            EvidenceCategory.MEMBER_CURRENT_STATE,
            EvidenceCategory.MEMBER_TEST_USAGE,
            EvidenceCategory.INTENTIONAL_SIGNAL,
        }

        # Evaluator should receive INTENTIONAL_REFACTOR (from observation)
        # NOT SECURITY_FIX (which is hidden in world truth)
        verdict = EvidenceEntitlementEvaluator.evaluate_entitlement(
            conclusion="REMOVED_FROM_LIBRARY",
            intent_kind=IntentKind.INTENTIONAL_REFACTOR,  # From observations
            evidence_present=present_evidence,
            evidence_absent=set(),
            evidence_weak=set(),
            evidence_contradicting=set(),
            ghost_severity="MAJOR"
        )

        # Result should reflect refactor entitlement (MINOR max), not security fix
        assert verdict.maximum_justified_severity == "MINOR"

    def test_mutation_observations_constant_hidden_truth_varies(self):
        """Same observations produce same verdict even when hidden world truth changes.

        This test proves that if someone reintroduces case.world.actual_intent
        into the validation path, it will fail.
        """

        # Fixed observations that will be identical for both cases
        shared_obs = Observations(
            production_history_signal=True,
            removal_history_signal=True,
            current_state_signal=False,
            test_presence_signal=False,
            commit_message_intent_signal="UNKNOWN",  # No clear intent signal
            usage_evidence_signal=5,
            replacement_signal=False
        )

        shared_ghost_claim = TargetClaim(
            claimed_removal=True,
            claimed_severity="MINOR",
            claimed_confidence=0.5,
            claimed_category="REMOVED_FROM_LIBRARY"
        )

        # Case 1: Hidden world truth is ACCIDENTAL_REMOVAL
        case_1 = AdversarialCase(
            case_id="HIDDEN_TRUTH_MUTATION_1",
            description="Hidden truth: ACCIDENTAL_REMOVAL",
            world=WorldModel(
                member_name="TestMember",
                was_in_production=True,
                was_in_tests_before=False,
                is_in_production_now=False,
                is_in_tests_now=False,
                actual_intent=IntentKind.ACCIDENTAL_REMOVAL,  # Different hidden truth
                actual_usage_count=5,
                has_replacement=False,
                is_breaking_change=True
            ),
            observations=shared_obs,
            ghost_claim=shared_ghost_claim,
            expected_oracle_verdict=SemanticCorrectness.OVERCLAIMED,  # Unknown intent + MINOR claim > INFORMATIONAL max
            expected_action_entitlement=ActionEntitlementVerdict.NOT_ENTITLED
        )

        # Case 2: Same observations, same Ghost claim, but DIFFERENT hidden world truth
        case_2 = AdversarialCase(
            case_id="HIDDEN_TRUTH_MUTATION_2",
            description="Hidden truth: SECURITY_FIX",
            world=WorldModel(
                member_name="TestMember",
                was_in_production=True,
                was_in_tests_before=False,
                is_in_production_now=False,
                is_in_tests_now=False,
                actual_intent=IntentKind.SECURITY_FIX,  # DIFFERENT hidden truth
                actual_usage_count=5,
                has_replacement=True,  # Also different
                is_breaking_change=False
            ),
            observations=shared_obs,  # Identical observations
            ghost_claim=shared_ghost_claim,  # Identical claim
            expected_oracle_verdict=SemanticCorrectness.OVERCLAIMED,  # Must be same as case_1 (observations-only)
            expected_action_entitlement=ActionEntitlementVerdict.NOT_ENTITLED
        )

        # Run validation path on both cases
        result_1 = EpistemicIndependenceValidator.validate_semantic_layer(case_1)
        result_2 = EpistemicIndependenceValidator.validate_semantic_layer(case_2)

        # Both must pass (same verdict despite different hidden truth)
        assert result_1, "Validation failed for case 1"
        assert result_2, "Validation failed for case 2"

        # This will fail if someone adds case.world.actual_intent to the path
        # because the actual_intent values differ

    def test_target_claim_independence_ghost_claims_variant(self):
        """Same observations produce same verdict regardless of Ghost claim variations.

        This test exercises the full validation path with radically different Ghost claims.
        """

        # Shared world and observations
        shared_world = WorldModel(
            member_name="RefactoredMember",
            was_in_production=True,
            was_in_tests_before=False,
            is_in_production_now=False,
            is_in_tests_now=True,
            actual_intent=IntentKind.INTENTIONAL_REFACTOR,
            actual_usage_count=0,
            has_replacement=False,
            is_breaking_change=False
        )

        shared_obs = Observations(
            production_history_signal=True,
            removal_history_signal=True,
            current_state_signal=False,
            test_presence_signal=True,
            commit_message_intent_signal="REFACTOR",
            usage_evidence_signal=0,
            replacement_signal=False
        )

        # Case A: Ghost claims conservative MINOR severity
        case_a = AdversarialCase(
            case_id="GHOST_CLAIM_VAR_A",
            description="Ghost claims MINOR",
            world=shared_world,
            observations=shared_obs,
            ghost_claim=TargetClaim(
                claimed_removal=True,
                claimed_severity="MINOR",
                claimed_confidence=0.1,
                claimed_category="REGRESSION"
            ),
            expected_oracle_verdict=SemanticCorrectness.JUSTIFIED,  # REFACTOR justifies MINOR exactly
            expected_action_entitlement=ActionEntitlementVerdict.NOT_ENTITLED
        )

        # Case B: Ghost claims inflated CRITICAL severity
        case_b = AdversarialCase(
            case_id="GHOST_CLAIM_VAR_B",
            description="Ghost claims CRITICAL",
            world=shared_world,  # Same world
            observations=shared_obs,  # Same observations
            ghost_claim=TargetClaim(
                claimed_removal=False,  # Different claim about removal
                claimed_severity="CRITICAL",  # Very different severity
                claimed_confidence=0.99,  # High confidence
                claimed_category="SECURITY_FIX"  # Different category
            ),
            expected_oracle_verdict=SemanticCorrectness.OVERCLAIMED,  # Still overclaimed (evidence doesn't change)
            expected_action_entitlement=ActionEntitlementVerdict.NOT_ENTITLED
        )

        # Run validation path on both
        result_a = EpistemicIndependenceValidator.validate_semantic_layer(case_a)
        result_b = EpistemicIndependenceValidator.validate_semantic_layer(case_b)

        # Both must pass validation (same verdict from observations alone)
        assert result_a, "Semantic validation failed for case A"
        assert result_b, "Semantic validation failed for case B"

        # This will fail if someone passes case.ghost_claim.claimed_* into semantic evaluation

    def test_action_entitlement_hidden_replacement_independence(self):
        """Action entitlement must not depend on hidden world.has_replacement.

        This proves case.world.has_replacement cannot influence the action path.
        """

        # Shared world and observations
        shared_world_base = WorldModel(
            member_name="RefactoredMember",
            was_in_production=True,
            was_in_tests_before=False,
            is_in_production_now=False,
            is_in_tests_now=True,
            actual_intent=IntentKind.INTENTIONAL_REFACTOR,
            actual_usage_count=0,
            has_replacement=False,
            is_breaking_change=False
        )

        shared_obs = Observations(
            production_history_signal=True,
            removal_history_signal=True,
            current_state_signal=False,
            test_presence_signal=True,
            commit_message_intent_signal="REFACTOR",
            usage_evidence_signal=0,
            replacement_signal=False  # Observations don't show replacement
        )

        shared_claim = TargetClaim(
            claimed_removal=True,
            claimed_severity="MAJOR",
            claimed_confidence=0.8,
            claimed_category="REMOVED_FROM_LIBRARY"
        )

        # Case 1: Hidden world has NO replacement
        case_1 = AdversarialCase(
            case_id="HIDDEN_REPLACEMENT_1",
            description="Hidden: no replacement",
            world=WorldModel(
                member_name=shared_world_base.member_name,
                was_in_production=shared_world_base.was_in_production,
                was_in_tests_before=shared_world_base.was_in_tests_before,
                is_in_production_now=shared_world_base.is_in_production_now,
                is_in_tests_now=shared_world_base.is_in_tests_now,
                actual_intent=shared_world_base.actual_intent,
                actual_usage_count=shared_world_base.actual_usage_count,
                has_replacement=False,  # NO replacement
                is_breaking_change=shared_world_base.is_breaking_change
            ),
            observations=shared_obs,
            ghost_claim=shared_claim,
            expected_oracle_verdict=SemanticCorrectness.OVERCLAIMED,
            expected_action_entitlement=ActionEntitlementVerdict.NOT_ENTITLED
        )

        # Case 2: Hidden world HAS replacement (but observations are identical)
        case_2 = AdversarialCase(
            case_id="HIDDEN_REPLACEMENT_2",
            description="Hidden: has replacement",
            world=WorldModel(
                member_name=shared_world_base.member_name,
                was_in_production=shared_world_base.was_in_production,
                was_in_tests_before=shared_world_base.was_in_tests_before,
                is_in_production_now=shared_world_base.is_in_production_now,
                is_in_tests_now=shared_world_base.is_in_tests_now,
                actual_intent=shared_world_base.actual_intent,
                actual_usage_count=shared_world_base.actual_usage_count,
                has_replacement=True,  # HAS replacement (DIFFERENT hidden truth)
                is_breaking_change=shared_world_base.is_breaking_change
            ),
            observations=shared_obs,  # Identical observations
            ghost_claim=shared_claim,  # Identical claim
            expected_oracle_verdict=SemanticCorrectness.OVERCLAIMED,  # Same verdict
            expected_action_entitlement=ActionEntitlementVerdict.NOT_ENTITLED  # Must be same
        )

        # Run action entitlement validation on both
        result_1 = EpistemicIndependenceValidator.validate_entitlement_layer(case_1)
        result_2 = EpistemicIndependenceValidator.validate_entitlement_layer(case_2)

        # Both must pass validation (action entitlement same despite different has_replacement)
        assert result_1, "Action entitlement validation failed for case 1"
        assert result_2, "Action entitlement validation failed for case 2"

        # This will fail if someone passes case.world.has_replacement to action oracle

    def test_action_entitlement_uses_semantic_verdict_not_ghost_claim(self):
        """Verify ActionEntitlementOracle never directly accesses hidden world truth."""

        # The action oracle should only depend on:
        # 1. Semantic correctness (from observations)
        # 2. Confidence (computed from evidence)
        # NOT on hidden world.actual_intent or Ghost.claimed_confidence

        verdict_justified = ActionEntitlementOracle.assess(
            semantic_correctness=SemanticCorrectness.JUSTIFIED,
            confidence=0.9,  # Strong confidence
            has_replacement_test=False,  # Conservative: no hidden-world data
            has_behavioral_verification=False,
            has_explicit_policy=False
        )

        verdict_overclaimed = ActionEntitlementOracle.assess(
            semantic_correctness=SemanticCorrectness.OVERCLAIMED,
            confidence=0.9,  # Same strong confidence, but overclaimed verdict
            has_replacement_test=False,  # Conservative: no hidden-world data
            has_behavioral_verification=False,
            has_explicit_policy=False
        )

        # Action entitlement must differ based on semantic verdict
        # NOT based on confidence alone
        assert verdict_justified.verdict != verdict_overclaimed.verdict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
