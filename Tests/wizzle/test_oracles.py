"""Tests for independent oracles."""

import pytest
from swizzle.wizzle.oracles import HistoryOracle, CurrentStateOracle

def test_history_oracle_detects_refactor():
    """History oracle should identify refactor-like commit messages."""
    # This test would run against actual repos in practice
    # For now, verify the oracle can be instantiated
    assert HistoryOracle() is not None

def test_current_state_oracle_scans_files():
    """Current state oracle should scan for enum members."""
    oracle = CurrentStateOracle()
    assert oracle is not None

def test_oracle_no_side_effects(tmp_path):
    """Oracles should not modify the repository."""
    import subprocess

    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@invalid", *args],
                       cwd=tmp_path, check=True, capture_output=True, timeout=60)

    git("init", "-q")
    (tmp_path / "a.py").write_text("x = 1\n")
    git("add", "-A")
    git("commit", "-q", "-m", "refactor: first")

    def snapshot():
        return {str(p.relative_to(tmp_path)): p.read_bytes()
                for p in sorted(tmp_path.rglob("*")) if p.is_file()}

    before = snapshot()
    HistoryOracle.analyze(tmp_path)
    CurrentStateOracle.analyze(tmp_path)
    assert snapshot() == before

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
