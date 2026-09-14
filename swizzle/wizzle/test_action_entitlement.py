"""Tests for ActionEntitlementOracle."""

import pytest
from .action_entitlement import (
    ActionEntitlementOracle, ActionEntitlementVerdict, ActionRisk
)
from .epistemic_model import SemanticCorrectness


def test_entitled_requires_semantic_justification():
    """Action cannot be entitled if semantic verdict is overclaimed."""
    detail = ActionEntitlementOracle.assess(
        semantic_correctness=SemanticCorrectness.OVERCLAIMED,
        confidence=0.95,
        has_replacement_test=True,
        has_behavioral_verification=True,
        has_explicit_policy=True
    )

    assert detail.verdict == ActionEntitlementVerdict.NOT_ENTITLED
    assert ActionEntitlementOracle.SEMANTIC_REQUIREMENTS.get(SemanticCorrectness.OVERCLAIMED) == False


def test_entitled_with_all_requirements_met():
    """Action is entitled when semantic correctness and all requirements met."""
    detail = ActionEntitlementOracle.assess(
        semantic_correctness=SemanticCorrectness.JUSTIFIED,
        confidence=0.95,
        has_replacement_test=True,
        has_behavioral_verification=True,
        has_explicit_policy=True,
        affected_systems=["main_module"]
    )

    assert detail.verdict == ActionEntitlementVerdict.ENTITLED
    assert detail.confidence == 0.95
    assert ActionRisk.CONFIDENCE_LOW not in detail.blocking_factors


def test_restricted_on_low_confidence():
    """Action restricted if confidence too low."""
    detail = ActionEntitlementOracle.assess(
        semantic_correctness=SemanticCorrectness.JUSTIFIED,
        confidence=0.6,
        has_replacement_test=True,
        has_behavioral_verification=True,
        has_explicit_policy=True
    )

    assert detail.verdict == ActionEntitlementVerdict.RESTRICTED
    assert ActionRisk.CONFIDENCE_LOW in detail.blocking_factors


def test_restricted_without_replacement_test():
    """Action restricted if replacement not tested."""
    detail = ActionEntitlementOracle.assess(
        semantic_correctness=SemanticCorrectness.JUSTIFIED,
        confidence=0.95,
        has_replacement_test=False,  # Missing
        has_behavioral_verification=True,
        has_explicit_policy=True
    )

    assert detail.verdict == ActionEntitlementVerdict.RESTRICTED
    assert ActionRisk.BEHAVIORAL_UNVERIFIED in detail.blocking_factors


def test_restricted_on_multiple_affected_systems():
    """Action restricted if multiple systems affected."""
    detail = ActionEntitlementOracle.assess(
        semantic_correctness=SemanticCorrectness.JUSTIFIED,
        confidence=0.95,
        has_replacement_test=True,
        has_behavioral_verification=True,
        has_explicit_policy=True,
        affected_systems=["system_a", "system_b", "system_c"]
    )

    assert detail.verdict == ActionEntitlementVerdict.RESTRICTED
    assert ActionRisk.SCOPE_UNCLEAR in detail.blocking_factors


def test_restricted_without_policy():
    """Action restricted without explicit policy."""
    detail = ActionEntitlementOracle.assess(
        semantic_correctness=SemanticCorrectness.JUSTIFIED,
        confidence=0.95,
        has_replacement_test=True,
        has_behavioral_verification=True,
        has_explicit_policy=False  # Missing
    )

    assert detail.verdict == ActionEntitlementVerdict.RESTRICTED
    assert ActionRisk.POLICY_REQUIRED in detail.blocking_factors


def test_requirements_for_entitlement_listed():
    """What-would-change-mind for entitlement is populated."""
    detail = ActionEntitlementOracle.assess(
        semantic_correctness=SemanticCorrectness.JUSTIFIED,
        confidence=0.5,
        has_replacement_test=False,
        has_behavioral_verification=False,
        has_explicit_policy=False
    )

    assert len(detail.requirements_for_entitlement) > 0
    assert any("Increase confidence" in r for r in detail.requirements_for_entitlement)
    assert any("Test replacement" in r for r in detail.requirements_for_entitlement)
    assert any("Verify behavior" in r for r in detail.requirements_for_entitlement)
    assert any("policy" in r.lower() for r in detail.requirements_for_entitlement)


def test_underclaimed_not_entitled_to_override():
    """Underclaimed findings should not justify action override."""
    detail = ActionEntitlementOracle.assess(
        semantic_correctness=SemanticCorrectness.UNDERCLAIMED,
        confidence=0.95,
        has_replacement_test=True,
        has_behavioral_verification=True,
        has_explicit_policy=True
    )

    assert detail.verdict == ActionEntitlementVerdict.NOT_ENTITLED
    assert "UNDERCLAIMED" in detail.reasoning or "semantic" in detail.reasoning.lower()


def test_inconclusive_not_entitled():
    """Inconclusive results cannot justify action."""
    detail = ActionEntitlementOracle.assess(
        semantic_correctness=SemanticCorrectness.INCONCLUSIVE,
        confidence=0.5
    )

    assert detail.verdict == ActionEntitlementVerdict.NOT_ENTITLED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
