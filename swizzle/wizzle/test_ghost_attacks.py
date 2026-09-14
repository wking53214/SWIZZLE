"""Tests for Ghost attack scenarios (Phase 3 Requirement #8).

Validates that all 10 attacks are properly defined and independently evaluable.
"""

import pytest
from .ghost_attacks import (
    GhostAttackGenerator, AttackType, GhostAttack
)


class TestAttackDefinitions:
    """Test that all attack scenarios are properly defined."""

    def test_attack_a_intentional_refactor_defined(self):
        """Attack A: Intentional refactor scenario is properly defined."""
        attack = GhostAttackGenerator.attack_a_intentional_refactor()

        assert attack.attack_id == "GHOST_ATTACK_A"
        assert attack.attack_type == AttackType.A_INTENTIONAL_REFACTOR
        assert attack.member_name == "LegacyStatus"
        assert attack.oracle_correct_verdict == "OVERCLAIMED"
        assert attack.expected_oracle_behavior["inferred_intent"] == "INTENTIONAL_REFACTOR"

    def test_attack_b_security_fix_defined(self):
        """Attack B: Security fix scenario is properly defined."""
        attack = GhostAttackGenerator.attack_b_security_fix()

        assert attack.attack_id == "GHOST_ATTACK_B"
        assert attack.attack_type == AttackType.B_SECURITY_FIX
        assert attack.oracle_correct_verdict == "JUSTIFIED"
        assert attack.expected_oracle_behavior["justified_severity"] == "MAJOR"

    def test_attack_c_test_only_migration_defined(self):
        """Attack C: Test-only migration scenario is properly defined."""
        attack = GhostAttackGenerator.attack_c_test_only_migration()

        assert attack.attack_id == "GHOST_ATTACK_C"
        assert attack.attack_type == AttackType.C_TEST_ONLY_MIGRATION
        assert attack.oracle_correct_verdict == "OVERCLAIMED"

    def test_attack_d_dead_code_defined(self):
        """Attack D: Dead code scenario is properly defined."""
        attack = GhostAttackGenerator.attack_d_dead_code()

        assert attack.attack_id == "GHOST_ATTACK_D"
        assert attack.attack_type == AttackType.D_DEAD_CODE
        assert attack.oracle_correct_verdict == "OVERCLAIMED"

    def test_attack_e_deprecation_path_defined(self):
        """Attack E: Deprecation removal scenario is properly defined."""
        attack = GhostAttackGenerator.attack_e_deprecation_path()

        assert attack.attack_id == "GHOST_ATTACK_E"
        assert attack.attack_type == AttackType.E_DEPRECATION_PATH
        assert attack.oracle_correct_verdict == "OVERCLAIMED"

    def test_attack_f_accidental_removal_defined(self):
        """Attack F: Accidental removal scenario is properly defined."""
        attack = GhostAttackGenerator.attack_f_accidental_removal()

        assert attack.attack_id == "GHOST_ATTACK_F"
        assert attack.attack_type == AttackType.F_ACCIDENTAL_REMOVAL
        assert attack.oracle_correct_verdict == "JUSTIFIED"

    def test_attack_g_api_evolution_defined(self):
        """Attack G: API evolution scenario is properly defined."""
        attack = GhostAttackGenerator.attack_g_api_evolution()

        assert attack.attack_id == "GHOST_ATTACK_G"
        assert attack.attack_type == AttackType.G_API_EVOLUTION
        assert attack.oracle_correct_verdict == "OVERCLAIMED"

    def test_attack_h_transitive_dependency_defined(self):
        """Attack H: Transitive dependency scenario is properly defined."""
        attack = GhostAttackGenerator.attack_h_transitive_dependency()

        assert attack.attack_id == "GHOST_ATTACK_H"
        assert attack.attack_type == AttackType.H_TRANSITIVE_DEPENDENCY
        assert attack.oracle_correct_verdict == "OVERCLAIMED"

    def test_attack_i_false_positive_defined(self):
        """Attack I: False positive scenario is properly defined."""
        attack = GhostAttackGenerator.attack_i_false_positive()

        assert attack.attack_id == "GHOST_ATTACK_I"
        assert attack.attack_type == AttackType.I_FALSE_POSITIVE
        assert attack.oracle_correct_verdict == "INCORRECT"

    def test_attack_j_ambiguous_context_defined(self):
        """Attack J: Ambiguous context scenario is properly defined."""
        attack = GhostAttackGenerator.attack_j_ambiguous_context()

        assert attack.attack_id == "GHOST_ATTACK_J"
        assert attack.attack_type == AttackType.J_AMBIGUOUS_CONTEXT
        assert attack.oracle_correct_verdict == "INCONCLUSIVE"


class TestAllAttacksComplete:
    """Test that all 10 attacks are available."""

    def test_all_ten_attacks_defined(self):
        """All 10 attacks should be available."""
        attacks = GhostAttackGenerator.get_all_attacks()

        assert len(attacks) == 10
        assert "A" in attacks
        assert "B" in attacks
        assert "C" in attacks
        assert "D" in attacks
        assert "E" in attacks
        assert "F" in attacks
        assert "G" in attacks
        assert "H" in attacks
        assert "I" in attacks
        assert "J" in attacks

    def test_each_attack_has_unique_id(self):
        """Each attack should have a unique ID."""
        attacks = GhostAttackGenerator.get_all_attacks()
        ids = [attack.attack_id for attack in attacks.values()]

        assert len(ids) == len(set(ids)), "Duplicate attack IDs found"

    def test_attack_verdicts_are_valid(self):
        """All attacks should have valid oracle verdicts."""
        valid_verdicts = {"CORRECT", "OVERCLAIMED", "UNDERCLAIMED", "CONTRADICTED",
                         "INCONCLUSIVE", "JUSTIFIED", "INCORRECT", "UNASKABLE"}

        attacks = GhostAttackGenerator.get_all_attacks()

        for letter, attack in attacks.items():
            assert attack.oracle_correct_verdict in valid_verdicts, (
                f"Attack {letter} has invalid verdict: {attack.oracle_correct_verdict}"
            )


class TestAttackStructure:
    """Test that attacks have proper structure."""

    def test_attack_has_required_fields(self):
        """Each attack should have all required fields."""
        attack = GhostAttackGenerator.attack_a_intentional_refactor()

        assert hasattr(attack, "attack_id")
        assert hasattr(attack, "attack_type")
        assert hasattr(attack, "member_name")
        assert hasattr(attack, "description")
        assert hasattr(attack, "repository_setup")
        assert hasattr(attack, "expected_ghost_behavior")
        assert hasattr(attack, "expected_oracle_behavior")
        assert hasattr(attack, "oracle_correct_verdict")
        assert hasattr(attack, "evidence_indicators")

    def test_repository_setup_has_content(self):
        """Each attack should have meaningful repository setup."""
        attacks = GhostAttackGenerator.get_all_attacks()

        for letter, attack in attacks.items():
            assert isinstance(attack.repository_setup, dict)
            assert len(attack.repository_setup) > 0, (
                f"Attack {letter} has empty repository_setup"
            )

    def test_oracle_behavior_expectations(self):
        """Oracle behavior should specify expected assessment."""
        attacks = GhostAttackGenerator.get_all_attacks()

        for letter, attack in attacks.items():
            oracle_behavior = attack.expected_oracle_behavior
            assert isinstance(oracle_behavior, dict)
            # Should specify semantic correctness in some form
            has_semantic_info = any(
                key in oracle_behavior for key in
                ["semantic", "factual", "inferred_intent", "justified_severity"]
            )
            assert has_semantic_info, (
                f"Attack {letter} lacks semantic expectation"
            )


class TestAttackEvaluation:
    """Test attack evaluation logic."""

    def test_evaluate_attack_oracle_correct(self):
        """Evaluation should recognize when oracle is correct."""
        attack = GhostAttackGenerator.attack_a_intentional_refactor()

        ghost_conclusion = {"finding": "REMOVED_FROM_LIBRARY", "severity": "MAJOR"}
        oracle_assessment = {"semantic_correctness": "OVERCLAIMED"}

        result = GhostAttackGenerator.evaluate_attack(
            attack, ghost_conclusion, oracle_assessment
        )

        assert result["oracle_correct"] is True
        assert result["attack_passed"] is True

    def test_evaluate_attack_oracle_incorrect(self):
        """Evaluation should detect when oracle is incorrect."""
        attack = GhostAttackGenerator.attack_a_intentional_refactor()

        ghost_conclusion = {"finding": "REMOVED_FROM_LIBRARY", "severity": "MAJOR"}
        oracle_assessment = {"semantic_correctness": "JUSTIFIED"}  # Wrong!

        result = GhostAttackGenerator.evaluate_attack(
            attack, ghost_conclusion, oracle_assessment
        )

        assert result["oracle_correct"] is False
        assert result["attack_passed"] is False
        assert "discrepancy" in result

    def test_evaluate_attack_result_structure(self):
        """Evaluation result should have proper structure."""
        attack = GhostAttackGenerator.attack_b_security_fix()

        ghost_conclusion = {"finding": "REMOVED_FROM_LIBRARY", "severity": "MAJOR"}
        oracle_assessment = {"semantic_correctness": "JUSTIFIED"}

        result = GhostAttackGenerator.evaluate_attack(
            attack, ghost_conclusion, oracle_assessment
        )

        assert "attack_id" in result
        assert "attack_type" in result
        assert "oracle_correct" in result
        assert "attack_passed" in result


class TestAttackTargets:
    """Test that attacks target different Ghost failure modes."""

    def test_attacks_target_different_modes(self):
        """Each attack should target different failure modes."""
        attacks = GhostAttackGenerator.get_all_attacks()
        types = [attack.attack_type for attack in attacks.values()]

        # Should have 10 unique attack types
        assert len(types) == 10
        assert len(set(types)) == 10

    def test_attack_a_targets_overclaim_on_refactor(self):
        """Attack A should expose Ghost overclaiming on refactoring."""
        attack = GhostAttackGenerator.attack_a_intentional_refactor()

        assert attack.expected_ghost_behavior["overclaimed_severity"] == "MAJOR"
        assert attack.expected_oracle_behavior["justified_severity"] == "MINOR"

    def test_attack_b_targets_valid_severity(self):
        """Attack B should test Ghost correctly identifying security risks."""
        attack = GhostAttackGenerator.attack_b_security_fix()

        assert attack.expected_oracle_behavior["justified_severity"] == "MAJOR"
        assert attack.oracle_correct_verdict == "JUSTIFIED"

    def test_attack_i_targets_false_positives(self):
        """Attack I should expose false positive detections."""
        attack = GhostAttackGenerator.attack_i_false_positive()

        assert attack.oracle_correct_verdict == "INCORRECT"
        assert attack.expected_oracle_behavior["factual"] == "INCORRECT"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
