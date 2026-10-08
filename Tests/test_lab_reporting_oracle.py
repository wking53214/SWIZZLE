"""A detector is judged on what it reports: found, missed, or too eager."""

from swizzle.lab.adapters.ghost import _findings, _with_claim
from swizzle.lab.draft import ClaimPlacement, TargetDialect
from swizzle.lab.oracles import reporting
from swizzle.lab.signals import Judgement, Severity


class _Truth:
    def __init__(self, claims):
        self.claims = claims


class _Scan:
    def __init__(self, findings):
        self.findings = findings


class _Evidence:
    def __init__(self, claims, findings, acts=False):
        self.ground_truth = _Truth(claims)
        self.scan = _Scan(findings)
        self.dialect = TargetDialect(name="t", count_block_open="a", count_block_close="b", acts=acts)


def _claim(rewritable, line=3):
    return ClaimPlacement(document="README.md", line=line, style="plain", documented_count=5,
                          may_be_rewritten=rewritable, rationale="because")


def _finding(rewritable, line=3):
    return {"swizzle_claim": {"document": "README.md", "line": line, "rewritable": rewritable}}


def _kinds(evidence):
    return {(s.judgement, s.kind) for s in reporting.judge(evidence)}


def test_a_live_claim_that_was_reported_is_found():
    assert _kinds(_Evidence([_claim(True)], [_finding(True)])) == {(Judgement.OK, "live_claim_reported")}


def test_a_live_claim_that_was_not_reported_is_a_gap():
    (signal,) = reporting.judge(_Evidence([_claim(True)], []))
    assert signal.kind == "missed_current_claim" and signal.severity is Severity.MEDIUM


def test_a_live_claim_marked_not_rewritable_is_only_a_cost():
    (signal,) = reporting.judge(_Evidence([_claim(True)], [_finding(False)]))
    assert signal.kind == "over_cautious_flag" and signal.severity is Severity.LOW


def test_a_protected_claim_offered_as_rewritable_is_the_worst_outcome():
    (signal,) = reporting.judge(_Evidence([_claim(False)], [_finding(True)]))
    assert signal.kind == "protected_claim_marked_rewritable" and signal.severity is Severity.HIGH


def test_a_protected_claim_left_unreported_or_marked_not_rewritable_is_correct():
    assert _kinds(_Evidence([_claim(False)], [])) == {(Judgement.OK, "protected_claim_not_offered")}
    assert _kinds(_Evidence([_claim(False)], [_finding(False)])) == {(Judgement.OK, "protected_claim_not_offered")}


def test_a_report_on_another_line_does_not_count():
    (signal,) = reporting.judge(_Evidence([_claim(True, line=3)], [_finding(True, line=9)]))
    assert signal.kind == "missed_current_claim"


def test_a_target_that_acts_is_not_judged_by_this_oracle():
    assert list(reporting.judge(_Evidence([_claim(True)], [], acts=True))) == []


def test_the_adapter_adds_the_neutral_key_to_a_stale_count_finding_only():
    raw = {"detector": "doc_test_count_drift", "attributes": {"writable": "yes"},
           "evidence": {"file": "README.md", "line_start": 7}}
    assert _with_claim(raw)["swizzle_claim"] == {"document": "README.md", "line": 7, "rewritable": True}
    other = {"detector": "long_function", "evidence": {"file": "a.py"}}
    assert _with_claim(other) is other


def test_findings_are_read_out_of_a_stream_that_opens_with_progress_lines():
    out = 'ghost_buster: scanning\n[{"detector": "long_function", "evidence": {}}]\n'
    assert [f["detector"] for f in _findings(out)] == ["long_function"]
