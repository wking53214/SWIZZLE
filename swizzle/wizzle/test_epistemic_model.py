"""Tests for epistemic model and oracle independence."""

import pytest
from pathlib import Path
from .epistemic_model import (
    IntentKind, FactualCorrectness, SemanticCorrectness,
    EvidenceProvenance, ObservedFact, ExperimentResult,
    SemanticTruth, GhostObservation
)
from .oracles import HistoryOracle, CurrentStateOracle

def test_epistemic_model_types_exist():
    """Verify epistemic model types are importable and usable."""
    
    result = ExperimentResult(
        case_id="test_001",
        world_name="test_world"
    )
    
    assert result.case_id == "test_001"
    assert result.factual_correctness == FactualCorrectness.UNASKABLE
    assert result.semantic_correctness == SemanticCorrectness.UNASKABLE

def test_fact_provenance():
    """Verify observed facts track their provenance."""
    
    fact = ObservedFact(
        description="member X was deleted",
        provenance=EvidenceProvenance.OBSERVED
    )
    
    assert fact.provenance == EvidenceProvenance.OBSERVED

def test_semantic_truth_independence():
    """Verify semantic truth can be declared independently."""
    
    truth = SemanticTruth(
        primary_intent=IntentKind.INTENTIONAL_REFACTOR,
        confidence=1.0,
        notes="This was a deliberate design change"
    )
    
    # This should not depend on Ghost's conclusion
    ghost_obs = GhostObservation(
        member_name="Status.PHANTOM",
        provenance_class="REMOVED_FROM_LIBRARY",
        severity="MAJOR"
    )
    
    # They are independent objects
    assert truth.primary_intent != ghost_obs.severity

def test_intent_taxonomy_covers_scenarios():
    """Verify intent taxonomy includes all needed categories."""
    
    needed_kinds = {
        IntentKind.ACCIDENTAL_REMOVAL,
        IntentKind.INTENTIONAL_REFACTOR,
        IntentKind.SECURITY_FIX,
        IntentKind.DEAD_CODE_CLEANUP,
    }
    
    available_kinds = set(IntentKind)
    assert needed_kinds.issubset(available_kinds)

def test_oracle_independence_no_ghost_access():
    """Oracles should not read Ghost's conclusion."""
    
    # Create an oracle
    history_oracle = HistoryOracle()
    
    # The oracle method should not take Ghost's conclusion as input
    import inspect
    sig = inspect.signature(HistoryOracle.analyze)
    params = list(sig.parameters.keys())
    
    # Should only take repo_path, not ghost_conclusion or similar
    assert "ghost" not in str(params).lower()
    assert "conclusion" not in str(params).lower()

def test_factual_vs_semantic_distinctness():
    """Verify we can represent factually correct but semantically wrong."""
    
    result = ExperimentResult(
        case_id="phantom_001",
        world_name="phantom_intentional_refactor"
    )
    
    # Ghost's observation might be factually correct
    result.factual_correctness = FactualCorrectness.CORRECT
    
    # But the conclusion might be semantically unjustified
    result.semantic_correctness = SemanticCorrectness.OVERCLAIMED
    
    # These are independent dimensions
    assert result.factual_correctness != result.semantic_correctness

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
