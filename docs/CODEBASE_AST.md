# Swizzle Codebase AST

**Generated**: 2026-09-18  
**Total Python Files**: 107  
**Total Classes**: 258  
**Total Functions**: 358

## Overview

Swizzle is structured in layers:

1. **Lab** (`swizzle/lab/`) - Core adversarial testing framework
2. **Integration** (`swizzle/integration/`) - Cross-repository continuous improvement ecosystem
3. **Wizzle** (`swizzle/wizzle/`) - Governance, entitlement, and epistemic verification layer
4. **Adapters** (`swizzle/lab/adapters/`) - Target system integrations (Ghost Tools, Pydantic v2)

---

## Layer: LAB (Core Testing Framework)

The laboratory performs adversarial testing of autonomous modification systems.

### Core Abstractions

| Module | Purpose | Key Classes |
|--------|---------|-------------|
| `adapter.py` | Target system interface | `TargetAdapter`, `Observation` |
| `genome.py` | Attack specification | `MutationSpec`, `RepositoryGenome` |
| `draft.py` | World construction | `WorldDraft`, `TargetDialect` |
| `evidence.py` | Observed data | `Evidence` |
| `groundtruth.py` | Expected behavior | `GroundTruth` |
| `signals.py` | Oracle findings | `Signal`, `Severity`, `Judgement` |

### Execution Pipeline

| Module | Purpose | Key Functions |
|--------|---------|---|
| `attack.py` | Run one adversarial case | `run(case, adapter)` |
| `world.py` | Build test repository | `simple()`, `witness_for()` |
| `sandbox.py` | Isolated execution | `Sandbox`, `Completed` |

### Oracle Framework (Verification)

| Module | Classes | Purpose |
|--------|---------|---------|
| `oracles/library.py` | 19 oracles | Extensible oracle logic library (16 implementations + registry) |
| `oracles/expectation.py` | Oracle | Structural expectations |
| `oracles/identity.py` | Oracle | Memory/identity consistency |
| `oracles/scope.py` | Oracle | Boundary enforcement |
| `oracles/semantic.py` | Oracle | Semantic correctness |
| `oracles/structural.py` | Oracle | Syntax/structure |
| `oracles/temporal.py` | Oracle | Temporal consistency |
| `oracles/ledger.py` | Oracle | Ledger integrity |

### Improvement & Fitness

| Module | Purpose |
|--------|---------|
| `fitness.py` | Score test results by finding severity |
| `minimize.py` | Delta-debug cases to minimal failing examples |
| `knowledge.py` | Track accumulated findings across runs |
| `metrics.py` | Compute coverage and rates |

### Reporting & History

| Module | Purpose |
|--------|---------|
| `convergence.py` | Track iteration history and settling behavior |
| `corpus.py` | Store canonicalized findings |
| `history.py` | Case history and episode tracking |
| `differential.py` | Compare two runs' findings |
| `coverage.py` | Oracle exercise matrix |
| `standing.py` | Resolution and probe status |

### Adapters (Target Systems)

| Module | Adapter Class | Wraps |
|--------|---------------|-------|
| `adapters/ghost.py` | `GhostToolsAdapter` | Ghost Tools (code modification) |
| `adapters/pydantic_v2.py` | `PydanticV2MigratorAdapter` | Pydantic v2 auto-migration |

---

## Layer: INTEGRATION (Continuous Improvement Ecosystem)

Implements the closed-loop improvement cycle between Swizzle and Ghost Tools.

### Arbitration (Improvement Validation)

| Module | Key Classes | Purpose |
|--------|-------------|---------|
| `arbiter.py` | `Arbiter`, `ValidationVerdict`, `ValidationMetric` | Validate improvements via metrics |
| `loop_orchestrator.py` | `LoopOrchestrator`, `LoopState`, `LoopIteration` | Coordinate improvement cycles |

### Decision Making

| Module | Key Classes | Purpose |
|--------|-------------|---------|
| `decision_engine.py` | `DecisionEngine`, `AutomatedDecision`, `DecisionPolicy` | Autonomous decision making with ML confidence |
| `ml_predictor.py` | `MLPredictor`, `PredictionCache` | ML-based confidence scoring |
| `decision_handlers.py` | `DecisionHandlers` | Handle decision outcomes |

### Event System

| Module | Key Classes | Purpose |
|--------|-------------|---------|
| `event_system.py` | `EventBus`, `Event`, `EventType`, `EventSeverity` | Pub/sub event system |
| `event_handlers.py` | `EventHandler`, `EventHandlerRegistry` | Route events to handlers |
| `event_evaluator.py` | `EventEvaluator` | Evaluate event significance |
| `hooks.py` | `HookManager` | Git hook integration for event triggering |

### Feedback & Analytics

| Module | Purpose |
|--------|---------|
| `feedback_loop.py` | Collect false positives and oracle training data |
| `triage_ledger.py` | Track decisions and filter patterns |
| `trend_analyzer.py` | Detect confidence/approval trends and anomalies |
| `query_engine.py` | Query improvement statistics |
| `test_track.py` | Track experiments and metrics |

### Cross-Repository Coordination

| Module | Purpose |
|--------|---------|
| `cross_repo.py` | Index and sync findings across repos |
| `unified_index.py` | Central index of events and decisions |
| `orchestrator.py` | Orchestrate bidirectional sync |
| `mutation_transfer.py` | Export mutation cases |

### Compliance & Governance

| Module | Key Classes | Purpose |
|--------|-------------|---------|
| `architecture_audit.py` | `ArchitectureAudit`, `ArchitectureViolation` | Verify architectural boundaries |
| `invariant_model.py` | `InvariantLibrary`, `Invariant` | Track system invariants |
| `performance_contract.py` | `PerformanceContract`, `PerformanceReport` | Monitor performance |
| `cicd_integration.py` | `CIDDIntegrationEngine`, `PerformanceThresholdManager` | CI/CD gate integration |

---

## Layer: WIZZLE (Governance & Entitlement)

Epistemic verification that oracles are trustworthy and make justified claims.

### Epistemic Model

| Module | Key Classes | Purpose |
|--------|-------------|---------|
| `epistemic_model.py` | `EvidenceStrength`, `SemanticCorrectness`, `ExperimentResult` | Evidence layers and correctness |
| `evidence_entitlement.py` | `EvidenceEntitlementEvaluator` | Check evidence requirements |
| `action_entitlement.py` | `ActionEntitlementOracle` | Verify action authorization |

### Evaluation & Testing

| Module | Key Classes | Purpose |
|--------|-------------|---------|
| `evaluator.py` | `Evaluator`, `ContrastivePairGenerator` | Run oracles on cases |
| `contrastive_evaluation.py` | `ContrastiveEvaluator` | Compare oracle assessments |
| `experiment_record.py` | `ExperimentRecord`, `OracleAssessment` | Record results |

### Attack Scenarios

| Module | Purpose |
|--------|---------|
| `ghost_attacks.py` | 10 canonical attack types on Ghost Tools |
| `ghost_invoker.py` | Invoke Ghost and parse findings |
| `ghost_simulator.py` | Simulate Ghost behavior |
| `history_generator.py` | Generate realistic git histories + scenarios |
| `oracles.py` | History, Current-State, Semantic Integrity oracles |

### Tests

Comprehensive test suites validating:
- Epistemic independence (oracles can't be misled by false claims)
- Evidence entitlement (finding severity is justified)
- Action entitlement (decisions are authorized)
- Oracle independence (one oracle doesn't depend on another)
- Success cases (complex scenarios work end-to-end)

---

## Root Layer: CLI & Invocation

| Module | Purpose |
|--------|---------|
| `cli.py` | Command-line interface |
| `invoke.py` | Run targets and capture output |
| `schema.py` | Result schemas and verdict types |
| `verdict.py` | Render findings and judge results |
| `proving.py` | Prove properties of systems |
| `summon.py` | Locate and set up target systems |
| `run.py` | High-level orchestration |
| `report.py` | Generate reports |

---

## Dependency Graph Summary

```
Lab (Testing) 
  ├─ attack.py ─→ sandbox.py ─→ adapter.py (TargetAdapter)
  ├─ oracle framework ─→ signals.py
  ├─ corpus.py ─→ genome.py (MutationSpec, RepositoryGenome)
  └─ fitness.py ─→ knowledge.py

Integration (Continuous Improvement)
  ├─ loop_orchestrator.py ─→ arbiter.py
  ├─ decision_engine.py ─→ event_system.py
  ├─ ml_predictor.py (feedback loop)
  └─ trend_analyzer.py (analytics)

Wizzle (Governance)
  ├─ evaluator.py ─→ oracles
  ├─ epistemic_model.py (correctness layers)
  ├─ evidence_entitlement.py
  └─ ghost_attacks.py (test scenarios)

CLI & Invocation
  └─ cli.py ─→ run.py ─→ lab modules
```

---

## Key Design Patterns

### 1. Adapter Pattern
`TargetAdapter` is the boundary between Swizzle and target systems. Each target (Ghost, Pydantic, etc.) implements:
- `dialect()` - operational markers and memory files
- `version()` - reproduction info
- `scan()` - read-only mode
- `act()` - write mode
- `export_output()` - materialize results

### 2. Oracle Pattern
All oracles inherit from `OracleLogic` and implement:
- `judge(evidence: Evidence) → Sequence[Signal]` - pure function evaluation
- Metadata: name, category (invariant, behavior, performance, etc.), domain

16 oracle implementations across 7 categories + composable profiles.

### 3. Event-Driven Integration
`EventBus` pub/sub for decoupled communication:
- `IMPROVEMENT_PROPOSED` → `Arbiter.validate()` → `VERDICT_RENDERED`
- Events persist in `UnifiedIndex`
- `DecisionEngine` consumes and routes

### 4. Layered Verification
Evidence flows through epistemic layers:
1. Observation (facts about run)
2. Semantic (interpretation of facts)
3. Entitlement (justification for claims)

Wizzle verifies each layer is independent.

---

## Statistics

### Classes by Domain

| Domain | Count |
|--------|-------|
| Oracle implementations | 19 |
| Integration (events, decisions, sync) | 45+ |
| Governance (epistemic, entitlement) | 30+ |
| Lab core (genome, evidence, signals) | 60+ |
| Test fixtures | 40+ |

### Code Organization

- **Lab**: 35 modules, ~5000 LOC (core testing)
- **Integration**: 22 modules, ~3500 LOC (improvement ecosystem)
- **Wizzle**: 18 modules, ~4000 LOC (governance)
- **Tests**: 30+ test modules

---

## Entry Points

### For Testing
```python
from swizzle.lab.adapters import GhostToolsAdapter
from swizzle.lab import attack, world

case = world.simple("test_name", ...)
result = attack.run(case, GhostToolsAdapter())
```

### For Improvement Loop
```python
from swizzle.integration.loop_orchestrator import LoopOrchestrator
from swizzle.integration.arbiter import Arbiter

orchestrator = LoopOrchestrator(workspace=Path("./loop_workspace"))
orchestrator.start_loop()
```

### For Governance Verification
```python
from swizzle.wizzle.evaluator import Evaluator
from swizzle.wizzle.action_entitlement import ActionEntitlementOracle

evaluator = Evaluator()
evaluator.run_all_oracles(case)
```

---

## Extension Points

1. **New Adapters**: Subclass `TargetAdapter` in `swizzle/lab/adapters/`
2. **New Oracles**: Subclass `OracleLogic` in `swizzle/lab/oracles/library.py`
3. **New Mutations**: Add `@mutator()` decorated functions to `swizzle/lab/mutators.py`
4. **New Events**: Add types to `EventType` enum in `swizzle/integration/event_system.py`
5. **New Governance Rules**: Add invariants to `swizzle/integration/invariant_model.py`
