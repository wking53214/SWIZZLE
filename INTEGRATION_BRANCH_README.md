# Swizzle-Ghost Tools Integration Branch

**Branch**: `claude/swizzle-ghost-tools-integration-lwnxoh`

## Summary

This branch implements **6 bidirectional integration bridges** between Swizzle and Ghost Tools, enabling comprehensive information flow that was previously one-directional.

Previously:
- Swizzle tested Ghost Tools but findings didn't feed back
- No shared model of constraints or invariants
- No mutation or oracle training data exchange
- No performance regression detection
- No cross-tool architecture validation

Now:
- Swizzle findings → Ghost learning
- Ghost decisions → Swizzle oracle training
- Shared constraint model across both tools
- Bidirectional mutation testing
- Performance regression detection
- Cross-tool architecture validation

## What's Implemented

### 1. **Shared Invariant Model** (`swizzle/integration/invariant_model.py`)
   - Unified schema for constraints both tools enforce
   - Defines 6 core invariants (no boundary escapes, content preservation, etc.)
   - Scope and severity levels standardized
   - Used by both tools for validation

### 2. **Triage Ledger Exchange** (`swizzle/integration/triage_ledger.py`)
   - Ghost's triage decisions → Swizzle oracle training data
   - Swizzle findings → Ghost casefile
   - Maps decision history (true/false/deferred) with reasoning
   - Exports in tool-specific formats for calibration

### 3. **Mutation Transfer** (`swizzle/integration/mutation_transfer.py`)
   - Swizzle's minimized adversarial cases → Ghost mutation suite
   - Ghost's mutations → Swizzle corpus
   - 3 seed mutation cases provided (symlink escape, prose deletion, dated claims)
   - Bidirectional test case sharing

### 4. **Performance Contract System** (`swizzle/integration/performance_contract.py`)
   - Establish explicit performance guarantees
   - Regression detection with baseline comparison
   - 3 sample contracts (scan time per file, memory usage, execution time)
   - Violation tracking and analysis

### 5. **Architecture Audit Bridge** (`swizzle/integration/architecture_audit.py`)
   - Swizzle detects Ghost architecture violations
   - Ghost validates Swizzle adapter contracts
   - Defined boundaries with allowed/forbidden imports
   - Compliance matrix across tools

### 6. **False Positive Feedback Loop** (`swizzle/integration/feedback_loop.py`)
   - Verified false positives train both tools
   - Filter patterns with confidence scores
   - Oracle training datapoints with ground truth
   - Filter effectiveness analysis

### Supporting Components

- **Orchestrator** (`swizzle/integration/orchestrator.py`): Ties all bridges together
  - Centralized data export/import
  - Bundle generation for each tool
  - Integration reporting and monitoring

- **Ghost Integration Consumer** (`ghost_tools_integration/consumer.py`): Ghost's side.
  Since removed from ghost_tools in 28685aa, recoverable from ghost_tools 0073c49;
  nothing reads the Ghost bundle now.
  - Loads Swizzle integration bundles
  - Applies false positive patterns to findings
  - Validates against invariants and contracts
  - Provides access to all shared data

- **Documentation** (`docs/INTEGRATION_GUIDE.md`): Complete guide
  - Explains each bridge in detail
  - Data flow diagrams
  - Usage examples for both tools
  - Version compatibility information

## File Structure

**Swizzle**:
```
swizzle/integration/
├── __init__.py
├── invariant_model.py
├── triage_ledger.py
├── mutation_transfer.py
├── performance_contract.py
├── architecture_audit.py
├── feedback_loop.py
└── orchestrator.py

docs/
└── INTEGRATION_GUIDE.md
```

**Ghost Tools** (removed from ghost_tools in 28685aa, recoverable from ghost_tools 0073c49):
```
ghost_tools_integration/
├── __init__.py
└── consumer.py
```

## Key Data Flows

### Triage → Oracle Training
```
Ghost Casefile (.ghost_casefile.json)
  ↓
import_ghost_casefile()
  ↓
TriageLedger.export_for_swizzle_oracle_training()
  ↓
→ Swizzle Oracle Calibration
```

### Mutations → Test Corpus
```
Swizzle Minimized Cases
  ↓
MutationCatalog.export_for_ghost_mutation_suite()
  ↓
→ Ghost Mutation Testing

Ghost Mutations
  ↓
MutationCatalog.export_for_swizzle()
  ↓
→ Swizzle Attack Corpus
```

### Performance Monitoring
```
Swizzle Execution Times
  ↓
PerformanceRun (with metrics)
  ↓
check_contract_violations()
  ↓
→ Regression Detection

detect_regressions() (95th percentile)
  ↓
→ Performance Report
```

### False Positives → Filters
```
Ghost Confirmed False Positive
  ↓
FalsePositivePattern (with indicators)
  ↓
SwizzleIntegrationConsumer.filter_false_positives()
  ↓
→ Filter Application on Next Scan

Swizzle Verified False Positive
  ↓
OracleTrainingDatapoint (ground truth)
  ↓
→ Ghost Prior Reasoning
```

## Usage Example

### Swizzle Side
```python
from swizzle.integration.orchestrator import IntegrationOrchestrator

orch = IntegrationOrchestrator(Path(".swizzle-integration"))

# Import Ghost's triage decisions
orch.import_ghost_casefile(Path(".ghost_casefile.json"))

# Export everything for Ghost to consume
orch.publish_ghost_integration_bundle(Path(".swizzle-for-ghost"))

# Export oracle training data
orch.publish_swizzle_integration_bundle(Path(".ghost-for-swizzle"))
```

### Ghost Side

The consumer below was removed from ghost_tools in 28685aa, recoverable from ghost_tools 0073c49.

```python
from ghost_tools_integration.consumer import SwizzleIntegrationConsumer, IntegrationConfig

consumer = SwizzleIntegrationConsumer(
    IntegrationConfig(swizzle_bundle_dir=Path(".swizzle-for-ghost"))
)

# Filter false positives
findings = consumer.filter_false_positives(findings)

# Validate against shared invariants
violations = consumer.validate_invariants(findings)

# Check performance contract
assert consumer.check_performance_contract("wall_time", elapsed_seconds)
```

## Integration Data Exported

When `orch.export_all()` runs, generates:
- `invariants.json` - 6 shared invariants
- `mutations.json` - Shared mutation test cases
- `performance.json` - Contracts and performance runs
- `swizzle-architecture.json` - Swizzle architecture rules
- `ghost-architecture.json` - Ghost architecture rules
- `feedback.json` - False positive patterns
- `triage-ledger.json` - Triage history (if Ghost casefile imported)

## Compatibility

- **Swizzle Version**: v0.4.0+
- **Ghost Tools Version**: v1.5.0+
- **Integration Model Version**: 1.0
- **Data Format**: JSON (language-agnostic)

## Next Steps

1. Generate initial integration bundles using orchestrator
2. Import bundles in both tools
3. Run Swizzle against Ghost to collect performance/architecture data
4. Collect triage decisions from Ghost operations
5. Refine false positive filters as data accumulates
6. Monitor oracle calibration improvements
7. Track performance regressions across versions

## Architecture Decisions

### Why JSON for Everything?
- Language-agnostic exchange
- Both tools are Python but integration should be portable
- Easy to inspect and debug
- Simple version evolution

### Why Six Bridges?
- Addresses different failure modes
- One bridge per integration dimension
- Incrementally adoptable

### Why Orchestrator?
- Centralized coordination prevents data consistency issues
- Single point for validation and reporting
- Easier to add new bridges later

### Why Consumer Pattern for Ghost?
- Ghost doesn't need to know about Swizzle internals
- Graceful degradation if data is missing
- Clear configuration for selective integration
- Easy to test in isolation

## Testing Integration

See `swizzle/integration/` for data structure tests. Key invariants:
- All exported JSON must be valid and parseable
- Version fields must match
- No circular dependencies in models
- All references must be resolvable

## Contributing

When adding new integration bridges:
1. Add new model file in `swizzle/integration/`
2. Update `orchestrator.py` to manage new model
3. Add a Ghost-side reader in ghost_tools first: it has none since 28685aa
4. Update `docs/INTEGRATION_GUIDE.md` with bridge explanation
5. Add example seed data to new model
6. Document data flow and version compatibility

---

**Status**: Complete and ready for integration testing
**Created**: 2026-09-18
**Author**: Claude Code
