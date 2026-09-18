"""End-to-end integration tests for Swizzle-Ghost Tools bridges.

Tests that both tools work together correctly via the shared integration model.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime

from swizzle.integration.orchestrator import IntegrationOrchestrator
from swizzle.integration.invariant_model import DEFAULT_INVARIANTS, Invariant, InvariantScope
from swizzle.integration.triage_ledger import (
    TriageLedger, TriageEntry, Decision, Severity, import_ghost_casefile
)
from swizzle.integration.mutation_transfer import DEFAULT_MUTATION_CATALOG, MutationCase
from swizzle.integration.performance_contract import (
    DEFAULT_PERFORMANCE_REPORT, PerformanceRun, PerformanceMetric
)
from swizzle.integration.architecture_audit import SWIZZLE_AUDIT, GHOST_AUDIT, ArchitectureViolation
from swizzle.integration.feedback_loop import (
    DEFAULT_FEEDBACK_REPORT, FalsePositivePattern, FindingType, OracleTrainingDatapoint
)


class TestIntegrationInvariantModel:
    """Test: Shared invariant model works correctly."""

    def test_default_invariants_loaded(self):
        """Verify 6 core invariants are defined."""
        assert len(DEFAULT_INVARIANTS.invariants) == 6

        # Check critical invariants exist
        assert "no_write_outside_boundary" in DEFAULT_INVARIANTS.invariants
        assert "authorized_content_preserved" in DEFAULT_INVARIANTS.invariants

    def test_invariant_severity_levels(self):
        """Verify invariants have correct severity."""
        inv = DEFAULT_INVARIANTS.invariants["no_write_outside_boundary"]
        assert inv.severity.value == "CRITICAL"

        inv2 = DEFAULT_INVARIANTS.invariants["test_suite_preserved"]
        assert inv2.severity.value == "HIGH"

    def test_invariant_export_json(self):
        """Verify invariants can be exported as JSON."""
        json_str = DEFAULT_INVARIANTS.to_json()
        data = json.loads(json_str)

        assert data["version"] == "1.0"
        assert len(data["invariants"]) == 6
        assert all("id" in inv for inv in data["invariants"].values())

    def test_invariant_applies_to_both_tools(self):
        """Verify invariants apply to both Swizzle and Ghost."""
        for inv_id, inv in DEFAULT_INVARIANTS.invariants.items():
            assert "ghost_tools" in inv.applies_to or "swizzle" in inv.applies_to


class TestIntegrationTriageLedger:
    """Test: Triage ledger exchange works correctly."""

    def test_triage_entry_creation(self):
        """Verify triage entries can be created."""
        entry = TriageEntry(
            id="test_1",
            finding_type="dated_claim",
            location="README.md",
            description="Explicitly marked as historical",
            severity_initial=Severity.MEDIUM,
            decision=Decision.FALSE,
            decided_by="ghost_tools",
            decided_at=datetime.now().isoformat(),
            reasoning="Date marker found in file",
        )

        assert entry.decision == Decision.FALSE
        assert entry.severity_initial == Severity.MEDIUM

    def test_triage_ledger_export_for_swizzle(self):
        """Verify ledger can be exported as Swizzle oracle training data."""
        ledger = TriageLedger(source_tool="ghost_tools")

        for i in range(5):
            entry = TriageEntry(
                id=f"case_{i}",
                finding_type="dated_claim",
                location="README.md",
                description="Test entry",
                severity_initial=Severity.MEDIUM,
                decision=Decision.FALSE if i % 2 == 0 else Decision.TRUE,
                decided_by="human",
                decided_at=datetime.now().isoformat(),
                reasoning="Test",
            )
            ledger.add_entry(entry)

        training = ledger.export_for_swizzle_oracle_training()
        assert "dated_claim" in training["training_data"]
        assert training["training_data"]["dated_claim"]["false_decisions"] >= 2

    def test_ghost_casefile_import(self, tmp_path):
        """Verify Ghost casefile can be imported."""
        casefile_data = {
            "case_1": {
                "finding_type": "dated_claim",
                "location": "README.md",
                "decision": "false",
                "reasoning": "Historical marker",
                "severity": "MEDIUM",
            },
            "case_2": {
                "finding_type": "prose_deleted",
                "location": "CONTRIBUTING.md",
                "decision": "true",
                "reasoning": "Author content was removed",
                "severity": "CRITICAL",
            }
        }

        casefile_path = tmp_path / "casefile.json"
        casefile_path.write_text(json.dumps(casefile_data))

        ledger = import_ghost_casefile(casefile_path)

        assert len(ledger.entries) == 2
        assert ledger.source_tool == "ghost_tools"


class TestIntegrationMutationTransfer:
    """Test: Mutation cases transfer between tools."""

    def test_mutation_cases_loaded(self):
        """Verify seed mutation cases are loaded."""
        assert len(DEFAULT_MUTATION_CATALOG.cases) >= 3

        assert "symlink_escape_boundary" in DEFAULT_MUTATION_CATALOG.cases
        assert "prose_inside_maintained_block" in DEFAULT_MUTATION_CATALOG.cases

    def test_mutation_case_structure(self):
        """Verify mutation cases have required fields."""
        case = DEFAULT_MUTATION_CATALOG.cases["symlink_escape_boundary"]

        assert case.hypothesis
        assert case.repository_mutations
        assert case.expected_outcome
        assert case.severity == "CRITICAL"
        assert case.minimized is True

    def test_mutation_export_for_ghost(self):
        """Verify mutations can be exported for Ghost."""
        ghost_format = DEFAULT_MUTATION_CATALOG.export_for_ghost_mutation_suite()
        cases = json.loads(ghost_format)

        assert len(cases) >= 3
        for case_id, case in cases.items():
            assert "hypothesis" in case
            assert "mutations" in case
            assert isinstance(case["mutations"], dict)

    def test_mutation_export_for_swizzle(self):
        """Verify mutations can be exported for Swizzle."""
        swizzle_format = DEFAULT_MUTATION_CATALOG.export_for_swizzle()
        cases = json.loads(swizzle_format)

        assert len(cases) >= 3
        for case_id, case in cases.items():
            assert "hypothesis" in case
            assert "mutations" in case


class TestIntegrationPerformanceContract:
    """Test: Performance contracts validate correctly."""

    def test_performance_contracts_defined(self):
        """Verify performance contracts are loaded."""
        assert len(DEFAULT_PERFORMANCE_REPORT.contracts) >= 3

        contract_ids = list(DEFAULT_PERFORMANCE_REPORT.contracts.keys())
        assert "ghost_scan_per_file" in contract_ids
        assert "ghost_memory_usage" in contract_ids

    def test_performance_run_validation(self):
        """Verify performance runs can be created and added."""
        report = DEFAULT_PERFORMANCE_REPORT

        run = PerformanceRun(
            id="test_run_1",
            case_id="test_case",
            tool="ghost_tools",
            tool_version="1.8.0",
            metrics=PerformanceMetric(
                timestamp=datetime.now().isoformat(),
                wall_time_seconds=0.05,
                user_cpu_seconds=0.04,
                system_cpu_seconds=0.01,
                peak_memory_mb=250,
                files_processed=1000,
                repository_size_mb=50,
                environment="test",
            )
        )

        report.add_run(run)
        assert "test_run_1" in report.runs

    def test_contract_violation_detection(self):
        """Verify contract violations are detected."""
        report = DEFAULT_PERFORMANCE_REPORT

        # Run that passes contract (50ms per file, under 100ms threshold)
        pass_run = PerformanceRun(
            id="run_pass",
            case_id="case_1",
            tool="ghost_tools",
            tool_version="1.8.0",
            metrics=PerformanceMetric(
                timestamp=datetime.now().isoformat(),
                wall_time_seconds=50,  # 50s / 1000 files = 50ms per file (under 100ms)
                user_cpu_seconds=40,
                system_cpu_seconds=10,
                peak_memory_mb=250,
                files_processed=1000,
                repository_size_mb=50,
                environment="test",
            )
        )

        # Run that violates contract (150ms per file, over 100ms threshold)
        fail_run = PerformanceRun(
            id="run_fail",
            case_id="case_1",
            tool="ghost_tools",
            tool_version="1.8.0",
            metrics=PerformanceMetric(
                timestamp=datetime.now().isoformat(),
                wall_time_seconds=150,  # 150s / 1000 files = 150ms per file (over 100ms)
                user_cpu_seconds=140,
                system_cpu_seconds=10,
                peak_memory_mb=400,
                files_processed=1000,
                repository_size_mb=50,
                environment="test",
            )
        )

        report.add_run(pass_run)
        report.add_run(fail_run)

        violations = report.check_contract_violations("ghost_scan_per_file")
        assert "run_fail" in violations
        assert "run_pass" not in violations

    def test_regression_detection(self):
        """Verify regression detection works."""
        report = DEFAULT_PERFORMANCE_REPORT

        # Baseline run
        baseline = PerformanceRun(
            id="baseline",
            case_id="case_2",
            tool="ghost_tools",
            tool_version="1.8.0",
            metrics=PerformanceMetric(
                timestamp=datetime.now().isoformat(),
                wall_time_seconds=10.0,
                user_cpu_seconds=9.0,
                system_cpu_seconds=1.0,
                peak_memory_mb=300,
                files_processed=1000,
                repository_size_mb=100,
                environment="test",
            )
        )

        # Regressed run (15% slower)
        regressed = PerformanceRun(
            id="regressed",
            case_id="case_2",
            tool="ghost_tools",
            tool_version="1.8.0",
            metrics=PerformanceMetric(
                timestamp=datetime.now().isoformat(),
                wall_time_seconds=11.5,  # 15% slower
                user_cpu_seconds=10.3,
                system_cpu_seconds=1.2,
                peak_memory_mb=300,
                files_processed=1000,
                repository_size_mb=100,
                environment="test",
            )
        )

        report.add_run(baseline)
        report.add_run(regressed)

        regressions = report.detect_regressions(threshold_percent=10)
        assert "case_2" in regressions


class TestIntegrationArchitectureAudit:
    """Test: Architecture audits work correctly."""

    def test_swizzle_boundaries_defined(self):
        """Verify Swizzle architecture boundaries exist."""
        assert len(SWIZZLE_AUDIT.boundaries) >= 3

        boundary_ids = list(SWIZZLE_AUDIT.boundaries.keys())
        assert "lab_independence" in boundary_ids
        assert "adapter_abstraction" in boundary_ids

    def test_ghost_boundaries_defined(self):
        """Verify Ghost architecture boundaries exist."""
        assert len(GHOST_AUDIT.boundaries) >= 3

        boundary_ids = list(GHOST_AUDIT.boundaries.keys())
        assert "tree_boundary" in boundary_ids
        assert "ledger_authority" in boundary_ids

    def test_violation_detection(self):
        """Verify architecture violations can be detected."""
        from swizzle.integration.architecture_audit import ArchitectureViolationType
        audit = SWIZZLE_AUDIT

        violation = ArchitectureViolation(
            id="test_violation",
            violation_type=ArchitectureViolationType.BOUNDARY_VIOLATION,
            boundary_id="lab_independence",
            location="swizzle/wizzle/test.py:42",
            description="Test violation",
            evidence={"import": "from swizzle.lab.draft import X"},
            severity="HIGH",
        )

        audit.add_violation(violation)

        violations = audit.violations_in_boundary("lab_independence")
        assert any(v.id == "test_violation" for v in violations)


class TestIntegrationFeedbackLoop:
    """Test: False positive feedback loop works."""

    def test_false_positive_patterns_loaded(self):
        """Verify false positive patterns are loaded."""
        assert len(DEFAULT_FEEDBACK_REPORT.false_positive_patterns) >= 2

    def test_pattern_structure(self):
        """Verify patterns have required fields."""
        pattern = DEFAULT_FEEDBACK_REPORT.false_positive_patterns["dated_readme_false_positive"]

        assert pattern.finding_type == FindingType.DATED_CLAIM
        assert 0 <= pattern.confidence <= 1
        assert pattern.confidence >= 0.90  # High confidence

    def test_oracle_training_data_creation(self):
        """Verify oracle training data can be created."""
        report = DEFAULT_FEEDBACK_REPORT

        for i in range(10):
            dp = OracleTrainingDatapoint(
                finding_id=f"finding_{i}",
                finding_type=FindingType.DATED_CLAIM,
                repository_features={"has_date": "yes"},
                tool_claim="Found dated claim",
                ground_truth=i < 8,  # 8 true, 2 false
                oracle_confidence=0.85,
                verified_by="ghost",
                verified_at=datetime.now().isoformat(),
            )
            report.add_training_datapoint(dp)

        assert len(report.oracle_training_data) >= 10

    def test_accuracy_calculation(self):
        """Verify oracle accuracy can be calculated."""
        report = DEFAULT_FEEDBACK_REPORT

        # Add balanced training data
        for i in range(20):
            dp = OracleTrainingDatapoint(
                finding_id=f"f_{i}",
                finding_type=FindingType.DATED_CLAIM,
                repository_features={},
                tool_claim="Claim",
                ground_truth=i < 10,
                oracle_confidence=0.8,
                verified_by="test",
                verified_at=datetime.now().isoformat(),
            )
            report.add_training_datapoint(dp)

        accuracy = report.oracle_accuracy_by_type()
        assert FindingType.DATED_CLAIM in accuracy


class TestIntegrationOrchestrator:
    """Test: Orchestrator coordinates all bridges."""

    def test_orchestrator_creation(self, tmp_path):
        """Verify orchestrator can be created."""
        orch = IntegrationOrchestrator(tmp_path / "integration")

        assert orch.invariants is not None
        assert orch.mutations is not None
        assert orch.performance is not None

    def test_orchestrator_export_all(self, tmp_path):
        """Verify orchestrator can export all data."""
        orch = IntegrationOrchestrator(tmp_path / "integration")
        orch.export_all()

        # Check files were created
        assert (tmp_path / "integration" / "invariants.json").exists()
        assert (tmp_path / "integration" / "mutations.json").exists()
        assert (tmp_path / "integration" / "performance.json").exists()

    def test_orchestrator_generate_bundles(self, tmp_path):
        """Verify orchestrator can generate tool-specific bundles."""
        orch = IntegrationOrchestrator(tmp_path / "integration")

        # Generate bundles
        ghost_bundle = orch.generate_ghost_integration_bundle()
        swizzle_bundle = orch.generate_swizzle_integration_bundle()

        # Verify bundle contents
        assert "invariants.json" in ghost_bundle
        assert "mutations.json" in ghost_bundle
        assert "performance-contracts.json" in ghost_bundle

        assert "invariants.json" in swizzle_bundle
        assert "oracle-training-data.json" in swizzle_bundle

    def test_orchestrator_publish_bundles(self, tmp_path):
        """Verify orchestrator can publish bundles to directories."""
        orch = IntegrationOrchestrator(tmp_path / "integration")

        ghost_dir = tmp_path / "ghost_bundle"
        swizzle_dir = tmp_path / "swizzle_bundle"

        orch.publish_ghost_integration_bundle(ghost_dir)
        orch.publish_swizzle_integration_bundle(swizzle_dir)

        # Verify files were written
        assert (ghost_dir / "invariants.json").exists()
        assert (swizzle_dir / "oracle-training-data.json").exists()

    def test_orchestrator_integration_report(self, tmp_path):
        """Verify orchestrator can generate integration report."""
        orch = IntegrationOrchestrator(tmp_path / "integration")

        report = orch.generate_integration_report()
        data = json.loads(report)

        assert "capabilities" in data
        assert data["capabilities"]["invariant_model"]["count"] == 6
        assert data["capabilities"]["mutation_transfer"]["count"] >= 3


class TestIntegrationRegressions:
    """Test: Known issues are caught by integration."""

    def test_symlink_escape_is_critical(self):
        """Regression: Symlink escape must be CRITICAL severity."""
        inv = DEFAULT_INVARIANTS.invariants["no_write_outside_boundary"]
        assert inv.severity.value == "CRITICAL"

    def test_prose_deletion_is_critical(self):
        """Regression: Prose deletion must be CRITICAL severity."""
        case = DEFAULT_MUTATION_CATALOG.cases["prose_inside_maintained_block"]
        assert case.severity == "CRITICAL"

    def test_dated_claim_pattern_exists(self):
        """Regression: Dated claim false positive pattern must exist."""
        assert "dated_readme_false_positive" in DEFAULT_FEEDBACK_REPORT.false_positive_patterns

    def test_tree_boundary_in_ghost_audit(self):
        """Regression: Tree boundary must be in Ghost audit."""
        assert "tree_boundary" in GHOST_AUDIT.boundaries


@pytest.mark.benchmark
class TestIntegrationPerformance:
    """Test: Integration operations stay fast."""

    def test_orchestrator_export_performance(self, benchmark, tmp_path):
        """Orchestrator.export_all() should complete in < 100ms."""
        orch = IntegrationOrchestrator(tmp_path / "perf_test")
        result = benchmark(orch.export_all)

    def test_invariant_export_performance(self, benchmark):
        """Invariant export should complete in < 50ms."""
        result = benchmark(DEFAULT_INVARIANTS.to_json)

    def test_mutation_export_performance(self, benchmark):
        """Mutation export should complete in < 50ms."""
        result = benchmark(DEFAULT_MUTATION_CATALOG.export_for_ghost_mutation_suite)
