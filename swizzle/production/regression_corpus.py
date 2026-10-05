"""Regression corpus from confirmed adversarial failures."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

@dataclass
class RegressionCase:
    case_id: str
    attack_class: str
    evidence_summary: str
    specimen_ref: Optional[str]
    result: str
    human_rejected: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

class RegressionCorpus:
    def __init__(self, path=None):
        self.path = path
        self.cases = []
        if path and Path(path).exists():
            self.load(Path(path))
    def add_from_failure(self, case_id, attack_class, evidence_summary, specimen_ref=None, metadata=None):
        case = RegressionCase(case_id, attack_class, evidence_summary, specimen_ref, "FAILED", metadata=metadata or {})
        self.cases.append(case)
        return case
    def reject(self, case_id):
        for c in self.cases:
            if c.case_id == case_id:
                c.human_rejected = True
                return
    def active_cases(self):
        return [c for c in self.cases if not c.human_rejected]
    def save(self, path=None):
        p = path or self.path
        data = [c.__dict__ for c in self.cases]
        Path(p).write_text(json.dumps(data, indent=2), encoding="utf-8")
    def load(self, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.cases = [RegressionCase(**d) for d in data]
        self.path = path
