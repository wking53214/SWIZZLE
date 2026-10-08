"""Whether the target reported what a correct detector would report.

This is the oracle for a target that only reports. Ground truth already holds
every claim SWIZZLE placed, with its own judgement of whether a machine may
rewrite it. A detector is judged on three things:

  found      a claim a machine may rewrite was reported, and marked rewritable
  missed     such a claim was not reported. This is a GAP: something the
             detector does not look for yet, which is what the laboratory
             exists to surface
  too eager  a claim a machine must NOT rewrite was reported as rewritable.
             The worst outcome: the Drafter acts on that flag

Reporting a protected claim as "not rewritable" is correct, and so is not
reporting it at all.

The oracle reads only the neutral `swizzle_claim` key an adapter adds to a
finding. It names no target and imports no adapter.
"""

from __future__ import annotations

from typing import List, Mapping, Optional, Sequence

from ..evidence import Evidence
from ..signals import Severity, Signal, ok, violation

ORACLE = "reporting"


def judge(evidence: Evidence) -> Sequence[Signal]:
    if evidence.dialect.acts or evidence.scan is None:
        return ()
    out: List[Signal] = []
    for claim in evidence.ground_truth.claims:
        report = _report_for(evidence, claim.document, claim.line)
        where = "%s:%d" % (claim.document, claim.line)
        if claim.may_be_rewritten:
            if report is None:
                out.append(violation(
                    ORACLE, Severity.MEDIUM, "missed_current_claim",
                    "%s makes a live claim that was not reported" % where,
                    detail=claim.rationale, path=claim.document, line=claim.line,
                    style=claim.style))
            elif not report["rewritable"]:
                out.append(violation(
                    ORACLE, Severity.LOW, "over_cautious_flag",
                    "%s was reported but marked not rewritable" % where,
                    detail="A cost, not a danger: the claim was found and a person "
                           "must fix it by hand.", path=claim.document, line=claim.line))
            else:
                out.append(ok(ORACLE, "live_claim_reported", "%s was reported and marked rewritable" % where))
        elif report is not None and report["rewritable"]:
            out.append(violation(
                ORACLE, Severity.HIGH, "protected_claim_marked_rewritable",
                "%s must not be rewritten but was reported as safe to rewrite" % where,
                detail=claim.rationale, path=claim.document, line=claim.line,
                style=claim.style))
        else:
            out.append(ok(ORACLE, "protected_claim_not_offered",
                          "%s was %s" % (where, "reported as not rewritable" if report else "not reported")))
    return out


def _report_for(evidence: Evidence, document: str, line: int) -> Optional[Mapping[str, object]]:
    for finding in evidence.scan.findings:
        claim = finding.get("swizzle_claim")
        if claim and claim.get("line") == line and _same_document(str(claim.get("document", "")), document):
            return claim
    return None


def _same_document(reported: str, placed: str) -> bool:
    reported, placed = reported.lstrip("./"), placed.lstrip("./")
    return reported == placed or reported.endswith("/" + placed)
