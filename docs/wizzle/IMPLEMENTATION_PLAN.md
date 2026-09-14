# WIZZLE Upgrade: Implementation Plan

## Current State Analysis

### What We Have
- Static repository with two scenario examples (PHANTOM, MEDIUM)
- Git history collapsed to single merge commit (actual history lost)
- Prose documentation of scenarios
- Two test functions that verify enum members exist
- No executable framework

### What We're Missing
- Actual git histories demonstrating forensics scenarios
- Epistemic model distinguishing observation/interpretation/conclusion
- Adversarial history generator
- Independent oracle system
- Evidence entitlement framework
- Contrastive pair mechanism
- Deterministic experiment runner
- Result schema and reporting

## Implementation Phases

### Phase 1: Foundation (Days 1-2)
1. Rebuild actual git histories for PHANTOM and MEDIUM
2. Create epistemic model types
3. Design oracle architecture
4. Build history generator primitives

### Phase 2: Execution (Days 3-4)
1. Implement scenario generators
2. Build independent oracles
3. Add evidence provenance tracking
4. Create contrastive pair generator

### Phase 3: Evaluation (Days 5-6)
1. Implement result schema
2. Add overclaim detection
3. Create minimization algorithm
4. Build holdout framework

### Phase 4: Integration (Days 7)
1. Build CLI commands
2. Add comprehensive tests
3. Update documentation
4. Clean up scaffolding

## Critical Design Decisions

1. **History Preservation**: Use git format-patch to preserve exact histories as versioned test data
2. **Oracle Independence**: No oracle reads Ghost's conclusion or WIZZLE's ground-truth label
3. **Semantic Truth**: Independently derived from experiment design, not from detector results
4. **Evidence Provenance**: Every datum tracks whether it's CONSTRUCTED, OBSERVED, DERIVED, etc.
5. **Minimization**: Preserves causal structure, not just byte count

## Acceptance Criteria

Must demonstrate:
1. Generate intentional-removal and accidental-removal histories
2. Generate contrastive pairs with similar evidence, different truth
3. Detect unjustified severity escalation
4. Preserve existing PHANTOM/MEDIUM scenarios
5. Machine-readable experiment results
6. Clear FACTUALLY_CORRECT vs SEMANTICALLY_CORRECT distinction
