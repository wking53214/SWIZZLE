# WIZZLE: Independent Verification Subsystem

WIZZLE is integrated into SWIZZLE as `swizzle.wizzle`. Use
`python -m swizzle verify ...` for the integrated entry point. Historical
standalone commands below are retained as provenance for the subsystem.

WIZZLE is an experimental instrument for determining whether autonomous software modification systems (like Ghost) are **justified** in the semantic conclusions they draw from historical evidence.

## Core Thesis

When Ghost observes historical evidence, does that evidence **entitle** Ghost to the semantic conclusions Ghost reaches?

### The Three Levels

**OBSERVATION**: What actually happened
- Member X existed in the codebase
- Member X was referenced by production code
- Reference to X disappeared
- X is now test-only

**INTERPRETATION**: What that observation might mean
- Accidental deletion (regression)
- Intentional refactoring (improvement)
- Security fix (intentional and appropriate)
- Dead code cleanup (safe)
- API deprecation (intentional design change)

**CONCLUSION**: What Ghost concluded (and whether it's justified)
- Ghost reports: MAJOR severity, regression
- Question: Is that conclusion actually justified by the available evidence?

## The Epistemic Challenge

Ghost asks:
> "What happened, and what should I safely do?"

WIZZLE asks:
> "Is Ghost entitled to believe what it just concluded?"

## Current State

### Phase 1: Foundation (In Progress)
- ✓ Epistemic model types (Observation, Interpretation, Conclusion)
- ✓ Intent taxonomy (ACCIDENTAL_REMOVAL, INTENTIONAL_REFACTOR, etc.)
- ✓ Independent oracles (HistoryOracle, CurrentStateOracle, etc.)
- ✓ Evidence provenance tracking
- ✓ Preserved PHANTOM and MEDIUM seed scenarios
- ⚘ History generator (generating)
- ⚘ Contrastive pair generation (next)

### Phase 2-4: Coming
- Semantic correctness evaluation
- Overclaim detection
- Minimization and replay
- Holdout evaluation framework
- CLI and comprehensive testing

## Key Design Principles

1. **No Semantic Leakage**: Oracles cannot read Ghost's conclusion or the scenario's declared ground-truth label
2. **Factual ≠ Semantic**: A finding can be factually correct but semantically unjustified
3. **Evidence Entitlement**: What evidence would justify a particular conclusion? Make it explicit
4. **Principled Minimization**: Preserve causal structure, not just byte count
5. **Independent Oracles**: Run in separate processes/functions; aggregate results carefully

## Running WIZZLE

```bash
# Inspect current state
python -m wizzle inspect

# Run all experiments
python -m wizzle run

# Compare against different Ghost versions
python -m wizzle compare ghost-1.7.8 ghost-1.7.9
```

(CLI not yet implemented; foundation phase in progress)