"""Cross-tool architecture audit and validation.

Swizzle's architecture violation detection can be applied to Ghost's changes.
Ghost's boundary tests can validate Swizzle's adapter contracts.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set
from pathlib import Path
import json


class ArchitectureViolationType(str, Enum):
    """Types of architecture violations."""
    BOUNDARY_VIOLATION = "boundary_violation"  # module imports across wrong boundary
    COUPLING_INTRODUCED = "coupling_introduced"  # unnecessary dependency added
    RESPONSIBILITY_BLURRED = "responsibility_blurred"  # module doing too much
    BYPASS_CONTROL = "bypass_control"  # control mechanism bypassed
    HIDDEN_DEPENDENCY = "hidden_dependency"  # non-obvious circular or deep dependency


@dataclass
class ArchitectureBoundary:
    """A logical module boundary."""
    id: str
    name: str
    description: str
    owns_modules: List[str]  # module names/paths this boundary manages
    can_import_from: List[str] = field(default_factory=list)  # allowed imports
    cannot_import_from: List[str] = field(default_factory=list)  # forbidden imports
    enforced_by: List[str] = field(default_factory=list)  # which tools enforce this


@dataclass
class ArchitectureViolation:
    """Evidence of an architecture rule being broken."""
    id: str
    violation_type: ArchitectureViolationType
    boundary_id: str  # which boundary is violated
    location: str  # file path or module
    description: str
    evidence: Dict[str, str]  # specific imports, calls, etc.
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW

    # Resolution
    discovered_in_commit: Optional[str] = None
    fixed_in_commit: Optional[str] = None
    unfixed_since: str = ""  # ISO 8601


@dataclass
class ArchitectureAudit:
    """Architecture rules for a tool."""
    tool_name: str  # "ghost_tools" or "swizzle"
    version: str = "1.0"
    boundaries: Dict[str, ArchitectureBoundary] = field(default_factory=dict)
    violations: Dict[str, ArchitectureViolation] = field(default_factory=dict)
    last_audit: str = ""

    def add_boundary(self, boundary: ArchitectureBoundary) -> None:
        """Define an architecture boundary."""
        self.boundaries[boundary.id] = boundary

    def add_violation(self, violation: ArchitectureViolation) -> None:
        """Record a violation."""
        self.violations[violation.id] = violation

    def violations_in_boundary(self, boundary_id: str) -> List[ArchitectureViolation]:
        """Get all violations in a specific boundary."""
        return [v for v in self.violations.values() if v.boundary_id == boundary_id]

    def unresolved_violations(self) -> List[ArchitectureViolation]:
        """Get violations not yet fixed."""
        return [v for v in self.violations.values() if v.fixed_in_commit is None]

    def to_json(self) -> str:
        """Export audit."""
        data = {
            "tool_name": self.tool_name,
            "version": self.version,
            "last_audit": self.last_audit,
            "boundaries": {
                bid: {
                    "id": b.id,
                    "name": b.name,
                    "description": b.description,
                    "owns_modules": b.owns_modules,
                    "can_import_from": b.can_import_from,
                    "cannot_import_from": b.cannot_import_from,
                    "enforced_by": b.enforced_by,
                }
                for bid, b in self.boundaries.items()
            },
            "violations": {
                vid: {
                    "id": v.id,
                    "type": v.violation_type.value,
                    "boundary_id": v.boundary_id,
                    "location": v.location,
                    "description": v.description,
                    "severity": v.severity,
                    "discovered_in_commit": v.discovered_in_commit,
                    "fixed_in_commit": v.fixed_in_commit,
                    "unfixed_since": v.unfixed_since,
                }
                for vid, v in self.violations.items()
            }
        }
        return json.dumps(data, indent=2)

    def save(self, path: Path) -> None:
        """Write to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())


# Swizzle architecture audit
SWIZZLE_AUDIT = ArchitectureAudit(tool_name="swizzle", version="1.0")

SWIZZLE_AUDIT.add_boundary(ArchitectureBoundary(
    id="lab_independence",
    name="Lab oracle independence",
    description="Ground truth cannot reach oracles; oracles are pure functions of evidence",
    owns_modules=["swizzle.lab.oracles", "swizzle.wizzle"],
    cannot_import_from=["swizzle.lab.draft", "swizzle.lab.sandbox"],
    enforced_by=["swizzle", "test_lab_oracle_independence"],
))

SWIZZLE_AUDIT.add_boundary(ArchitectureBoundary(
    id="adapter_abstraction",
    name="Target adapter abstraction",
    description="Nothing above lab/adapter.py names the target",
    owns_modules=["swizzle.lab.adapters"],
    can_import_from=["swizzle.lab.adapter", "swizzle.lab.sandbox"],
    enforced_by=["swizzle"],
))

SWIZZLE_AUDIT.add_boundary(ArchitectureBoundary(
    id="corpus_isolation",
    name="Corpus data isolation",
    description="Corpus contains only serializable RepositoryGenome and verdict, no runtime state",
    owns_modules=["swizzle.corpus"],
    cannot_import_from=["swizzle.lab"],
    enforced_by=["swizzle"],
))


# Ghost Tools architecture audit
GHOST_AUDIT = ArchitectureAudit(tool_name="ghost_tools", version="1.0")

GHOST_AUDIT.add_boundary(ArchitectureBoundary(
    id="tree_boundary",
    name="Repository boundary",
    description="All writes stay within repository root; symlinks and traversal are contained",
    owns_modules=["ghost_buster.boundary", "ghost_buster.annotate"],
    enforced_by=["ghost_tools", "swizzle"],
))

GHOST_AUDIT.add_boundary(ArchitectureBoundary(
    id="ledger_authority",
    name="Ledger is append-only",
    description="Ledger entries are never removed or severity downgraded",
    owns_modules=["ghost_buster.ledger", "ghost_buster.casefile"],
    cannot_import_from=["ghost_buster.mutation"],  # mutations shouldn't suppress ledger
    enforced_by=["ghost_tools"],
))

GHOST_AUDIT.add_boundary(ArchitectureBoundary(
    id="surgeon_isolation",
    name="Surgeon operates on branch",
    description="Original branch is never written to; operates on temporary branch only",
    owns_modules=["ghost_buster.annotate", "ghost_buster.branches"],
    enforced_by=["ghost_tools", "swizzle"],
))


@dataclass
class ArchitectureComplianceReport:
    """Cross-tool architecture compliance."""
    audits: Dict[str, ArchitectureAudit] = field(default_factory=dict)
    compatibility_matrix: Dict[str, Dict[str, bool]] = field(default_factory=dict)  # tool x boundary
    version: str = "1.0"
    last_updated: str = ""

    def check_compliance(self, tool_name: str, boundary_id: str) -> bool:
        """Is a tool compliant with a boundary?"""
        if tool_name not in self.audits:
            return False
        audit = self.audits[tool_name]
        if boundary_id not in audit.boundaries:
            return False

        unresolved = audit.violations_in_boundary(boundary_id)
        return len(unresolved) == 0

    def to_json(self) -> str:
        """Export report."""
        data = {
            "version": self.version,
            "last_updated": self.last_updated,
            "audits": {
                tool: json.loads(audit.to_json())
                for tool, audit in self.audits.items()
            },
            "compliance_matrix": self.compatibility_matrix,
        }
        return json.dumps(data, indent=2)
