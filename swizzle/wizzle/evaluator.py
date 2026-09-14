"""Experiment evaluation engine.

Runs independent oracles and produces machine-readable results.
Does not allow semantic truth to leak from ground-truth labels.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, Set
from dataclasses import asdict
from .epistemic_model import (
    ExperimentResult, IntentKind, FactualCorrectness,
    SemanticCorrectness, ObservedFact, SemanticTruth, GhostObservation
)
from .oracles import HistoryOracle, CurrentStateOracle, SemanticIntegrityOracle
from .additional_oracles import (
    SeverityOracle, TopologyOracle, RegressionRiskOracle,
    TestCoverageOracle, BehavioralCompatibilityOracle, HistoricalUsageOracle
)
from .evidence_entitlement import (
    EvidenceEntitlementEvaluator, EvidenceCategory, classify_evidence_from_oracle_results
)

class Evaluator:
    """Run experiments and produce results."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
    
    def run_oracles(self) -> Dict[str, Any]:
        """Run all independent oracles."""

        oracles_results = {}

        # Run primary oracles independently
        oracles_results["history"] = HistoryOracle.analyze(self.repo_path)
        oracles_results["current_state"] = CurrentStateOracle.analyze(self.repo_path)
        oracles_results["semantic_integrity"] = SemanticIntegrityOracle.analyze(
            oracles_results["current_state"],
            oracles_results["history"]
        )

        return oracles_results

    def run_all_oracles(self) -> Dict[str, Any]:
        """Run all oracles including additional discrimination oracles.

        Returns results from all 9 oracles for comprehensive analysis.
        """

        oracles_results = self.run_oracles()

        # Run additional oracles that strengthen discrimination ability
        oracles_results["severity"] = SeverityOracle.analyze(oracles_results)
        oracles_results["topology"] = TopologyOracle.analyze(self.repo_path)
        oracles_results["regression_risk"] = RegressionRiskOracle.analyze(oracles_results)
        oracles_results["test_coverage"] = TestCoverageOracle.analyze(
            self.repo_path, oracles_results
        )
        oracles_results["behavioral_compatibility"] = BehavioralCompatibilityOracle.analyze(
            self.repo_path
        )
        oracles_results["historical_usage"] = HistoricalUsageOracle.analyze(self.repo_path)

        return oracles_results

    @staticmethod
    def independent_warrant(oracle_results: Dict[str, Any]) -> tuple[str, frozenset, frozenset]:
        """Return the warrant inputs without any target claim."""
        inferred = oracle_results.get("history", {}).get(
            "inferred_intent", IntentKind.UNKNOWN_INTENT.name
        )
        present, absent = classify_evidence_from_oracle_results(oracle_results)
        return inferred, frozenset(present), frozenset(absent)
    
    def evaluate_observation(
        self,
        ghost_obs: GhostObservation,
        oracle_results: Dict[str, Any],
    ) -> ExperimentResult:
        """Evaluate a target claim against independently observed evidence.

        The evaluator deliberately accepts no world model or declared intent.
        Ground truth belongs to experiment construction and may be attached
        later for post-hoc comparison, but it cannot influence this warrant.
        """

        result = ExperimentResult(
            case_id=f"ghost_{ghost_obs.member_name}",
            world_name="to_be_determined"
        )

        # Assess factual correctness
        # Did Ghost correctly identify what's in the code?
        if ghost_obs.provenance_class == "REMOVED_FROM_LIBRARY":
            # Check if member is indeed absent from production
            current_state = oracle_results["current_state"]
            members_in_prod = set(current_state.get("members_in_production", []))
            if ghost_obs.member_name not in members_in_prod:
                result.factual_correctness = FactualCorrectness.CORRECT
            else:
                result.factual_correctness = FactualCorrectness.INCORRECT

        # Assess semantic correctness using Evidence Entitlement Evaluator
        # Extract evidence from oracle results
        test_imports_member = ghost_obs.member_name in oracle_results.get("current_state", {}).get("members_in_tests", [])
        present_evidence, absent_evidence = classify_evidence_from_oracle_results(
            oracle_results,
            test_imports_member=test_imports_member
        )

        # Determine conclusion category from Ghost observation
        conclusion = ghost_obs.provenance_class or "REMOVED_FROM_LIBRARY"

        inferred, _, _ = self.independent_warrant(oracle_results)
        try:
            intent_kind = IntentKind[inferred]
        except (KeyError, TypeError):
            intent_kind = IntentKind.UNKNOWN_INTENT

        # Use Evidence Entitlement Evaluator for full semantic assessment
        verdict = EvidenceEntitlementEvaluator.evaluate_entitlement(
            conclusion=conclusion,
            intent_kind=intent_kind,
            evidence_present=present_evidence,
            evidence_absent=absent_evidence,
            evidence_weak=set(),  # Not yet collected from oracles
            evidence_contradicting=set(),  # Not yet collected from oracles
            ghost_severity=ghost_obs.severity or "UNKNOWN"
        )

        # Map entitlement verdict to semantic correctness
        result.semantic_correctness = verdict.semantic_correctness
        result.overclaim = verdict.semantic_correctness == SemanticCorrectness.OVERCLAIMED
        result.underclaim = verdict.semantic_correctness == SemanticCorrectness.UNDERCLAIMED

        # Store detailed reasoning
        result.ghost_conclusion = ghost_obs
        return result

    def evaluate_ghost_conclusion(
        self,
        ghost_obs: GhostObservation,
        oracle_results: Dict[str, Any],
    ) -> ExperimentResult:
        """Backward-compatible name for independent observation evaluation."""
        return self.evaluate_observation(ghost_obs, oracle_results)
    
    def save_result(self, result: ExperimentResult, output_path: Path):
        """Save experiment result as JSON."""
        
        # Convert to dict, handling enums
        result_dict = asdict(result)
        
        # Convert enums to strings
        def enum_to_str(obj):
            if hasattr(obj, 'name'):
                return obj.name
            return obj
        
        def convert_enums(d):
            if isinstance(d, dict):
                return {k: convert_enums(v) for k, v in d.items()}
            elif isinstance(d, list):
                return [convert_enums(v) for v in d]
            else:
                return enum_to_str(d)
        
        result_dict = convert_enums(result_dict)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(result_dict, f, indent=2)

class ContrastivePairGenerator:
    """Generate paired worlds with same evidence, different semantic truth."""
    
    @staticmethod
    def generate_pair(intent_a: IntentKind, intent_b: IntentKind) -> tuple:
        """Generate two worlds that look similar but have different intent.
        
        Returns (world_a_spec, world_b_spec, shared_evidence)
        """
        
        # Both worlds have identical commit messages and structure
        # Only the ground-truth intent differs
        
        shared_evidence = {
            "member_removed_from_production": True,
            "member_now_in_tests": True,
            "removal_commit_message": "refactor: simplify implementation",
            "commit_messages_appear_intentional": True,
        }
        
        return (
            {"intent": intent_a, "name": f"world_{intent_a.name}"},
            {"intent": intent_b, "name": f"world_{intent_b.name}"},
            shared_evidence
        )
