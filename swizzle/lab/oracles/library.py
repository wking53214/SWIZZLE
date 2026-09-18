"""Oracle logic library for Swizzle.

Provides domain-specific oracle implementations and composition patterns.
Each oracle is a pure function of Evidence -> Sequence[Signal], answering
a specific question about system behavior independent of other oracles.

ORACLE CATEGORIES
=================

1. INVARIANT ORACLES - Verify system-declared invariants are maintained
   - write_containment: All writes stay within declared boundaries
   - isolation: Changes don't affect unrelated systems
   - idempotency: Repeating operation produces same result

2. BEHAVIOR ORACLES - Verify observable behavior matches expectations
   - exit_code: Process termination status
   - output_format: stdout/stderr structure
   - side_effects: File system, network, database changes

3. PERFORMANCE ORACLES - Verify performance characteristics
   - execution_time: Operation completes within budget
   - memory_usage: Peak memory stays under limit
   - resource_exhaustion: No resource leaks

4. SEMANTIC ORACLES - Verify logical correctness
   - data_integrity: Content preservation and transformation
   - consistency: Internal state coherence
   - causality: Effects follow causes

5. RECOVERY ORACLES - Verify fault handling and recovery
   - crash_safety: No data loss on crash
   - rollback: State can be reverted
   - resumption: Operation can resume from checkpoint

6. COMPATIBILITY ORACLES - Verify system integration
   - version_compatibility: Compatible with declared versions
   - dependency_satisfaction: Dependencies available
   - interface_stability: Interface unchanged

7. AUDIT ORACLES - Verify auditability and compliance
   - audit_trail: Changes are logged
   - authorization: Only authorized changes allowed
   - traceability: Changes linked to requests/decisions
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from ..evidence import Evidence
from ..signals import Severity, Signal, ok, unsure, violation


# ============================================================================
# ORACLE BASE AND INTERFACE
# ============================================================================

class OracleLogic(ABC):
    """Base class for oracle implementations with metadata."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this oracle."""
        pass

    @property
    @abstractmethod
    def category(self) -> str:
        """Category: invariant, behavior, performance, semantic, recovery, compatibility, audit."""
        pass

    @property
    @abstractmethod
    def domain(self) -> str:
        """Domain: generic, code_modification, refactoring, infrastructure, config, etc."""
        pass

    @property
    def description(self) -> str:
        """Human-readable description of what this oracle checks."""
        return self.__doc__ or f"Oracle: {self.name}"

    @property
    def severity_floor(self) -> Severity:
        """Minimum severity this oracle can report."""
        return Severity.LOW

    @abstractmethod
    def judge(self, evidence: Evidence) -> Sequence[Signal]:
        """Evaluate evidence and return signals."""
        pass


# ============================================================================
# INVARIANT ORACLES
# ============================================================================

class WriteContainmentOracle(OracleLogic):
    """Verify all writes stay within declared boundaries.

    Useful for: sandboxed execution, container isolation, permission
    enforcement, deployment systems.
    """

    def __init__(self, allowed_roots: Optional[Set[str]] = None):
        self.allowed_roots = allowed_roots or {"/"}

    @property
    def name(self) -> str:
        return "write_containment"

    @property
    def category(self) -> str:
        return "invariant"

    @property
    def domain(self) -> str:
        return "generic"

    def judge(self, evidence: Evidence) -> Sequence[Signal]:
        out: List[Signal] = []
        changed = evidence.changed() or {}

        for path in changed.keys():
            if not any(path.startswith(root) for root in self.allowed_roots):
                out.append(violation(
                    self.name, Severity.CRITICAL, "write_outside_boundary",
                    f"write to {path} outside allowed roots",
                    detail=f"Allowed: {self.allowed_roots}",
                    path=path
                ))
        return out if out else [ok(self.name, "all_writes_contained",
                                    f"all writes within {self.allowed_roots}")]


class IsolationOracle(OracleLogic):
    """Verify changes don't affect unrelated systems/files."""

    def __init__(self, protected_paths: Optional[Set[str]] = None):
        self.protected_paths = protected_paths or {".git", ".env", "secrets/"}

    @property
    def name(self) -> str:
        return "isolation"

    @property
    def category(self) -> str:
        return "invariant"

    @property
    def domain(self) -> str:
        return "generic"

    def judge(self, evidence: Evidence) -> Sequence[Signal]:
        out: List[Signal] = []
        changed = evidence.changed() or {}

        for path in changed.keys():
            if any(protected in path for protected in self.protected_paths):
                out.append(violation(
                    self.name, Severity.CRITICAL, "protected_path_modified",
                    f"protected path modified: {path}",
                    detail=f"Protected paths: {self.protected_paths}",
                    path=path
                ))
        return out if out else [ok(self.name, "isolation_maintained",
                                    "no protected paths were modified")]


class IdempotencyOracle(OracleLogic):
    """Verify repeating the operation produces identical results."""

    @property
    def name(self) -> str:
        return "idempotency"

    @property
    def category(self) -> str:
        return "invariant"

    @property
    def domain(self) -> str:
        return "infrastructure"

    def judge(self, evidence: Evidence) -> Sequence[Signal]:
        # This would compare first run against second run
        # In current Swizzle, this requires multi-run comparison
        if not evidence.has_metadata("second_run"):
            return [unsure(self.name, "no_comparison",
                          "idempotency requires second run for comparison")]

        first_changes = evidence.metadata("first_run", {}).get("changed", set())
        second_changes = evidence.metadata("second_run", {}).get("changed", set())

        if first_changes == second_changes:
            return [ok(self.name, "idempotent",
                      "both runs produced identical results")]
        else:
            return [violation(
                self.name, Severity.HIGH, "non_idempotent",
                f"runs produced different results: {first_changes ^ second_changes}"
            )]


# ============================================================================
# BEHAVIOR ORACLES
# ============================================================================

class ExitCodeOracle(OracleLogic):
    """Verify process exit codes match expectations."""

    def __init__(self, acceptable_codes: Optional[Set[int]] = None):
        self.acceptable_codes = acceptable_codes or {0}

    @property
    def name(self) -> str:
        return "exit_code"

    @property
    def category(self) -> str:
        return "behavior"

    @property
    def domain(self) -> str:
        return "generic"

    def judge(self, evidence: Evidence) -> Sequence[Signal]:
        if evidence.observation.failed:
            return [violation(
                self.name, Severity.HIGH, "process_failed",
                f"exit code {evidence.observation.failure} not in {self.acceptable_codes}",
                detail=evidence.observation.failure
            )]
        return [ok(self.name, "acceptable_exit", "process exited successfully")]


class OutputFormatOracle(OracleLogic):
    """Verify stdout/stderr structure and presence."""

    def __init__(self, require_stdout: bool = False,
                 require_json: bool = False,
                 forbidden_strings: Optional[Set[str]] = None):
        self.require_stdout = require_stdout
        self.require_json = require_json
        self.forbidden_strings = forbidden_strings or {"Error:", "FATAL"}

    @property
    def name(self) -> str:
        return "output_format"

    @property
    def category(self) -> str:
        return "behavior"

    @property
    def domain(self) -> str:
        return "generic"

    def judge(self, evidence: Evidence) -> Sequence[Signal]:
        out: List[Signal] = []
        stdout = evidence.observation.stdout

        if self.require_stdout and not stdout:
            out.append(violation(
                self.name, Severity.MAJOR, "missing_output",
                "process produced no stdout"
            ))

        for forbidden in self.forbidden_strings:
            if forbidden in stdout:
                out.append(violation(
                    self.name, Severity.MAJOR, "forbidden_output",
                    f"output contains forbidden string: {forbidden}"
                ))

        if self.require_json:
            import json
            try:
                json.loads(stdout)
            except (json.JSONDecodeError, ValueError):
                out.append(violation(
                    self.name, Severity.MAJOR, "invalid_json",
                    "stdout is not valid JSON"
                ))

        return out if out else [ok(self.name, "output_valid", "output format acceptable")]


class SideEffectOracle(OracleLogic):
    """Verify side effects (files, network, processes) are expected."""

    def __init__(self, allowed_files: Optional[Set[str]] = None,
                 allowed_processes: Optional[Set[str]] = None):
        self.allowed_files = allowed_files
        self.allowed_processes = allowed_processes

    @property
    def name(self) -> str:
        return "side_effects"

    @property
    def category(self) -> str:
        return "behavior"

    @property
    def domain(self) -> str:
        return "generic"

    def judge(self, evidence: Evidence) -> Sequence[Signal]:
        out: List[Signal] = []

        # Check file side effects
        if self.allowed_files is not None:
            created = evidence.metadata("created_files", set())
            for f in created:
                if f not in self.allowed_files:
                    out.append(violation(
                        self.name, Severity.MAJOR, "unexpected_file",
                        f"unexpected file created: {f}"
                    ))

        # Check process side effects
        if self.allowed_processes is not None:
            spawned = evidence.metadata("spawned_processes", set())
            for p in spawned:
                if p not in self.allowed_processes:
                    out.append(violation(
                        self.name, Severity.MAJOR, "unexpected_process",
                        f"unexpected process spawned: {p}"
                    ))

        return out if out else [ok(self.name, "side_effects_acceptable",
                                    "side effects within expectations")]


# ============================================================================
# PERFORMANCE ORACLES
# ============================================================================

class ExecutionTimeOracle(OracleLogic):
    """Verify operation completes within time budget."""

    def __init__(self, max_seconds: float = 300.0):
        self.max_seconds = max_seconds

    @property
    def name(self) -> str:
        return "execution_time"

    @property
    def category(self) -> str:
        return "performance"

    @property
    def domain(self) -> str:
        return "generic"

    def judge(self, evidence: Evidence) -> Sequence[Signal]:
        if evidence.observation.timed_out:
            return [violation(
                self.name, Severity.HIGH, "timeout",
                f"operation exceeded {self.max_seconds}s timeout"
            )]

        elapsed = evidence.metadata("elapsed_seconds", 0.0)
        if elapsed > self.max_seconds:
            return [violation(
                self.name, Severity.MAJOR, "slow_execution",
                f"operation took {elapsed:.1f}s, budget is {self.max_seconds}s"
            )]

        return [ok(self.name, "within_budget",
                  f"completed in {elapsed:.1f}s (budget: {self.max_seconds}s)")]


class MemoryUsageOracle(OracleLogic):
    """Verify peak memory stays under limit."""

    def __init__(self, max_mb: float = 1024.0):
        self.max_mb = max_mb

    @property
    def name(self) -> str:
        return "memory_usage"

    @property
    def category(self) -> str:
        return "performance"

    @property
    def domain(self) -> str:
        return "generic"

    def judge(self, evidence: Evidence) -> Sequence[Signal]:
        peak_mb = evidence.metadata("peak_memory_mb", 0.0)

        if peak_mb > self.max_mb:
            return [violation(
                self.name, Severity.MAJOR, "memory_exceeded",
                f"peak memory {peak_mb:.1f}MB exceeds limit {self.max_mb}MB"
            )]

        return [ok(self.name, "memory_acceptable",
                  f"peak memory {peak_mb:.1f}MB within limit")]


# ============================================================================
# SEMANTIC ORACLES
# ============================================================================

class DataIntegrityOracle(OracleLogic):
    """Verify content preservation and transformation correctness."""

    def __init__(self, preserve_checksums: bool = True,
                 validate_schema: bool = False):
        self.preserve_checksums = preserve_checksums
        self.validate_schema = validate_schema

    @property
    def name(self) -> str:
        return "data_integrity"

    @property
    def category(self) -> str:
        return "semantic"

    @property
    def domain(self) -> str:
        return "generic"

    def judge(self, evidence: Evidence) -> Sequence[Signal]:
        out: List[Signal] = []

        if self.preserve_checksums:
            checksums_before = evidence.metadata("checksums_before", {})
            checksums_after = evidence.metadata("checksums_after", {})

            for path, before_hash in checksums_before.items():
                if path not in checksums_after:
                    out.append(violation(
                        self.name, Severity.CRITICAL, "file_deleted",
                        f"file was deleted: {path}"
                    ))
                elif before_hash != checksums_after[path]:
                    # Only flag if not explicitly allowed to change
                    if not evidence.ground_truth.permitted_edits:
                        out.append(violation(
                            self.name, Severity.HIGH, "unexpected_modification",
                            f"file modified unexpectedly: {path}"
                        ))

        return out if out else [ok(self.name, "data_intact",
                                    "data integrity maintained")]


class ConsistencyOracle(OracleLogic):
    """Verify internal state coherence (e.g., index/data agreement)."""

    @property
    def name(self) -> str:
        return "consistency"

    @property
    def category(self) -> str:
        return "semantic"

    @property
    def domain(self) -> str:
        return "generic"

    def judge(self, evidence: Evidence) -> Sequence[Signal]:
        # Check for consistency markers in metadata
        inconsistencies = evidence.metadata("inconsistencies", [])

        if inconsistencies:
            return [violation(
                self.name, Severity.CRITICAL, "state_inconsistent",
                f"internal state inconsistencies detected: {inconsistencies}"
            )]

        return [ok(self.name, "consistent", "internal state is consistent")]


# ============================================================================
# RECOVERY ORACLES
# ============================================================================

class CrashSafetyOracle(OracleLogic):
    """Verify no data loss on unexpected termination."""

    @property
    def name(self) -> str:
        return "crash_safety"

    @property
    def category(self) -> str:
        return "recovery"

    @property
    def domain(self) -> str:
        return "infrastructure"

    def judge(self, evidence: Evidence) -> Sequence[Signal]:
        if evidence.observation.failed and evidence.observation.failure == "SIGKILL":
            # Verify partial writes don't corrupt state
            corrupt = evidence.metadata("data_corruption", [])
            if corrupt:
                return [violation(
                    self.name, Severity.CRITICAL, "crash_corruption",
                    f"data corruption on crash: {corrupt}"
                )]
            return [ok(self.name, "crash_safe",
                      "no corruption despite SIGKILL")]

        return [unsure(self.name, "no_crash", "process did not crash")]


class RollbackOracle(OracleLogic):
    """Verify state can be reverted on failure."""

    @property
    def name(self) -> str:
        return "rollback"

    @property
    def category(self) -> str:
        return "recovery"

    @property
    def domain(self) -> str:
        return "infrastructure"

    def judge(self, evidence: Evidence) -> Sequence[Signal]:
        if not evidence.has_metadata("rollback_attempted"):
            return [unsure(self.name, "no_rollback_test",
                          "rollback not tested in this case")]

        state_before = evidence.metadata("state_before_rollback", {})
        state_after = evidence.metadata("state_after_rollback", {})

        if state_before == state_after:
            return [ok(self.name, "rollback_successful",
                      "state fully reverted")]
        else:
            return [violation(
                self.name, Severity.CRITICAL, "rollback_incomplete",
                "state not fully reverted after rollback"
            )]


# ============================================================================
# COMPATIBILITY ORACLES
# ============================================================================

class VersionCompatibilityOracle(OracleLogic):
    """Verify compatibility with declared versions."""

    def __init__(self, compatible_versions: Optional[Set[str]] = None):
        self.compatible_versions = compatible_versions

    @property
    def name(self) -> str:
        return "version_compatibility"

    @property
    def category(self) -> str:
        return "compatibility"

    @property
    def domain(self) -> str:
        return "generic"

    def judge(self, evidence: Evidence) -> Sequence[Signal]:
        if not self.compatible_versions:
            return [unsure(self.name, "unconstrained",
                          "no version constraints defined")]

        version = evidence.observation.version.get("version", "unknown")

        if version not in self.compatible_versions:
            return [violation(
                self.name, Severity.HIGH, "incompatible_version",
                f"version {version} not in compatible set {self.compatible_versions}"
            )]

        return [ok(self.name, "version_compatible",
                  f"version {version} is compatible")]


class DependencySatisfactionOracle(OracleLogic):
    """Verify required dependencies are available."""

    def __init__(self, required_dependencies: Optional[Set[str]] = None):
        self.required_dependencies = required_dependencies or set()

    @property
    def name(self) -> str:
        return "dependency_satisfaction"

    @property
    def category(self) -> str:
        return "compatibility"

    @property
    def domain(self) -> str:
        return "generic"

    def judge(self, evidence: Evidence) -> Sequence[Signal]:
        available = evidence.metadata("available_dependencies", set())
        missing = self.required_dependencies - available

        if missing:
            return [violation(
                self.name, Severity.HIGH, "missing_dependencies",
                f"required dependencies not available: {missing}"
            )]

        return [ok(self.name, "dependencies_satisfied",
                  f"all {len(self.required_dependencies)} dependencies available")]


# ============================================================================
# AUDIT ORACLES
# ============================================================================

class AuditTrailOracle(OracleLogic):
    """Verify changes are logged and traceable."""

    @property
    def name(self) -> str:
        return "audit_trail"

    @property
    def category(self) -> str:
        return "audit"

    @property
    def domain(self) -> str:
        return "generic"

    def judge(self, evidence: Evidence) -> Sequence[Signal]:
        if evidence.observation.abstained:
            return [ok(self.name, "no_changes", "no changes, no audit needed")]

        audit_entries = evidence.metadata("audit_entries", [])
        changed_count = len(evidence.changed() or {})

        if not audit_entries:
            return [violation(
                self.name, Severity.HIGH, "missing_audit_trail",
                f"{changed_count} changes made but no audit trail"
            )]

        if len(audit_entries) < changed_count:
            return [violation(
                self.name, Severity.MAJOR, "incomplete_audit",
                f"only {len(audit_entries)} of {changed_count} changes logged"
            )]

        return [ok(self.name, "audit_complete",
                  f"all {changed_count} changes logged")]


class AuthorizationOracle(OracleLogic):
    """Verify only authorized changes were made."""

    @property
    def name(self) -> str:
        return "authorization"

    @property
    def category(self) -> str:
        return "audit"

    @property
    def domain(self) -> str:
        return "generic"

    def judge(self, evidence: Evidence) -> Sequence[Signal]:
        changed = evidence.changed() or {}
        permitted = evidence.ground_truth.permitted_edits or []
        permitted_paths = {e.path for e in permitted}

        unauthorized = [p for p in changed.keys() if p not in permitted_paths]

        if unauthorized:
            return [violation(
                self.name, Severity.CRITICAL, "unauthorized_changes",
                f"unauthorized changes to: {unauthorized}",
                detail=f"Permitted paths: {permitted_paths}"
            )]

        return [ok(self.name, "all_authorized",
                  f"all {len(changed)} changes were authorized")]


# ============================================================================
# ORACLE LIBRARY AND COMPOSITION
# ============================================================================

@dataclass
class OracleProfile:
    """Predefined set of oracles for a domain."""

    name: str
    domain: str
    oracles: Dict[str, OracleLogic]
    description: str = ""

    def select(self, names: Optional[List[str]] = None) -> Dict[str, OracleLogic]:
        """Select subset of oracles from this profile."""
        if not names:
            return self.oracles
        return {k: v for k, v in self.oracles.items() if k in names}


class OracleLibrary:
    """Central registry and selector for oracle implementations."""

    def __init__(self):
        self.oracles: Dict[str, OracleLogic] = {}
        self.profiles: Dict[str, OracleProfile] = {}
        self._initialize_defaults()

    def _initialize_defaults(self):
        """Initialize default oracles and profiles."""

        # Register individual oracles
        oracles = [
            WriteContainmentOracle(),
            IsolationOracle(),
            IdempotencyOracle(),
            ExitCodeOracle(),
            OutputFormatOracle(),
            SideEffectOracle(),
            ExecutionTimeOracle(),
            MemoryUsageOracle(),
            DataIntegrityOracle(),
            ConsistencyOracle(),
            CrashSafetyOracle(),
            RollbackOracle(),
            VersionCompatibilityOracle(),
            DependencySatisfactionOracle(),
            AuditTrailOracle(),
            AuthorizationOracle(),
        ]

        for oracle in oracles:
            self.oracles[oracle.name] = oracle

        # Define profiles
        self.profiles["code_modification"] = OracleProfile(
            name="code_modification",
            domain="code",
            oracles={
                "write_containment": self.oracles["write_containment"],
                "isolation": self.oracles["isolation"],
                "data_integrity": self.oracles["data_integrity"],
                "audit_trail": self.oracles["audit_trail"],
            },
            description="Oracles for code modification systems (refactoring, generation)"
        )

        self.profiles["infrastructure"] = OracleProfile(
            name="infrastructure",
            domain="infrastructure",
            oracles={
                "idempotency": self.oracles["idempotency"],
                "crash_safety": self.oracles["crash_safety"],
                "rollback": self.oracles["rollback"],
                "consistency": self.oracles["consistency"],
            },
            description="Oracles for infrastructure provisioning systems"
        )

        self.profiles["strict_verification"] = OracleProfile(
            name="strict_verification",
            domain="all",
            oracles=self.oracles.copy(),
            description="All available oracles for comprehensive verification"
        )

        self.profiles["fast_check"] = OracleProfile(
            name="fast_check",
            domain="all",
            oracles={
                "exit_code": self.oracles["exit_code"],
                "output_format": self.oracles["output_format"],
            },
            description="Minimal oracles for quick feedback"
        )

    def register(self, oracle: OracleLogic) -> None:
        """Register a custom oracle."""
        self.oracles[oracle.name] = oracle

    def get(self, name: str) -> Optional[OracleLogic]:
        """Get oracle by name."""
        return self.oracles.get(name)

    def by_category(self, category: str) -> Dict[str, OracleLogic]:
        """Get all oracles in a category."""
        return {k: v for k, v in self.oracles.items()
                if v.category == category}

    def by_domain(self, domain: str) -> Dict[str, OracleLogic]:
        """Get all oracles for a domain."""
        return {k: v for k, v in self.oracles.items()
                if v.domain == domain}

    def profile(self, name: str) -> Optional[OracleProfile]:
        """Get predefined profile."""
        return self.profiles.get(name)

    def list_profiles(self) -> List[str]:
        """List available profiles."""
        return list(self.profiles.keys())

    def describe_oracle(self, name: str) -> Optional[str]:
        """Get oracle description."""
        oracle = self.get(name)
        return oracle.description if oracle else None


# Global library instance
_library: Optional[OracleLibrary] = None


def get_library() -> OracleLibrary:
    """Get global oracle library."""
    global _library
    if _library is None:
        _library = OracleLibrary()
    return _library
