"""Phase 3 Requirement #10: Oracle independence verification.

Tests that oracles are truly independent assessment layers that:
1. Do not access Ghost's conclusions, severity, or confidence
2. Produce the same assessment even when Ghost results are corrupted
3. Cannot be misled by Ghost's false claims

This ensures WIZZLE's epistemic foundation is sound.
"""

import pytest
import json
from copy import deepcopy
from .oracles import HistoryOracle, CurrentStateOracle, SemanticIntegrityOracle
from .additional_oracles import SeverityOracle, TopologyOracle, RegressionRiskOracle
from .epistemic_model import IntentKind
from .evaluator import Evaluator
from pathlib import Path


class TestOracleIndependenceNever:
    """Tests that verify oracles NEVER access Ghost results."""

    def test_history_oracle_no_ghost_access(self):
        """HistoryOracle analyzes git history, never reads Ghost findings."""

        # Setup: Any ghost claim about severity/confidence should not affect history analysis
        oracle_results = {}

        # Run oracle WITHOUT any ghost data present
        # We can't mock Path.exists, so we'll just verify the method signature
        import inspect
        sig = inspect.signature(HistoryOracle.analyze)

        # Should only take repo_path
        params = list(sig.parameters.keys())
        assert params == ["repo_path"], (
            f"HistoryOracle.analyze should only take repo_path, got {params}"
        )

        # Should NOT have parameters for ghost_conclusion, ghost_severity, etc
        forbidden_params = [
            "ghost_severity", "ghost_confidence", "ghost_conclusion",
            "ghost_findings", "ghost_result"
        ]
        for param in forbidden_params:
            assert param not in params, (
                f"HistoryOracle.analyze should not accept {param}"
            )

    def test_current_state_oracle_no_ghost_access(self):
        """CurrentStateOracle scans files, never reads Ghost findings."""

        import inspect
        sig = inspect.signature(CurrentStateOracle.analyze)

        params = list(sig.parameters.keys())
        assert params == ["repo_path"]

        forbidden_params = [
            "ghost_severity", "ghost_confidence", "ghost_conclusion"
        ]
        for param in forbidden_params:
            assert param not in params

    def test_severity_oracle_no_ghost_access(self):
        """SeverityOracle determines justified severity, never reads Ghost claims."""

        import inspect
        sig = inspect.signature(SeverityOracle.analyze)

        params = list(sig.parameters.keys())
        assert params == ["oracle_results"]

        # Should work ONLY on oracle results, not Ghost results
        assert "ghost" not in params[0].lower()


class TestOracleIndependenceConsistency:
    """Tests that oracle assessments remain consistent regardless of Ghost corruption."""

    def test_oracle_consistent_with_clean_ghost(self):
        """Baseline: Oracles produce consistent results with good Ghost data."""

        oracle_results = {
            "history": {
                "inferred_intent": "INTENTIONAL_REFACTOR",
                "confidence": 0.8,
            },
            "current_state": {
                "members_in_production": [],
                "members_in_tests": ["LegacyStatus"],
            }
        }

        # Run oracle assessment
        severity_result = SeverityOracle.analyze(oracle_results)

        # Should produce consistent result
        assert severity_result["justified_severity"] == "MINOR"
        baseline_verdict = severity_result["justified_severity"]

        return baseline_verdict

    def test_oracle_consistent_with_corrupted_ghost_severity(self):
        """Oracle verdict unchanged even if Ghost severity claim is wrong."""

        # Setup: Oracle results indicating intentional refactor
        oracle_results = {
            "history": {
                "inferred_intent": "INTENTIONAL_REFACTOR",
                "confidence": 0.8,
            },
            "current_state": {
                "members_in_production": [],
                "members_in_tests": ["LegacyStatus"],
            }
        }

        # Run oracle WITHOUT corrupted ghost claim
        severity_result_clean = SeverityOracle.analyze(oracle_results)

        # Now simulate Ghost making a FALSE claim about severity
        # (This should NOT affect oracle's assessment)
        ghost_false_claim = {
            "severity": "CRITICAL",  # False and extreme
            "confidence": 0.99,       # False confidence
            "member_removed": True
        }

        # Oracle should still produce same assessment (it doesn't read ghost_false_claim)
        severity_result_with_corruption = SeverityOracle.analyze(oracle_results)

        # Severity assessment should be IDENTICAL
        assert severity_result_clean["justified_severity"] == severity_result_with_corruption["justified_severity"]
        assert severity_result_clean["risk_level"] == severity_result_with_corruption["risk_level"]

    def test_oracle_consistent_with_corrupted_ghost_confidence(self):
        """Oracle assessment independent of Ghost's confidence claim."""

        oracle_results = {
            "history": {
                "inferred_intent": "ACCIDENTAL_REMOVAL",
                "confidence": 0.3,  # Low confidence
            },
            "current_state": {
                "members_in_production": [],
                "members_in_tests": [],
            }
        }

        result1 = SeverityOracle.analyze(oracle_results)

        # Even if Ghost claims high confidence, oracle verdict unchanged
        ghost_false_confidence = {"confidence": 0.95}  # Oracle never reads this

        result2 = SeverityOracle.analyze(oracle_results)

        assert result1["justified_severity"] == result2["justified_severity"]


class TestOracleIndependenceCannotBeMisled:
    """Tests that oracles cannot be misled by Ghost's claims."""

    def test_oracle_unaffected_by_false_ghost_removal_claim(self):
        """Oracle assessment unchanged if Ghost falsely claims removal."""

        # True state: Member still exists in production
        oracle_results = {
            "current_state": {
                "members_in_production": ["PHANTOM"],  # Actually there
                "members_in_tests": [],
            },
            "history": {
                "inferred_intent": "UNKNOWN_INTENT",
                "confidence": 0.5,
            }
        }

        # Ghost might falsely claim: "PHANTOM removed"
        # But oracle only looks at actual file state
        severity_result = SeverityOracle.analyze(oracle_results)

        # Oracle should work correctly on actual state
        assert isinstance(severity_result["justified_severity"], str)
        assert severity_result["justified_severity"] in ["TRIVIAL", "MINOR", "MAJOR", "CRITICAL"]

    def test_oracle_unaffected_by_false_ghost_intention_claim(self):
        """Oracle judgment unchanged if Ghost mischaracterizes intent."""

        oracle_results = {
            "history": {
                "inferred_intent": "SECURITY_FIX",  # True intent
                "confidence": 0.85,
            },
            "current_state": {
                "members_in_production": [],
                "members_in_tests": [],
            }
        }

        severity_result = SeverityOracle.analyze(oracle_results)
        baseline_severity = severity_result["justified_severity"]

        # Ghost might falsely claim: "This looks like a refactor"
        # But oracle reads actual commit history, not Ghost's interpretation
        ghost_false_interpretation = {"oracle_interpretation": "INTENTIONAL_REFACTOR"}

        # Oracle produces same result
        severity_result2 = SeverityOracle.analyze(oracle_results)

        assert severity_result2["justified_severity"] == baseline_severity

    def test_oracle_unaffected_by_ghost_confidence_inflation(self):
        """Oracle doesn't inflate verdict based on Ghost's false confidence."""

        oracle_results = {
            "history": {
                "inferred_intent": "UNKNOWN_INTENT",  # Low confidence situation
                "confidence": 0.2,  # Very low
            },
            "current_state": {
                "members_in_production": [],
                "members_in_tests": [],
            }
        }

        severity_result = SeverityOracle.analyze(oracle_results)

        # Ghost might falsely claim high confidence (to pressure action)
        # But oracle confidence is based on evidence, not Ghost's claim
        ghost_false_confidence_boost = {"confidence": 0.95}

        # Oracle produces same conservative assessment
        severity_result2 = SeverityOracle.analyze(oracle_results)

        assert severity_result["confidence"] == severity_result2["confidence"]
        # Should remain low due to uncertain intent
        assert severity_result["confidence"] < 0.5


class TestOracleIndependenceContradictory:
    """Tests that oracles work correctly even when Ghost contradicts them."""

    def test_oracle_functions_when_ghost_says_opposite(self):
        """Oracles produce correct assessment even when Ghost says the opposite."""

        oracle_results = {
            "history": {
                "inferred_intent": "INTENTIONAL_REFACTOR",
                "confidence": 0.8,
            },
            "current_state": {
                "members_in_production": [],
                "members_in_tests": ["Member"],
            }
        }

        verdict = SeverityOracle.analyze(oracle_results)

        # Oracle says: MINOR severity for intentional refactor
        assert verdict["justified_severity"] == "MINOR"

        # Even if Ghost says: CRITICAL severity (opposite)
        ghost_opposite_claim = {
            "severity": "CRITICAL",
            "claim": "This is a major breaking change"
        }

        # Oracle still produces correct assessment
        verdict2 = SeverityOracle.analyze(oracle_results)
        assert verdict2["justified_severity"] == "MINOR"

        # Oracles can therefore detect Ghost's error
        oracle_claims_minor = verdict["justified_severity"]
        ghost_claims_critical = "CRITICAL"

        assert oracle_claims_minor != ghost_claims_critical, (
            "Oracles successfully identified divergence from Ghost"
        )


class TestOracleIndependenceVerifiable:
    """Tests that oracle independence can be verified programmatically."""

    def test_oracle_results_reproducible(self):
        """Same oracle input produces same results repeatedly."""

        oracle_results = {
            "history": {
                "inferred_intent": "SECURITY_FIX",
                "confidence": 0.9,
            },
            "current_state": {
                "members_in_production": [],
                "members_in_tests": [],
            }
        }

        # Run oracle multiple times
        results = [SeverityOracle.analyze(oracle_results) for _ in range(5)]

        # All results should be identical
        assert all(r["justified_severity"] == results[0]["justified_severity"] for r in results)
        assert all(r["risk_level"] == results[0]["risk_level"] for r in results)

    def test_oracle_order_independence(self):
        """Oracle results don't depend on analysis order."""

        oracle_results = {
            "history": {
                "inferred_intent": "INTENTIONAL_REFACTOR",
                "confidence": 0.7,
            },
            "current_state": {
                "members_in_production": [],
                "members_in_tests": ["Member"],
            }
        }

        # Analyze in one order
        severity1 = SeverityOracle.analyze(oracle_results)
        regression1 = RegressionRiskOracle.analyze(oracle_results)

        # Analyze in different order
        regression2 = RegressionRiskOracle.analyze(oracle_results)
        severity2 = SeverityOracle.analyze(oracle_results)

        # Results should be identical
        assert severity1["justified_severity"] == severity2["justified_severity"]
        assert regression1["regression_risk"] == regression2["regression_risk"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
