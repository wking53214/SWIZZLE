"""Ghost Simulator: Generate plausible Ghost findings for testing.

IMPORTANT: This module generates SIMULATED Ghost findings for testing.
These results are NOT independent validation of Ghost behavior.

This is a FIXTURE, not an oracle.

Use for:
- Development/testing when Ghost binary unavailable
- Baseline comparison
- Regression artifact

Do NOT use for:
- Semantic truth about Ghost's behavior
- Oracle validation
- Ground truth about what Ghost would actually find

Real Ghost must be invoked separately for meaningful experiments.
"""

from dataclasses import dataclass
from typing import List, Dict, Any
from pathlib import Path

from .ghost_invoker import GhostFinding, GhostAnalysis
from .epistemic_model import IntentKind


@dataclass
class GhostSimulationProfile:
    """Profile of how Ghost behaves on a scenario type."""
    intent: IntentKind
    expected_finding: str  # e.g., "REMOVED_FROM_LIBRARY"
    likely_severity: str   # What Ghost typically claims
    confidence: float      # How confident Ghost is
    will_overclaim: bool   # Does Ghost tend to overclaim?


class GhostSimulator:
    """Simulate Ghost findings for testing."""

    # Profiles of how Ghost behaves on different intent types
    PROFILES = {
        IntentKind.INTENTIONAL_REFACTOR: GhostSimulationProfile(
            intent=IntentKind.INTENTIONAL_REFACTOR,
            expected_finding="REMOVED_FROM_LIBRARY",
            likely_severity="MAJOR",  # Ghost often overclaims here
            confidence=0.7,
            will_overclaim=True  # Key test case
        ),
        IntentKind.ACCIDENTAL_REMOVAL: GhostSimulationProfile(
            intent=IntentKind.ACCIDENTAL_REMOVAL,
            expected_finding="REGRESSION",
            likely_severity="MAJOR",
            confidence=0.85,
            will_overclaim=False
        ),
        IntentKind.SECURITY_FIX: GhostSimulationProfile(
            intent=IntentKind.SECURITY_FIX,
            expected_finding="SECURITY_REGRESSION",
            likely_severity="CRITICAL",
            confidence=0.9,
            will_overclaim=False
        ),
        IntentKind.DEAD_CODE_CLEANUP: GhostSimulationProfile(
            intent=IntentKind.DEAD_CODE_CLEANUP,
            expected_finding="DEAD_CODE_CLEANUP",
            likely_severity="MINOR",
            confidence=0.6,
            will_overclaim=False
        ),
        IntentKind.TEST_ONLY_MIGRATION: GhostSimulationProfile(
            intent=IntentKind.TEST_ONLY_MIGRATION,
            expected_finding="TEST_ONLY_MIGRATION",
            likely_severity="INFORMATIONAL",
            confidence=0.65,
            will_overclaim=False
        ),
    }

    @staticmethod
    def simulate_findings(
        repo_path: Path,
        inferred_intent: IntentKind,
        member_name: str = "PHANTOM"
    ) -> GhostAnalysis:
        """Generate simulated Ghost findings based on inferred intent.

        Args:
            repo_path: Path to repository (for context)
            inferred_intent: What the oracle inferred
            member_name: Name of the removed member

        Returns:
            GhostAnalysis with simulated findings
        """

        profile = GhostSimulator.PROFILES.get(
            inferred_intent,
            GhostSimulationProfile(
                intent=IntentKind.UNKNOWN_INTENT,
                expected_finding="REMOVED_FROM_LIBRARY",
                likely_severity="UNKNOWN",
                confidence=0.3,
                will_overclaim=False
            )
        )

        # Generate finding based on profile
        finding = GhostFinding(
            member_name=member_name,
            file_path="enums.py",
            severity=profile.likely_severity,
            category=profile.expected_finding,
            message=f"Member {member_name} was removed from production code "
                   f"but remains in test files (confidence: {profile.confidence:.1%})",
            metadata={
                "confidence": profile.confidence,
                "simulated": True,
                "inferred_intent": inferred_intent.name,
                "will_overclaim": profile.will_overclaim
            }
        )

        return GhostAnalysis(
            findings=[finding],
            repository_path=repo_path,
            status="success"
        )

    @staticmethod
    def evaluate_scenario(
        repo_path: Path,
        oracle_results: Dict[str, Any],
        ground_truth_intent: IntentKind,
        member_name: str = "PHANTOM"
    ) -> Dict[str, Any]:
        """Run full evaluation: simulate Ghost, compare with oracles.

        Args:
            repo_path: Repository path
            oracle_results: Results from Evaluator.run_oracles()
            ground_truth_intent: The actual semantic intent
            member_name: Member being evaluated

        Returns:
            Evaluation report
        """
        from .evaluator import Evaluator
        # Simulate Ghost findings
        ghost_analysis = GhostSimulator.simulate_findings(
            repo_path, ground_truth_intent, member_name
        )

        # Evaluate Ghost's conclusion
        evaluator = Evaluator(repo_path)
        ghost_obs = ghost_analysis.findings[0]

        # Convert GhostFinding to GhostObservation
        from .epistemic_model import GhostObservation
        ghost_obs_model = GhostObservation(
            member_name=ghost_obs.member_name,
            provenance_class=ghost_obs.category,
            severity=ghost_obs.severity,
            evidence_cited=[ghost_obs.message]
        )

        result = evaluator.evaluate_observation(ghost_obs_model, oracle_results)
        # The simulated world label is retained only in the report. It is
        # intentionally not supplied to the independent evaluator.
        result.semantic_truth = None

        # Format report
        return {
            "scenario": repo_path.name,
            "member": member_name,
            "ground_truth_intent": ground_truth_intent.name,
            "ghost_finding": {
                "category": ghost_obs.category,
                "severity": ghost_obs.severity,
                "confidence": ghost_obs.metadata.get("confidence", 0.0),
                "message": ghost_obs.message
            },
            "oracle_inferred_intent": oracle_results.get("history", {}).get("inferred_intent"),
            "verdict": {
                "semantic_correctness": result.semantic_correctness.name,
                "factual_correctness": result.factual_correctness.name,
                "overclaimed": result.overclaim,
                "underclaimed": result.underclaim
            },
            "would_catch_overclaim": (
                result.semantic_correctness.name == "OVERCLAIMED"
                and ghost_obs.metadata.get("will_overclaim")
            )
        }
