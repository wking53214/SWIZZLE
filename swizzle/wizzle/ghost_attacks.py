"""Phase 3 Requirement #8: 10 specific Ghost attacks for failure mode testing.

These attacks systematically test where Ghost fails, overclaims, or misinterprets:

Attack A: Intentional Refactor (member removed as part of cleanup)
Attack B: Security Fix (member removed due to vulnerability)
Attack C: Test-Only Migration (member moved from production to tests)
Attack D: Dead Code (member unused but harmless)
Attack E: Deprecation Path (replacement exists and documented)
Attack F: Accidental Removal (member unintentionally deleted)
Attack G: API Evolution (signature changed, old version removed)
Attack H: Transitive Dependency (member depends on removed member)
Attack I: False Positive (member not actually removed)
Attack J: Ambiguous Context (removal could be intentional or accidental)

Each attack targets a different Ghost failure mode and is independently
evaluable by oracles without knowing Ghost's conclusion.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from pathlib import Path
from enum import Enum, auto


class AttackType(Enum):
    """The 10 attack types for Ghost failure mode testing."""
    A_INTENTIONAL_REFACTOR = auto()
    B_SECURITY_FIX = auto()
    C_TEST_ONLY_MIGRATION = auto()
    D_DEAD_CODE = auto()
    E_DEPRECATION_PATH = auto()
    F_ACCIDENTAL_REMOVAL = auto()
    G_API_EVOLUTION = auto()
    H_TRANSITIVE_DEPENDENCY = auto()
    I_FALSE_POSITIVE = auto()
    J_AMBIGUOUS_CONTEXT = auto()


@dataclass
class GhostAttack:
    """A single attack scenario to test Ghost's failure modes."""
    attack_id: str
    attack_type: AttackType
    member_name: str
    description: str
    repository_setup: Dict[str, Any]  # Files and content to create
    expected_ghost_behavior: Dict[str, Any]  # What Ghost should say
    expected_oracle_behavior: Dict[str, Any]  # What oracles should determine
    oracle_correct_verdict: str  # CORRECT, OVERCLAIMED, UNDERCLAIMED, CONTRADICTED
    evidence_indicators: Dict[str, bool]  # What evidence should be present


class GhostAttackGenerator:
    """Generate and evaluate Ghost attack scenarios."""

    ATTACKS = {}  # Populated by attack_* methods

    @staticmethod
    def attack_a_intentional_refactor() -> GhostAttack:
        """Attack A: Intentional refactoring should not be flagged as MAJOR."""

        return GhostAttack(
            attack_id="GHOST_ATTACK_A",
            attack_type=AttackType.A_INTENTIONAL_REFACTOR,
            member_name="LegacyStatus",
            description=(
                "Member intentionally removed as part of comprehensive refactor. "
                "Commit messages explicitly indicate refactoring intent. "
                "Member remains in tests for backward compatibility. "
                "Ghost should flag as removal but severity should be MINOR not MAJOR."
            ),
            repository_setup={
                "production_before": "class LegacyStatus(Enum):\n    OLD_STATE = 1",
                "production_after": "",  # Removed
                "test_content": "from enum import LegacyStatus  # For backward compat",
                "commit_message": "refactor: simplify status enum, remove legacy states",
            },
            expected_ghost_behavior={
                "finding": "REMOVED_FROM_LIBRARY",
                "overclaimed_severity": "MAJOR",
            },
            expected_oracle_behavior={
                "inferred_intent": "INTENTIONAL_REFACTOR",
                "justified_severity": "MINOR",
                "factual": "CORRECT",
                "semantic": "OVERCLAIMED",
            },
            oracle_correct_verdict="OVERCLAIMED",
            evidence_indicators={
                "commit_indicates_refactor": True,
                "member_in_tests": True,
                "member_gone_from_production": True,
                "no_regression_indicators": True,
            }
        )

    @staticmethod
    def attack_b_security_fix() -> GhostAttack:
        """Attack B: Security removal should justify MAJOR severity."""

        return GhostAttack(
            attack_id="GHOST_ATTACK_B",
            attack_type=AttackType.B_SECURITY_FIX,
            member_name="WeakAuthMethod",
            description=(
                "Member removed due to security vulnerability. "
                "Commit message indicates security fix. "
                "Ghost should correctly identify as MAJOR severity. "
                "Oracles should confirm security context."
            ),
            repository_setup={
                "production_before": "def weak_auth(): return True  # VULNERABLE",
                "production_after": "",  # Removed
                "test_content": "",
                "commit_message": "security: remove weak authentication method (CVE-2024-1234)",
            },
            expected_ghost_behavior={
                "finding": "REMOVED_FROM_LIBRARY",
                "severity": "MAJOR",
            },
            expected_oracle_behavior={
                "inferred_intent": "SECURITY_FIX",
                "justified_severity": "MAJOR",
                "factual": "CORRECT",
                "semantic": "JUSTIFIED",
            },
            oracle_correct_verdict="JUSTIFIED",
            evidence_indicators={
                "commit_indicates_security": True,
                "member_gone_from_production": True,
                "severity_matches_evidence": True,
            }
        )

    @staticmethod
    def attack_c_test_only_migration() -> GhostAttack:
        """Attack C: Test-only member in production should justify LOW severity."""

        return GhostAttack(
            attack_id="GHOST_ATTACK_C",
            attack_type=AttackType.C_TEST_ONLY_MIGRATION,
            member_name="TestHelper",
            description=(
                "Member was test-only in production (imported in production but only for testing). "
                "Removal is low-risk as it was never part of actual production logic. "
                "Ghost may overclaim severity."
            ),
            repository_setup={
                "production_before": "from tests import TestHelper",  # Only imported, not used
                "production_after": "",  # Removed
                "test_content": "class TestHelper: pass",
                "commit_message": "refactor: move test helper to test module",
            },
            expected_ghost_behavior={
                "finding": "REMOVED_FROM_LIBRARY",
                "overclaimed_severity": "MAJOR",
            },
            expected_oracle_behavior={
                "inferred_intent": "TEST_ONLY_MIGRATION",
                "justified_severity": "MINOR",
                "factual": "CORRECT",
                "semantic": "OVERCLAIMED",
            },
            oracle_correct_verdict="OVERCLAIMED",
            evidence_indicators={
                "member_only_in_tests": True,
                "removal_is_safe": True,
            }
        )

    @staticmethod
    def attack_d_dead_code() -> GhostAttack:
        """Attack D: Unused dead code removal should be low severity."""

        return GhostAttack(
            attack_id="GHOST_ATTACK_D",
            attack_type=AttackType.D_DEAD_CODE,
            member_name="UnusedUtil",
            description=(
                "Member has no references and was never called. "
                "Removal is safe with zero regression risk. "
                "Ghost may flag but severity should be TRIVIAL/MINOR."
            ),
            repository_setup={
                "production_before": "def unused_function(): return 42",
                "production_after": "",  # Removed
                "references": 0,
                "commit_message": "chore: remove dead code",
            },
            expected_ghost_behavior={
                "finding": "REMOVED_FROM_LIBRARY",
                "overclaimed_severity": "MAJOR",
            },
            expected_oracle_behavior={
                "inferred_intent": "DEAD_CODE_REMOVAL",
                "justified_severity": "TRIVIAL",
                "regression_risk": "NONE",
                "semantic": "OVERCLAIMED",
            },
            oracle_correct_verdict="OVERCLAIMED",
            evidence_indicators={
                "member_unreferenced": True,
                "never_called": True,
                "removal_safe": True,
            }
        )

    @staticmethod
    def attack_e_deprecation_path() -> GhostAttack:
        """Attack E: Removal of deprecated member with replacement should be MINOR."""

        return GhostAttack(
            attack_id="GHOST_ATTACK_E",
            attack_type=AttackType.E_DEPRECATION_PATH,
            member_name="OldAPI",
            description=(
                "Member was deprecated with warnings and has documented replacement. "
                "Users had migration path. Removal is not a breaking change. "
                "Ghost may overclaim severity."
            ),
            repository_setup={
                "production_before": "@deprecated('Use new_api() instead')\ndef old_api(): pass",
                "production_after": "",  # Removed
                "migration_path": "# Migrate from old_api() to new_api()",
                "commit_message": "refactor: remove deprecated old_api, use new_api",
            },
            expected_ghost_behavior={
                "finding": "REMOVED_FROM_LIBRARY",
                "overclaimed_severity": "MAJOR",
            },
            expected_oracle_behavior={
                "inferred_intent": "DEPRECATION_REMOVAL",
                "justified_severity": "MINOR",
                "has_replacement": True,
                "semantic": "OVERCLAIMED",
            },
            oracle_correct_verdict="OVERCLAIMED",
            evidence_indicators={
                "has_deprecation_notice": True,
                "has_replacement": True,
                "migration_documented": True,
            }
        )

    @staticmethod
    def attack_f_accidental_removal() -> GhostAttack:
        """Attack F: Accidental removal without deprecation should justify MAJOR."""

        return GhostAttack(
            attack_id="GHOST_ATTACK_F",
            attack_type=AttackType.F_ACCIDENTAL_REMOVAL,
            member_name="CriticalAPI",
            description=(
                "Member was used in production but removed accidentally. "
                "No deprecation warnings or migration path. "
                "No clear intent indicators. "
                "Ghost should correctly identify as MAJOR regression risk."
            ),
            repository_setup={
                "production_before": "def critical_api(): return important_data",
                "production_after": "",  # Accidentally removed
                "usage_count": 10,  # Was heavily used
                "commit_message": "cleanup: remove unused imports",  # Misleading message
            },
            expected_ghost_behavior={
                "finding": "REMOVED_FROM_LIBRARY",
                "severity": "MAJOR",
            },
            expected_oracle_behavior={
                "inferred_intent": "ACCIDENTAL_REMOVAL",  # Or UNKNOWN
                "regression_risk": "HIGH",
                "justified_severity": "MAJOR",
                "semantic": "JUSTIFIED",
            },
            oracle_correct_verdict="JUSTIFIED",
            evidence_indicators={
                "high_usage_count": True,
                "no_deprecation": True,
                "intent_unclear": True,
                "regression_risk_high": True,
            }
        )

    @staticmethod
    def attack_g_api_evolution() -> GhostAttack:
        """Attack G: API evolution where old signature replaced by new one."""

        return GhostAttack(
            attack_id="GHOST_ATTACK_G",
            attack_type=AttackType.G_API_EVOLUTION,
            member_name="OldSignature",
            description=(
                "Function signature changed: old_sig(a,b,c) replaced by new_sig(a,b,c,d). "
                "Old version removed, new version available. "
                "Removal is intentional evolution, justified MINOR severity."
            ),
            repository_setup={
                "production_before": "def old_signature(a, b, c): return compute(a,b,c)",
                "production_after": "def new_signature(a, b, c, d): return compute(a,b,c,d)",
                "commit_message": "refactor: evolve API to support new parameter",
                "has_replacement": True,
            },
            expected_ghost_behavior={
                "finding": "REMOVED_FROM_LIBRARY",
                "overclaimed_severity": "MAJOR",
            },
            expected_oracle_behavior={
                "inferred_intent": "API_EVOLUTION",
                "justified_severity": "MINOR",
                "has_replacement": True,
                "semantic": "OVERCLAIMED",
            },
            oracle_correct_verdict="OVERCLAIMED",
            evidence_indicators={
                "has_replacement": True,
                "replacement_compatible": True,
                "evolution_not_breaking": True,
            }
        )

    @staticmethod
    def attack_h_transitive_dependency() -> GhostAttack:
        """Attack H: Removal of member that other removed members depended on."""

        return GhostAttack(
            attack_id="GHOST_ATTACK_H",
            attack_type=AttackType.H_TRANSITIVE_DEPENDENCY,
            member_name="DepHelper",
            description=(
                "Member is a helper that was only used by other removed members. "
                "Its removal is a consequence, not a root cause. "
                "Should not be flagged independently as breaking change."
            ),
            repository_setup={
                "production_before": (
                    "def dep_helper(): return base_impl()\n"
                    "def only_caller(): return dep_helper()"
                ),
                "production_after": "",  # Both removed together
                "commit_message": "refactor: remove obsolete feature set",
            },
            expected_ghost_behavior={
                "finding": "REMOVED_FROM_LIBRARY",
                "severity": "MAJOR",
            },
            expected_oracle_behavior={
                "inferred_intent": "TRANSITIVE_REMOVAL",
                "justified_severity": "MINOR",  # Not independently breaking
                "semantic": "OVERCLAIMED",
            },
            oracle_correct_verdict="OVERCLAIMED",
            evidence_indicators={
                "only_used_by_removed": True,
                "removal_is_consequence": True,
            }
        )

    @staticmethod
    def attack_i_false_positive() -> GhostAttack:
        """Attack I: Member not actually removed (false positive detection)."""

        return GhostAttack(
            attack_id="GHOST_ATTACK_I",
            attack_type=AttackType.I_FALSE_POSITIVE,
            member_name="StillThere",
            description=(
                "Ghost claims member removed but it still exists. "
                "False positive: member was moved, aliased, or regenerated. "
                "Factual incorrectness."
            ),
            repository_setup={
                "production_before": "STILL_THERE = 1",
                "production_after": "STILL_THERE = 1",  # Still there!
                "ghost_claim": "REMOVED",
            },
            expected_ghost_behavior={
                "finding": "REMOVED_FROM_LIBRARY",
                "incorrect_factually": True,
            },
            expected_oracle_behavior={
                "member_still_in_production": True,
                "factual": "INCORRECT",
                "semantic": "UNASKABLE",
            },
            oracle_correct_verdict="INCORRECT",
            evidence_indicators={
                "member_exists": True,
                "ghost_is_wrong": True,
            }
        )

    @staticmethod
    def attack_j_ambiguous_context() -> GhostAttack:
        """Attack J: Context ambiguous - could be intentional or accidental."""

        return GhostAttack(
            attack_id="GHOST_ATTACK_J",
            attack_type=AttackType.J_AMBIGUOUS_CONTEXT,
            member_name="Ambiguous",
            description=(
                "Commit message vague: 'cleanup' could mean intentional or accidental. "
                "Member was used but not heavily. "
                "Oracles should return INCONCLUSIVE due to insufficient intent signals."
            ),
            repository_setup={
                "production_before": "def ambiguous(): return value",
                "production_after": "",  # Removed
                "usage_count": 2,  # Some usage but not heavy
                "commit_message": "cleanup",  # Ambiguous!
            },
            expected_ghost_behavior={
                "finding": "REMOVED_FROM_LIBRARY",
                "confidence": 0.5,  # Should be uncertain
            },
            expected_oracle_behavior={
                "inferred_intent": "UNKNOWN_INTENT",
                "semantic": "INCONCLUSIVE",
                "oracle_confidence": 0.3,
            },
            oracle_correct_verdict="INCONCLUSIVE",
            evidence_indicators={
                "intent_unclear": True,
                "moderate_usage": True,
                "insufficient_signals": True,
            }
        )

    @staticmethod
    def get_all_attacks() -> Dict[str, GhostAttack]:
        """Get all 10 attack scenarios."""

        return {
            "A": GhostAttackGenerator.attack_a_intentional_refactor(),
            "B": GhostAttackGenerator.attack_b_security_fix(),
            "C": GhostAttackGenerator.attack_c_test_only_migration(),
            "D": GhostAttackGenerator.attack_d_dead_code(),
            "E": GhostAttackGenerator.attack_e_deprecation_path(),
            "F": GhostAttackGenerator.attack_f_accidental_removal(),
            "G": GhostAttackGenerator.attack_g_api_evolution(),
            "H": GhostAttackGenerator.attack_h_transitive_dependency(),
            "I": GhostAttackGenerator.attack_i_false_positive(),
            "J": GhostAttackGenerator.attack_j_ambiguous_context(),
        }

    @staticmethod
    def evaluate_attack(
        attack: GhostAttack,
        ghost_conclusion: Dict[str, Any],
        oracle_assessment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate whether Ghost's conclusion matches what oracles determine.

        Returns:
            {
                "attack_passed": bool,  # Did oracles correctly identify the failure mode?
                "ghost_correct": bool,  # Was Ghost's conclusion justified?
                "oracle_correct": bool,  # Did oracles make the right call?
                "discrepancy": str,  # What went wrong?
            }
        """

        result = {
            "attack_id": attack.attack_id,
            "attack_type": attack.attack_type.name,
        }

        # Extract oracle verdict
        oracle_verdict = oracle_assessment.get("semantic_correctness")
        expected_verdict = attack.oracle_correct_verdict

        # Determine if attack successfully identified failure mode
        result["oracle_correct"] = oracle_verdict == expected_verdict
        result["attack_passed"] = result["oracle_correct"]

        if not result["attack_passed"]:
            result["discrepancy"] = (
                f"Oracle verdict '{oracle_verdict}' differs from expected '{expected_verdict}'"
            )

        return result
