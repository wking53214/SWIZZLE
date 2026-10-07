"""SWIZZLE x TOUCHSTONE: the judging rules, then the live pairing.

The unit tests feed `judge` hand-written findings so every outcome is
pinned without ghost_buster in the room. The last two run the real thing
and skip, visibly, when either checkout is absent.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from swizzle import touchstone as ts

ROOT = Path(__file__).resolve().parents[1]


def _staged(tmp_path: Path) -> Path:
    s = tmp_path / "stage"
    (s / "specimens").mkdir(parents=True)
    (s / "specimens" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (s / "specimens" / "b.py").write_text("y = 1\n", encoding="utf-8")
    (s / "specimens" / "c.py").write_text(
        "def f():\n    pass\n    verdict = EvaluationVerdict.CRITICAL\n", encoding="utf-8")
    return s


def _finding(stage, rel, detector, line=None, related=(), severity="minor"):
    return {"detector": detector, "severity": severity, "summary": detector,
            "evidence": {"absolute_file": str(stage / rel), "line_start": line,
                         "related_files": list(related)}}


def _key(**entries):
    return {sid: dict(specimen_id=sid, **e) for sid, e in entries.items()}


def test_silence_over_a_failure_mode_is_an_escape(tmp_path):
    s = _staged(tmp_path)
    key = _key(fm_3_1_silent_pass=dict(specimen_class="FAILURE_MODE", path="specimens/a.py",
                                       expected_verdict="REFUSE"))
    [j] = ts.judge(key, [], s)
    assert j.outcome == ts.ESCAPED


def test_duplicate_must_connect_both_files(tmp_path):
    s = _staged(tmp_path)
    meta = {"companions": ["specimens/b.py"]}
    key = _key(fm_3_3_flattening_duplicate=dict(
        specimen_class="FAILURE_MODE", path="specimens/a.py", metadata=meta,
        expected_verdict="SAME_CONTENT"))
    alone = [_finding(s, "specimens/a.py", "drifted_copy", related=["specimens/zzz.py"])]
    assert ts.judge(key, alone, s)[0].outcome == ts.MISNAMED
    linked = [_finding(s, "specimens/a.py", "drifted_copy", related=["specimens/b.py"])]
    assert ts.judge(key, linked, s)[0].outcome == ts.BANISHED


def test_anchored_failure_mode_needs_the_right_line(tmp_path):
    s = _staged(tmp_path)
    key = _key(fm_3_4_unreachable_branch=dict(
        specimen_class="FAILURE_MODE", path="specimens/c.py", expected_verdict="UNREACHABLE"))
    far = [_finding(s, "specimens/c.py", "dead_code", line=40)]
    assert ts.judge(key, far, s)[0].outcome == ts.MISNAMED
    near = [_finding(s, "specimens/c.py", "unreachable_declared_state", line=3)]
    assert ts.judge(key, near, s)[0].outcome == ts.BANISHED


def test_reference_refused_is_conjured_and_style_is_not(tmp_path):
    s = _staged(tmp_path)
    key = _key(reference_a=dict(specimen_class="REFERENCE", path="specimens/a.py",
                                expected_verdict="ACCEPT"))
    style = [_finding(s, "specimens/a.py", "placeholder_name")]
    assert ts.judge(key, style, s)[0].outcome == ts.DISMISSED
    refused = [_finding(s, "specimens/a.py", "unassessable_file", severity="major")]
    assert ts.judge(key, refused, s)[0].outcome == ts.CONJURED


def test_out_of_scope_classes_are_abstentions_not_skips(tmp_path):
    s = _staged(tmp_path)
    key = _key(pair_x=dict(specimen_class="RECONSTRUCTION_PAIR", path="specimens/a.py",
                           expected_verdict="FAITHFUL"))
    [j] = ts.judge(key, [_finding(s, "specimens/a.py", "dead_code")], s)
    assert j.outcome == ts.OUT_OF_SCOPE and j.findings == [("dead_code", "minor")]


def test_unknown_failure_mode_is_unmapped_and_blocks(tmp_path):
    s = _staged(tmp_path)
    key = _key(fm_9_9_new=dict(specimen_class="FAILURE_MODE", path="specimens/a.py",
                               expected_verdict="REFUSE"))
    card = ts.Scorecard("t", "p", ts.judge(key, [], s))
    assert card.judgements[0].outcome == ts.UNMAPPED
    assert ts.blocked(card) == ["fm_9_9_new"]


def test_missing_registry_is_loud(tmp_path):
    with pytest.raises(ts.TouchstoneUnavailable):
        ts.load_answer_key(tmp_path)


def test_comparison_flags_a_regression():
    def card(outcome):
        return ts.Scorecard("t", "p", [ts.Judgement("fm", "FAILURE_MODE", "REFUSE", outcome)])
    assert ts.Comparison(card(ts.BANISHED), card(ts.ESCAPED)).regressed()
    assert not ts.Comparison(card(ts.ESCAPED), card(ts.BANISHED)).regressed()


LIVE_TS = ts.locate_touchstone()
LIVE_GHOST = os.environ.get("GHOST_TOOLS") or (ROOT.parent / "ghost_tools")
live = pytest.mark.skipif(
    LIVE_TS is None or not (Path(LIVE_GHOST) / "ghost_buster" / "cli.py").is_file(),
    reason="needs TOUCHSTONE (with registry.json) and ghost_tools checkouts")


@live
def test_every_touchstone_failure_mode_has_a_true_name():
    key = ts.load_answer_key(LIVE_TS)
    modes = {sid for sid, e in key.items() if e["specimen_class"] == "FAILURE_MODE"}
    assert modes and modes <= set(ts.TRUE_NAMES)


@live
def test_live_scorecard_runs_and_is_trustworthy():
    done = subprocess.run(
        (sys.executable, "-m", "swizzle", "touchstone", "--json",
         "--touchstone", str(LIVE_TS), "--ghost-tools", str(LIVE_GHOST)),
        cwd=str(ROOT), capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-800:]
    card = json.loads(done.stdout)
    assert "claims hold" in card["proof"]
    outcomes = {j["outcome"] for j in card["judgements"]}
    assert not outcomes & {ts.UNMAPPED, ts.UNSUMMONED}


def test_a_relation_mention_does_not_catch_a_property(tmp_path):
    """A finding about another file that merely lists the specimen as related
    must not count as naming the silent pass."""
    s = _staged(tmp_path)
    key = _key(fm_3_1_silent_pass=dict(specimen_class="FAILURE_MODE", path="specimens/a.py",
                                       expected_verdict="REFUSE"))
    elsewhere = [_finding(s, "specimens/b.py", "name_disagreement", related=["specimens/a.py"])]
    assert ts.judge(key, elsewhere, s)[0].outcome == ts.ESCAPED


def test_bare_filename_never_matches(tmp_path):
    assert not ts._touches(["", "a.py"], "specimens/a.py")
    assert ts._touches(["", "pairs/a.py"], "specimens/pairs/a.py")


def test_malformed_registry_is_unavailable_not_a_crash(tmp_path):
    (tmp_path / "touchstone_production").mkdir()
    (tmp_path / "touchstone_production" / "registry.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ts.TouchstoneUnavailable):
        ts.load_answer_key(tmp_path)
