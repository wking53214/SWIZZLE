"""Explicit SWIZZLE-to-WIZZLE verification boundary.

SWIZZLE owns experiment construction and target execution. WIZZLE receives
only the resulting repository path and the target's raw claim. Its warrant
comes from its own observation oracles, never from SWIZZLE ground truth or
the target's conclusion.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from .epistemic_model import ExperimentResult, GhostObservation
from .evaluator import Evaluator


@dataclass(frozen=True)
class VerificationArtifact:
    """Immutable hand-off from target execution to independent verification."""

    repository: Path
    target: str
    findings: tuple[Mapping[str, Any], ...] = ()
    raw_stdout: str = ""
    raw_stderr: str = ""
    target_version: Mapping[str, str] = None

    def __post_init__(self) -> None:
        if self.target_version is None:
            object.__setattr__(self, "target_version", {})
        else:
            object.__setattr__(self, "target_version", dict(self.target_version))


def verify_artifact(
    artifact: VerificationArtifact,
    *,
    member_name: str,
    provenance_class: str,
    severity: str,
    evidence_cited: Sequence[str] = (),
) -> tuple[ExperimentResult, Mapping[str, Any]]:
    """Observe and evaluate a target claim without consuming hidden truth."""
    evaluator = Evaluator(artifact.repository)
    oracle_results = evaluator.run_all_oracles()
    claim = GhostObservation(
        member_name=member_name,
        provenance_class=provenance_class,
        severity=severity,
        evidence_cited=list(evidence_cited),
    )
    result = evaluator.evaluate_observation(claim, oracle_results)
    return result, oracle_results
