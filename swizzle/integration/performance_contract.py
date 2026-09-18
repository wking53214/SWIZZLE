"""Performance regression detection via contracts.

Swizzle runs at scale but doesn't currently feed performance data back.
This module establishes performance contracts that Ghost Tools can verify.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
import json
from datetime import datetime


@dataclass
class PerformanceMetric:
    """A single performance measurement."""
    timestamp: str  # ISO 8601
    wall_time_seconds: float
    user_cpu_seconds: float
    system_cpu_seconds: float
    peak_memory_mb: float
    files_processed: int
    repository_size_mb: float

    # Context
    environment: str  # "ci", "local", "benchmark"
    tool_version: str = ""
    python_version: str = ""
    platform: str = ""  # "linux", "macos", "windows"


@dataclass
class PerformanceContract:
    """A performance guarantee one tool makes."""
    id: str  # e.g., "ghost_scan_time_per_file"
    description: str  # e.g., "scan completes in < 100ms per file"
    metric_type: str  # "wall_time", "memory", "throughput"

    # The contract bounds
    threshold_value: float  # max allowed value
    threshold_unit: str  # "seconds", "mb", "ms_per_file"
    percentile: int = 95  # 95th percentile, not max

    # When it applies
    applies_to_tool: str = ""  # "ghost_tools" or "swizzle"
    applies_after_version: Optional[str] = None
    applies_to_repo_sizes: str = ""  # "all", "small", "large"

    # Enforcement
    enforced_by: str = ""  # which tool verifies this
    violations: List[str] = field(default_factory=list)


@dataclass
class PerformanceRun:
    """Results from running a tool on a test case."""
    id: str  # unique run identifier
    case_id: str  # which mutation case / repository
    tool: str  # "ghost_tools" or "swizzle"
    tool_version: str
    metrics: PerformanceMetric
    contracts_passed: List[str] = field(default_factory=list)
    contracts_violated: List[str] = field(default_factory=list)


@dataclass
class PerformanceReport:
    """Performance tracking and regression detection."""
    runs: Dict[str, PerformanceRun] = field(default_factory=dict)
    contracts: Dict[str, PerformanceContract] = field(default_factory=dict)
    version: str = "1.0"
    last_updated: str = ""

    def add_run(self, run: PerformanceRun) -> None:
        """Record a performance run."""
        self.runs[run.id] = run

    def add_contract(self, contract: PerformanceContract) -> None:
        """Define a performance contract."""
        self.contracts[contract.id] = contract

    def check_contract_violations(self, contract_id: str) -> List[str]:
        """Find runs that violated a specific contract."""
        if contract_id not in self.contracts:
            return []

        contract = self.contracts[contract_id]
        violations = []

        for run in self.runs.values():
            if run.tool != contract.applies_to_tool:
                continue

            # Get metric value based on contract type
            if contract.metric_type == "wall_time":
                value = run.metrics.wall_time_seconds
            elif contract.metric_type == "memory":
                value = run.metrics.peak_memory_mb
            elif contract.metric_type == "throughput":
                if run.metrics.files_processed > 0:
                    value = run.metrics.wall_time_seconds / run.metrics.files_processed
                else:
                    continue
            else:
                continue

            if value > contract.threshold_value:
                violations.append(run.id)
                if contract_id not in run.contracts_violated:
                    run.contracts_violated.append(contract_id)

        return violations

    def detect_regressions(self, threshold_percent: int = 10) -> Dict[str, List[str]]:
        """Detect performance regressions vs baseline.

        Compares recent runs to historical baseline (first run per case).
        Returns dict mapping case_id to list of regression descriptions.
        """
        regressions = {}

        # Group runs by case
        by_case: Dict[str, List[PerformanceRun]] = {}
        for run in self.runs.values():
            if run.case_id not in by_case:
                by_case[run.case_id] = []
            by_case[run.case_id].append(run)

        for case_id, runs in by_case.items():
            if len(runs) < 2:
                continue

            # First run is baseline, compare others to it
            baseline = runs[0]
            case_regressions = []

            for recent in runs[1:]:
                # Check each metric for regression
                time_change = ((recent.metrics.wall_time_seconds - baseline.metrics.wall_time_seconds)
                              / baseline.metrics.wall_time_seconds * 100)
                memory_change = ((recent.metrics.peak_memory_mb - baseline.metrics.peak_memory_mb)
                                / baseline.metrics.peak_memory_mb * 100)

                if time_change > threshold_percent:
                    case_regressions.append(
                        f"Wall time increased {time_change:.1f}% ({baseline.metrics.wall_time_seconds:.2f}s -> {recent.metrics.wall_time_seconds:.2f}s)"
                    )
                if memory_change > threshold_percent:
                    case_regressions.append(
                        f"Memory usage increased {memory_change:.1f}% ({baseline.metrics.peak_memory_mb:.1f}MB -> {recent.metrics.peak_memory_mb:.1f}MB)"
                    )

            if case_regressions:
                regressions[case_id] = case_regressions

        return regressions

    def to_json(self) -> str:
        """Export complete report."""
        data = {
            "version": self.version,
            "last_updated": self.last_updated,
            "contracts": {
                cid: {
                    "id": c.id,
                    "description": c.description,
                    "metric_type": c.metric_type,
                    "threshold_value": c.threshold_value,
                    "threshold_unit": c.threshold_unit,
                    "percentile": c.percentile,
                    "applies_to_tool": c.applies_to_tool,
                    "violations": c.violations,
                }
                for cid, c in self.contracts.items()
            },
            "runs": {
                rid: {
                    "id": r.id,
                    "case_id": r.case_id,
                    "tool": r.tool,
                    "tool_version": r.tool_version,
                    "metrics": {
                        "timestamp": r.metrics.timestamp,
                        "wall_time_seconds": r.metrics.wall_time_seconds,
                        "user_cpu_seconds": r.metrics.user_cpu_seconds,
                        "peak_memory_mb": r.metrics.peak_memory_mb,
                        "files_processed": r.metrics.files_processed,
                    },
                    "contracts_violated": r.contracts_violated,
                }
                for rid, r in self.runs.items()
            }
        }
        return json.dumps(data, indent=2)

    def save(self, path: Path) -> None:
        """Write to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())


# Seed with realistic contracts
DEFAULT_PERFORMANCE_REPORT = PerformanceReport(version="1.0")

DEFAULT_PERFORMANCE_REPORT.add_contract(PerformanceContract(
    id="ghost_scan_per_file",
    description="ghost-buster scan completes in < 100ms per file",
    metric_type="throughput",
    threshold_value=0.1,
    threshold_unit="seconds_per_file",
    applies_to_tool="ghost_tools",
    enforced_by="swizzle",
))

DEFAULT_PERFORMANCE_REPORT.add_contract(PerformanceContract(
    id="ghost_memory_usage",
    description="ghost-buster uses < 500MB for repositories < 100MB",
    metric_type="memory",
    threshold_value=500,
    threshold_unit="mb",
    applies_to_tool="ghost_tools",
    applies_to_repo_sizes="small",
    enforced_by="swizzle",
))

DEFAULT_PERFORMANCE_REPORT.add_contract(PerformanceContract(
    id="swizzle_case_execution",
    description="Swizzle executes a case in < 60 seconds",
    metric_type="wall_time",
    threshold_value=60,
    threshold_unit="seconds",
    applies_to_tool="swizzle",
    enforced_by="swizzle",
))
