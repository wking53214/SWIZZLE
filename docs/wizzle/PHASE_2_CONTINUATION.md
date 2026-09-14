# Phase 2 Continuation: Ghost Integration and Semantic Evaluation

## Current State

Phase 2 has successfully:
- Generated three complete scenario repositories with full git histories
- Implemented independent oracle system that analyzes repositories
- Created evaluation framework that produces oracle assessments
- Built CLI for scenario inspection

## Critical Next Tasks

### 1. Ghost Integration (High Priority)

**Objective**: Invoke Ghost on generated scenarios and capture its findings.

**Implementation**:
```python
# ghost_invoker.py
class GhostInvoker:
    """Invoke Ghost on a repository and capture results."""
    
    def invoke(self, repo_path: Path) -> GhostFinding:
        """Run Ghost and return parsed JSON findings."""
        # 1. Determine Ghost version/location
        # 2. Run: ghost analyze --json {repo_path}
        # 3. Parse JSON output
        # 4. Return structured GhostFinding object
        
    def compare_with_oracle(self, ghost_finding: GhostFinding, 
                           oracle_result: dict) -> EvaluationResult:
        """Compare Ghost's conclusion against oracle assessment."""
        # Determine if Ghost's finding is:
        # - FACTUALLY_CORRECT (member truly exists/removed as observed)
        # - SEMANTICALLY_JUSTIFIED (conclusion justified by available evidence)
        # - OVERCLAIMED (conclusion exceeds what evidence supports)
```

**Tests Needed**:
- `test_ghost_invocation()`: Verify Ghost runs and returns valid JSON
- `test_ghost_finding_parsing()`: Verify JSON parsing works
- `test_ghost_null_hypothesis()`: What does Ghost report on non-existent member?

### 2. Semantic Correctness Assessment

**Objective**: Determine when Ghost's finding exceeds evidence entitlement.

**Key Question**: Given the evidence, is Ghost entitled to conclude MAJOR severity?

**Implementation Approach**:
```python
# overclaim_detection.py
def assess_semantic_correctness(ghost_finding: GhostFinding,
                                oracle_history: dict,
                                current_state: dict) -> SemanticCorrectness:
    """Determine if conclusion is justified by evidence."""
    
    # Evidence categories Ghost can consider:
    # 1. STRUCTURAL: Member exists in tests but not production
    # 2. HISTORICAL: When was it removed? (from history oracle)
    # 3. INTENT_SIGNALS: Commit messages suggesting purpose
    # 4. CONTEXT: How long was it in production? Usage patterns?
    
    # Evaluation logic:
    if ghost_finding.severity == "MAJOR":
        # Is this justified?
        # - If evidence clearly shows INTENTIONAL_REFACTOR → OVERCLAIMED
        # - If evidence is ambiguous → might be JUSTIFIED
        # - If evidence shows recent removal → might be JUSTIFIED
        
    return semantic_correctness_assessment
```

**Evidence Thresholds** (to be formalized):
- INTENTIONAL_REFACTOR + REFACTOR_COMMIT_FOUND → OVERCLAIMED (if marked MAJOR)
- ACCIDENTAL_REMOVAL + NO_RESTORE_IN_PRODUCTION → JUSTIFIED (MAJOR is reasonable)
- INTENTIONAL_REFACTOR + TEST_ADDED_AFTER_REMOVAL → JUSTIFIED (test-only is safe)

### 3. Minimization Engine (Medium Priority)

**Objective**: Reduce scenarios to smallest form that preserves semantic structure.

**What NOT to do**: Simply remove commits until the test passes (loses causality)

**What to do**: Preserve the essential evidence chain:
```
[ESSENTIAL] Member added
[ESSENTIAL] Member used in production
[ESSENTIAL] Member removed (with intent signal)
[ESSENTIAL] Member restored (for tests) or tests reference it
[REMOVABLE] Intermediate cleanup commits
[REMOVABLE] Unrelated members (ACTIVE, INACTIVE)
```

**Implementation**:
```python
def minimize_scenario(repo_path: Path) -> Path:
    """Create minimal version preserving semantic structure."""
    
    # 1. Identify critical commits
    #    - Where member added/removed/restored
    
    # 2. Identify intent signals
    #    - Commit messages, code patterns
    
    # 3. Remove commits not affecting member lifecycle
    
    # 4. Create new minimal repo with squashed commits
    #    (preserving message content and timing relationships)
    
    # 5. Verify Ghost still finds member
```

### 4. Holdout Evaluation Framework

**Objective**: Systematically test WIZZLE's correctness on held-out scenarios.

**Approach**:
- Divide corpus into training (PHANTOM, MEDIUM) and test sets
- Measure: Precision/recall of semantic correctness assessment
- Evaluate: Does WIZZLE correctly predict when Ghost overclaims?

## Implementation Order

1. **Immediate**: Ghost integration (enables actual evaluation)
2. **Next**: Overclaim detection algorithm (formalize semantic thresholds)
3. **Then**: Minimization engine (create test fixtures)
4. **Finally**: Holdout evaluation (measure correctness)

## Key Design Decisions Still Pending

### Decision: Ghost Version Compatibility
- **Question**: Which Ghost versions should WIZZLE test against?
- **Options**:
  a) Single stable version (simpler, less comprehensive)
  b) Multiple versions (enables regression detection)
  c) Local Ghost build (complete control, harder setup)

### Decision: Evidence Weighting
- **Question**: How much confidence in intent signals?
- **Current approach**: Treat as weak signals (confidence < 1.0)
- **Alternative**: Ignore intent signals, use only structural evidence
- **Tradeoff**: More conservative vs. better discrimination

### Decision: Test-Only Member Classification
- **Question**: Is test-only member usage ever a regression?
- **Current approach**: If intentionally refactored, test-only is safe
- **Risk case**: What if member's semantic meaning changed?
- **Resolution**: Needs explicit test-only intent marker in commit

## Success Criteria

✓ Ghost invocation works on all three scenarios
✓ Oracle and Ghost results can be compared
✓ Semantic correctness assessment produces meaningful verdicts
✓ WIZZLE correctly identifies at least one overclaimed Ghost finding
✓ Minimized scenarios remain <50% original size with same Ghost finding

## References

**Related Files**:
- `wizzle/epistemic_model.py`: Core type system
- `wizzle/evaluator.py`: Oracle integration
- `wizzle/oracles.py`: Independent analysis
- `build_scenarios.py`: Scenario generation

**Key Concepts**:
- Evidence provenance (7 categories)
- Factual vs semantic correctness (independent dimensions)
- Intent taxonomy (16 categories)
- Evidence entitlement (what conclusion does evidence justify?)
