"""Unified invariant schema for Swizzle and Ghost Tools.

Invariants are the "rules of the game" — constraints each tool must enforce.
This schema allows both tools to express and share what they claim to guarantee.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from pathlib import Path
import json


class InvariantScope(str, Enum):
    """Where an invariant applies."""
    REPOSITORY = "repository"
    WORKING_TREE = "working_tree"
    BRANCH = "branch"
    FILE = "file"
    CONTENT = "content"
    METADATA = "metadata"


class InvariantSeverity(str, Enum):
    """Impact of violating this invariant."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class InvariantViolation:
    """Evidence that an invariant was violated."""
    invariant_id: str
    scope: InvariantScope
    location: str  # path, branch name, commit hash, etc.
    description: str
    evidence: Dict[str, str]  # specific findings
    severity: InvariantSeverity
    reproduced: bool = False
    minimized_case: Optional[str] = None


@dataclass
class Invariant:
    """A constraint the system must maintain.

    Example invariants:
    - "Repository content never written outside repo boundaries"
    - "Authorized content is never deleted without detection"
    - "Branch state is reverted if operation fails"
    - "Test suite still passes after modifications"
    - "Ledger entries are never suppressed"
    """
    id: str
    name: str
    description: str
    scope: InvariantScope
    severity: InvariantSeverity

    # How to detect violation
    check_function: Optional[str] = None  # reference to checker

    # When it applies
    applies_to: List[str] = field(default_factory=list)  # tool names: ["ghost_tools", "swizzle"]
    applies_after: Optional[str] = None  # version
    applies_before: Optional[str] = None  # version

    # Related information
    related_issues: List[str] = field(default_factory=list)  # issue tracker IDs
    discovered_by: Optional[str] = None  # which tool/method found it
    historical_violations: List[InvariantViolation] = field(default_factory=list)


@dataclass
class InvariantLibrary:
    """Shared invariant definitions both tools know about."""
    invariants: Dict[str, Invariant] = field(default_factory=dict)
    version: str = "1.0"
    last_updated: str = ""

    def add_invariant(self, invariant: Invariant) -> None:
        """Register an invariant."""
        self.invariants[invariant.id] = invariant

    def to_json(self) -> str:
        """Export as JSON for cross-tool consumption."""
        data = {
            "version": self.version,
            "last_updated": self.last_updated,
            "invariants": {
                iid: {
                    "id": inv.id,
                    "name": inv.name,
                    "description": inv.description,
                    "scope": inv.scope.value,
                    "severity": inv.severity.value,
                    "applies_to": inv.applies_to,
                    "related_issues": inv.related_issues,
                    "discovered_by": inv.discovered_by,
                }
                for iid, inv in self.invariants.items()
            }
        }
        return json.dumps(data, indent=2)

    def save(self, path: Path) -> None:
        """Write to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())


# Shared invariants both tools enforce
DEFAULT_INVARIANTS = InvariantLibrary(
    version="1.0",
    last_updated="2026-09-18"
)

DEFAULT_INVARIANTS.add_invariant(Invariant(
    id="no_write_outside_boundary",
    name="No writes outside repository boundary",
    description="All file writes must remain within the repository root. Symlinks or path traversal must not escape it.",
    scope=InvariantScope.REPOSITORY,
    severity=InvariantSeverity.CRITICAL,
    applies_to=["ghost_tools", "swizzle"],
    related_issues=["swizzle#1"],
))

DEFAULT_INVARIANTS.add_invariant(Invariant(
    id="authorized_content_preserved",
    name="Authorized content is not deleted",
    description="Prose, comments, or data explicitly placed inside marked blocks by users must not be deleted.",
    scope=InvariantScope.CONTENT,
    severity=InvariantSeverity.CRITICAL,
    applies_to=["ghost_tools", "swizzle"],
    related_issues=["swizzle#1"],
))

DEFAULT_INVARIANTS.add_invariant(Invariant(
    id="branch_state_reverted_on_failure",
    name="Branch state reverted on operation failure",
    description="If an operation fails, the repository must be left on its original branch, clean.",
    scope=InvariantScope.BRANCH,
    severity=InvariantSeverity.HIGH,
    applies_to=["ghost_tools", "swizzle"],
))

DEFAULT_INVARIANTS.add_invariant(Invariant(
    id="ledger_never_suppressed",
    name="Ledger entries are never suppressed",
    description="Triage decisions and case history can add entries but never remove or lower severity.",
    scope=InvariantScope.METADATA,
    severity=InvariantSeverity.HIGH,
    applies_to=["ghost_tools"],
))

DEFAULT_INVARIANTS.add_invariant(Invariant(
    id="test_suite_preserved",
    name="Test suite continues to pass",
    description="After modifications, the repository's own test suite must still pass.",
    scope=InvariantScope.REPOSITORY,
    severity=InvariantSeverity.HIGH,
    applies_to=["ghost_tools"],
))

DEFAULT_INVARIANTS.add_invariant(Invariant(
    id="verification_independent",
    name="Verification is independent of implementation",
    description="Verification oracles must not consume the implementation's ground truth or conclusions.",
    scope=InvariantScope.REPOSITORY,
    severity=InvariantSeverity.HIGH,
    applies_to=["swizzle"],
))
