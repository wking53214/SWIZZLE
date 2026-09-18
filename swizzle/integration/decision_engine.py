"""Autonomous decision engine for inter-tool integration.

Makes low-risk decisions automatically based on event confidence and severity.
Routes high-risk decisions to human review.

Risk Matrix:
- Low Risk: High confidence FP patterns, minor oracle updates (auto-apply)
- Medium Risk: Architecture violations, performance regressions (review required)
- High Risk: Critical violations, consensus reversals (escalate)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import uuid

from swizzle.integration.event_system import Event, EventType


class DecisionType(str, Enum):
    """Types of decisions the engine can make."""
    APPLY_FILTER_PATTERN = "apply_filter_pattern"  # Add to false positive filters
    REJECT_FILTER_PATTERN = "reject_filter_pattern"  # Pattern too aggressive
    UPDATE_ORACLE_TRAINING = "update_oracle_training"  # Retrain oracle
    ESCALATE_VIOLATION = "escalate_violation"  # Alert on architecture issue
    ADJUST_PERFORMANCE_THRESHOLD = "adjust_performance_threshold"  # Loosen contract
    ADD_TEST_CASE = "add_test_case"  # Include in mutation suite
    SUPPRESS_FINDING = "suppress_finding"  # Ignore recurrent FP
    REQUIRE_HUMAN_REVIEW = "require_human_review"  # Escalate to human


class RiskLevel(str, Enum):
    """Risk level of a decision."""
    LOW = "low"  # Auto-apply safe
    MEDIUM = "medium"  # Review recommended
    HIGH = "high"  # Escalate always
    CRITICAL = "critical"  # Block until resolved


class ConfidenceSource(str, Enum):
    """Why we're confident in a decision."""
    PATTERN_MATCH = "pattern_match"  # Historical pattern matches this
    CONSENSUS = "consensus"  # Multiple sources agree
    STATISTICAL = "statistical"  # Threshold exceeded
    EXPERT_SYSTEM = "expert_system"  # Rule engine output
    ML_MODEL = "ml_model"  # ML model prediction


@dataclass
class ConfidenceScore:
    """Confidence assessment for a decision."""
    value: float  # 0.0 to 1.0
    source: ConfidenceSource
    evidence: List[str]  # Why we're confident (e.g., "pattern_dated_readme matched 5 times")
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AutomatedDecision:
    """A decision made by the decision engine."""
    id: str
    type: DecisionType
    risk_level: RiskLevel
    confidence: ConfidenceScore
    triggered_by: Event  # which event triggered this

    # Action details
    action_data: Dict[str, Any] = field(default_factory=dict)

    # Execution
    approved: bool = False
    approval_reason: Optional[str] = None
    executed: bool = False
    executed_at: Optional[str] = None
    execution_result: Optional[str] = None

    # Audit trail
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    created_by: str = "decision_engine"
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None


class DecisionPolicy:
    """Policy that determines auto-approval thresholds."""

    def __init__(self):
        # Minimum confidence to auto-apply by risk level
        self.auto_apply_thresholds: Dict[RiskLevel, float] = {
            RiskLevel.LOW: 0.85,  # 85% confidence needed for low-risk auto-apply
            RiskLevel.MEDIUM: 0.95,  # 95% for medium-risk (review recommended)
            RiskLevel.HIGH: 1.0,  # Never auto-apply high-risk
            RiskLevel.CRITICAL: 1.0,  # Never auto-apply critical
        }

        # Which decision types are auto-approvable at each risk level
        self.auto_approvable_types: Dict[RiskLevel, List[DecisionType]] = {
            RiskLevel.LOW: [
                DecisionType.APPLY_FILTER_PATTERN,
                DecisionType.UPDATE_ORACLE_TRAINING,
                DecisionType.ADD_TEST_CASE,
                DecisionType.SUPPRESS_FINDING,
            ],
            RiskLevel.MEDIUM: [
                DecisionType.ADJUST_PERFORMANCE_THRESHOLD,
            ],
            RiskLevel.HIGH: [],  # Nothing auto-approvable
            RiskLevel.CRITICAL: [],  # Nothing auto-approvable
        }

    def should_auto_approve(
        self,
        decision_type: DecisionType,
        risk_level: RiskLevel,
        confidence: float,
    ) -> bool:
        """Determine if decision should be auto-approved."""
        # Check if type is auto-approvable at this risk level
        if decision_type not in self.auto_approvable_types.get(risk_level, []):
            return False

        # Check if confidence meets threshold
        threshold = self.auto_apply_thresholds[risk_level]
        return confidence >= threshold

    def should_escalate(self, risk_level: RiskLevel) -> bool:
        """Determine if decision should be escalated."""
        return risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)


class DecisionEngine:
    """Autonomous decision-making engine."""

    def __init__(self):
        self.policy = DecisionPolicy()
        self.decisions: Dict[str, AutomatedDecision] = {}
        self.decision_log: List[AutomatedDecision] = []
        self.handlers: Dict[DecisionType, Callable[[AutomatedDecision], None]] = {}

    def evaluate_event(self, event: Event) -> Optional[AutomatedDecision]:
        """Evaluate an event and potentially create a decision."""
        if event.type == EventType.FALSE_POSITIVE_CONFIRMED:
            return self._evaluate_false_positive(event)
        elif event.type == EventType.VIOLATION_DETECTED:
            return self._evaluate_violation(event)
        elif event.type == EventType.PERFORMANCE_REGRESSED:
            return self._evaluate_regression(event)
        elif event.type == EventType.MUTATION_CASE_DISCOVERED:
            return self._evaluate_mutation(event)
        elif event.type == EventType.ORACLE_TRAINING_IMPROVED:
            return self._evaluate_oracle_improvement(event)

        return None

    def _evaluate_false_positive(self, event: Event) -> AutomatedDecision:
        """Evaluate false positive pattern confirmation."""
        confidence = ConfidenceScore(
            value=event.data.get("confidence", 0.8),
            source=ConfidenceSource.PATTERN_MATCH,
            evidence=[
                f"Pattern confirmed by {event.source_tool}",
                f"Confidence from event: {event.data.get('confidence', 'N/A')}",
            ],
        )

        # High confidence FP patterns are low-risk to add to filters
        risk = RiskLevel.LOW if confidence.value >= 0.90 else RiskLevel.MEDIUM

        decision = AutomatedDecision(
            id=str(uuid.uuid4()),
            type=DecisionType.APPLY_FILTER_PATTERN,
            risk_level=risk,
            confidence=confidence,
            triggered_by=event,
            action_data={
                "false_positive_id": event.data.get("false_positive_id"),
                "finding_type": event.data.get("finding_type"),
                "indicators": event.data.get("indicators", []),
            },
        )

        return decision

    def _evaluate_violation(self, event: Event) -> AutomatedDecision:
        """Evaluate architecture violation."""
        # Violations are medium-risk (need review)
        severity_map = {
            "CRITICAL": RiskLevel.HIGH,
            "HIGH": RiskLevel.MEDIUM,
            "MEDIUM": RiskLevel.MEDIUM,
            "LOW": RiskLevel.LOW,
        }

        severity = event.data.get("severity", "MEDIUM")
        risk = severity_map.get(severity, RiskLevel.MEDIUM)

        confidence = ConfidenceScore(
            value=1.0,  # Violations are deterministic
            source=ConfidenceSource.EXPERT_SYSTEM,
            evidence=[
                f"Violation detected by Swizzle audit",
                f"Type: {event.data.get('violation_type')}",
            ],
        )

        decision = AutomatedDecision(
            id=str(uuid.uuid4()),
            type=DecisionType.ESCALATE_VIOLATION,
            risk_level=risk,
            confidence=confidence,
            triggered_by=event,
            action_data={
                "violation_id": event.data.get("violation_id"),
                "boundary_id": event.data.get("boundary_id"),
                "location": event.data.get("location"),
            },
        )

        return decision

    def _evaluate_regression(self, event: Event) -> AutomatedDecision:
        """Evaluate performance regression."""
        regression_pct = event.data.get("regression_percent", 0)

        # Decide based on severity
        if regression_pct > 30:
            risk = RiskLevel.HIGH
            confidence_val = 0.95
        elif regression_pct > 15:
            risk = RiskLevel.MEDIUM
            confidence_val = 0.90
        else:
            risk = RiskLevel.LOW
            confidence_val = 0.80

        confidence = ConfidenceScore(
            value=confidence_val,
            source=ConfidenceSource.STATISTICAL,
            evidence=[
                f"Regression: {regression_pct:.1f}%",
                f"Metric: {event.data.get('metric_name')}",
            ],
        )

        decision = AutomatedDecision(
            id=str(uuid.uuid4()),
            type=DecisionType.ADJUST_PERFORMANCE_THRESHOLD if regression_pct < 15 else DecisionType.ESCALATE_VIOLATION,
            risk_level=risk,
            confidence=confidence,
            triggered_by=event,
            action_data={
                "contract_id": event.data.get("contract_id"),
                "regression_percent": regression_pct,
            },
        )

        return decision

    def _evaluate_mutation(self, event: Event) -> AutomatedDecision:
        """Evaluate new mutation case."""
        # Adding test cases is low-risk
        confidence = ConfidenceScore(
            value=0.95,  # High confidence in Swizzle's minimized cases
            source=ConfidenceSource.EXPERT_SYSTEM,
            evidence=[
                "Mutation minimized by Swizzle",
                f"Severity: {event.data.get('severity')}",
            ],
        )

        decision = AutomatedDecision(
            id=str(uuid.uuid4()),
            type=DecisionType.ADD_TEST_CASE,
            risk_level=RiskLevel.LOW,
            confidence=confidence,
            triggered_by=event,
            action_data={
                "case_id": event.data.get("case_id"),
                "hypothesis": event.data.get("hypothesis"),
                "severity": event.data.get("severity"),
            },
        )

        return decision

    def _evaluate_oracle_improvement(self, event: Event) -> AutomatedDecision:
        """Evaluate oracle training improvement."""
        improvement = event.data.get("improvement_percent", 0)
        confidence_val = min(0.95, 0.70 + improvement / 100)  # Scale confidence by improvement

        confidence = ConfidenceScore(
            value=confidence_val,
            source=ConfidenceSource.ML_MODEL,
            evidence=[
                f"Oracle improvement: {improvement:.1f}%",
                f"New accuracy: {event.data.get('accuracy', 0):.2%}",
            ],
        )

        decision = AutomatedDecision(
            id=str(uuid.uuid4()),
            type=DecisionType.UPDATE_ORACLE_TRAINING,
            risk_level=RiskLevel.LOW,
            confidence=confidence,
            triggered_by=event,
            action_data={
                "finding_type": event.data.get("finding_type"),
                "accuracy": event.data.get("accuracy"),
                "training_size": event.data.get("training_size"),
            },
        )

        return decision

    def make_decision(self, event: Event) -> Optional[AutomatedDecision]:
        """Evaluate event and create decision (but don't execute yet)."""
        decision = self.evaluate_event(event)
        if not decision:
            return None

        # Store decision
        self.decisions[decision.id] = decision
        self.decision_log.append(decision)

        # Check if auto-approvable
        if self.policy.should_auto_approve(
            decision.type,
            decision.risk_level,
            decision.confidence.value,
        ):
            decision.approved = True
            decision.approval_reason = "Auto-approved by policy"
            self.execute_decision(decision)

        return decision

    def register_handler(
        self,
        decision_type: DecisionType,
        handler: Callable[[AutomatedDecision], None],
    ) -> None:
        """Register a handler for a decision type."""
        self.handlers[decision_type] = handler

    def execute_decision(self, decision: AutomatedDecision) -> bool:
        """Execute an approved decision."""
        if not decision.approved:
            return False

        handler = self.handlers.get(decision.type)
        if not handler:
            decision.execution_result = "No handler registered"
            return False

        try:
            handler(decision)
            decision.executed = True
            decision.executed_at = datetime.now().isoformat()
            decision.execution_result = "Success"
            return True
        except Exception as e:
            decision.execution_result = f"Error: {str(e)}"
            return False

    def require_review(self, decision: AutomatedDecision) -> None:
        """Mark decision as requiring human review."""
        decision.approved = False
        decision.approval_reason = "Requires human review"

    def approve_decision(
        self,
        decision_id: str,
        approved_by: str,
        reason: Optional[str] = None,
    ) -> bool:
        """Approve a decision pending review."""
        decision = self.decisions.get(decision_id)
        if not decision:
            return False

        decision.approved = True
        decision.approval_reason = reason or "Approved by reviewer"
        decision.reviewed_by = approved_by
        decision.reviewed_at = datetime.now().isoformat()

        return self.execute_decision(decision)

    def reject_decision(
        self,
        decision_id: str,
        rejected_by: str,
        reason: str,
    ) -> bool:
        """Reject a decision pending review."""
        decision = self.decisions.get(decision_id)
        if not decision:
            return False

        decision.approved = False
        decision.approval_reason = f"Rejected: {reason}"
        decision.reviewed_by = rejected_by
        decision.reviewed_at = datetime.now().isoformat()

        return True

    def pending_review(self) -> List[AutomatedDecision]:
        """Get decisions pending human review."""
        return [d for d in self.decision_log if not d.approved and d.risk_level != RiskLevel.LOW]

    def get_decisions_by_type(self, decision_type: DecisionType) -> List[AutomatedDecision]:
        """Get all decisions of a specific type."""
        return [d for d in self.decision_log if d.type == decision_type]

    def get_execution_report(self) -> Dict[str, Any]:
        """Generate execution report."""
        executed = [d for d in self.decision_log if d.executed]
        failed = [d for d in self.decision_log if d.executed and d.execution_result != "Success"]

        return {
            "total_decisions": len(self.decision_log),
            "auto_approved": len([d for d in self.decision_log if d.approval_reason == "Auto-approved by policy"]),
            "executed": len(executed),
            "failed": len(failed),
            "pending_review": len(self.pending_review()),
            "by_type": {
                dtype.value: len(self.get_decisions_by_type(dtype))
                for dtype in DecisionType
            },
            "generated": datetime.now().isoformat(),
        }


# Global decision engine instance
_engine: Optional[DecisionEngine] = None


def get_decision_engine() -> DecisionEngine:
    """Get or create global decision engine."""
    global _engine
    if _engine is None:
        _engine = DecisionEngine()
    return _engine


def reset_decision_engine() -> None:
    """Reset to fresh engine (for testing)."""
    global _engine
    _engine = DecisionEngine()
