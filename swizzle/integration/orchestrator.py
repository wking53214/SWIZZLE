"""Integration orchestrator for Swizzle and Ghost Tools.

Coordinates data flow between the two tools using the shared models.
"""

from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import json

from .invariant_model import DEFAULT_INVARIANTS
from .triage_ledger import TriageLedger
from .mutation_transfer import DEFAULT_MUTATION_CATALOG
from .performance_contract import DEFAULT_PERFORMANCE_REPORT
from .architecture_audit import SWIZZLE_AUDIT, GHOST_AUDIT
from .feedback_loop import DEFAULT_FEEDBACK_REPORT


class IntegrationOrchestrator:
    """Coordinates all integration bridges between Swizzle and Ghost Tools."""

    def __init__(self, workspace_dir: Path):
        self.workspace = workspace_dir
        self.workspace.mkdir(parents=True, exist_ok=True)

        # Load or initialize all shared models
        self.invariants = DEFAULT_INVARIANTS
        self.mutations = DEFAULT_MUTATION_CATALOG
        self.performance = DEFAULT_PERFORMANCE_REPORT
        self.swizzle_architecture = SWIZZLE_AUDIT
        self.ghost_architecture = GHOST_AUDIT
        self.feedback = DEFAULT_FEEDBACK_REPORT
        self.triage_ledger: Optional[TriageLedger] = None

    def export_all(self) -> None:
        """Export all integration data to disk."""
        self.invariants.save(self.workspace / "invariants.json")
        self.mutations.save(self.workspace / "mutations.json")
        self.performance.save(self.workspace / "performance.json")
        self.swizzle_architecture.save(self.workspace / "swizzle-architecture.json")
        self.ghost_architecture.save(self.workspace / "ghost-architecture.json")
        self.feedback.save(self.workspace / "feedback.json")
        if self.triage_ledger:
            self.triage_ledger.save(self.workspace / "triage-ledger.json")

    def import_ghost_casefile(self, casefile_path: Path) -> None:
        """Import Ghost's triage casefile as training data."""
        from .triage_ledger import import_ghost_casefile
        self.triage_ledger = import_ghost_casefile(casefile_path)
        self.triage_ledger.save(self.workspace / "triage-ledger-from-ghost.json")

    def generate_ghost_integration_bundle(self) -> Dict[str, str]:
        """Generate all data Ghost Tools should consume.

        Returns mapping of file_name -> json_content.
        """
        bundle = {
            "invariants.json": self.invariants.to_json(),
            "mutations.json": self.mutations.to_json(),
            "performance-contracts.json": self.performance.to_json(),
            "feedback-patterns.json": self.feedback.export_for_ghost_filter_update(),
            "architecture-rules.json": self.ghost_architecture.to_json(),
        }
        return bundle

    def generate_swizzle_integration_bundle(self) -> Dict[str, str]:
        """Generate all data Swizzle should consume.

        Returns mapping of file_name -> json_content.
        """
        bundle = {
            "invariants.json": self.invariants.to_json(),
            "mutations.json": self.mutations.to_json(),
            "performance-contracts.json": self.performance.to_json(),
            "oracle-training-data.json": self.feedback.export_for_swizzle_oracle_update(),
            "architecture-rules.json": self.swizzle_architecture.to_json(),
        }
        if self.triage_ledger:
            bundle["triage-training-data.json"] = self.triage_ledger.export_for_swizzle_oracle_training()
        return bundle

    def publish_ghost_integration_bundle(self, target_dir: Path) -> None:
        """Write Ghost integration bundle to target directory."""
        target_dir.mkdir(parents=True, exist_ok=True)
        bundle = self.generate_ghost_integration_bundle()
        for filename, content in bundle.items():
            (target_dir / filename).write_text(content)

    def publish_swizzle_integration_bundle(self, target_dir: Path) -> None:
        """Write Swizzle integration bundle to target directory."""
        target_dir.mkdir(parents=True, exist_ok=True)
        bundle = self.generate_swizzle_integration_bundle()
        for filename, content in bundle.items():
            (target_dir / filename).write_text(content)

    def generate_integration_report(self) -> str:
        """Generate a report of all integration capabilities."""
        report = {
            "title": "Swizzle-Ghost Tools Integration Report",
            "generated": datetime.now().isoformat(),
            "capabilities": {
                "invariant_model": {
                    "description": "Shared invariant schema for both tools",
                    "count": len(self.invariants.invariants),
                    "invariants": list(self.invariants.invariants.keys()),
                },
                "mutation_transfer": {
                    "description": "Adversarial cases shared as mutation tests",
                    "count": len(self.mutations.cases),
                    "cases": list(self.mutations.cases.keys()),
                },
                "triage_ledger": {
                    "description": "Triage decisions as shared learning data",
                    "entries": len(self.triage_ledger.entries) if self.triage_ledger else 0,
                },
                "performance_contracts": {
                    "description": "Performance regression detection",
                    "contracts": len(self.performance.contracts),
                    "contract_ids": list(self.performance.contracts.keys()),
                },
                "architecture_audit": {
                    "description": "Cross-tool architecture validation",
                    "swizzle_boundaries": len(self.swizzle_architecture.boundaries),
                    "ghost_boundaries": len(self.ghost_architecture.boundaries),
                },
                "feedback_loop": {
                    "description": "False positive and oracle training data",
                    "patterns": len(self.feedback.false_positive_patterns),
                    "training_datapoints": len(self.feedback.oracle_training_data),
                },
            },
            "files_generated": [
                "invariants.json",
                "mutations.json",
                "performance.json",
                "swizzle-architecture.json",
                "ghost-architecture.json",
                "feedback.json",
                "triage-ledger.json" if self.triage_ledger else None,
            ],
        }
        return json.dumps(report, indent=2)
