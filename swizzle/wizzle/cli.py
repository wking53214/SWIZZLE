"""WIZZLE command-line interface."""

import sys
import json
from pathlib import Path
from .evaluator import Evaluator
from .epistemic_model import IntentKind, SemanticTruth, GhostObservation

def cmd_inspect(repo_path: str):
    """Inspect a repository."""
    repo = Path(repo_path)
    evaluator = Evaluator(repo)
    results = evaluator.run_oracles()
    
    print("=== Repository Inspection ===\n")
    print("Current State Oracle Results:")
    current = results["current_state"]
    print(f"  Files: {current.get('files', [])}")
    print(f"  Production members: {current.get('members_in_production', [])}")
    print(f"  Test members: {current.get('members_in_tests', [])}")
    print(f"  Both: {current.get('members_in_both', [])}")
    
    print("\nHistory Oracle Results:")
    history = results["history"]
    print(f"  Inferred intent: {history.get('inferred_intent')}")
    print(f"  Confidence: {history.get('confidence'):.2f}")
    print(f"  Evidence: {json.dumps(history.get('evidence'), indent=4)}")

def cmd_run():
    """Run all experiments."""
    print("=== Running All Experiments ===\n")
    print("Phase 2: Experiment runner (not yet implemented)")
    print("This will:")
    print("  1. Generate test repositories")
    print("  2. Run Ghost on each")
    print("  3. Evaluate results with oracles")
    print("  4. Produce machine-readable results")

def cmd_corpus():
    """List corpus cases."""
    corpus_dir = Path(__file__).parent.parent / "corpus"
    if corpus_dir.exists():
        cases = list(corpus_dir.glob("*/"))
        print(f"Found {len(cases)} corpus cases")
        for case in sorted(cases):
            print(f"  - {case.name}")
    else:
        print("No corpus directory yet")

def print_help():
    """Print help message."""
    print("WIZZLE: Epistemic Adversary for Autonomous Modifiers")
    print("\nUse `python -m swizzle verify ...` for integrated verification.")
    print("\nCommands:")
    print("  inspect <repo>  - Analyze a repository with oracles")
    print("  run            - Run all experiments")
    print("  corpus         - List corpus cases")
    print("  help           - Show this message")

def main(argv=None):
    """Main CLI entry point."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 1:
        print_help()
        return 1

    cmd = args[0]

    if cmd == "inspect" and len(args) > 1:
        cmd_inspect(args[1])
    elif cmd == "run":
        cmd_run()
    elif cmd == "corpus":
        cmd_corpus()
    elif cmd == "help":
        print_help()
    else:
        print(f"Unknown command: {cmd}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
