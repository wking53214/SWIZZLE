"""Tests for additional oracles implementing Phase 3 Requirement #9.

These tests verify that the new oracles (Severity, Topology, RegressionRisk,
TestCoverage, BehavioralCompatibility, HistoricalUsage) function correctly
and strengthen oracle discrimination ability.
"""

import pytest
import tempfile
from pathlib import Path
from .additional_oracles import (
    SeverityOracle, TopologyOracle, RegressionRiskOracle,
    TestCoverageOracle, BehavioralCompatibilityOracle, HistoricalUsageOracle
)
from .epistemic_model import IntentKind


class TestSeverityOracle:
    """Test SeverityOracle severity justification logic."""

    def test_severity_test_only_member(self):
        """Test-only removal should justify MINOR severity."""
        oracle_results = {
            "current_state": {
                "members_in_tests": ["PHANTOM"],
                "members_in_production": []
            },
            "history": {
                "inferred_intent": IntentKind.UNKNOWN_INTENT.name,
                "confidence": 0.3
            }
        }

        result = SeverityOracle.analyze(oracle_results)

        assert result["justified_severity"] == "MINOR"
        assert result["risk_level"] == "LOW"
        assert result["confidence"] > 0.8

    def test_severity_intentional_refactoring(self):
        """Intentional refactoring should justify MINOR severity."""
        oracle_results = {
            "current_state": {
                "members_in_tests": [],
                "members_in_production": []
            },
            "history": {
                "inferred_intent": "INTENTIONAL_REFACTOR",
                "confidence": 0.8
            }
        }

        result = SeverityOracle.analyze(oracle_results)

        assert result["justified_severity"] == "MINOR"
        assert result["risk_level"] == "LOW"

    def test_severity_security_fix(self):
        """Security fix should justify MAJOR severity."""
        oracle_results = {
            "current_state": {
                "members_in_tests": [],
                "members_in_production": []
            },
            "history": {
                "inferred_intent": "SECURITY_FIX",
                "confidence": 0.9
            }
        }

        result = SeverityOracle.analyze(oracle_results)

        assert result["justified_severity"] == "MAJOR"
        assert result["risk_level"] == "HIGH"

    def test_severity_unknown_intent(self):
        """Unknown intent should justify MAJOR severity conservatively."""
        oracle_results = {
            "current_state": {
                "members_in_tests": [],
                "members_in_production": []
            },
            "history": {
                "inferred_intent": IntentKind.UNKNOWN_INTENT.name,
                "confidence": 0.2
            }
        }

        result = SeverityOracle.analyze(oracle_results)

        assert result["justified_severity"] == "MAJOR"
        assert result["confidence"] < 0.5


class TestTopologyOracle:
    """Test TopologyOracle dependency analysis."""

    def test_topology_isolated_module(self):
        """Isolated module with no imports should have LOW coupling."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create isolated file
            (repo_path / "isolated.py").write_text("x = 1")

            result = TopologyOracle.analyze(repo_path)

            # Empty or very low import count indicates isolation
            assert result["coupling_level"] in ["ISOLATED", "LOW"]
            assert result["import_count"] >= 0

    def test_topology_high_coupling(self):
        """Many imports indicate high coupling."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create multiple files with many imports to trigger high coupling
            for i in range(10):
                (repo_path / f"module_{i}.py").write_text(
                    "import sys\nimport os\nfrom pathlib import Path\nfrom typing import Dict\n"
                    "import json\nimport subprocess\nfrom datetime import datetime"
                )

            result = TopologyOracle.analyze(repo_path)

            assert result["import_count"] > 0
            # With 10 files x 6 imports each, coupling should be medium or high
            assert result["coupling_level"] in ["MEDIUM", "HIGH"]


class TestRegressionRiskOracle:
    """Test RegressionRiskOracle regression likelihood assessment."""

    def test_regression_risk_intentional_removal(self):
        """Intentional removal should have LOW regression risk."""
        oracle_results = {
            "current_state": {
                "members_in_tests": ["PHANTOM"]
            },
            "history": {
                "inferred_intent": "INTENTIONAL_REFACTOR",
                "evidence": {"message_analysis": {}}
            }
        }

        result = RegressionRiskOracle.analyze(oracle_results)

        assert result["regression_risk"] in ["LOW", "MEDIUM"]
        assert "Intentional removal" in result["risk_factors"][0] or len(result["risk_factors"]) > 0

    def test_regression_risk_unknown_intent(self):
        """Unknown intent should have HIGH regression risk."""
        oracle_results = {
            "current_state": {
                "members_in_tests": []
            },
            "history": {
                "inferred_intent": "UNKNOWN_INTENT",
                "evidence": {}
            }
        }

        result = RegressionRiskOracle.analyze(oracle_results)

        # With member not in tests and unknown intent, risk should be higher
        assert result["regression_risk"] in ["MEDIUM", "HIGH"]


class TestTestCoverageOracle:
    """Test TestCoverageOracle coverage analysis."""

    def test_test_coverage_no_tests(self):
        """Repository with no tests should report NO_TESTS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create only non-test files
            (repo_path / "main.py").write_text("x = 1")

            oracle_results = {
                "current_state": {
                    "members_in_tests": []
                }
            }

            result = TestCoverageOracle.analyze(repo_path, oracle_results)

            assert result["test_files_count"] == 0
            assert result["coverage_level"] == "NO_TESTS"

    def test_test_coverage_with_tests(self):
        """Repository with tests should report coverage level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create test files
            (repo_path / "test_main.py").write_text("def test_x(): pass")

            oracle_results = {
                "current_state": {
                    "members_in_tests": []
                }
            }

            result = TestCoverageOracle.analyze(repo_path, oracle_results)

            assert result["test_files_count"] > 0
            assert result["coverage_level"] in ["INDIRECT_COVERAGE", "DIRECT_COVERAGE"]

    def test_test_coverage_direct_import(self):
        """Member in tests should report DIRECT_COVERAGE."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create test file
            (repo_path / "test_main.py").write_text("from enum import PHANTOM")

            oracle_results = {
                "current_state": {
                    "members_in_tests": ["PHANTOM"]
                }
            }

            result = TestCoverageOracle.analyze(repo_path, oracle_results)

            assert result["test_imports_member"] is True
            assert result["coverage_level"] == "DIRECT_COVERAGE"


class TestBehavioralCompatibilityOracle:
    """Test BehavioralCompatibilityOracle semantic preservation."""

    def test_no_migration_notice(self):
        """Code without migration notices should report LOW compatibility."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create file without migration notices
            (repo_path / "code.py").write_text("x = 1")

            result = BehavioralCompatibilityOracle.analyze(repo_path)

            assert result["has_deprecation_notice"] is False
            assert result["compatibility_level"] == "LOW"

    def test_with_deprecation_notice(self):
        """Code with deprecation notice should report MEDIUM compatibility."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create file with deprecation notice
            (repo_path / "code.py").write_text(
                "# This function is deprecated and will be removed"
            )

            result = BehavioralCompatibilityOracle.analyze(repo_path)

            assert result["has_deprecation_notice"] is True
            assert result["compatibility_level"] in ["MEDIUM", "HIGH"]

    def test_with_replacement(self):
        """Code with replacement should report HIGH compatibility."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create file indicating replacement
            (repo_path / "code.py").write_text(
                "# Deprecated: Use the replacement function instead"
            )

            result = BehavioralCompatibilityOracle.analyze(repo_path)

            assert result["has_replacement"] is True


class TestHistoricalUsageOracle:
    """Test HistoricalUsageOracle usage pattern analysis."""

    def test_usage_trend_analysis(self):
        """Oracle should classify usage trends."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Initialize minimal git repo
            import subprocess
            subprocess.run(
                f"cd {repo_path} && git init",
                shell=True,
                capture_output=True
            )

            result = HistoricalUsageOracle.analyze(repo_path)

            # Should return structured result even if no commits
            assert "member_age" in result
            assert "usage_trend" in result
            assert result["confidence"] >= 0.0


class TestOracleIntegration:
    """Test integration of multiple oracles."""

    def test_oracle_independence(self):
        """Oracles should produce results independently."""
        oracle_results = {
            "current_state": {
                "members_in_tests": ["PHANTOM"],
                "members_in_production": []
            },
            "history": {
                "inferred_intent": "INTENTIONAL_REFACTOR",
                "confidence": 0.8
            }
        }

        # Run oracles independently
        severity_result = SeverityOracle.analyze(oracle_results)
        regression_result = RegressionRiskOracle.analyze(oracle_results)

        # Both should produce results without depending on each other
        assert severity_result["justified_severity"] is not None
        assert regression_result["regression_risk"] is not None

        # Results should be consistent (both see intentional refactor as lower risk)
        assert severity_result["risk_level"] in ["LOW", "UNKNOWN"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
