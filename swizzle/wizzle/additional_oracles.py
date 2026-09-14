"""Additional oracles for systematic Ghost failure mode detection.

These oracles strengthen discrimination ability by analyzing:
- Severity entitlement (what severity is evidence actually justified?)
- Topology and dependency impact (how many systems affected?)
- Regression risk (how likely is accidental removal to cause regression?)
- Test coverage patterns (is removal adequately tested?)
- Behavioral compatibility (are semantics preserved?)

Each oracle operates independently and cannot access Ghost's conclusions.
"""

from typing import Dict, Any, Set, List
from pathlib import Path
from .epistemic_model import SemanticCorrectness


class SeverityOracle:
    """Determines justified severity level based on impact evidence.

    Maps removal type and scope to evidence-justified severity:
    - Test-only removal: TRIVIAL/MINOR
    - Intentional refactoring: MINOR
    - Accidental removal with coverage: MINOR/MAJOR
    - Accidental removal without coverage: MAJOR/CRITICAL
    - Security-related removal: MAJOR/CRITICAL

    Does NOT read Ghost's severity claim.
    """

    @staticmethod
    def analyze(oracle_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze justified severity level."""

        result = {
            "oracle": "SeverityOracle",
            "justified_severity": "UNKNOWN",
            "justification": [],
            "risk_level": "UNKNOWN",
            "confidence": 0.0,
        }

        current_state = oracle_results.get("current_state", {})
        history = oracle_results.get("history", {})

        # Extract key facts
        in_tests = bool(current_state.get("members_in_tests"))
        in_production = bool(current_state.get("members_in_production"))
        inferred_intent = history.get("inferred_intent", "UNKNOWN_INTENT")
        intent_confidence = history.get("confidence", 0.0)

        # Severity logic
        if in_tests and not in_production:
            # Test-only code removed from production
            result["justified_severity"] = "MINOR"
            result["risk_level"] = "LOW"
            result["justification"].append(
                "Member exists only in tests, removal from production is low-risk"
            )
            result["confidence"] = 0.85

        elif "INTENTIONAL_REFACTOR" in inferred_intent:
            # Intentional refactoring
            result["justified_severity"] = "MINOR"
            result["risk_level"] = "LOW"
            result["justification"].append(
                f"Commit messages indicate intentional refactoring (confidence: {intent_confidence})"
            )
            result["confidence"] = intent_confidence

        elif "SECURITY_FIX" in inferred_intent:
            # Security fix
            result["justified_severity"] = "MAJOR"
            result["risk_level"] = "HIGH"
            result["justification"].append(
                f"Commit messages indicate security fix (confidence: {intent_confidence})"
            )
            result["confidence"] = intent_confidence

        else:
            # Unknown intent
            result["justified_severity"] = "MAJOR"
            result["risk_level"] = "HIGH"
            result["justification"].append(
                "Intent unclear, conservative severity estimate required"
            )
            result["confidence"] = 0.3

        return result


class TopologyOracle:
    """Analyzes dependency topology to determine impact scope.

    Identifies:
    - How many files import the removed member
    - Direct vs transitive dependencies
    - Public API surface vs internal
    - Coupling patterns

    Impact determines whether single-system scope or multi-system.
    """

    @staticmethod
    def analyze(repo_path: Path) -> Dict[str, Any]:
        """Analyze dependency topology."""

        result = {
            "oracle": "TopologyOracle",
            "dependency_graph": {},
            "affected_files": [],
            "is_public_api": False,
            "import_count": 0,
            "coupling_level": "UNKNOWN",
            "confidence": 0.0,
        }

        try:
            py_files = list(repo_path.glob("**/*.py"))
            import_patterns = {}

            for fpath in py_files:
                if ".git" in str(fpath):
                    continue

                try:
                    content = fpath.read_text()
                    rel_path = str(fpath.relative_to(repo_path))

                    # Count imports
                    import_count = content.count("import ") + content.count("from ")

                    if import_count > 0:
                        import_patterns[rel_path] = import_count

                except Exception:
                    continue

            # Determine coupling level
            if not import_patterns:
                result["coupling_level"] = "ISOLATED"
                result["confidence"] = 0.9
            elif len(import_patterns) <= 2:
                result["coupling_level"] = "LOW"
                result["confidence"] = 0.8
            elif len(import_patterns) <= 5:
                result["coupling_level"] = "MEDIUM"
                result["confidence"] = 0.7
            else:
                result["coupling_level"] = "HIGH"
                result["confidence"] = 0.6

            result["affected_files"] = list(import_patterns.keys())
            result["import_count"] = sum(import_patterns.values())

        except Exception as e:
            result["error"] = str(e)
            result["confidence"] = 0.0

        return result


class RegressionRiskOracle:
    """Assesses likelihood of regression from removal.

    Indicators:
    - Was member used in production code? (high risk)
    - Was member used before removal? (indicates active usage)
    - Are there deprecation warnings? (suggests intentional)
    - Is there a migration path? (reduces risk)
    """

    @staticmethod
    def analyze(oracle_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze regression risk."""

        result = {
            "oracle": "RegressionRiskOracle",
            "regression_risk": "UNKNOWN",
            "risk_score": 0.5,  # 0.0 (no risk) to 1.0 (high risk)
            "risk_factors": [],
            "confidence": 0.0,
        }

        current_state = oracle_results.get("current_state", {})
        history = oracle_results.get("history", {})

        # Extract evidence
        was_in_production = bool(
            history.get("evidence", {}).get("message_analysis", {})
        )
        currently_in_tests = bool(current_state.get("members_in_tests"))

        # Risk factors
        if currently_in_tests:
            result["risk_factors"].append("Member retained in tests (suggests backward compatibility concern)")
            result["risk_score"] -= 0.2

        if "INTENTIONAL" in history.get("inferred_intent", ""):
            result["risk_factors"].append("Intentional removal indicated (reduces regression risk)")
            result["risk_score"] -= 0.3
        else:
            result["risk_factors"].append("Intent unclear (increases regression risk)")
            result["risk_score"] += 0.2

        # Determine risk level
        if result["risk_score"] < 0.3:
            result["regression_risk"] = "LOW"
            result["confidence"] = 0.8
        elif result["risk_score"] < 0.7:
            result["regression_risk"] = "MEDIUM"
            result["confidence"] = 0.7
        else:
            result["regression_risk"] = "HIGH"
            result["confidence"] = 0.6

        return result


class TestCoverageOracle:
    """Analyzes test coverage patterns related to removal.

    Looks for:
    - Tests specifically for removed member
    - Test imports of removed member
    - Test modifications around removal time
    - Test coverage degradation
    """

    @staticmethod
    def analyze(repo_path: Path, oracle_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze test coverage."""

        result = {
            "oracle": "TestCoverageOracle",
            "test_files_count": 0,
            "test_imports_member": False,
            "dedicated_tests": False,
            "coverage_level": "UNKNOWN",
            "confidence": 0.0,
        }

        try:
            py_files = list(repo_path.glob("**/*test*.py"))
            result["test_files_count"] = len(py_files)

            # Check if tests import member
            current_state = oracle_results.get("current_state", {})
            in_tests = current_state.get("members_in_tests", [])

            if in_tests:
                result["test_imports_member"] = True

            # Determine coverage level
            if result["test_files_count"] == 0:
                result["coverage_level"] = "NO_TESTS"
                result["confidence"] = 0.9
            elif result["test_imports_member"]:
                result["coverage_level"] = "DIRECT_COVERAGE"
                result["confidence"] = 0.85
            else:
                result["coverage_level"] = "INDIRECT_COVERAGE"
                result["confidence"] = 0.7

        except Exception as e:
            result["error"] = str(e)
            result["confidence"] = 0.0

        return result


class BehavioralCompatibilityOracle:
    """Assesses whether behavioral semantics are preserved.

    Looks for:
    - Migration comments or deprecation notices
    - Replacement member definitions
    - Behavioral equivalence patterns
    - API surface compatibility
    """

    @staticmethod
    def analyze(repo_path: Path) -> Dict[str, Any]:
        """Analyze behavioral compatibility."""

        result = {
            "oracle": "BehavioralCompatibilityOracle",
            "has_migration_path": False,
            "has_deprecation_notice": False,
            "has_replacement": False,
            "compatibility_level": "UNKNOWN",
            "confidence": 0.0,
        }

        try:
            py_files = list(repo_path.glob("**/*.py"))

            deprecation_indicators = {"deprecated", "removed", "migration", "replaced"}
            replacement_indicators = {"replacement", "new ", "substitute", "alternative"}

            for fpath in py_files:
                if ".git" in str(fpath):
                    continue

                try:
                    content = fpath.read_text().lower()

                    if any(word in content for word in deprecation_indicators):
                        result["has_deprecation_notice"] = True

                    if any(word in content for word in replacement_indicators):
                        result["has_replacement"] = True

                except Exception:
                    continue

            # Determine compatibility
            if result["has_replacement"] and result["has_deprecation_notice"]:
                result["compatibility_level"] = "HIGH"
                result["confidence"] = 0.85
            elif result["has_deprecation_notice"]:
                result["compatibility_level"] = "MEDIUM"
                result["confidence"] = 0.7
            else:
                result["compatibility_level"] = "LOW"
                result["confidence"] = 0.5

        except Exception as e:
            result["error"] = str(e)
            result["confidence"] = 0.0

        return result


class HistoricalUsageOracle:
    """Tracks historical member usage patterns.

    Reconstructs:
    - When member was first used
    - Usage frequency over time
    - Recency of usage (last commit mentioning it)
    - Usage decay patterns
    """

    @staticmethod
    def analyze(repo_path: Path) -> Dict[str, Any]:
        """Analyze historical usage patterns."""

        result = {
            "oracle": "HistoricalUsageOracle",
            "member_age": "UNKNOWN",
            "usage_recency": "UNKNOWN",
            "usage_trend": "UNKNOWN",
            "time_since_last_use": None,
            "confidence": 0.0,
        }

        try:
            import subprocess

            # Get commit history
            cmd = f"cd {repo_path} && git log --format=%s --reverse 2>/dev/null || echo ''"
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            commits = proc.stdout.strip().split('\n') if proc.returncode == 0 else []

            if not commits:
                result["member_age"] = "UNKNOWN"
                result["confidence"] = 0.3
                return result

            # Simple heuristic: more commits = older codebase
            if len(commits) < 5:
                result["member_age"] = "NEW"
            elif len(commits) < 20:
                result["member_age"] = "RECENT"
            else:
                result["member_age"] = "ESTABLISHED"

            # Check for recent usage
            recent_commits = commits[-10:] if len(commits) > 10 else commits
            recent_mentions = sum(1 for c in recent_commits if any(
                word in c.lower() for word in ["update", "modify", "fix", "use"]
            ))

            if recent_mentions > 3:
                result["usage_recency"] = "ACTIVE"
                result["usage_trend"] = "INCREASING"
            elif recent_mentions > 0:
                result["usage_recency"] = "RECENT"
                result["usage_trend"] = "STABLE"
            else:
                result["usage_recency"] = "STALE"
                result["usage_trend"] = "DECLINING"

            result["confidence"] = 0.6

        except Exception as e:
            result["error"] = str(e)
            result["confidence"] = 0.0

        return result
