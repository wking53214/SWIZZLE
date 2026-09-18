# Swizzle-Ghost Tools Integration Guide

This document describes the six integration bridges that enable bidirectional information flow between Swizzle and Ghost Tools.

## Overview

Swizzle and Ghost Tools are complementary systems:
- **Swizzle** is an adversarial evaluation framework that tests Ghost Tools by constructing edge cases and verifying behavior
- **Ghost Tools** is a scanning and healing tool for repositories

Previously, this relationship was one-way: Swizzle tested Ghost, but the results and insights didn't feed back.

These integrations enable:
1. Swizzle findings → Ghost learning
2. Ghost decisions → Swizzle oracle training
3. Shared constraints and invariants
4. Bidirectional mutation testing
5. Performance regression detection
6. Cross-tool architecture validation

## The Six Integration Bridges

### 1. Shared Invariant Model (`invariant_model.py`)

**Purpose**: Unified specification of constraints both tools must enforce.

**What it solves**: Neither tool previously exposed its "rules of the game". Now both can:
- Declare what invariants they enforce
- Learn invariants discovered by the other
- Validate changes against shared rules

**Key concepts**:
- `Invariant`: A constraint the system must maintain (e.g., "writes never escape repo")
- `InvariantScope`: Where it applies (repository, branch, file, content)
- `InvariantViolation`: Evidence the invariant was broken
- `InvariantLibrary`: Registry of known invariants

**Example**:
```python
inv = Invariant(
    id="no_write_outside_boundary",
    name="No writes outside repository boundary",
    applies_to=["ghost_tools", "swizzle"],
    severity=InvariantSeverity.CRITICAL,
)
```

**Files exported for consumption**:
- `invariants.json`: All registered invariants

---

### 2. Triage Ledger Exchange (`triage_ledger.py`)

**Purpose**: Ghost's triage decisions become Swizzle's oracle training data (and vice versa).

**What it solves**: 
- Ghost makes human decisions about whether findings are real (true), false positives, or deferred
- Swizzle's oracles need calibration data
- These datasets can train each other

**Key concepts**:
- `Decision`: Human judgment (true, false, deferred, suppressed)
- `TriageEntry`: One triage decision with reasoning
- `TriageLedger`: History of decisions that both tools learn from

**Data flows**:
- Ghost's casefile → Swizzle oracle training (via `export_for_swizzle_oracle_training()`)
- Swizzle findings → Ghost casefile (via `export_for_ghost_casefile()`)

**Example**:
```python
entry = TriageEntry(
    id="case_123",
    finding_type="dated_claim",
    decision=Decision.FALSE,
    reasoning="README explicitly marked as historical",
)
```

**Files exported**:
- `triage-ledger.json`: Complete ledger
- `triage-training-data.json`: Swizzle oracle training format
- Ghost casefile format (for Ghost consumption)

---

### 3. Mutation Transfer (`mutation_transfer.py`)

**Purpose**: Swizzle's minimized adversarial cases become Ghost's mutation test seeds.

**What it solves**:
- Swizzle spends effort minimizing reproduction cases
- Ghost has a mutation testing system
- These cases are valuable test material for both

**Key concepts**:
- `MutationCase`: A single test case (repository mutations + expected outcome)
- `MutationCatalog`: Shared test case library
- Cases can flow between tools in both directions

**Data flows**:
- Swizzle's minimized cases → Ghost mutation suite
- Ghost's mutations → Swizzle corpus (bidirectional)

**Example**:
```python
case = MutationCase(
    id="symlink_escape",
    hypothesis="tool fails on symlinks escaping repo",
    repository_mutations={"README.md": "...", ".link": "symlink"},
    expected_outcome="write must stay within repo",
)
```

**Files exported**:
- `mutations.json`: All cases in shared format
- Swizzle genome format (via `export_for_swizzle()`)
- Ghost mutation suite format (via `export_for_ghost_mutation_suite()`)

---

### 4. Performance Regression Detection (`performance_contract.py`)

**Purpose**: Establish and verify performance contracts between runs.

**What it solves**:
- Swizzle runs at scale but doesn't track performance
- Ghost could regress in performance without notice
- Need an explicit contract to detect regressions

**Key concepts**:
- `PerformanceContract`: A guarantee (e.g., "scan < 100ms per file")
- `PerformanceMetric`: One measurement
- `PerformanceRun`: Test results with metrics
- Contracts have thresholds and percentiles

**Data flows**:
- Swizzle timing data → Performance report
- Ghost verifies against contracts
- Regressions detected via `detect_regressions()`

**Example**:
```python
contract = PerformanceContract(
    id="ghost_scan_per_file",
    description="scan completes in < 100ms per file",
    threshold_value=0.1,
    threshold_unit="seconds_per_file",
)
```

**Files exported**:
- `performance.json`: Contracts, runs, and regression analysis

---

### 5. Architecture Audit Bridge (`architecture_audit.py`)

**Purpose**: Cross-tool architecture validation.

**What it solves**:
- Each tool has architecture rules (boundaries, allowed imports)
- Swizzle tests for architecture violations in Ghost
- Ghost's boundary enforcement can validate Swizzle
- Changes need to pass both tools' architecture checks

**Key concepts**:
- `ArchitectureBoundary`: A logical module boundary
- `ArchitectureViolation`: Evidence of violation
- `ArchitectureAudit`: Rules for one tool
- Compliance checking across tools

**Data flows**:
- Swizzle finds Ghost architecture issues → reported in audit
- Ghost validates Swizzle adapter contracts
- Both tools maintain their own audits

**Example**:
```python
boundary = ArchitectureBoundary(
    id="oracle_independence",
    name="Lab oracle independence",
    owns_modules=["swizzle.lab.oracles"],
    cannot_import_from=["swizzle.lab.sandbox"],
)
```

**Files exported**:
- `swizzle-architecture.json`: Swizzle rules and violations
- `ghost-architecture.json`: Ghost rules and violations

---

### 6. False Positive Feedback Loop (`feedback_loop.py`)

**Purpose**: False positives train both tools to filter better.

**What it solves**:
- Ghost produces false positives
- Swizzle has verified false positives
- Both can learn patterns to filter
- Oracles improve with feedback

**Key concepts**:
- `FindingType`: Category of finding (prose_deleted, dated_claim, etc.)
- `FalsePositivePattern`: A pattern that predicts false positives
- `OracleTrainingDatapoint`: Ground truth for oracle training
- `FeedbackReport`: Training data and filter improvements

**Data flows**:
- Ghost: confirmed false → Swizzle oracle training data
- Swizzle: verified false → Ghost filter patterns
- Patterns improve over time with examples

**Example**:
```python
pattern = FalsePositivePattern(
    id="dated_readme_false_positive",
    finding_type=FindingType.DATED_CLAIM,
    description="README with 'generated on DATE' is historical",
    confidence=0.95,
)
```

**Files exported**:
- `feedback.json`: Patterns and training data
- `oracle-training-data.json`: Swizzle oracle format
- `feedback-patterns.json`: Ghost filter format

---

## Using the Integrations

### For Swizzle

```python
from swizzle.integration.orchestrator import IntegrationOrchestrator

# Set up orchestrator
orch = IntegrationOrchestrator(Path("/tmp/swizzle-integration"))

# Import Ghost's triage decisions
orch.import_ghost_casefile(Path("/tmp/ghost_tools/.ghost_casefile.json"))

# Export everything for Ghost
orch.publish_ghost_integration_bundle(Path("/tmp/ghost_tools/.swizzle-integration"))

# Export oracle training data
orch.publish_swizzle_integration_bundle(Path("/tmp/swizzle/.ghost-integration"))

# Report
print(orch.generate_integration_report())
```

### For Ghost Tools

```python
from ghost_tools_integration.consumer import SwizzleIntegrationConsumer, IntegrationConfig

# Set up consumer
config = IntegrationConfig(
    swizzle_bundle_dir=Path(".swizzle-integration"),
    enabled_integrations=["all"],
)
consumer = SwizzleIntegrationConsumer(config)

# Filter false positives
findings = ghost_buster.scan(repo_path)
findings = consumer.filter_false_positives(findings)

# Validate invariants
violations = consumer.validate_invariants(findings)

# Check performance
if not consumer.check_performance_contract("wall_time", elapsed_seconds):
    print("Performance regression detected!")

# Get triage priors
priors = consumer.apply_triage_priors("dated_claim")
```

### Orchestrator Interface

The `IntegrationOrchestrator` coordinates all bridges:

```python
from swizzle.integration.orchestrator import IntegrationOrchestrator

orch = IntegrationOrchestrator(workspace)

# Export all integration data
orch.export_all()

# Generate bundles for each tool
ghost_bundle = orch.generate_ghost_integration_bundle()
swizzle_bundle = orch.generate_swizzle_integration_bundle()

# Publish to directories
orch.publish_ghost_integration_bundle(ghost_dir)
orch.publish_swizzle_integration_bundle(swizzle_dir)
```

---

## Data Flow Diagram

```
Swizzle                          Shared Models                      Ghost Tools
─────────────────────────────────────────────────────────────────────────────

Oracle Training ←──────── Triage Ledger ──────────→ Triage Decisions
        ↓                                                    ↑
Oracle Confidence                                    Ghost Case File
        
Attack Cases ←──────── Mutation Transfer ──────────→ Mutation Testing
        
Minimal Cases                  (bidirectional)         Test Seeds


Timing Data ←──────── Performance Contract ──────────→ Regression Detection
        ↓                                                    ↑
                    Check against thresholds
        
Architecture Rules ←──────── Invariant Model ──────────→ Validate Changes
        
        ↓                                                    ↑
Oracle Violations                                   Boundary Violations


                  ┌─────────────────────┐
                  │ Architecture Audit  │
                  │   - Boundaries      │
                  │   - Violations      │
                  │   - Compliance      │
                  └─────────────────────┘
                              ↑
                  ┌───────────┴───────────┐
                  │                       │
            Swizzle                   Ghost Tools
            Adapter                   Imports
            Contract


False Positives ←──────── Feedback Loop ──────────→ Filter Patterns
        ↓                                                    ↑
Verified FP                                           Ghost False FP
        
        └─→ Oracle Training Improvements ←─┘
        └─→ Filter Effectiveness Analysis ←─┘
```

---

## Version and Compatibility

- **Integration Version**: 1.0
- **Requires**: Swizzle v0.4.0+, Ghost Tools v1.5.0+
- **Shared Model Version**: 1.0

All models use JSON for language-agnostic exchange.

---

## Next Steps

1. Run the orchestrator to generate initial bundles
2. Import bundles in both tools
3. Run Swizzle against Ghost to populate performance/architecture data
4. Collect triage decisions from Ghost operations
5. Refine filters and oracle models as data accumulates
6. Monitor false positive rate improvements
7. Track performance regressions as both tools evolve
