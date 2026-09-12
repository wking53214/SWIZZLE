"""The judgement, against findings written by hand.

These do not run ghost_buster. They pin the rules down: what counts as
named, what counts as nearly named, and what a warp is allowed to tolerate
without tolerating its own answer away.
"""

from __future__ import annotations

from swizzle.schema import Disclosure, Proof, TrueName, Verdict, Warp
from swizzle.verdict import judge

HOLDS = Proof(holds=True, kind="executed", account="demonstrated")
FAILS = Proof(holds=False, kind="failed", account="did not demonstrate")


def _finding(detector, file, line):
    return {"detector": detector, "evidence": {"file": file, "line_start": line}}


def _defect(**over):
    base = dict(
        name="w", targets="sql_injection", intent="x" * 70,
        disclosure=Disclosure.UNDISCLOSED, files={"app/q.py": ""},
        prove=lambda root: HOLDS,
        true_name=TrueName("sql_injection", "app/q.py", 10, 12, "because"),
        tolerated=("dead_code",),
    )
    base.update(over)
    return Warp(**base)


def _decoy(**over):
    base = dict(
        name="d", targets="sql_injection", intent="x" * 70,
        disclosure=Disclosure.UNDISCLOSED, files={"app/q.py": ""},
        prove=lambda root: HOLDS, true_name=None,
        forbidden=("sql_injection",),
    )
    base.update(over)
    return Warp(**base)


def test_named_in_the_span_is_banished():
    out = judge(_defect(), [_finding("sql_injection", "app/q.py", 11)], HOLDS)
    assert out.verdict is Verdict.BANISHED


def test_a_finding_with_no_line_is_accepted():
    """Some detectors report whole files. That is a format, not a miss."""
    out = judge(_defect(), [_finding("sql_injection", "app/q.py", None)], HOLDS)
    assert out.verdict is Verdict.BANISHED


def test_silence_is_an_escape():
    out = judge(_defect(), [], HOLDS)
    assert out.verdict is Verdict.ESCAPED


def test_right_detector_wrong_line_is_a_misnaming():
    out = judge(_defect(), [_finding("sql_injection", "app/q.py", 40)], HOLDS)
    assert out.verdict is Verdict.MISNAMED


def test_another_detector_on_the_defect_is_a_misnaming():
    out = judge(_defect(), [_finding("long_function", "app/q.py", 11)], HOLDS)
    assert out.verdict is Verdict.MISNAMED


def test_tolerated_noise_elsewhere_does_not_rescue_an_escape():
    out = judge(_defect(), [_finding("dead_code", "app/q.py", None)], HOLDS)
    assert out.verdict is Verdict.ESCAPED


def test_the_right_detector_in_another_file_is_not_credited():
    """A true finding about a different function is not a near miss."""
    out = judge(_defect(), [_finding("sql_injection", "app/other.py", 3)], HOLDS)
    assert out.verdict is Verdict.ESCAPED


def test_a_quiet_decoy_is_dismissed():
    out = judge(_decoy(), [_finding("dead_code", "app/q.py", None)], HOLDS)
    assert out.verdict is Verdict.DISMISSED


def test_a_flagged_decoy_is_a_false_positive():
    out = judge(_decoy(), [_finding("sql_injection", "app/q.py", 3)], HOLDS)
    assert out.verdict is Verdict.CONJURED


def test_a_failed_proof_is_never_an_escape():
    """SWIZZLE's own failure must not read as a blind spot."""
    out = judge(_defect(), [], FAILS)
    assert out.verdict is Verdict.UNSUMMONED
    out = judge(_decoy(), [_finding("sql_injection", "app/q.py", 3)], FAILS)
    assert out.verdict is Verdict.UNSUMMONED


def test_a_missing_proof_is_never_an_escape():
    out = judge(_defect(), [], None)
    assert out.verdict is Verdict.UNSUMMONED
