"""Durable machine-readable experiment record.

Every experiment produces a structured record capturing:
- What was constructed (scenario)
- What was observed (from repository)
- What was inferred (by oracles)
- What conclusions were reached
- What entitlements were justified
- Complete provenance and reproducibility
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from enum import Enum
from pathlib import Path
from datetime import datetime
import json


class ExecutionStatus(Enum):
    """Status of target invocation."""
    EXECUTED = "executed"           # Target ran successfully
    UNAVAILABLE = "unavailable"     # Target not available
    TIMEOUT = "timeout"             # Execution timed out
    CRASHED = "crashed"             # Target crashed
    MALFORMED_OUTPUT = "malformed"  # Output unparseable
    NO_FINDINGS = "no_findings"     # Executed but no findings
    ERRORED = "errored"             # Unknown error


@dataclass
class RepositoryDigest:
    """Reproducible repository state hash."""
    commit_hash: str
    tree_hash: str
    file_count: int
    scenario_name: str

    def __str__(self) -> str:
        return f"{self.scenario_name}:{self.commit_hash[:8]}"


@dataclass
class ObservedEvidence:
    """A single observed fact from the repository."""
    description: str
    provenance: str  # CONSTRUCTED, OBSERVED, DERIVED, etc.
    value: Any
    source: Optional[str] = None
    confidence: float = 1.0


@dataclass
class OracleAssessment:
    """Result from one oracle."""
    oracle_name: str
    observations: List[ObservedEvidence] = field(default_factory=list)
    inferred_intent: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "oracle_name": self.oracle_name,
            "observations": [
                {
                    "description": o.description,
                    "provenance": o.provenance,
                    "value": o.value,
                    "source": o.source,
                    "confidence": o.confidence
                }
                for o in self.observations
            ],
            "inferred_intent": self.inferred_intent,
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }


@dataclass
class TargetExecution:
    """Record of invoking the target (Ghost)."""
    status: ExecutionStatus
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    timed_out: bool = False
    timeout_seconds: float = 30.0
    execution_time_ms: float = 0.0
    findings_count: int = 0
    error_message: Optional[str] = None


@dataclass
class TargetFinding:
    """A single finding from the target."""
    member_name: str
    category: str  # e.g., "REMOVED_FROM_LIBRARY"
    severity: str  # e.g., "MAJOR"
    confidence: float  # Target's reported confidence
    message: str
    evidence_cited: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SemanticVerdict:
    """Semantic correctness assessment."""
    verdict: str  # SUPPORTED, OVERCLAIMED, UNDERCLAIMED, CONTRADICTED, INCONCLUSIVE, UNASKABLE
    factual_correctness: str
    semantic_correctness: str
    supporting_evidence: List[str] = field(default_factory=list)
    contradicting_evidence: List[str] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)
    what_would_change_mind: List[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class ExperimentRecord:
    """Complete durable record of one experiment."""

    # Identity
    experiment_id: str
    scenario_id: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Construction
    repository_digest: Optional[RepositoryDigest] = None
    scenario_description: str = ""
    ground_truth_intent: Optional[str] = None

    # Execution
    target_execution: Optional[TargetExecution] = None
    target_findings: List[TargetFinding] = field(default_factory=list)

    # Independent observations
    oracle_assessments: List[OracleAssessment] = field(default_factory=list)

    # Semantic evaluation
    semantic_verdict: Optional[SemanticVerdict] = None

    # Action entitlement (separate from semantic)
    action_entitled: bool = False
    action_reasoning: str = ""
    required_for_action: List[str] = field(default_factory=list)

    # Reproducibility
    minimized_scenario_id: Optional[str] = None
    replay_digest: Optional[str] = None

    # Holdout classification
    holdout_status: Optional[str] = None  # DISCOVERY, HOLDOUT_H1, HOLDOUT_H2, HOLDOUT_H3

    # Metadata
    notes: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dictionary."""
        return {
            "experiment_id": self.experiment_id,
            "scenario_id": self.scenario_id,
            "created_at": self.created_at,
            "repository_digest": asdict(self.repository_digest) if self.repository_digest else None,
            "scenario_description": self.scenario_description,
            "ground_truth_intent": self.ground_truth_intent,
            "target_execution": asdict(self.target_execution) if self.target_execution else None,
            "target_findings": [asdict(f) for f in self.target_findings],
            "oracle_assessments": [o.to_dict() for o in self.oracle_assessments],
            "semantic_verdict": asdict(self.semantic_verdict) if self.semantic_verdict else None,
            "action_entitled": self.action_entitled,
            "action_reasoning": self.action_reasoning,
            "required_for_action": self.required_for_action,
            "minimized_scenario_id": self.minimized_scenario_id,
            "replay_digest": self.replay_digest,
            "holdout_status": self.holdout_status,
            "notes": self.notes,
            "tags": self.tags
        }

    def save(self, output_path: Path) -> None:
        """Save record as JSON."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    @classmethod
    def load(cls, input_path: Path) -> "ExperimentRecord":
        """Load record from JSON."""
        with open(input_path) as f:
            data = json.load(f)
        # Reconstruct from dict
        return cls(
            experiment_id=data.get("experiment_id", ""),
            scenario_id=data.get("scenario_id", ""),
            created_at=data.get("created_at", ""),
            scenario_description=data.get("scenario_description", ""),
            ground_truth_intent=data.get("ground_truth_intent"),
            action_entitled=data.get("action_entitled", False),
            action_reasoning=data.get("action_reasoning", ""),
            required_for_action=data.get("required_for_action", []),
            minimized_scenario_id=data.get("minimized_scenario_id"),
            replay_digest=data.get("replay_digest"),
            holdout_status=data.get("holdout_status"),
            notes=data.get("notes", ""),
            tags=data.get("tags", [])
        )
