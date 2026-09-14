"""Evidence Entitlement Evaluator.

Determines what evidence is required to justify particular conclusions.

This is the core of semantic correctness evaluation.

Key principle: A conclusion can be FACTUALLY CORRECT but SEMANTICALLY UNJUSTIFIED.

Example:
  Observation: Status.PHANTOM was removed from production
  Ghost's conclusion: MAJOR regression

  The observation may be factually correct.
  But without additional evidence of:
    - unintended removal
    - semantic breakage
    - current incompatibility

  The MAJOR severity is not justified.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Set, List, Optional, Dict
from .epistemic_model import IntentKind, SemanticCorrectness, EvidenceProvenance


class EvidenceCategory(Enum):
    """Categories of evidence that may support a conclusion."""
    MEMBER_PRODUCTION_HISTORY = auto()      # Was member used in production?
    MEMBER_REMOVAL_HISTORY = auto()         # Was it removed?
    MEMBER_CURRENT_STATE = auto()           # Is it in current code?
    MEMBER_TEST_USAGE = auto()              # Is it used in tests?
    REPLACEMENT_EQUIVALENCE = auto()        # Is there a replacement?
    SEMANTIC_CHANGE_EVIDENCE = auto()       # Evidence of semantic difference?
    UNINTENDED_SIGNAL = auto()              # Evidence of accidental removal?
    INTENTIONAL_SIGNAL = auto()             # Evidence of intentional removal?
    SECURITY_SIGNAL = auto()                # Evidence of security motivation?
    RELEASE_NOTES = auto()                  # Documented in release notes?
    COMMIT_MESSAGE_PATTERN = auto()         # Commit message intent signal?
    DEVELOPER_INTENT = auto()               # Direct evidence of intent?
    REPLACEMENT_VERIFICATION = auto()       # Tested replacement behavior?
    TEMPORAL_CONTEXT = auto()               # When did removal happen?
    SCOPE_CONTEXT = auto()                  # Release/branch-specific?


@dataclass
class EvidenceRequirement:
    """What evidence is required for a conclusion."""
    category: EvidenceCategory
    presence_required: bool = True          # Must be present (vs absent)
    strength_minimum: float = 0.5           # 0.0 - 1.0 confidence minimum
    alternate_requirements: List['EvidenceRequirement'] = field(default_factory=list)
    notes: str = ""


@dataclass
class EntitlementVerdictDetail:
    """Details of an entitlement decision."""
    conclusion: str                         # e.g., "REMOVED_FROM_LIBRARY"

    # What we found
    present_evidence: Set[EvidenceCategory] = field(default_factory=set)
    absent_evidence: Set[EvidenceCategory] = field(default_factory=set)
    weak_evidence: Set[EvidenceCategory] = field(default_factory=set)
    contradicting_evidence: Set[EvidenceCategory] = field(default_factory=set)

    # The verdict
    is_entitled: bool = False
    confidence: float = 0.0
    semantic_correctness: SemanticCorrectness = SemanticCorrectness.UNASKABLE

    # Reasoning
    supporting_evidence: List[str] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)
    disconfirming_evidence: List[str] = field(default_factory=list)
    what_would_change_mind: List[str] = field(default_factory=list)

    # Severity entitlement
    maximum_justified_severity: str = "INFORMATIONAL"  # What's the max justified?
    ghost_claimed_severity: str = "UNKNOWN"
    severity_justified: bool = False


class EvidenceEntitlementEvaluator:
    """Determine if conclusions are justified by evidence."""

    # Evidence requirements for different conclusions
    ENTITLEMENT_RULES = {
        "REMOVED_FROM_LIBRARY": {
            "required": [
                EvidenceCategory.MEMBER_PRODUCTION_HISTORY,
                EvidenceCategory.MEMBER_REMOVAL_HISTORY,
                EvidenceCategory.MEMBER_CURRENT_STATE,
            ],
            "max_severity_without_intent": "INFORMATIONAL",  # Just facts
            "max_severity_intentional": "MINOR",             # Intentional removal OK
            "max_severity_accidental": "MAJOR",              # Accidental is serious
            "max_severity": "MAJOR",                         # Security fix removal is justified MAJOR
        },
        "REGRESSION": {
            "required": [
                EvidenceCategory.MEMBER_PRODUCTION_HISTORY,
                EvidenceCategory.MEMBER_REMOVAL_HISTORY,
                EvidenceCategory.UNINTENDED_SIGNAL,  # Evidence it was accidental
            ],
            "alternate": [
                # OR: semantic breakage evidence
                [EvidenceCategory.SEMANTIC_CHANGE_EVIDENCE,
                 EvidenceCategory.REPLACEMENT_VERIFICATION],
            ],
            "max_severity": "MAJOR",
        },
        "SECURITY_REGRESSION": {
            "required": [
                EvidenceCategory.MEMBER_PRODUCTION_HISTORY,
                EvidenceCategory.MEMBER_REMOVAL_HISTORY,
                EvidenceCategory.SECURITY_SIGNAL,
                EvidenceCategory.SEMANTIC_CHANGE_EVIDENCE,  # Must show how it breaks
            ],
            "max_severity": "CRITICAL",
        },
        "DEAD_CODE_CLEANUP": {
            "required": [
                EvidenceCategory.MEMBER_PRODUCTION_HISTORY,
                EvidenceCategory.MEMBER_REMOVAL_HISTORY,
                EvidenceCategory.INTENTIONAL_SIGNAL,
                # Death evidence: unused after some point
            ],
            "max_severity": "MINOR",
        },
        "TEST_ONLY_MIGRATION": {
            "required": [
                EvidenceCategory.MEMBER_PRODUCTION_HISTORY,
                EvidenceCategory.MEMBER_REMOVAL_HISTORY,
                EvidenceCategory.MEMBER_TEST_USAGE,
                EvidenceCategory.INTENTIONAL_SIGNAL,
            ],
            "max_severity": "INFORMATIONAL",  # Safe by design
        },
    }

    @staticmethod
    def evaluate_entitlement(
        conclusion: str,
        intent_kind: IntentKind,
        evidence_present: Set[EvidenceCategory],
        evidence_absent: Set[EvidenceCategory],
        evidence_weak: Set[EvidenceCategory],
        evidence_contradicting: Set[EvidenceCategory],
        ghost_severity: str = "UNKNOWN"
    ) -> EntitlementVerdictDetail:
        """Evaluate whether a conclusion is entitled.

        Args:
            conclusion: The semantic conclusion (e.g., "REGRESSION", "DEAD_CODE_CLEANUP")
            intent_kind: The inferred intent from independent oracle
            evidence_present: Set of evidence categories we found
            evidence_absent: Set of evidence categories we lack
            evidence_weak: Set of evidence categories with weak signal
            evidence_contradicting: Set of evidence that contradicts conclusion
            ghost_severity: What severity did Ghost claim?

        Returns:
            EntitlementVerdictDetail with full reasoning
        """

        verdict = EntitlementVerdictDetail(
            conclusion=conclusion,
            present_evidence=evidence_present,
            absent_evidence=evidence_absent,
            weak_evidence=evidence_weak,
            contradicting_evidence=evidence_contradicting,
            ghost_claimed_severity=ghost_severity,
        )

        # Check if conclusion has entitlement rules
        if conclusion not in EvidenceEntitlementEvaluator.ENTITLEMENT_RULES:
            verdict.semantic_correctness = SemanticCorrectness.UNASKABLE
            verdict.what_would_change_mind.append(
                f"Define entitlement rules for conclusion: {conclusion}"
            )
            return verdict

        rules = EvidenceEntitlementEvaluator.ENTITLEMENT_RULES[conclusion]

        # Check required evidence
        required = set(rules.get("required", []))
        have_required = required & evidence_present
        missing_required = required - evidence_present

        # Check contradicting evidence
        if evidence_contradicting:
            verdict.semantic_correctness = SemanticCorrectness.CONTRADICTED
            verdict.disconfirming_evidence = [str(e) for e in evidence_contradicting]
            verdict.is_entitled = False
            verdict.confidence = 0.0
            return verdict

        # Base entitlement on required evidence
        if missing_required:
            verdict.is_entitled = False
            verdict.confidence = max(0.0, len(have_required) / len(required))
            verdict.missing_evidence = [str(e) for e in missing_required]
            verdict.what_would_change_mind.append(
                f"Provide evidence for: {', '.join(str(e) for e in missing_required)}"
            )

            # Even if not fully entitled, assess semantic correctness
            if verdict.confidence > 0.5:
                verdict.semantic_correctness = SemanticCorrectness.UNDERCLAIMED
            else:
                verdict.semantic_correctness = SemanticCorrectness.INCONCLUSIVE

            return verdict

        # We have all required evidence
        verdict.is_entitled = True
        verdict.supporting_evidence = [str(e) for e in have_required]

        # Check for weak evidence that undermines confidence
        has_weak_intent = EvidenceCategory.DEVELOPER_INTENT in evidence_weak
        if has_weak_intent and intent_kind == IntentKind.UNKNOWN_INTENT:
            # Weak intent signal makes verdict inconclusive
            verdict.semantic_correctness = SemanticCorrectness.INCONCLUSIVE
            verdict.confidence = 0.3
            verdict.what_would_change_mind.append(
                "Clearer evidence of intent (commit messages, deprecation, etc.)"
            )
            return verdict

        # Now assess severity entitlement
        max_justified = rules.get("max_severity_without_intent", "INFORMATIONAL")

        # Adjust based on inferred intent
        if intent_kind == IntentKind.INTENTIONAL_REFACTOR:
            max_justified = rules.get("max_severity_intentional", "MINOR")
        elif intent_kind == IntentKind.ACCIDENTAL_REMOVAL:
            max_justified = rules.get("max_severity_accidental", "MAJOR")
        elif intent_kind == IntentKind.SECURITY_FIX:
            max_justified = rules.get("max_severity", "CRITICAL")

        verdict.maximum_justified_severity = max_justified

        # Check if Ghost's severity is justified
        severity_order = {"INFORMATIONAL": 1, "MINOR": 2, "MAJOR": 3, "CRITICAL": 4}

        ghost_level = severity_order.get(ghost_severity, 0)
        max_level = severity_order.get(max_justified, 0)

        if ghost_level > max_level:
            verdict.severity_justified = False
            verdict.semantic_correctness = SemanticCorrectness.OVERCLAIMED
            verdict.confidence = 0.8  # High confidence in overclaim
            verdict.what_would_change_mind.append(
                f"Evidence of security impact or unintended removal (to justify {ghost_severity})"
            )
        elif ghost_level < max_level and max_level >= 2:  # MINOR or higher
            verdict.severity_justified = True
            verdict.semantic_correctness = SemanticCorrectness.UNDERCLAIMED
            verdict.confidence = 0.7
            verdict.what_would_change_mind.append(
                f"Accept that {max_justified} is appropriate for this scenario"
            )
        else:
            verdict.severity_justified = True
            verdict.semantic_correctness = SemanticCorrectness.JUSTIFIED
            verdict.confidence = 0.9

        return verdict


def classify_evidence_from_oracle_results(
    oracle_results: Dict,
    test_imports_member: bool = False,
) -> tuple[Set[EvidenceCategory], Set[EvidenceCategory]]:
    """Convert oracle results into evidence categories.

    Args:
        oracle_results: Output from Evaluator.run_oracles()
        test_imports_member: Whether tests reference the member

    Returns:
        (present_evidence, absent_evidence)
    """

    present = set()
    absent = set()

    # Analyze current state
    current_state = oracle_results.get("current_state", {})
    history = oracle_results.get("history", {})

    # Production history: if member exists in history, we have evidence
    if history.get("inferred_intent"):
        present.add(EvidenceCategory.MEMBER_PRODUCTION_HISTORY)
    else:
        absent.add(EvidenceCategory.MEMBER_PRODUCTION_HISTORY)

    # Removal history: if history shows refactor/cleanup patterns
    if "refactor" in str(history.get("inferred_intent", "")).lower():
        present.add(EvidenceCategory.MEMBER_REMOVAL_HISTORY)
        present.add(EvidenceCategory.INTENTIONAL_SIGNAL)
    elif "fix" in str(history.get("inferred_intent", "")).lower():
        present.add(EvidenceCategory.MEMBER_REMOVAL_HISTORY)
        present.add(EvidenceCategory.SECURITY_SIGNAL)
    else:
        present.add(EvidenceCategory.MEMBER_REMOVAL_HISTORY)

    # Current state: member not in production
    members_in_prod = set(current_state.get("members_in_production", []))
    if not members_in_prod:
        present.add(EvidenceCategory.MEMBER_CURRENT_STATE)
    else:
        absent.add(EvidenceCategory.MEMBER_CURRENT_STATE)

    # Test usage
    if test_imports_member:
        present.add(EvidenceCategory.MEMBER_TEST_USAGE)
    else:
        absent.add(EvidenceCategory.MEMBER_TEST_USAGE)

    return present, absent
