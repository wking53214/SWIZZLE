#!/usr/bin/env python3
"""Build complete PHANTOM and MEDIUM scenario repositories.

This script generates full git histories for adversarial test cases,
demonstrating where Ghost's conclusions exceed what evidence justifies.
"""

import sys
import subprocess
from pathlib import Path
from swizzle.wizzle.history_generator import (
    HistoryGenerator,
    PhantomScenario,
    AccidentalRemovalScenario,
    MediumPriorityScenario,
    SecurityFixScenario,
    DeadCodeCleanupScenario,
    APIDeprecationScenario,
    RevertScenario,
    BranchDivergenceScenario,
    TestOnlyMigrationScenario,
    PartialReplacementScenario,
    CherryPickScenario,
    MultipleRemovalScenario
)

def build_scenario(scenario_class, output_dir: Path) -> Path:
    """Generate a complete scenario repository."""
    scenario_name, specs = scenario_class.create_world(None)
    repo_path = output_dir / scenario_name

    print(f"\n=== Building {scenario_name} ===")
    print(f"Target: {repo_path}")

    # Clean if exists
    if repo_path.exists():
        subprocess.run(f"rm -rf {repo_path}", shell=True, check=True)

    # Initialize generator and build
    gen = HistoryGenerator(repo_path, seed=42)
    gen.init_repo()
    commits = gen.create_commits(specs)

    print(f"Created {len(commits)} commits:")
    for i, commit in enumerate(commits, 1):
        print(f"  {i}. {commit[:8]}")

    # Show final state
    log_output = subprocess.run(
        f"cd {repo_path} && git log --oneline",
        shell=True,
        capture_output=True,
        text=True
    ).stdout
    print(f"\nFinal git log:")
    for line in log_output.strip().split('\n'):
        print(f"  {line}")

    # Show file structure
    print(f"\nFinal repository structure:")
    for py_file in repo_path.glob("*.py"):
        print(f"  - {py_file.name}")

    return repo_path

def main():
    """Generate all scenario repositories."""
    corpus_dir = Path(__file__).parent / "corpus"
    corpus_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("WIZZLE Scenario Builder - Extended Corpus")
    print("=" * 60)

    # Define all scenarios to build
    scenarios = [
        (PhantomScenario, "PHANTOM scenario (intentional removal)"),
        (AccidentalRemovalScenario, "Accidental removal scenario (contrastive pair)"),
        (MediumPriorityScenario, "MEDIUM priority scenario"),
        (SecurityFixScenario, "Security fix removal scenario"),
        (DeadCodeCleanupScenario, "Dead code cleanup scenario"),
        (APIDeprecationScenario, "API deprecation scenario"),
        (RevertScenario, "Revert scenario"),
        (BranchDivergenceScenario, "Branch divergence scenario"),
        (TestOnlyMigrationScenario, "Test-only migration scenario"),
        (PartialReplacementScenario, "Partial replacement scenario"),
        (CherryPickScenario, "Cherry-pick removal scenario"),
        (MultipleRemovalScenario, "Multiple removal scenario"),
    ]

    repos = []
    for scenario_class, description in scenarios:
        print(f"\n>>> Building: {description}")
        repo = build_scenario(scenario_class, corpus_dir)
        repos.append(repo)

    print("\n" + "=" * 60)
    print(f"SUCCESS: Built {len(repos)} scenario repositories")
    print("=" * 60)
    print(f"\nGenerated corpus:")
    for i, repo in enumerate(repos, 1):
        print(f"  {i}. {repo.name}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
