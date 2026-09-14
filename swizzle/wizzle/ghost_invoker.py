"""Ghost integration: invoke Ghost on repositories and capture findings.

This module bridges WIZZLE's independent evaluation with Ghost's analysis,
enabling comparison between Ghost's conclusions and oracle assessments.
"""

import json
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any

from .evidence_entitlement import (
    EvidenceEntitlementEvaluator, classify_evidence_from_oracle_results
)
from .epistemic_model import SemanticCorrectness, IntentKind

@dataclass
class GhostFinding:
    """A single finding from Ghost analysis."""
    member_name: str
    file_path: str
    severity: str  # "MAJOR", "MINOR", etc.
    category: str  # "REGRESSION", "IMPROVEMENT", etc.
    message: str
    metadata: Dict[str, Any]

@dataclass
class GhostAnalysis:
    """Complete analysis results from Ghost."""
    findings: list[GhostFinding]
    repository_path: Path
    status: str  # "success", "error", etc.
    error_message: Optional[str] = None

class GhostInvoker:
    """Invoke Ghost on repositories and capture its findings."""

    def __init__(self, ghost_path: Optional[Path] = None, allow_missing: bool = True):
        """Initialize Ghost invoker.

        Args:
            ghost_path: Path to Ghost executable. If None, searches PATH.
            allow_missing: If True, GhostInvoker can initialize without Ghost available
                          (will return UNAVAILABLE status on invoke()).
                          If False, raises RuntimeError if Ghost not found.
        """
        self.ghost_path = ghost_path
        self.allow_missing = allow_missing
        self.ghost_available = False

        try:
            if self.ghost_path is None:
                self.ghost_path = self._find_ghost()
            self.ghost_available = True
        except RuntimeError:
            if not allow_missing:
                raise
            self.ghost_path = None

    @staticmethod
    def _find_ghost() -> Path:
        """Find Ghost executable in PATH.

        Raises:
            RuntimeError: If Ghost is not found.
        """
        result = subprocess.run(
            "which ghost",
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Ghost not found in PATH. "
                "Install Ghost or pass ghost_path explicitly."
            )
        return Path(result.stdout.strip())

    def invoke(self, repo_path: Path, timeout: float = 30.0) -> GhostAnalysis:
        """Run Ghost on a repository and return findings.

        Args:
            repo_path: Path to repository to analyze
            timeout: Maximum execution time in seconds

        Returns:
            GhostAnalysis with findings or explicit error status

        Status values distinguish:
            "success" - Ghost executed, parsed, may have 0 findings
            "unavailable" - Ghost executable not found
            "timeout" - Execution exceeded timeout
            "crashed" - Non-zero exit but parsed output
            "malformed_output" - Could not parse JSON
            "no_findings" - Executed but produced no findings
            "error" - Repository missing or other error
        """

        # Check if Ghost is available
        if not self.ghost_available:
            return GhostAnalysis(
                findings=[],
                repository_path=repo_path,
                status="unavailable",
                error_message="Ghost executable not found"
            )

        if not repo_path.exists():
            return GhostAnalysis(
                findings=[],
                repository_path=repo_path,
                status="error",
                error_message=f"Repository not found: {repo_path}"
            )

        try:
            # Attempt to invoke Ghost with JSON output
            cmd = f"{self.ghost_path} analyze --json {repo_path}"
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            # Handle non-zero exit
            if result.returncode != 0:
                return GhostAnalysis(
                    findings=[],
                    repository_path=repo_path,
                    status="crashed",
                    error_message=f"Ghost exited with code {result.returncode}: {result.stderr}"
                )

            # Try to parse JSON output
            try:
                findings_data = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                return GhostAnalysis(
                    findings=[],
                    repository_path=repo_path,
                    status="malformed_output",
                    error_message=f"Failed to parse Ghost output as JSON: {e}\nOutput: {result.stdout[:500]}"
                )

            # Parse findings
            findings = self._parse_findings(findings_data)

            if not findings:
                return GhostAnalysis(
                    findings=[],
                    repository_path=repo_path,
                    status="no_findings",
                    error_message="Ghost executed successfully but produced no findings"
                )

            return GhostAnalysis(
                findings=findings,
                repository_path=repo_path,
                status="success"
            )

        except subprocess.TimeoutExpired:
            return GhostAnalysis(
                findings=[],
                repository_path=repo_path,
                status="timeout",
                error_message=f"Ghost analysis timed out after {timeout}s"
            )
        except Exception as e:
            return GhostAnalysis(
                findings=[],
                repository_path=repo_path,
                status="error",
                error_message=f"Unexpected error during Ghost invocation: {e}"
            )

    @staticmethod
    def _parse_findings(data: Any) -> list[GhostFinding]:
        """Parse Ghost JSON output into GhostFinding objects.

        Expected Ghost output format:
        {
            "findings": [
                {
                    "member": "PHANTOM",
                    "file": "enums.py",
                    "severity": "MAJOR",
                    "category": "REGRESSION",
                    "message": "...",
                    "metadata": {...}
                }
            ]
        }
        """
        findings = []

        if isinstance(data, dict) and "findings" in data:
            for item in data["findings"]:
                try:
                    finding = GhostFinding(
                        member_name=item.get("member", "unknown"),
                        file_path=item.get("file", "unknown"),
                        severity=item.get("severity", "UNKNOWN"),
                        category=item.get("category", "UNKNOWN"),
                        message=item.get("message", ""),
                        metadata=item.get("metadata", {})
                    )
                    findings.append(finding)
                except (KeyError, TypeError):
                    # Skip malformed findings
                    continue

        return findings

    def compare_with_oracle(self, ghost_analysis: GhostAnalysis,
                           oracle_results: Dict) -> Dict[str, Any]:
        """Compare Ghost findings against oracle assessment.

        Args:
            ghost_analysis: Results from Ghost.invoke()
            oracle_results: Results from Evaluator.run_oracles()

        Returns:
            Comparison results with semantic correctness assessment
        """
        comparison = {
            "ghost_findings_count": len(ghost_analysis.findings),
            "ghost_status": ghost_analysis.status,
            "oracle_inferred_intent": oracle_results.get("history", {}).get("inferred_intent"),
            "assessments": []
        }

        # Compare each Ghost finding against oracle
        for finding in ghost_analysis.findings:
            assessment = {
                "member": finding.member_name,
                "ghost_severity": finding.severity,
                "ghost_category": finding.category,
                "oracle_assessment": self._assess_finding(
                    finding,
                    oracle_results
                )
            }
            comparison["assessments"].append(assessment)

        return comparison

    @staticmethod
    def _assess_finding(ghost_finding: GhostFinding,
                       oracle_results: Dict) -> Dict[str, str]:
        """Assess whether Ghost's finding is semantically justified.

        Args:
            ghost_finding: Finding from Ghost
            oracle_results: Oracle assessment

        Returns:
            Assessment with semantic correctness verdict
        """
        # Get oracle's inferred intent from history
        inferred_intent = oracle_results.get("history", {}).get("inferred_intent")
        inferred_intent_str = str(inferred_intent).split('.')[-1] if inferred_intent else "UNKNOWN_INTENT"

        # Convert string intent to IntentKind enum if needed
        intent_kind = IntentKind.UNKNOWN_INTENT
        if isinstance(inferred_intent, str):
            try:
                intent_kind = IntentKind[inferred_intent]
            except (KeyError, AttributeError):
                intent_kind = IntentKind.UNKNOWN_INTENT
        elif isinstance(inferred_intent, IntentKind):
            intent_kind = inferred_intent

        # Extract evidence from oracle results
        test_imports_member = ghost_finding.member_name in oracle_results.get(
            "current_state", {}
        ).get("members_in_tests", [])
        present_evidence, absent_evidence = classify_evidence_from_oracle_results(
            oracle_results,
            test_imports_member=test_imports_member
        )

        # Map Ghost's category to a conclusion type
        conclusion = ghost_finding.category or "REMOVED_FROM_LIBRARY"

        # Use Evidence Entitlement Evaluator for semantic correctness assessment
        try:
            verdict_detail = EvidenceEntitlementEvaluator.evaluate_entitlement(
                conclusion=conclusion,
                intent_kind=intent_kind,
                evidence_present=present_evidence,
                evidence_absent=absent_evidence,
                evidence_weak=set(),
                evidence_contradicting=set(),
                ghost_severity=ghost_finding.severity or "UNKNOWN"
            )

            semantic_correctness = verdict_detail.semantic_correctness.name
            reason = (
                f"Evidence entitlement analysis: "
                f"max justified severity is {verdict_detail.maximum_justified_severity}, "
                f"Ghost claimed {ghost_finding.severity}"
            )

            return {
                "factual_correctness": "UNASKABLE",
                "semantic_correctness": semantic_correctness,
                "reason": reason,
                "oracle_intent": inferred_intent_str,
                "maximum_justified_severity": verdict_detail.maximum_justified_severity,
                "is_entitled": verdict_detail.is_entitled,
                "confidence": str(verdict_detail.confidence)
            }

        except Exception as e:
            return {
                "factual_correctness": "UNASKABLE",
                "semantic_correctness": "UNASKABLE",
                "reason": f"Assessment failed: {str(e)}",
                "oracle_intent": inferred_intent_str
            }
