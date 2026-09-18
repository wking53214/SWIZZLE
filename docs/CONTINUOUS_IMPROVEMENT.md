# Continuous Improvement Loop and Arbiter

## Overview

Swizzle and Ghost Tools implement a continuous improvement ecosystem through two coordinated systems:

1. **Loop Orchestrator** - Manages iterative improvement cycles between the two repositories
2. **Arbiter** - Validates improvements through metrics-based decision making

Together, they create a feedback loop where both repositories analyze each other, propose improvements, and validate them against established criteria before integration.

## The Continuous Improvement Loop

### Architecture

The loop operates between two repositories:
- **Swizzle**: Adversarial testing and verification framework
- **Ghost Tools**: Scanning and surgical improvement tools

### Loop Lifecycle

#### 1. Initialization
- Loop starts in IDLE state
- Convergence threshold set to 1% (improvements below this trigger termination)
- Maximum iterations limit set (typically 20)
- Loop state persisted in `loop_state.json` for resume capability

#### 2. Iteration Cycle
Each iteration follows this sequence:

```
Analyze Target → Propose Improvement → Arbiter Validates → Accept/Reject → Record → Check Convergence
```

**Phase 1: Generate Improvements**
- Source repository analyzes target repository
- Identifies enhancement opportunities through:
  - Structural analysis
  - Performance profiling
  - Mutation testing results
  - Cross-repository audits
- Proposes improvements with unique improvement IDs

**Phase 2: Arbiter Validation**
- Arbiter evaluates each improvement against:
  - Critical metrics (must not regress)
  - Weighted improvement scores
  - Acceptance thresholds specific to each repository
  - Confidence thresholds
- Returns `ValidationVerdict` with detailed reasoning

**Phase 3: Accept or Reject**
- Improvements with `ACCEPT` verdict → applied to target repository
- Improvements with `CONDITIONAL` verdict → flagged for human review
- Improvements with `REJECT` verdict → discarded
- All verdicts recorded with full justification

**Phase 4: Record Iteration**
- Iteration number and status recorded
- Sender/receiver repos documented
- Net improvement percentage calculated
- Acceptance rate updated per repository
- Timestamp recorded

**Phase 5: Convergence Check**
- If last 3 iterations average < 1% improvement → converged
- If reached max iterations → halts
- Otherwise → continues to next iteration

### Loop State Management

```python
class LoopState:
    status: LoopStatus  # IDLE, RUNNING, PAUSED, CONVERGED, STALLED
    iterations: List[LoopIteration]  # Complete history
    convergence_threshold: float  # 0.01 = 1%
    max_iterations: int  # Typical: 20
    current_iteration: int
    total_improvement: float  # Cumulative across all iterations
    converged: bool
```

#### Status Transitions
- `IDLE` → `RUNNING` (via `start_loop()`)
- `RUNNING` → `PAUSED` (via `pause_loop()`)
- `PAUSED` → `RUNNING` (via `resume_loop()`)
- `RUNNING` → `CONVERGED` (when improvements < threshold)
- `RUNNING` → `STALLED` (when no progress for N iterations)

### Acceptance Rates Tracking

The loop tracks acceptance rates per repository to understand improvement quality:
- **Perfect acceptance** (95-100%): High-quality proposals, well-aligned systems
- **Good acceptance** (80-95%): Generally solid proposals with occasional rejections
- **Selective acceptance** (50-80%): Mixed quality, some fundamental misalignment
- **Low acceptance** (<50%): Major disconnect between systems

This metric reveals both the quality of proposals and the alignment level between Swizzle and Ghost Tools.

## The Arbiter System

### Purpose

The Arbiter acts as a neutral referee between repositories. Its responsibilities:

1. **Evaluate** proposed improvements against concrete, measurable criteria
2. **Measure** impact on critical quality signals
3. **Decide** whether to accept, conditionally accept, or reject proposals
4. **Record** all verdicts with detailed justification for auditability and learning

### Validation Metrics

Each improvement is measured against one or more metrics:

```python
class ValidationMetric:
    name: str              # e.g., "test_pass_rate", "execution_time"
    before_value: float    # Baseline measurement
    after_value: float     # Post-improvement measurement
    unit: str             # e.g., "%", "seconds", "findings"
    importance: float     # Weight in overall decision (0.0-1.0)
```

#### Common Metrics for Swizzle ↔ Ghost Tools

**From Swizzle analyzing Ghost Tools**:
- Test pass rate (critical)
- Mutation detection rate
- Execution time per file
- Memory usage
- Code complexity
- Coverage percentage

**From Ghost Tools analyzing Swizzle**:
- Attack generation success rate (critical)
- Minimization efficiency
- Oracle accuracy
- Convergence speed
- Case diversity
- Execution stability

### Verdict Types

```python
class ValidationVerdictType(str, Enum):
    ACCEPT = "accept"              # Clear improvement, apply immediately
    REJECT = "reject"              # Regression or no improvement
    NEEDS_REVIEW = "needs_review"  # Significant but needs human judgment
    CONDITIONAL = "conditional"    # Meets threshold but with concerns
```

### Verdict Decision Logic

```
If any critical metric regressed:
    → REJECT (confidence: 0.95)
    Reason: "Critical metric <name> regressed from <before> to <after>"

Else calculate weighted score:
    weighted_score = (sum of metric_improvements × metric_importance) / total_importance

If weighted_score >= acceptance_threshold (default 0.0):
    → ACCEPT (confidence: min(0.99, 0.5 + weighted_score))
    Reason: "Net improvement of <score>%"

Else if weighted_score >= threshold × 0.5:
    → CONDITIONAL (confidence: 0.7)
    Reason: "Marginal improvement of <score>%, needs review"

Else:
    → REJECT (confidence: 0.9)
    Reason: "No improvement or regression of <score>%"
```

### Critical Metrics

Metrics can be marked as "critical", meaning any regression automatically rejects the improvement:

```python
arbiter = Arbiter(repo_name="ghost_tools")
arbiter.add_critical_metric("test_pass_rate")
arbiter.add_critical_metric("parsing_errors_count")
arbiter.add_critical_metric("security_findings_count")
```

An improvement that causes a critical metric to regress is automatically rejected regardless of overall weighted score.

### Acceptance Thresholds

Repositories can set individual acceptance thresholds based on their needs:

```python
# Ghost Tools requires 5% minimum improvement
ghost_arbiter = Arbiter(repo_name="ghost_tools")
ghost_arbiter.set_acceptance_threshold(0.05)

# Swizzle requires 2% minimum improvement
swizzle_arbiter = Arbiter(repo_name="swizzle")
swizzle_arbiter.set_acceptance_threshold(0.02)
```

This allows each system to have different quality bars appropriate to its risk profile.

## Integration with Event System

The continuous loop integrates with Ghost Tools and Swizzle's event systems:

### Events Published

**Improvement Events:**
- `IMPROVEMENT_PROPOSED` - New improvement ready for validation
- `VALIDATION_STARTED` - Arbiter beginning evaluation

**Decision Events:**
- `VERDICT_RENDERED` - Arbiter completed evaluation
- `VERDICT_RECORDED` - Verdict persisted to history
- `IMPROVEMENT_ACCEPTED` - Improvement approved for application
- `IMPROVEMENT_REJECTED` - Improvement rejected with reasons

**Loop Events:**
- `ITERATION_STARTED` - New iteration beginning
- `ITERATION_COMPLETED` - Iteration finished
- `CONVERGENCE_ACHIEVED` - Loop has converged
- `LOOP_PAUSED` - Loop paused for review

### Event Flow

```
Repository A                Event Bus              Arbiter              Repository B
    ↓                          ↓                      ↓                      ↓
Analyze B ──→ IMPROVEMENT_PROPOSED ─→ validate() ─→ VERDICT_RECORDED ──→ Apply (if ACCEPT)
              (with metrics)                         (with confidence)
                                       ↓
                              Feedback via event
```

## Integration Example: Swizzle Improving Ghost Tools

### Scenario: Complete Iteration

1. **Initialization**
   ```
   LoopOrchestrator.start_loop()
   Status: RUNNING, Iteration: 0, Total Improvement: 0%
   ```

2. **Swizzle analyzes Ghost Tools**
   ```
   - Runs full test suite
   - Profiles execution time
   - Identifies: "loop_invariant_call" optimization (serum site)
   - Proposes improvement ID: "swizzle-gt-001"
   ```

3. **Arbiter evaluates**
   ```
   Metrics evaluated:
   - test_pass_rate: 98% → 98% (no regression) ✓
   - execution_time: 4.2s → 3.8s (9.5% improvement) ✓
   - code_complexity: 3.2 → 3.1 (3.1% improvement) ✓
   
   Weighted score = (9.5% × 0.8 + 3.1% × 0.2) / 1.0 = 8.14%
   Score >= threshold (0%) → ACCEPT
   Confidence = min(0.99, 0.5 + 0.0814) = 0.5814 ≈ 0.58
   ```

4. **Ghost Tools applies improvement**
   ```
   - Modifies 2 lines in loop_orchestrator.py
   - Re-runs test suite: 98% passing (✓ no regression)
   - Commits with message referencing verdict
   - Event published: IMPROVEMENT_ACCEPTED
   ```

5. **Ghost Tools analyzes Swizzle** (counter-proposal)
   ```
   - Analyzes Swizzle codebase
   - Proposes optimization to mutation minimization
   - Improvement ID: "gt-swizzle-001"
   ```

6. **Loop records iteration**
   ```
   Iteration 1:
   - sender: swizzle → receiver: ghost_tools
   - improvement_id: swizzle-gt-001
   - accepted: true
   - net_improvement: 8.14%
   - acceptance_rate: 100% (so far)
   - timestamp: 2026-09-18T23:15:00Z
   
   Iteration 2:
   - sender: ghost_tools → receiver: swizzle
   - improvement_id: gt-swizzle-001
   - accepted: true
   - net_improvement: 6.2%
   - acceptance_rate: 100%
   ```

7. **Convergence monitoring**
   ```
   After 10 iterations:
   - Last 3 improvements: 1.2%, 0.8%, 0.5%
   - Average: 0.83% (< 1% threshold)
   - Status: CONVERGED
   - Total cumulative improvement: 42.3%
   ```

## Configuration

### Loop Parameters

```python
from ghost_tools.integration.loop_orchestrator import LoopOrchestrator

orchestrator = LoopOrchestrator(workspace=Path("./loop_workspace"))

# Adjust convergence criteria
orchestrator.loop_state.convergence_threshold = 0.01  # 1%
orchestrator.loop_state.max_iterations = 25

# Start the loop
orchestrator.start_loop()

# Pause for review if needed
orchestrator.pause_loop()

# Resume later
orchestrator.resume_loop()
```

### Arbiter Parameters

```python
from ghost_tools.integration.arbiter import Arbiter

arbiter = Arbiter(repo_name="ghost_tools")

# Set acceptance bar (minimum improvement required)
arbiter.set_acceptance_threshold(0.05)  # 5% minimum

# Mark critical metrics that cannot regress
arbiter.add_critical_metric("test_pass_rate")
arbiter.add_critical_metric("security_findings_count")
arbiter.add_critical_metric("committed_secrets_count")
```

## Outputs and History

### Loop State Persistence
Location: `<workspace>/loop_state.json`

Contains:
- Current status (IDLE, RUNNING, PAUSED, CONVERGED)
- All iteration records (sender, receiver, verdict, improvement)
- Total improvement tracked cumulatively
- Convergence status and achieved threshold

### Iteration History
Each iteration record includes:
- Iteration number
- Source and target repository
- Improvement ID (unique within loop)
- Acceptance decision (bool)
- Net improvement percentage
- Timestamp (ISO 8601)

### Verdict History
Each verdict record includes:
- Source and target repositories
- Improvement ID being evaluated
- Verdict type (ACCEPT/REJECT/CONDITIONAL/NEEDS_REVIEW)
- Confidence score (0.0-1.0)
- Detailed reason for decision
- All evaluated metrics and their before/after values
- Timestamp

## Success Criteria

The continuous improvement loop achieves success when:

1. **Convergence Achieved**
   - Improvements drop below 1% threshold
   - No significant enhancements available
   - Both systems at local optimum

2. **High Acceptance Rates**
   - Both repos maintaining >80% acceptance rate
   - Indicates good alignment and proposal quality

3. **Quality Maintained**
   - All critical metrics passing throughout
   - No regressions introduced by any accepted improvement

4. **Productivity Gains**
   - Total cumulative improvement > baseline
   - Example: -70% code findings, -15% execution time

Example success metrics:
- Initial state: 100 code quality findings
- After convergence: 30 findings (-70%)
- All 309 tests passing throughout
- No security issues introduced
- Swizzle acceptance rate: 93%
- Ghost acceptance rate: 88%

## Failure Modes and Recovery

### Stalled Loop
**Cause**: No improvements proposed for N iterations
**Detection**: Loop status transitions to STALLED
**Recovery**: 
- Check if convergence already achieved (expected)
- Or analyze why proposals dropped off
- Or increase convergence threshold if acceptable
- Or reset and target different improvement areas

### High Rejection Rate (< 50%)
**Cause**: Proposed improvements consistently fail arbiter validation
**Detection**: Acceptance rate drops below 50% threshold
**Recovery**:
- Review specific rejection reasons
- Adjust critical metrics if too strict
- Increase acceptance threshold if too high
- Improve improvement proposal quality/analysis

### Regression Detection
**Cause**: Accepted improvement caused test failures in next iteration
**Detection**: Next iteration's metrics show regression
**Recovery**:
- Arbiter automatically catches in next validation
- Previous improvement rejected in analysis
- Quality gate prevents repeated regressions
- Loop continues with better understanding

### Metric Oscillation
**Cause**: Some metric improving while another regresses
**Detection**: Weighted score calculation balances gains and losses
**Recovery**:
- Review metric importance weights
- Consider adjusting critical metrics list
- May indicate need for longer-term optimization

## Best Practices

1. **Set reasonable thresholds**
   - Convergence: 1% threshold (lower = stricter termination)
   - Acceptance: 0-5% (higher = require more improvement)
   - Max iterations: 20-30 typical

2. **Mark truly critical metrics**
   - Only metrics that must never regress
   - Examples: test pass rate, security findings
   - Keep this list minimal (3-5 metrics max)

3. **Monitor acceptance rates**
   - Should stay >75% for healthy loop
   - <50% indicates misalignment
   - Track per repository for asymmetric patterns

4. **Review first iterations**
   - Manually validate that first improvements make sense
   - Verify metrics are measured correctly
   - Ensure no systematic bias in proposals

5. **Persist loop state**
   - Always save state to enable resume
   - Allows inspection between iterations
   - Useful for interrupted or long-running loops

6. **Log all verdicts**
   - Record detailed reasoning for every verdict
   - Enables audit trail and post-loop analysis
   - Supports learning over multiple loop runs

7. **Balance automation and review**
   - ACCEPT verdicts apply immediately
   - CONDITIONAL verdicts wait for human review
   - REJECT verdicts have reasoning recorded
   - Find right threshold for your risk profile
