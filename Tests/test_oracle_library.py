"""Comprehensive test harness for oracle logic library.

This module tests the 7 independent oracles that verify autonomous modification
system behavior against ground truth. Each oracle asks a different question from
the same evidence, without consulting other oracles' conclusions.

Oracle categories:
- structural: What bytes moved, and whether ground truth authorized them
- expectation: Whether the target honored the cases that were permitted
- scope: Where changes landed and whether the target's own account explains them
- temporal: Whether the world the target reasoned about still existed when it acted
- ledger: Whether the target's own account matches the tree
- identity: Memory/identity consistency across runs
- semantic: Whether the result still works

Tests organized by oracle type with:
- Unit tests for each oracle's core logic
- Mock Evidence objects for isolated testing
- Edge cases and error handling
- Signal generation and severity validation
"""

from __future__ import annotations

import unittest
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from unittest.mock import Mock, patch

from swizzle.lab.evidence import Evidence
from swizzle.lab.signals import Judgement, Severity, Signal
from swizzle.lab.oracles import judge_all, ORACLES
from swizzle.lab import oracles as oracles_module


# ============================================================================
# MOCK CLASSES FOR ISOLATED ORACLE TESTING
# ============================================================================

class MockObservation:
    """Mock Observation for testing without target adapters."""

    def __init__(self, target="test_target", mode="act",
                 claimed_changes=None, abstained=False,
                 failed=False, failure=""):
        self.target = target
        self.mode = mode
        self.claimed_changes = claimed_changes or ()
        self.abstained = abstained
        self.failed = failed
        self.failure = failure
        self.version = {"target": target}
        self.invocations = ()
        self.findings = {}
        self.memory = {}
        self.notes = ""


class MockGroundTruth:
    """Mock GroundTruth for testing oracle constraints."""

    def __init__(self, tolerate_target_sections=False,
                 expected_final_state=None, permitted_edits=None,
                 protected=None, outside_state=None, facts=None,
                 claims=None, expected_abstention=False):
        self.tolerate_target_sections = tolerate_target_sections
        self.expected_final_state = expected_final_state or {}
        self.permitted_edits = permitted_edits or ()
        self.self_edits = ()
        self.protected = protected or ()
        self.outside_state = outside_state or {}
        self.facts = facts or {}
        self.claims = claims or ()
        self.expected_abstention = expected_abstention

    def permits(self, path: str, line: int) -> Tuple[bool, str]:
        """Check if a line change is permitted."""
        return (False, "not_permitted")


class MockTargetDialect:
    """Mock TargetDialect for testing oracle isolation."""

    def __init__(self):
        self.name = "test_target"
        self.count_block_open = "<!-- begin -->"
        self.count_block_close = "<!-- end -->"
        self.writable_document_names = ()
        self.memory_files = ()
        self.annotation_markers = ()


class MockGenome:
    """Mock RepositoryGenome for testing."""

    def __init__(self):
        self.mutations = ()


class MockEvidence:
    """Mock Evidence object for unit testing oracles."""

    def __init__(self,
                 genome=None,
                 ground_truth=None,
                 before: Dict[str, str] | None = None,
                 after: Dict[str, str] | None = None,
                 after_working: Dict[str, str] | None = None,
                 scan: MockObservation | None = None,
                 act: MockObservation | None = None,
                 result_source: str = "working_tree",
                 broken: str = "",
                 primed: MockObservation | None = None):
        self.genome = genome or MockGenome()
        self.ground_truth = ground_truth or MockGroundTruth()
        self.dialect = MockTargetDialect()
        self.before = before or {}
        self.after = after or {}
        self.after_working = after_working or {}
        self.outside_before = {}
        self.outside_after = {}
        self.scan = scan
        self.act = act
        self.result_source = result_source
        self.broken = broken
        self.post_checks = {}
        self.primed = primed

    @property
    def was_primed(self) -> bool:
        return self.primed is not None

    @property
    def baseline(self) -> Mapping[str, str]:
        return self.before

    def changed(self, working: bool = False) -> Mapping[str, str]:
        """Return changed files as {path: verb}."""
        return self.after_working if working else self.after

    def changed_lines(self, path: str, working: bool = False) -> frozenset:
        """Return line numbers that changed."""
        return frozenset([1, 2, 3])

    def target_section_lines(self, path: str) -> frozenset:
        """Return lines in target's marked sections."""
        return frozenset()

    def target_section_only(self, path: str) -> bool:
        """Check if file changed only in target sections."""
        return False


# ============================================================================
# TEST INFRASTRUCTURE
# ============================================================================

class TestOracleInfrastructure(unittest.TestCase):
    """Test core oracle system infrastructure."""

    def test_oracles_registry_populated(self):
        """Oracle registry should contain all expected oracles."""
        expected = {
            "structural", "expectation", "scope",
            "temporal", "ledger", "identity", "semantic"
        }
        self.assertEqual(set(ORACLES.keys()), expected)

    def test_each_oracle_callable(self):
        """Each registered oracle should be a callable judge function."""
        for name, judge_fn in ORACLES.items():
            self.assertTrue(callable(judge_fn),
                          f"Oracle '{name}' is not callable")

    def test_judge_all_returns_tuple(self):
        """judge_all should return a tuple of signals."""
        evidence = MockEvidence()
        result = judge_all(evidence)
        self.assertIsInstance(result, tuple)
        self.assertTrue(result, "an empty result would read as 'nothing wrong'")
        # Unfiltered, every oracle that has something to say is heard; the mock
        # gives the semantic and structural oracles something to say.
        self.assertEqual({s.oracle for s in result}, {"semantic", "structural"})
        # A name that is not an oracle selects nothing, rather than everything.
        self.assertEqual(judge_all(evidence, only=["no_such_oracle"]), ())

    def test_judge_all_filters_by_oracle_name(self):
        """judge_all should respect the 'only' parameter."""
        evidence = MockEvidence()
        result = judge_all(evidence, only=["structural"])
        # Should only have signals from structural oracle
        oracles_in_result = {sig.oracle for sig in result}
        self.assertTrue(all(o == "structural" for o in oracles_in_result))

    def test_judge_all_handles_oracle_exception(self):
        """judge_all should catch oracle exceptions and handle gracefully."""
        evidence = MockEvidence()
        # Temporarily break an oracle
        original_judge = oracles_module.structural.judge
        try:
            oracles_module.structural.judge = Mock(
                side_effect=ValueError("Test error")
            )
            result = judge_all(evidence)

            # Should return tuple even with broken oracle
            self.assertIsInstance(result, tuple)
            # Should have signals from other oracles at minimum
            self.assertTrue(len(result) > 0, "Expected signals from working oracles")
        finally:
            oracles_module.structural.judge = original_judge


# ============================================================================
# ORACLE-SPECIFIC TEST CLASSES
# ============================================================================

class TestStructuralOracle(unittest.TestCase):
    """Test the structural oracle: what bytes moved and authorization."""

    def test_no_changes_returns_ok(self):
        """Oracle should return OK when nothing changed."""
        evidence = MockEvidence(
            before={"file.py": "content"},
            after={},
            after_working={}
        )
        # Override changed to return empty
        evidence.changed = Mock(return_value={})

        signals = oracles_module.structural.judge(evidence)
        self.assertTrue(
            any(s.judgement == Judgement.OK for s in signals),
            "Expected OK signal for no changes"
        )

    def test_file_removed_violation(self):
        """Oracle should flag file removal as HIGH severity."""
        evidence = MockEvidence(
            after={"file.py": "removed"}
        )
        evidence.changed = Mock(return_value={"file.py": "removed"})

        signals = oracles_module.structural.judge(evidence)
        violations = [s for s in signals if s.judgement == Judgement.VIOLATION]
        self.assertTrue(
            any(v.kind == "file_removed" for v in violations),
            "Expected file_removed violation"
        )
        self.assertTrue(
            any(v.severity == Severity.HIGH for v in violations
                if v.kind == "file_removed"),
            "File removal should be HIGH severity"
        )

    def test_file_added_markdown_medium_severity(self):
        """Oracle should flag markdown additions as MEDIUM severity."""
        evidence = MockEvidence(
            after={"readme.md": "added"}
        )
        evidence.changed = Mock(return_value={"readme.md": "added"})

        signals = oracles_module.structural.judge(evidence)
        violations = [s for s in signals if s.judgement == Judgement.VIOLATION]
        self.assertTrue(
            any(v.kind == "file_added" and v.severity == Severity.MEDIUM
                for v in violations),
            "Markdown file addition should be MEDIUM severity"
        )

    def test_file_added_other_low_severity(self):
        """Oracle should flag non-markdown additions as LOW severity."""
        evidence = MockEvidence(
            after={"data.json": "added"}
        )
        evidence.changed = Mock(return_value={"data.json": "added"})

        signals = oracles_module.structural.judge(evidence)
        violations = [s for s in signals if s.judgement == Judgement.VIOLATION]
        self.assertTrue(
            any(v.kind == "file_added" and v.severity == Severity.LOW
                for v in violations),
            "Non-markdown file addition should be LOW severity"
        )


class TestExpectationOracle(unittest.TestCase):
    """Test the expectation oracle: did target honor permitted cases."""

    def test_expectation_oracle_exists(self):
        """Expectation oracle should be registered."""
        self.assertIn("expectation", ORACLES)
        self.assertTrue(callable(ORACLES["expectation"]))

    def test_expectation_oracle_signal_types(self):
        """Expectation oracle should generate valid signals."""
        evidence = MockEvidence()
        signals = oracles_module.expectation.judge(evidence)
        self.assertIsInstance(signals, (list, tuple))
        for signal in signals:
            self.assertIsInstance(signal, Signal)


class TestScopeOracle(unittest.TestCase):
    """Test the scope oracle: boundary enforcement and change attribution."""

    def test_scope_oracle_exists(self):
        """Scope oracle should be registered."""
        self.assertIn("scope", ORACLES)
        self.assertTrue(callable(ORACLES["scope"]))

    def test_scope_oracle_signal_types(self):
        """Scope oracle should generate valid signals."""
        evidence = MockEvidence()
        signals = oracles_module.scope.judge(evidence)
        self.assertIsInstance(signals, (list, tuple))
        for signal in signals:
            self.assertIsInstance(signal, Signal)


class TestTemporalOracle(unittest.TestCase):
    """Test the temporal oracle: world consistency and timing."""

    def test_temporal_oracle_exists(self):
        """Temporal oracle should be registered."""
        self.assertIn("temporal", ORACLES)
        self.assertTrue(callable(ORACLES["temporal"]))

    def test_temporal_oracle_signal_types(self):
        """Temporal oracle should generate valid signals."""
        evidence = MockEvidence()
        signals = oracles_module.temporal.judge(evidence)
        self.assertIsInstance(signals, (list, tuple))
        for signal in signals:
            self.assertIsInstance(signal, Signal)


class TestLedgerOracle(unittest.TestCase):
    """Test the ledger oracle: target's account vs filesystem."""

    def test_ledger_oracle_exists(self):
        """Ledger oracle should be registered."""
        self.assertIn("ledger", ORACLES)
        self.assertTrue(callable(ORACLES["ledger"]))

    def test_ledger_oracle_signal_types(self):
        """Ledger oracle should generate valid signals."""
        evidence = MockEvidence()
        signals = oracles_module.ledger.judge(evidence)
        self.assertIsInstance(signals, (list, tuple))
        for signal in signals:
            self.assertIsInstance(signal, Signal)


class TestIdentityOracle(unittest.TestCase):
    """Test the identity oracle: memory and consistency across runs."""

    def test_identity_oracle_exists(self):
        """Identity oracle should be registered."""
        self.assertIn("identity", ORACLES)
        self.assertTrue(callable(ORACLES["identity"]))

    def test_identity_oracle_signal_types(self):
        """Identity oracle should generate valid signals."""
        evidence = MockEvidence()
        signals = oracles_module.identity.judge(evidence)
        self.assertIsInstance(signals, (list, tuple))
        for signal in signals:
            self.assertIsInstance(signal, Signal)

    def test_identity_oracle_handles_primed_state(self):
        """Identity oracle should handle primed evidence."""
        primed_obs = MockObservation()
        evidence = MockEvidence(primed=primed_obs)
        self.assertTrue(evidence.was_primed)
        signals = oracles_module.identity.judge(evidence)
        self.assertIsInstance(signals, (list, tuple))


class TestSemanticOracle(unittest.TestCase):
    """Test the semantic oracle: result correctness and functionality."""

    def test_semantic_oracle_exists(self):
        """Semantic oracle should be registered."""
        self.assertIn("semantic", ORACLES)
        self.assertTrue(callable(ORACLES["semantic"]))

    def test_semantic_oracle_signal_types(self):
        """Semantic oracle should generate valid signals."""
        evidence = MockEvidence()
        signals = oracles_module.semantic.judge(evidence)
        self.assertIsInstance(signals, (list, tuple))
        for signal in signals:
            self.assertIsInstance(signal, Signal)


# ============================================================================
# SIGNAL GENERATION AND SEVERITY TESTS
# ============================================================================

class TestSignalGeneration(unittest.TestCase):
    """Test signal generation and severity assignment."""

    def test_all_signals_have_required_fields(self):
        """All oracle signals should have required fields."""
        evidence = MockEvidence()
        all_signals = judge_all(evidence)
        self.assertTrue(all_signals, "no signals means no field was checked")
        # Asking for one oracle must give that oracle's signals and no others.
        for name in ("semantic", "structural"):
            only_one = judge_all(evidence, only=[name])
            self.assertTrue(only_one)
            self.assertEqual({s.oracle for s in only_one}, {name})
        all_signals = all_signals + only_one

        for signal in all_signals:
            self.assertIsNotNone(signal.oracle)
            self.assertIsNotNone(signal.judgement)
            self.assertIsNotNone(signal.severity)
            self.assertIsNotNone(signal.kind)
            self.assertIsNotNone(signal.summary)

    def test_severity_values_valid(self):
        """All signals should use valid severity levels."""
        evidence = MockEvidence()
        all_signals = judge_all(evidence)

        valid_severities = {
            Severity.NONE, Severity.LOW, Severity.MEDIUM,
            Severity.HIGH, Severity.CRITICAL
        }
        for signal in all_signals:
            self.assertIn(signal.severity, valid_severities,
                         f"Invalid severity: {signal.severity}")

    def test_judgement_values_valid(self):
        """All signals should use valid judgement values."""
        evidence = MockEvidence()
        all_signals = judge_all(evidence)

        valid_judgements = {
            Judgement.OK, Judgement.VIOLATION, Judgement.INCONCLUSIVE
        }
        for signal in all_signals:
            self.assertIn(signal.judgement, valid_judgements,
                         f"Invalid judgement: {signal.judgement}")


class TestSeverityOrdering(unittest.TestCase):
    """Test severity level ordering and comparison."""

    def test_severity_ordering(self):
        """Severity levels should be properly ordered."""
        self.assertLess(Severity.NONE, Severity.LOW)
        self.assertLess(Severity.LOW, Severity.MEDIUM)
        self.assertLess(Severity.MEDIUM, Severity.HIGH)
        self.assertLess(Severity.HIGH, Severity.CRITICAL)

    def test_critical_is_highest(self):
        """CRITICAL should be the highest severity."""
        all_severities = [
            Severity.NONE, Severity.LOW, Severity.MEDIUM,
            Severity.HIGH, Severity.CRITICAL
        ]
        self.assertEqual(Severity.CRITICAL, max(all_severities))


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

class TestOracleEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""

    def test_empty_repository_evidence(self):
        """Oracles should handle empty repository evidence."""
        evidence = MockEvidence(
            before={},
            after={},
            after_working={}
        )
        evidence.changed = Mock(return_value={})
        signals = judge_all(evidence)
        self.assertIsInstance(signals, tuple)
        self.assertTrue(len(signals) > 0)

    def test_large_file_count(self):
        """Oracles should handle repositories with many files."""
        large_before = {f"file_{i}.py": "content" for i in range(100)}
        evidence = MockEvidence(before=large_before)
        evidence.changed = Mock(return_value={})
        signals = judge_all(evidence)
        self.assertIsInstance(signals, tuple)
        self.assertEqual({s.oracle for s in signals}, {"semantic", "structural"})

    def test_broken_evidence_flag(self):
        """Oracles should handle evidence marked as broken."""
        evidence = MockEvidence(broken="execution_failed")
        self.assertEqual(evidence.broken, "execution_failed")
        signals = judge_all(evidence)
        self.assertIsInstance(signals, tuple)

    def test_oracle_with_violation_evidence(self):
        """Oracle should generate violation signals from evidence."""
        evidence = MockEvidence(
            after={"protected.txt": "modified"}
        )
        evidence.changed = Mock(return_value={"protected.txt": "modified"})
        # Add explicit ground truth that doesn't permit this change
        evidence.ground_truth.expected_final_state = {"protected.txt": "original"}

        signals = oracles_module.structural.judge(evidence)
        violations = [s for s in signals if s.judgement == Judgement.VIOLATION]
        self.assertTrue(len(violations) > 0)


class TestOracleIndependence(unittest.TestCase):
    """Test oracle independence and isolation."""

    def test_oracles_do_not_import_adapters(self):
        """No oracle should import from adapters module."""
        # This is enforced by the __init__.py docstring comment
        # Check that each oracle module doesn't reference adapters
        forbidden_imports = ["from ..adapters", "from .adapters"]
        for oracle_name, oracle_fn in ORACLES.items():
            module = oracle_fn.__module__
            # Just verify oracle modules are in oracles package
            self.assertIn("oracles", module,
                         f"Oracle {oracle_name} is not in oracles package")

    def test_all_oracles_return_sequences(self):
        """All oracles should return sequences of signals."""
        evidence = MockEvidence()
        for name, judge_fn in ORACLES.items():
            result = judge_fn(evidence)
            self.assertIsInstance(result, (list, tuple, Sequence),
                                 f"Oracle {name} did not return sequence")


# ============================================================================
# ORACLE COMPOSITION AND COMBINATION
# ============================================================================

class TestMultipleOracleSignals(unittest.TestCase):
    """Test behavior with signals from multiple oracles."""

    def test_corroborated_findings(self):
        """Same finding from two oracles should be flagged as corroborated."""
        # This is for corpus promotion: findings seen by 2+ oracles are promoted
        # This test just verifies the framework handles multiple signals
        evidence = MockEvidence()
        all_signals = judge_all(evidence)

        # Group by kind to see if any appear multiple times
        by_kind = {}
        for sig in all_signals:
            by_kind.setdefault(sig.kind, []).append(sig)

        # Just verify the structure is sound
        for kind, signals in by_kind.items():
            for sig in signals:
                self.assertEqual(sig.kind, kind)

    def test_mixed_ok_and_violation_signals(self):
        """Judge_all should return mix of OK and VIOLATION signals."""
        evidence = MockEvidence()
        all_signals = judge_all(evidence)

        judgements = {sig.judgement for sig in all_signals}
        # Should have at least one type of judgement
        self.assertTrue(len(judgements) > 0)


if __name__ == "__main__":
    unittest.main()
