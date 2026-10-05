"""Removal testing for proposed deletions/consolidations."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List

class RemovalProperty(str, Enum):
    BEHAVIOR_PRESERVATION = "behavior_preservation"
    PUBLIC_API_PRESERVATION = "public_api_preservation"
    HIDDEN_DEPENDENCY_PRESERVATION = "hidden_dependency_preservation"
    SIDE_EFFECT_PRESERVATION = "side_effect_preservation"
    SECURITY_PROPERTY_PRESERVATION = "security_property_preservation"
    PROVENANCE_PRESERVATION = "provenance_preservation"
    AUTHORIZATION_PRESERVATION = "authorization_preservation"
    CNS_BOUNDARY_PRESERVATION = "cns_boundary_preservation"

class PropertyResult(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_TESTED = "NOT_TESTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"

@dataclass
class RemovalTestResult:
    proposal_id: str
    property_results: Dict[str, str]
    overall: str
    differential_summary: str = ""
    adversarial_hits: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RemovalTest:
    proposal_id: str
    before_snapshot: Dict[str, Any]
    after_snapshot: Dict[str, Any]
    property_checks: Dict[RemovalProperty, Callable] = field(default_factory=dict)
    def run(self) -> RemovalTestResult:
        results = {}
        for prop in RemovalProperty:
            checker = self.property_checks.get(prop)
            if checker is None:
                results[prop.value] = PropertyResult.NOT_TESTED.value
            else:
                try:
                    results[prop.value] = checker(self.before_snapshot, self.after_snapshot).value
                except Exception:
                    results[prop.value] = PropertyResult.UNKNOWN.value
        failed = [k for k, v in results.items() if v == PropertyResult.FAILED.value]
        overall = "FAILED" if failed else ("PASSED" if any(v == PropertyResult.PASSED.value for v in results.values()) else "UNKNOWN")
        return RemovalTestResult(self.proposal_id, results, overall)
