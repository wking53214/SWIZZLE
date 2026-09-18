"""Mutation case transfer between Swizzle and Ghost Tools.

Swizzle's minimized adversarial cases can seed Ghost's mutation test suite.
Ghost's mutation model can produce new cases for Swizzle to attack.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
import json


@dataclass
class MutationCase:
    """A single mutation case that either tool can execute."""
    id: str  # unique identifier
    hypothesis: str  # what this tests (e.g., "tool fails on symlinks escaping repo")
    repository_mutations: Dict[str, str]  # file_path -> content mutations
    expected_outcome: str  # what the tool should or shouldn't do
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW

    # Execution constraints
    requires_git: bool = True
    requires_test_suite: bool = False
    test_command: Optional[str] = None
    timeout_seconds: int = 300

    # Source information
    discovered_by: str = ""  # "swizzle" or "ghost_tools"
    discovered_when: str = ""  # ISO 8601
    minimized: bool = False  # has this been reduced to minimal reproduction?

    # Related data
    related_issues: List[str] = field(default_factory=list)
    related_findings: List[str] = field(default_factory=list)


@dataclass
class MutationCatalog:
    """Shared mutation test cases."""
    cases: Dict[str, MutationCase] = field(default_factory=dict)
    version: str = "1.0"

    def add_case(self, case: MutationCase) -> None:
        """Register a mutation case."""
        self.cases[case.id] = case

    def cases_by_severity(self) -> Dict[str, List[MutationCase]]:
        """Group cases by severity."""
        by_severity = {}
        for case in self.cases.values():
            if case.severity not in by_severity:
                by_severity[case.severity] = []
            by_severity[case.severity].append(case)
        return by_severity

    def export_for_swizzle(self) -> str:
        """Export as Swizzle repository genomes."""
        genomes = {}
        for case_id, case in self.cases.items():
            genomes[case_id] = {
                "id": case.id,
                "hypothesis": case.hypothesis,
                "mutations": case.repository_mutations,
                "expected_outcome": case.expected_outcome,
                "severity": case.severity,
                "discovered_by": case.discovered_by,
                "minimized": case.minimized,
                "related_issues": case.related_issues,
            }
        return json.dumps(genomes, indent=2)

    def export_for_ghost_mutation_suite(self) -> str:
        """Export as Ghost mutation test cases."""
        mutations = {}
        for case_id, case in self.cases.items():
            # Ghost's mutation model: what files to mutate and how
            mutations[case_id] = {
                "id": case.id,
                "hypothesis": case.hypothesis,
                "mutations": case.repository_mutations,
                "test_command": case.test_command,
                "should_fail": "failure" in case.expected_outcome.lower(),
                "requires_test_suite": case.requires_test_suite,
                "related_issues": case.related_issues,
            }
        return json.dumps(mutations, indent=2)

    def to_json(self) -> str:
        """Export complete catalog."""
        data = {
            "version": self.version,
            "cases": {
                cid: {
                    "id": c.id,
                    "hypothesis": c.hypothesis,
                    "mutations": c.repository_mutations,
                    "expected_outcome": c.expected_outcome,
                    "severity": c.severity,
                    "requires_git": c.requires_git,
                    "requires_test_suite": c.requires_test_suite,
                    "test_command": c.test_command,
                    "discovered_by": c.discovered_by,
                    "discovered_when": c.discovered_when,
                    "minimized": c.minimized,
                    "related_issues": c.related_issues,
                }
                for cid, c in self.cases.items()
            }
        }
        return json.dumps(data, indent=2)

    def save(self, path: Path) -> None:
        """Write to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())


# Seed the catalog with cases from known Swizzle discoveries
DEFAULT_MUTATION_CATALOG = MutationCatalog(version="1.0")

DEFAULT_MUTATION_CATALOG.add_case(MutationCase(
    id="symlink_escape_boundary",
    hypothesis="symlink in target path allows write outside repository",
    repository_mutations={
        "README.md": "<!-- ghost_buster:test-count -->\n5\n<!-- /ghost_buster:test-count -->",
        ".symlink_escape": "symlink to /tmp/evil",
    },
    expected_outcome="write should fail or be contained within repository",
    severity="CRITICAL",
    discovered_by="swizzle",
    minimized=True,
    related_issues=["swizzle#1"],
))

DEFAULT_MUTATION_CATALOG.add_case(MutationCase(
    id="prose_inside_maintained_block",
    hypothesis="prose inside opt-in block is deleted during rewrite",
    repository_mutations={
        "README.md": "# Title\n\n<!-- ghost_buster:test-count -->\nAuthor wrote this sentence here.\n5\n<!-- /ghost_buster:test-count -->\n\n# Footer",
    },
    expected_outcome="author prose inside block must not be deleted",
    severity="CRITICAL",
    discovered_by="swizzle",
    minimized=True,
    related_issues=["swizzle#1"],
))

DEFAULT_MUTATION_CATALOG.add_case(MutationCase(
    id="dated_claim_not_rewritten",
    hypothesis="tool correctly refuses to rewrite dated claims",
    repository_mutations={
        "README.md": "# Status\n\nAs of 2020, this project is maintained.\n\n*This README was generated on 2023-01-01*",
    },
    expected_outcome="tool should not rewrite dated claims",
    severity="MEDIUM",
    discovered_by="swizzle",
    minimized=True,
    requires_test_suite=True,
))
