# WIZZLE Phase 3 — Baseline State Documentation

**Date**: 2026-09-12  
**Branch**: claude/ghost-tools-clone-j3frq0  
**Latest Commit**: 61a9fdf (Add session completion summary)  

## Current Implementation State

### Architecture Present ✓

**Epistemic Model** (wizzle/epistemic_model.py)
- ✓ EvidenceProvenance enum (7 categories)
- ✓ FactualCorrectness enum (4 states)
- ✓ SemanticCorrectness enum (6 states)
- ✓ IntentKind enum (16 categories)
- ✓ EvidenceStrength enum (6 categories)
- ✓ ObservedFact, InterpretationHypothesis, SemanticTruth dataclasses
- ✓ GhostObservation dataclass
- ✓ EvidenceEntitlement dataclass
- ✓ ExperimentResult dataclass

**Oracle Architecture** (wizzle/oracles.py)
- ✓ HistoryOracle: Analyzes commit messages for intent signals
- ✓ CurrentStateOracle: Scans repository structure
- ✓ SemanticIntegrityOracle: Cross-validates history vs state
- All oracles declared independent (no Ghost access)

**Ghost Integration** (wizzle/ghost_invoker.py)
- ✓ GhostFinding dataclass
- ✓ GhostAnalysis dataclass
- ✓ GhostInvoker class with:
  - ✓ _find_ghost() - finds Ghost in PATH
  - ✓ invoke() - runs Ghost with timeout and error handling
  - ✓ _parse_findings() - parses JSON output
  - ✓ compare_with_oracle() - basic Ghost-Oracle comparison
  - ✓ _assess_finding() - placeholder for semantic assessment

**Evaluator** (wizzle/evaluator.py)
- ✓ run_oracles() - orchestrates oracle execution
- ✓ evaluate_ghost_conclusion() - compares Ghost output vs semantic truth
- ✓ Basic factual correctness assessment
- ✓ Basic semantic correctness assessment (OVERCLAIMED for INTENTIONAL_REFACTOR + MAJOR)

**Scenario Generation** (wizzle/history_generator.py)
- ✓ HistoryGenerator class with deterministic git manipulation
- ✓ PhantomScenario: Intentional removal (7 commits + tests)
- ✓ AccidentalRemovalScenario: Contrastive pair (4 commits)
- ✓ MediumPriorityScenario: API simplification (6 commits + tests)

**CLI** (wizzle/cli.py)
- ✓ python -m wizzle inspect <repo>
- ✓ python -m wizzle run (stub)
- ✓ python -m wizzle corpus (lists scenarios)
- ✓ python -m wizzle help

**Scripts**
- ✓ build_scenarios.py: Generates corpus repositories deterministically
- ✓ evaluate_scenarios.py: Runs oracle analysis on corpus
- ✓ reconstruct_history.py: Documentation of historical reconstruction

### Test Coverage

**Current**: 20 passing tests
- ✓ test_epistemic_model.py: 7 tests (model types, independence, provenance)
- ✓ test_ghost_invoker.py: 11 tests (JSON parsing, timeout handling, comparison)
- ✓ test_oracles.py: 3 tests (oracle functionality, independence, no side effects)

### Corpus State

**Generated Scenarios**:
1. phantom_intentional_refactor/ - 7 commits, full git history
2. phantom_accidental_removal/ - 4 commits, contrastive pair
3. medium_priority_intentional_removal/ - 6 commits, API change case

Each scenario:
- ✓ Has complete git history with commit messages
- ✓ Contains enums.py with members
- ✓ Contains library.py with production code
- ✓ Contains test files referencing removed members
- ✓ Renders as executable repository

### NOT YET IMPLEMENTED

**Critical Missing Pieces**:
- ❌ Real Ghost invocation (GhostInvoker has framework but cannot actually run Ghost)
- ❌ Evidence entitlement evaluator (placeholder exists, needs full implementation)
- ❌ Overclaim/underclaim detection (basic case in evaluate_ghost_conclusion, needs formalization)
- ❌ Contradiction detection (not implemented)
- ❌ Inconclusive case handling (not implemented)
- ❌ Contrastive pair evaluation (framework exists, needs execution)
- ❌ Minimization engine (not started)
- ❌ Replay system (not started)
- ❌ Holdout mechanism (not started)
- ❌ Frozen corpus versioning (not started)
- ❌ Machine-readable result schema (skeleton in ExperimentResult, needs completion)
- ❌ Extended attack corpus (only 3 scenarios, need ~15+ for real evaluation)
- ❌ Semantic migration scenarios (not in corpus)
- ❌ Branch divergence scenarios (not in corpus)
- ❌ Revert/squash scenarios (not in corpus)
- ❌ Test-only resurrection patterns (basic case present, needs variants)

**Oracle Enhancements Needed**:
- ❌ IntentOracle (dedicated intent analysis)
- ❌ SeverityOracle (independent severity assessment)
- ❌ EvidenceEntitlementOracle (explicit entitlement rules)
- ❌ ContrastiveOracle (pair-wise comparison)
- ❌ TopologyOracle (branch/revert/split analysis)
- ❌ ReplacementOracle (equivalence detection)

**Provenance Tracking Needs**:
- ❌ Explicit provenance on all important fields
- ❌ CONSTRUCTED vs OBSERVED vs DERIVED tracking
- ❌ TARGET_REPORTED separate from ground truth
- ❌ UNASKABLE state management

**Evidence Analysis Needs**:
- ❌ "What would change my mind?" fields
- ❌ Supporting evidence lists
- ❌ Missing evidence detection
- ❌ Disconfirming evidence tracking
- ❌ Evidence necessity vs sufficiency matrices

### Verified Baseline Behavior

**Test Suite**: 20/20 passing
```
$ python3 -m pytest wizzle/ -v
PASSED: epistemic_model (7 tests)
PASSED: ghost_invoker (11 tests)
PASSED: oracles (3 tests)
```

**Scenario Generation**: Working
```
$ python3 build_scenarios.py
Creates: phantom_intentional_refactor (7 commits)
Creates: phantom_accidental_removal (4 commits)
Creates: medium_priority_intentional_removal (6 commits)
```

**Scenario Evaluation**: Working
```
$ python3 evaluate_scenarios.py
Runs oracles on all corpus scenarios
Produces oracle assessment results
```

**CLI**: Working
```
$ python3 -m wizzle help
Lists 4 commands (inspect, run, corpus, help)

$ python3 -m wizzle inspect corpus/phantom_intentional_refactor
Shows oracle results for scenario
```

**Oracle Independence**: Verified
- HistoryOracle: Reads only git history, no Ghost access
- CurrentStateOracle: Reads only files/structure, no Ghost access
- SemanticIntegrityOracle: Combines observations, no Ghost access
- No oracle calls Ghost or reads ground-truth labels

### Key Architectural Decisions Already Made

1. **Independent Oracles**: Each oracle operates on separate evidence dimension
2. **Provenance Tracking**: EvidenceProvenance enum used throughout
3. **Separation of Concerns**: 
   - Factual correctness (did Ghost see the right facts?)
   - Semantic correctness (is conclusion justified?)
   - These are tracked as independent dimensions
4. **Weak Intent Signals**: Commit messages treated as suggestive, not authoritative
5. **Contrastive Pairs**: AccidentalRemovalScenario as paired world for testing

### Configuration & Environment

**Python**: 3.11.15
**Pytest**: 9.1.1
**Git**: Available in environment
**Ghost**: NOT currently available in environment (would need to be installed)

**Directory Structure**:
```
wizzle/
├── epistemic_model.py       # Type system
├── oracles.py               # Oracle implementations
├── evaluator.py             # Orchestration
├── ghost_invoker.py         # Ghost integration
├── cli.py                   # CLI interface
├── history_generator.py     # Scenario generation
├── __main__.py              # Module entry
├── test_*.py                # Tests (20 total)

build_scenarios.py           # Generate corpus
evaluate_scenarios.py        # Evaluate corpus
corpus/                      # Generated scenarios
├── phantom_intentional_refactor/
├── phantom_accidental_removal/
├── medium_priority_intentional_removal/
```

### What Works, What Doesn't

**Works**:
- ✓ Test suite execution
- ✓ Deterministic scenario generation
- ✓ Oracle analysis of repositories
- ✓ Basic CLI commands
- ✓ GhostFinding parsing (with mocked Ghost)
- ✓ Epistemic model type system
- ✓ Oracle independence enforcement

**Doesn't Work Yet**:
- ❌ Real Ghost invocation (no Ghost binary)
- ❌ Full semantic verdict (incomplete evidence entitlement)
- ❌ Overclaim detection with real data (only placeholder logic)
- ❌ Minimization (not implemented)
- ❌ Replay mechanism (not implemented)
- ❌ Holdout corpus (not implemented)

**Unknown (not tested)**:
- ? What happens with ambiguous commit histories
- ? How well do oracles scale to large repositories
- ? Performance characteristics of evaluator
- ? Edge cases in contrastive pair evaluation

### Documentation Present

- ✓ README.md - Project overview
- ✓ COMPLETION_SUMMARY.md - Session 2 results
- ✓ PHASE_2_CONTINUATION.md - Session 2 roadmap
- ✓ STATUS.md - Metrics and phase tracking
- ✓ IMPLEMENTATION_PLAN.md - High-level design
- ✓ FORENSICS_SCENARIOS.md - Scenario documentation

### Next Phase Requirements (from Phase 3 mandate)

Must implement:
1. Real Ghost execution with real invocation
2. Evidence entitlement evaluator (formalized)
3. Overclaim/underclaim detection (complete)
4. Contradiction and inconclusive case handling
5. Contrastive pair execution and evaluation
6. Extended attack corpus (15+ scenarios)
7. Additional oracles (Intent, Severity, Entitlement, Topology)
8. Minimization engine
9. Replay system
10. Frozen holdout mechanism
11. Complete result schema with provenance
12. "What would change my mind?" metadata
13. Full test coverage for all new functionality

### Branch Information

- Current branch: claude/ghost-tools-clone-j3frq0
- Remote: origin/claude/ghost-tools-clone-j3frq0
- Tracking: origin/claude/ghost-tools-clone-j3frq0
- All commits pushed to remote

### Ready to Proceed

This baseline has been established. The Phase 3 implementation can now:
1. Extend existing architecture (oracles, evaluator, model)
2. Preserve working code (scenario generation, CLI, tests)
3. Add new functionality (real Ghost invocation, evidence entitlement, minimization)
4. Maintain backward compatibility

No breaking changes are required to move forward.
