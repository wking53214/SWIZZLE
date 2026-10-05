"""Oracle hierarchy — every oracle declares dependency basis."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

class OracleBasis(str, Enum):
    TARGET_REPORTED = "TARGET_REPORTED"
    HARNESS_OBSERVED = "HARNESS_OBSERVED"
    RECONSTRUCTED = "RECONSTRUCTED"
    REFERENCE_COMPARISON = "REFERENCE_COMPARISON"
    DIFFERENTIAL = "DIFFERENTIAL"
    ADVERSARIAL = "ADVERSARIAL"

@dataclass
class OracleDeclaration:
    oracle_id: str
    name: str
    basis: OracleBasis
    description: str
    depends_on_target: bool
    depends_on_adapter: bool
    independent_of_target: bool
    independent_of_adapter: bool
    def __post_init__(self):
        if self.basis == OracleBasis.TARGET_REPORTED and self.independent_of_target:
            raise ValueError(f"{self.oracle_id}: TARGET_REPORTED cannot claim independence from target")
        if self.independent_of_target and self.depends_on_target:
            raise ValueError(f"{self.oracle_id}: contradictory independence claims")

class OracleRegistry:
    def __init__(self):
        self._oracles: Dict[str, OracleDeclaration] = {}
    def register(self, decl: OracleDeclaration):
        self._oracles[decl.oracle_id] = decl
    def get(self, oracle_id):
        return self._oracles.get(oracle_id)
    def list_independent(self):
        return [o for o in self._oracles.values() if o.independent_of_target and o.independent_of_adapter]
    def list_by_basis(self, basis: OracleBasis):
        return [o for o in self._oracles.values() if o.basis == basis]
