"""CNS attack catalogue for docking-boundary evaluation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

CNS_ATTACK_CLASSES = [
    "authority_spoofing", "authority_omission", "authority_substitution",
    "scope_expansion", "scope_truncation", "delegation_laundering",
    "provenance_loss", "unknown_laundering", "adapter_bypass",
    "direct_cns_access", "multiple_cns_seams", "stale_cns_contract",
    "replay", "mutation_after_authorization", "baseline_drift",
    "fail_open_behavior", "fail_closed_bypass", "identity_confusion",
    "serialization_ambiguity", "canonicalization_mismatch",
    "private_interface_leakage", "error_path_bypass", "emergency_path_bypass",
]

@dataclass
class CNSAttackCase:
    attack_class: str
    description: str
    expected_detection: str
    severity: str = "high"

class CNSAttackCatalogue:
    DEFAULT_CASES = [
        CNSAttackCase("authority_spoofing", "Inject forged authority via adapter", "reject / fail closed"),
        CNSAttackCase("authority_omission", "Strip authority from governed action", "reject / fail closed"),
        CNSAttackCase("scope_expansion", "Widen delegated scope beyond authorization", "reject"),
        CNSAttackCase("unknown_laundering", "Convert UNKNOWN into approval", "reject"),
        CNSAttackCase("adapter_bypass", "Reach CNS without adapter", "detect dual path"),
        CNSAttackCase("multiple_cns_seams", "Second communication path to CNS", "detect / fail"),
        CNSAttackCase("baseline_drift", "Transform against drifted baseline", "refuse"),
        CNSAttackCase("fail_open_behavior", "Treat ambiguity as allow", "must fail closed"),
        CNSAttackCase("emergency_path_bypass", "Emergency override without constraints", "reject"),
    ]
    def __init__(self, cases=None):
        self.cases = cases or list(self.DEFAULT_CASES)
    def by_class(self, attack_class):
        return [c for c in self.cases if c.attack_class == attack_class]
    def all_classes(self):
        return sorted({c.attack_class for c in self.cases})
