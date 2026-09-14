"""Action Entitlement Oracle: Independent assessment of justified action.

Determines whether autonomous action (modification) is warranted, separate from
whether a conclusion is semantically sound.

Example:
  Semantic verdict: JUSTIFIED (removal was intentional)
  Action entitlement: NOT_ENTITLED (should still require code review before modifying)

This layer prevents WIZZLE from assuming semantic correctness implies action warrant.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from .epistemic_model import SemanticCorrectness


class ActionEntitlementVerdict(Enum):
    """Whether autonomous action is justified."""
    ENTITLED = auto()           # Safe to act autonomously
    RESTRICTED = auto()         # Manual review required
    NOT_ENTITLED = auto()       # Action not justified
    INSUFFICIENT_EVIDENCE = auto()  # Cannot determine
    UNASKABLE = auto()          # Cannot be determined


class ActionRisk(Enum):
    """Categories of risk preventing action."""
    FACTUAL_UNCERTAINTY = auto()     # Fact claims unclear
    SEMANTIC_AMBIGUITY = auto()      # Multiple valid interpretations
    HIDDEN_DEPENDENCIES = auto()     # Unknown side effects
    BEHAVIORAL_UNVERIFIED = auto()   # Replacement not tested
    INTENT_UNCLEAR = auto()          # Why was it removed?
    MODIFICATION_RISK = auto()       # Change could break things
    IRREVERSIBLE = auto()            # Cannot safely undo
    POLICY_REQUIRED = auto()         # Requires explicit policy
    SCOPE_UNCLEAR = auto()           # Affects other systems?
    CONFIDENCE_LOW = auto()          # Not confident enough


@dataclass
class ActionEntitlementDetail:
    """Complete action entitlement assessment."""
    verdict: ActionEntitlementVerdict

    # Reasoning
    semantic_prerequisite: SemanticCorrectness
    supporting_rationale: List[str] = field(default_factory=list)
    blocking_factors: List[ActionRisk] = field(default_factory=list)

    # What would change mind
    requirements_for_entitlement: List[str] = field(default_factory=list)

    # Evidence quality
    evidence_strength: float = 0.0  # 0.0-1.0
    confidence: float = 0.0

    # Metadata
    reasoning: str = ""


class ActionEntitlementOracle:
    """Assess whether autonomous action is justified."""

    # Semantic prerequisites for action
    SEMANTIC_REQUIREMENTS = {
        SemanticCorrectness.JUSTIFIED: True,      # Can act
        SemanticCorrectness.UNDERCLAIMED: False,  # Too conservative, don't override
        SemanticCorrectness.OVERCLAIMED: False,   # Conclusion not justified
        SemanticCorrectness.CONTRADICTED: False,  # Evidence contradicts
        SemanticCorrectness.INCONCLUSIVE: False,  # Uncertain
        SemanticCorrectness.UNASKABLE: False,     # Cannot determine
    }

    @staticmethod
    def assess(
        semantic_correctness: SemanticCorrectness,
        confidence: float = 0.5,
        has_replacement_test: bool = False,
        has_behavioral_verification: bool = False,
        has_explicit_policy: bool = False,
        affected_systems: List[str] = None,
        risk_factors: List[ActionRisk] = None
    ) -> ActionEntitlementDetail:
        """Assess whether action is entitled given semantic verdict.

        Args:
            semantic_correctness: Result from semantic evaluation
            confidence: Confidence in the conclusion (0.0-1.0)
            has_replacement_test: Is replacement behavior verified?
            has_behavioral_verification: Are semantics preserved?
            has_explicit_policy: Is there explicit authorization?
            affected_systems: Systems that could be affected
            risk_factors: Additional risk factors

        Returns:
            ActionEntitlementDetail with verdict and reasoning
        """

        if risk_factors is None:
            risk_factors = []
        if affected_systems is None:
            affected_systems = []

        detail = ActionEntitlementDetail(
            verdict=ActionEntitlementVerdict.UNASKABLE,
            semantic_prerequisite=semantic_correctness,
            evidence_strength=confidence,
            confidence=confidence
        )

        # Semantic prerequisite check
        if not ActionEntitlementOracle.SEMANTIC_REQUIREMENTS.get(semantic_correctness, False):
            detail.verdict = ActionEntitlementVerdict.NOT_ENTITLED
            detail.blocking_factors.append(ActionRisk.SEMANTIC_AMBIGUITY)
            detail.reasoning = (
                f"Semantic verdict '{semantic_correctness.name}' does not justify autonomous action"
            )
            return detail

        # Confidence check
        if confidence < 0.7:
            detail.verdict = ActionEntitlementVerdict.RESTRICTED
            detail.blocking_factors.append(ActionRisk.CONFIDENCE_LOW)
            detail.requirements_for_entitlement.append(
                f"Increase confidence above 0.7 (currently {confidence:.2f})"
            )

        # Replacement verification
        if not has_replacement_test:
            detail.blocking_factors.append(ActionRisk.BEHAVIORAL_UNVERIFIED)
            detail.requirements_for_entitlement.append(
                "Test replacement behavior to verify semantic preservation"
            )

        # Behavioral verification
        if not has_behavioral_verification:
            detail.blocking_factors.append(ActionRisk.IRREVERSIBLE)
            detail.requirements_for_entitlement.append(
                "Verify behavior with actual execution before modifying"
            )

        # Scope risk
        if len(affected_systems) > 1:
            detail.blocking_factors.append(ActionRisk.SCOPE_UNCLEAR)
            detail.requirements_for_entitlement.append(
                f"Verify impact across {len(affected_systems)} affected systems"
            )

        # Policy requirement
        if not has_explicit_policy:
            detail.blocking_factors.append(ActionRisk.POLICY_REQUIRED)
            detail.requirements_for_entitlement.append(
                "Obtain explicit policy authorization"
            )

        # Add external risk factors
        detail.blocking_factors.extend(risk_factors)

        # Determine final verdict
        if detail.blocking_factors:
            detail.verdict = ActionEntitlementVerdict.RESTRICTED
            detail.reasoning = (
                f"Action restricted due to: {', '.join([r.name for r in detail.blocking_factors])}"
            )
        else:
            detail.verdict = ActionEntitlementVerdict.ENTITLED
            detail.reasoning = "All conditions met for autonomous action"
            detail.supporting_rationale = [
                f"Semantic correctness: {semantic_correctness.name}",
                f"Confidence: {confidence:.2f}",
                "Replacement tested",
                "Behavior verified",
                "Policy authorized"
            ]

        return detail
