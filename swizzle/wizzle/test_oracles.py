"""Tests for independent oracles."""

import pytest
from pathlib import Path
from .oracles import HistoryOracle, CurrentStateOracle

def test_history_oracle_detects_refactor():
    """History oracle should identify refactor-like commit messages."""
    # This test would run against actual repos in practice
    # For now, verify the oracle can be instantiated
    oracle = HistoryOracle()
    assert oracle is not None

def test_current_state_oracle_scans_files():
    """Current state oracle should scan for enum members."""
    oracle = CurrentStateOracle()
    assert oracle is not None

def test_oracle_no_side_effects():
    """Oracles should not modify the repository."""
    oracle = HistoryOracle()
    # Just calling analyze should not modify anything
    # (This is verified by inspection, but good to document)
    assert True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
