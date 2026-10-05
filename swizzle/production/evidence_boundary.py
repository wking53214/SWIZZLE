"""Evidence boundary: target claim ≠ harness observation ≠ independent capture."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

class EvidenceLane(str, Enum):
    TARGET_CLAIM = "TARGET_CLAIM"
    HARNESS_OBSERVATION = "HARNESS_OBSERVATION"
    INDEPENDENT_CAPTURE = "INDEPENDENT_CAPTURE"

@dataclass
class LaneEvidence:
    lane: EvidenceLane
    summary: str
    payload: Dict[str, Any] = field(default_factory=dict)
    producer: str = ""
    authoritative: bool = False

class EvidenceBoundary:
    def __init__(self):
        self._lanes = {lane: [] for lane in EvidenceLane}
    def record_target_claim(self, summary, payload=None, producer="target"):
        self._lanes[EvidenceLane.TARGET_CLAIM].append(
            LaneEvidence(EvidenceLane.TARGET_CLAIM, summary, payload or {}, producer, False))
    def record_harness_observation(self, summary, payload=None, producer="harness"):
        self._lanes[EvidenceLane.HARNESS_OBSERVATION].append(
            LaneEvidence(EvidenceLane.HARNESS_OBSERVATION, summary, payload or {}, producer, False))
    def record_independent(self, summary, payload=None, producer="independent"):
        self._lanes[EvidenceLane.INDEPENDENT_CAPTURE].append(
            LaneEvidence(EvidenceLane.INDEPENDENT_CAPTURE, summary, payload or {}, producer, True))
    def authoritative_evidence(self):
        return [e for e in self._lanes[EvidenceLane.INDEPENDENT_CAPTURE] if e.authoritative]
    def assert_no_target_as_authority(self):
        for e in self._lanes[EvidenceLane.TARGET_CLAIM]:
            if e.authoritative:
                raise RuntimeError("TARGET_CLAIM marked authoritative — adapter must not manufacture authority")
