"""Triage ledger exchange between Ghost Tools and Swizzle.

Ghost's triage decisions (what humans decided about findings) become Swizzle's
oracle training data. Conversely, Swizzle findings can be exported as Ghost
casefiles for Ghost to learn from.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from pathlib import Path
import json
from datetime import datetime


class Decision(str, Enum):
    """Human triage decision about a finding."""
    TRUE = "true"  # finding is real
    FALSE = "false"  # finding is false positive
    DEFERRED = "deferred"  # needs more context
    SUPPRESSED = "suppressed"  # intentionally ignored


class Severity(str, Enum):
    """Finding severity levels (unified across tools)."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class TriageEntry:
    """One decision in the triage ledger."""
    id: str  # unique identifier
    finding_type: str  # e.g., "prose_inside_maintained_block", "write_outside_boundary"
    location: str  # file path or repository identifier
    description: str
    severity_initial: Severity
    decision: Decision
    decided_by: str  # "ghost_tools", "swizzle", or user name
    decided_at: str  # ISO 8601 timestamp
    reasoning: str  # why this decision was made

    # Links to evidence
    associated_issues: List[str] = field(default_factory=list)
    related_minimized_case: Optional[str] = None  # Swizzle case ID if applicable

    # Outcome tracking
    outcome_severity: Optional[Severity] = None  # what severity revealed after decision
    validated: bool = False  # was this decision verified by another tool?


@dataclass
class TriageLedger:
    """Shared triage history both tools learn from."""
    entries: Dict[str, TriageEntry] = field(default_factory=dict)
    version: str = "1.0"
    source_tool: str = ""  # "ghost_tools" or "swizzle"
    last_updated: str = ""

    def add_entry(self, entry: TriageEntry) -> None:
        """Add a triage decision."""
        self.entries[entry.id] = entry

    def export_for_ghost_casefile(self) -> str:
        """Export as Ghost casefile format for Ghost to consume."""
        casefile = {}
        for entry_id, entry in self.entries.items():
            casefile[entry_id] = {
                "finding_type": entry.finding_type,
                "location": entry.location,
                "description": entry.description,
                "decision": entry.decision.value,
                "reasoning": entry.reasoning,
                "decided_at": entry.decided_at,
            }
        return json.dumps(casefile, indent=2)

    def export_for_swizzle_oracle_training(self) -> Dict:
        """Export as Swizzle oracle training data.

        Returns dict mapping finding types to (true_count, false_count, recent_decisions).
        This informs oracle thresholds and confidence calibration.
        """
        findings_by_type: Dict[str, List[TriageEntry]] = {}
        for entry in self.entries.values():
            if entry.finding_type not in findings_by_type:
                findings_by_type[entry.finding_type] = []
            findings_by_type[entry.finding_type].append(entry)

        training_data = {}
        for finding_type, entries in findings_by_type.items():
            true_count = sum(1 for e in entries if e.decision == Decision.TRUE)
            false_count = sum(1 for e in entries if e.decision == Decision.FALSE)
            deferred_count = sum(1 for e in entries if e.decision == Decision.DEFERRED)

            recent = sorted(entries, key=lambda e: e.decided_at, reverse=True)[:5]

            training_data[finding_type] = {
                "true_decisions": true_count,
                "false_decisions": false_count,
                "deferred_decisions": deferred_count,
                "false_positive_rate": false_count / (true_count + false_count) if (true_count + false_count) > 0 else 0,
                "recent_decisions": [
                    {
                        "decision": e.decision.value,
                        "severity": e.severity_initial.value,
                        "reasoning": e.reasoning,
                    }
                    for e in recent
                ],
            }

        return {
            "version": self.version,
            "source_tool": self.source_tool,
            "last_updated": self.last_updated,
            "training_data": training_data,
        }

    def to_json(self) -> str:
        """Export complete ledger."""
        data = {
            "version": self.version,
            "source_tool": self.source_tool,
            "last_updated": self.last_updated,
            "entries": {
                eid: {
                    "id": e.id,
                    "finding_type": e.finding_type,
                    "location": e.location,
                    "description": e.description,
                    "severity_initial": e.severity_initial.value,
                    "decision": e.decision.value,
                    "decided_by": e.decided_by,
                    "decided_at": e.decided_at,
                    "reasoning": e.reasoning,
                    "associated_issues": e.associated_issues,
                    "related_minimized_case": e.related_minimized_case,
                    "outcome_severity": e.outcome_severity.value if e.outcome_severity else None,
                    "validated": e.validated,
                }
                for eid, e in self.entries.items()
            }
        }
        return json.dumps(data, indent=2)

    def save(self, path: Path) -> None:
        """Write to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())


def import_ghost_casefile(casefile_path: Path) -> TriageLedger:
    """Import Ghost's casefile as Swizzle training ledger."""
    import json
    casefile = json.loads(casefile_path.read_text())

    ledger = TriageLedger(source_tool="ghost_tools", last_updated=datetime.now().isoformat())

    for entry_id, case_data in casefile.items():
        # Map Ghost's triage format to unified TriageEntry
        entry = TriageEntry(
            id=entry_id,
            finding_type=case_data.get("finding_type", "unknown"),
            location=case_data.get("location", ""),
            description=case_data.get("description", ""),
            severity_initial=Severity[case_data.get("severity", "MEDIUM").upper()],
            decision=Decision[case_data.get("decision", "DEFERRED").upper()],
            decided_by="ghost_tools",
            decided_at=case_data.get("decided_at", datetime.now().isoformat()),
            reasoning=case_data.get("reasoning", ""),
        )
        ledger.add_entry(entry)

    return ledger


# Default ledger instance for event handlers
DEFAULT_LEDGER = TriageLedger(version="1.0", source_tool="integrated")
