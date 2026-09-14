"""Tests for Ghost invocation and integration."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from .ghost_invoker import GhostInvoker, GhostFinding, GhostAnalysis


def test_ghost_finding_dataclass():
    """Test GhostFinding construction."""
    finding = GhostFinding(
        member_name="PHANTOM",
        file_path="enums.py",
        severity="MAJOR",
        category="REGRESSION",
        message="Member removed but used in tests",
        metadata={"confidence": 0.85}
    )

    assert finding.member_name == "PHANTOM"
    assert finding.severity == "MAJOR"
    assert finding.category == "REGRESSION"
    assert finding.metadata["confidence"] == 0.85


def test_ghost_analysis_dataclass():
    """Test GhostAnalysis construction."""
    findings = [
        GhostFinding("A", "file.py", "MAJOR", "REG", "msg", {})
    ]
    analysis = GhostAnalysis(
        findings=findings,
        repository_path=Path("/repo"),
        status="success"
    )

    assert len(analysis.findings) == 1
    assert analysis.status == "success"


def test_parse_findings_valid_json():
    """Test parsing valid Ghost JSON output."""
    data = {
        "findings": [
            {
                "member": "PHANTOM",
                "file": "enums.py",
                "severity": "MAJOR",
                "category": "REGRESSION",
                "message": "Test message",
                "metadata": {"confidence": 0.8}
            }
        ]
    }

    findings = GhostInvoker._parse_findings(data)
    assert len(findings) == 1
    assert findings[0].member_name == "PHANTOM"


def test_parse_findings_empty_list():
    """Test parsing empty findings list."""
    data = {"findings": []}
    findings = GhostInvoker._parse_findings(data)
    assert findings == []


def test_parse_findings_invalid_structure():
    """Test parsing handles malformed data gracefully."""
    data = {
        "findings": [
            {
                "member": "PHANTOM"
                # Missing required fields
            },
            {
                "member": "MEDIUM",
                "file": "enums.py",
                "severity": "MINOR",
                "category": "IMPROVEMENT",
                "message": "Valid",
                "metadata": {}
            }
        ]
    }

    findings = GhostInvoker._parse_findings(data)
    # Should skip malformed, keep valid
    assert len(findings) >= 1


def test_parse_findings_no_findings_key():
    """Test parsing JSON without findings key."""
    data = {"status": "success"}
    findings = GhostInvoker._parse_findings(data)
    assert findings == []


def test_invoker_nonexistent_repo():
    """Test invoker handles nonexistent repository."""
    invoker = GhostInvoker.__new__(GhostInvoker)
    invoker.ghost_path = Path("/fake/ghost")
    invoker.ghost_available = True

    analysis = invoker.invoke(Path("/nonexistent/repo"))
    assert analysis.status == "error"
    assert "not found" in analysis.error_message.lower()


def test_compare_with_oracle_basic():
    """Test comparing Ghost findings with oracle results."""
    invoker = GhostInvoker.__new__(GhostInvoker)
    invoker.ghost_path = Path("/fake/ghost")

    ghost_analysis = GhostAnalysis(
        findings=[
            GhostFinding("PHANTOM", "enums.py", "MAJOR", "REGRESSION",
                        "Member removed", {})
        ],
        repository_path=Path("/repo"),
        status="success"
    )

    oracle_results = {
        "history": {
            "inferred_intent": "INTENTIONAL_REFACTOR",
            "confidence": 0.4
        }
    }

    comparison = invoker.compare_with_oracle(ghost_analysis, oracle_results)
    assert comparison["ghost_findings_count"] == 1
    assert comparison["oracle_inferred_intent"] == "INTENTIONAL_REFACTOR"
    assert len(comparison["assessments"]) == 1


def test_assess_finding_intentional_refactor():
    """Test assessment when intent is intentional refactor."""
    ghost_finding = GhostFinding(
        "PHANTOM", "enums.py", "MAJOR", "REMOVED_FROM_LIBRARY", "msg", {}
    )

    oracle_results = {
        "history": {
            "inferred_intent": "INTENTIONAL_REFACTOR",
            "confidence": 0.5
        },
        "current_state": {
            "members_in_production": [],
            "members_in_tests": ["PHANTOM"]
        }
    }

    assessment = GhostInvoker._assess_finding(ghost_finding, oracle_results)

    assert assessment["oracle_intent"] == "INTENTIONAL_REFACTOR"
    # With intentional refactor intent, MAJOR severity is OVERCLAIMED (max is MINOR)
    assert assessment["semantic_correctness"] == "OVERCLAIMED"


@patch('swizzle.wizzle.ghost_invoker.Path.exists')
@patch('swizzle.wizzle.ghost_invoker.subprocess.run')
def test_invoke_ghost_success(mock_run, mock_exists):
    """Test successful Ghost invocation (with mocked Ghost)."""
    invoker = GhostInvoker.__new__(GhostInvoker)
    invoker.ghost_path = Path("/usr/bin/ghost")
    invoker.ghost_available = True

    # Mock path existence
    mock_exists.return_value = True

    # Mock successful Ghost output
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = json.dumps({
        "findings": [
            {
                "member": "TEST",
                "file": "file.py",
                "severity": "MINOR",
                "category": "INFO",
                "message": "Found member",
                "metadata": {}
            }
        ]
    })

    analysis = invoker.invoke(Path("/repo"))

    assert analysis.status == "success"
    assert len(analysis.findings) == 1


@patch('swizzle.wizzle.ghost_invoker.Path.exists')
@patch('swizzle.wizzle.ghost_invoker.subprocess.run')
def test_invoke_ghost_timeout(mock_run, mock_exists):
    """Test Ghost invocation timeout handling."""
    import subprocess

    invoker = GhostInvoker.__new__(GhostInvoker)
    invoker.ghost_path = Path("/usr/bin/ghost")
    invoker.ghost_available = True

    # Mock path existence
    mock_exists.return_value = True
    mock_run.side_effect = subprocess.TimeoutExpired("ghost", 30)

    analysis = invoker.invoke(Path("/repo"))

    assert analysis.status == "timeout"
    assert "timed out" in analysis.error_message.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
