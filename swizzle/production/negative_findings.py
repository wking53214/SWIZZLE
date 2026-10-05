"""Preserve negative findings: not observed ≠ absent."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

class TestOutcome(str, Enum):
    TESTED = "TESTED"
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_TESTED = "NOT_TESTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"

@dataclass
class OutcomeRecord:
    test_id: str
    outcome: TestOutcome
    summary: str
    attack_class: Optional[str] = None
    oracle_basis: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

_OUTCOMES: List[OutcomeRecord] = []

def record_outcome(test_id, outcome, summary, attack_class=None, oracle_basis=None, details=None):
    rec = OutcomeRecord(test_id, outcome, summary, attack_class, oracle_basis, details or {})
    _OUTCOMES.append(rec)
    return rec

def all_outcomes():
    return list(_OUTCOMES)
