"""Red-team follow-ups for `swizzle assay`: what the answer key really proved, what Ghost
really looked at, a floor that means something, which copies were used, and Ctrl-C.

Every test here failed on the code that preceded it.
"""
import json
import subprocess
from pathlib import Path

import pytest

from swizzle import assay as ts
from swizzle import cli
from swizzle.invoke import Findings, scan

# ------------------------------------------------------------------ helpers

SUMMARY_NOW = ("answer key status: ANSWER_KEY_UNVALIDATED (9 verified by execution, 1 by static check, "
               "15 unvalidated, of 25 entries)")


def _fake_assay(tmp_path, verifier_output="29/29 manifest claims hold\n" + SUMMARY_NOW, code=0, modes=5, ids=None):
    root = tmp_path / "assay"
    (root / "assay_production").mkdir(parents=True)
    registry = {sid: {"specimen_class": "FAILURE_MODE", "path": "specimens/a.py", "expected_verdict": "REFUSE"}
                for sid in (ids or ["m%d" % i for i in range(modes)])}
    (root / "assay_production" / "registry.json").write_text(json.dumps(registry))
    (root / "verify_manifest.py").write_text("print(%r)\nraise SystemExit(%d)\n" % (verifier_output, code))
    return root


def _ghost_dir(tmp_path):
    ghost = tmp_path / "ghost"
    (ghost / "ghost_buster").mkdir(parents=True)
    (ghost / "ghost_buster" / "cli.py").write_text("")
    return ghost


def _card(proof="29/29 manifest claims hold", breakdown=None, caught=3, **kw):
    js = [ts.Judgement("m%d" % i, "FAILURE_MODE", "X", ts.BANISHED if i < caught else ts.ESCAPED)
          for i in range(5)]
    return ts.Scorecard("k", proof, js, breakdown=breakdown, **kw)


def _levels(execution, static, unvalidated):
    return {"verified_by_execution": execution, "verified_by_static_check": static,
            "unvalidated": unvalidated, "total": execution + static + unvalidated}


# ------------------------------------------------- 1. what the key really proved

def test_breakdown_is_read_from_the_current_summary_line():
    got = ts.parse_breakdown("29/29 manifest claims hold\n" + SUMMARY_NOW + "\n")
    assert got == _levels(9, 1, 15)


@pytest.mark.parametrize("line", [
    'ASSAY_SUMMARY {"VERIFIED_BY_EXECUTION": 9, "VERIFIED_BY_STATIC_CHECK": 1, "UNVALIDATED": 15}',
    'ASSAY_SUMMARY {"counts": {"verified_by_execution": 9, "verified_by_static_check": 1, "unvalidated": 15}}',
    "VERIFIED_BY_EXECUTION=9 VERIFIED_BY_STATIC_CHECK=1 UNVALIDATED=15",
    "entries: 9 verified by execution, 1 by static check, 15 unvalidated",
])
def test_breakdown_tolerates_other_spellings(line):
    got = ts.parse_breakdown("29/29 manifest claims hold\n" + line + "\n")
    assert got is not None and (got["verified_by_execution"], got["verified_by_static_check"],
                                got["unvalidated"]) == (9, 1, 15)


def test_no_summary_line_means_no_breakdown_never_a_guess():
    assert ts.parse_breakdown("29/29 manifest claims hold\n") is None
    assert ts.parse_breakdown("9 verified by execution") is None      # a partial line is not a breakdown


def test_mostly_unvalidated_key_is_not_called_reliable_without_saying_so():
    card = _card(breakdown=_levels(9, 1, 15))
    d = card.to_dict()
    assert d["key_proven"] is True
    assert d["numbers_reliable"] is False
    assert d["key_breakdown"] == {"available": True, **_levels(9, 1, 15)}
    assert "unvalidated" in d["numbers_reliability_note"]
    text = card.render()
    assert "15 unvalidated" in text and "NOT FULLY VALIDATED" in text


def test_missing_breakdown_says_so_in_text_and_json_and_is_not_reliable():
    card = _card(breakdown=None)
    d = card.to_dict()
    assert d["key_breakdown"] == {"available": False, "note": "breakdown unavailable"}
    assert d["numbers_reliable"] is False
    assert "breakdown unavailable" in card.render()


def test_a_fully_validated_key_is_reliable():
    card = _card(breakdown=_levels(20, 5, 0))
    assert card.to_dict()["numbers_reliable"] is True
    assert "NOT FULLY VALIDATED" not in card.render()


def test_cli_surfaces_the_breakdown_from_the_verifier(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ASSAY", str(_fake_assay(tmp_path, ids=["fm_3_1_silent_pass"])))
    ghost = _ghost_dir(tmp_path)
    monkeypatch.setattr(ts, "stage", lambda *a, **k: tmp_path)
    monkeypatch.setattr(ts, "scan", lambda *a, **k: Findings([]))
    assert cli.main(["assay", "--ghost-tools", str(ghost), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["key_breakdown"]["unvalidated"] == 15
    assert payload["numbers_reliable"] is False


def test_the_verifiers_real_failure_reason_is_relayed(tmp_path, monkeypatch, capsys):
    out = ("  PASS  table ok\n"
           "  FAIL  3.4 unreachable branch: the 100,000-sample search still finds no CRITICAL verdict\n"
           "  FAIL  registry: each entry's validation status is what this run really asserted\n"
           "\n24/26 manifest claims hold\n\nWHAT FAILED\n\n"
           "* 3.4 unreachable branch: the 100,000-sample search still finds no CRITICAL verdict\n"
           "    What happened: numpy is not installed in the sandbox\n")
    monkeypatch.setenv("ASSAY", str(_fake_assay(tmp_path, out, code=1)))
    ghost = _ghost_dir(tmp_path)
    assert cli.main(["assay", "--ghost-tools", str(ghost)]) == 2
    err = capsys.readouterr().err
    assert "3.4 unreachable branch" in err
    assert "numpy is not installed" in err
    assert "24/26" in err


def test_a_verifier_that_crashes_with_no_summary_still_gives_its_last_words(tmp_path):
    root = _fake_assay(tmp_path)
    (root / "verify_manifest.py").write_text("import sys\nsys.stderr.write('Traceback\\nKeyError: boom\\n')\nraise SystemExit(1)\n")
    ok, why = ts.prove_answer_key(root)
    assert not ok and "KeyError: boom" in why and "exited 1" in why


# ------------------------------------------------------ 2. a Ghost that did not look

def _stage(tmp_path):
    s = tmp_path / "stage"
    (s / "specimens").mkdir(parents=True, exist_ok=True)
    (s / "specimens" / "ref.py").write_text("x = 1\n")
    (s / "specimens" / "mode.py").write_text("# nothing\n")
    return s


def _key():
    return {"fm_3_1_silent_pass": dict(specimen_id="fm_3_1_silent_pass", specimen_class="FAILURE_MODE",
                                       path="specimens/mode.py", expected_verdict="REFUSE"),
            "ref_a": dict(specimen_id="ref_a", specimen_class="REFERENCE", path="specimens/ref.py",
                          expected_verdict="ACCEPT")}


def _outcomes(findings, tmp_path):
    return {j.specimen_id: j for j in ts.judge(_key(), findings, _stage(tmp_path))}


def test_silence_from_a_blind_ghost_is_not_acceptance(tmp_path):
    blind = Findings([], ["structural: a detector raised"], blind=["structural: a detector raised"])
    js = _outcomes(blind, tmp_path)
    assert js["ref_a"].outcome == ts.UNRELIABLE
    assert "structural" in js["ref_a"].unreliable_because[0]
    assert js["fm_3_1_silent_pass"].outcome == ts.ESCAPED            # still a miss, now with the caveat
    assert js["fm_3_1_silent_pass"].unreliable_because


def test_silence_from_a_seeing_ghost_is_still_acceptance(tmp_path):
    for clean in ([], Findings([])):
        assert _outcomes(clean, tmp_path)["ref_a"].outcome == ts.DISMISSED


def test_an_unparsable_file_taints_only_that_specimen(tmp_path):
    found = Findings([], ["parse: 1 file(s) could not be parsed"], unparsable={"specimens/ref.py": "SyntaxError"})
    assert found.blind == []
    assert _outcomes(found, tmp_path)["ref_a"].outcome == ts.UNRELIABLE
    elsewhere = Findings([], ["parse: 1"], unparsable={"specimens/mode.py": "SyntaxError"})
    assert _outcomes(elsewhere, tmp_path)["ref_a"].outcome == ts.DISMISSED


def test_the_totals_separate_reliable_acceptance_from_unreliable(tmp_path):
    blind = Findings([], blind=["a baseline hid 2 finding(s) from this scan"])
    card = ts.Scorecard("k", "29/29 manifest claims hold", ts.judge(_key(), blind, _stage(tmp_path)),
                        blind=list(blind.blind))
    numbers = card.numbers()
    assert numbers["references_accepted_reliable"] == 0
    assert numbers["references_accepted_but_ghost_did_not_fully_look"] == 1
    text = card.render()
    assert "accepted (reliable) 0 of 1" in text and "accepted but Ghost did not fully look 1" in text
    assert card.to_dict()["scan_blind"] == ["a baseline hid 2 finding(s) from this scan"]


def _ghost_stub(tmp_path, body, code=0):
    ghost = tmp_path / "ghost_stub"
    (ghost / "ghost_buster").mkdir(parents=True)
    (ghost / "ghost_buster" / "__init__.py").write_text("")
    (ghost / "ghost_buster" / "cli.py").write_text(
        "import sys\nsys.stdout.write(%r)\nraise SystemExit(%d)\n" % (body, code))
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    return ghost, repo


def test_baseline_suppression_in_ghosts_envelope_is_read(tmp_path):
    body = json.dumps({"status": "ok", "exit_code": 0, "findings": [], "unmeasured": [],
                       "baseline": {"path": "/x/.ghost_baseline.json", "suppressed": 3}})
    ghost, repo = _ghost_stub(tmp_path, body)
    found = scan(repo, ghost)
    assert found.suppressed == 3 and found.baseline_path == "/x/.ghost_baseline.json"
    assert "hid 3 finding" in found.blind[0]


def test_old_and_clean_new_envelopes_are_not_blind(tmp_path):
    ghost, repo = _ghost_stub(tmp_path, "[]")
    assert scan(repo, ghost).blind == []
    body = json.dumps({"status": "ok", "exit_code": 0, "findings": [], "unmeasured": [],
                       "baseline": {"path": "p", "suppressed": 0}, "scan": {"unparsable": []}})
    ghost, repo = _ghost_stub(tmp_path / "b", body)
    assert scan(repo, ghost).blind == []


def test_an_incomplete_scan_with_no_reason_is_blind_and_a_named_unparsable_file_is_per_file(tmp_path):
    body = json.dumps({"status": "incomplete", "exit_code": 1, "findings": [], "unmeasured": []})
    ghost, repo = _ghost_stub(tmp_path, body, 1)
    assert "incomplete" in scan(repo, ghost).blind[0]
    body = json.dumps({"status": "incomplete", "exit_code": 1, "findings": [],
                       "scan": {"unparsable": [{"file": "specimens/ref.py", "reason": "SyntaxError"}]},
                       "unmeasured": [{"check": "parse", "state": "unparsable", "by_request": False,
                                       "reason": "1 file(s) could not be parsed, so the code detectors skipped them"}]})
    ghost, repo = _ghost_stub(tmp_path / "c", body, 1)
    found = scan(repo, ghost)
    assert found.blind == [] and found.unparsable == {"specimens/ref.py": "SyntaxError"}


# --------------------------------------------------------------- 3. the floor

def _run_assay(tmp_path, monkeypatch, card, *argv):
    monkeypatch.setenv("ASSAY", str(_fake_assay(tmp_path)))
    ghost = _ghost_dir(tmp_path)
    monkeypatch.setattr(ts, "run", lambda *a, **k: card)
    return cli.main(["assay", "--ghost-tools", str(ghost)] + list(argv))


@pytest.mark.parametrize("floor", ["0", "-1", "-5", "6", "100"])
def test_a_floor_outside_one_to_the_number_of_failure_modes_is_exit_2(tmp_path, monkeypatch, capsys, floor):
    assert _run_assay(tmp_path, monkeypatch, _card(caught=5), "--floor", floor) == 2
    err = capsys.readouterr().err
    assert "--floor" in err and "from 1 to 5" in err and "Traceback" not in err


@pytest.mark.parametrize("floor", ["1", "3", "5"])
def test_a_floor_in_range_is_accepted(tmp_path, monkeypatch, floor):
    assert _run_assay(tmp_path, monkeypatch, _card(caught=5), "--floor", floor) == 0


def test_an_out_of_range_floor_is_rejected_before_anything_is_scored(tmp_path, monkeypatch):
    monkeypatch.setenv("ASSAY", str(_fake_assay(tmp_path)))
    monkeypatch.setattr(ts, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("scored")))
    assert cli.main(["assay", "--ghost-tools", str(_ghost_dir(tmp_path)), "--floor", "0"]) == 2


def test_a_floor_shortfall_explained_only_by_blindness_is_undecided_not_a_failure(tmp_path, monkeypatch, capsys):
    judgements = [ts.Judgement("m0", "FAILURE_MODE", "X", ts.BANISHED),
                  ts.Judgement("m1", "FAILURE_MODE", "X", ts.ESCAPED, unreliable_because=["a check did not run"]),
                  ts.Judgement("m2", "FAILURE_MODE", "X", ts.ESCAPED, unreliable_because=["a check did not run"]),
                  ts.Judgement("m3", "FAILURE_MODE", "X", ts.ESCAPED),
                  ts.Judgement("m4", "FAILURE_MODE", "X", ts.ESCAPED)]
    card = ts.Scorecard("k", "29/29 manifest claims hold", judgements, blind=["a check did not run"])
    assert _run_assay(tmp_path, monkeypatch, card, "--floor", "3") == 2          # 1 caught, 3 possible
    assert "FLOOR UNDECIDED" in capsys.readouterr().out
    assert _run_assay(tmp_path / "x", monkeypatch, card, "--floor", "4") == 1    # fails even if blindness is forgiven


def test_unreliable_acceptances_never_help_a_floor(tmp_path, monkeypatch):
    card = _card(caught=2)
    card.judgements.append(ts.Judgement("ref", "REFERENCE", "ACCEPT", ts.UNRELIABLE))
    assert _run_assay(tmp_path, monkeypatch, card, "--floor", "3") == 1


# -------------------------------------------------------------- 5. which copies

def _git_checkout(path: Path, files: dict) -> str:
    path.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text)
    env = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null", "PATH": __import__("os").environ["PATH"]}
    for step in (("init", "-q"), ("add", "-A"),
                 ("-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "x")):
        subprocess.run(("git",) + step, cwd=str(path), env=env, check=True, capture_output=True)
    return subprocess.run(("git", "rev-parse", "HEAD"), cwd=str(path), env=env, check=True,
                          capture_output=True, text=True).stdout.strip()


def test_the_paths_and_commits_used_are_printed_and_in_the_json(tmp_path, monkeypatch, capsys):
    assay_dir = _fake_assay(tmp_path)
    assay_sha = _git_checkout(assay_dir, {"README.md": "x"})
    ghost = _ghost_dir(tmp_path)
    ghost_sha = _git_checkout(ghost, {"pyproject.toml": '[project]\nname = "g"\nversion = "1.2.3"\n'})
    monkeypatch.setenv("ASSAY", str(assay_dir))
    monkeypatch.setattr(ts, "run", lambda *a, **k: _card(breakdown=_levels(20, 5, 0)))
    assert cli.main(["assay", "--ghost-tools", str(ghost)]) == 0
    text = capsys.readouterr().out
    assert str(assay_dir) in text and assay_sha[:12] in text
    assert str(ghost) in text and ghost_sha[:12] in text and "1.2.3" in text
    assert cli.main(["assay", "--ghost-tools", str(ghost), "--json"]) == 0
    sources = json.loads(capsys.readouterr().out)["sources"]
    assert sources["assay_commit"] == assay_sha and sources["ghost_tools_commit"] == ghost_sha
    assert sources["ghost_tools_version"] == "1.2.3"
    assert sources["assay_found_by"] == "$ASSAY"


def test_an_unreadable_commit_is_said_to_be_unreadable(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ASSAY", str(_fake_assay(tmp_path)))
    monkeypatch.setattr(ts, "run", lambda *a, **k: _card(breakdown=_levels(20, 5, 0)))
    assert cli.main(["assay", "--ghost-tools", str(_ghost_dir(tmp_path)), "--json"]) == 0
    sources = json.loads(capsys.readouterr().out)["sources"]
    assert sources["assay_commit"] is None and sources["ghost_tools_commit"] is None


def test_a_sibling_ghost_is_named_as_a_sibling(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ASSAY", str(_fake_assay(tmp_path)))
    ghost = _ghost_dir(tmp_path)
    monkeypatch.setenv("GHOST_TOOLS", str(ghost))
    monkeypatch.setattr(ts, "run", lambda *a, **k: _card(breakdown=_levels(20, 5, 0)))
    assert cli.main(["assay", "--json"]) == 0
    sources = json.loads(capsys.readouterr().out)["sources"]
    assert sources["ghost_tools_found_by"] == "$GHOST_TOOLS" and sources["ghost_tools"] == str(ghost)


# ---------------------------------------------------------------- 6. Ctrl-C

def test_ctrl_c_under_json_is_valid_json_with_no_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ASSAY", str(_fake_assay(tmp_path)))
    monkeypatch.setattr(ts, "run", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert cli.main(["assay", "--ghost-tools", str(_ghost_dir(tmp_path)), "--json"]) == 130
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "interrupted" and payload["exit_code"] == 130
    assert "interrupted" in captured.err and "Traceback" not in captured.err + captured.out


def test_ctrl_c_in_text_mode_is_a_clear_message(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ASSAY", str(_fake_assay(tmp_path)))
    monkeypatch.setattr(ts, "run", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert cli.main(["assay", "--ghost-tools", str(_ghost_dir(tmp_path))]) == 130
    captured = capsys.readouterr()
    assert "interrupted" in captured.err and captured.out == "" and "Traceback" not in captured.err


def test_ctrl_c_during_a_real_command_leaves_no_traceback(monkeypatch, capsys):
    import swizzle.cli as c
    monkeypatch.setattr(c, "_list", lambda args: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert c.main(["list"]) == 130
    assert "Traceback" not in capsys.readouterr().err
