"""Reports must fail closed: a crash is not a pass, a bad path is not a fallback.

Each test reproduces something the red team found.
"""

import json
import os
import shutil
import stat
import tempfile
from pathlib import Path

import pytest

from swizzle import assay as ts
from swizzle import cli
from swizzle.governor import run as gov
from swizzle.governor.run import Finding, judge_outcome, select
from swizzle.governor.scenarios import SCENARIOS

GOOD = {"completed": True, "decision": "REJECT", "refused": False, "crashed": False, "notes": []}


def _scn(name="tests_weakened"):
    return next(s for s in SCENARIOS if s.name == name)


def _debris():
    return {p.name for p in Path(tempfile.gettempdir()).glob("swizzle-governor-*")}


# --------------------------------------------------------------- 1. crashed Warden

@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_a_crashed_warden_is_never_held(scenario):
    crashed = {**GOOD, "completed": False, "crashed": True, "decision": None, "error": "RuntimeError: boom\nmore"}
    found = judge_outcome(scenario, crashed)
    assert found is not None and found.status == "not_run"
    assert found.detail == "Warden crashed before deciding: RuntimeError: boom"


def test_no_output_no_decision_and_error_are_not_run_never_held():
    s = _scn()
    for outcome in (None, {"unavailable": "ImportError: x"}, {**GOOD, "completed": False},
                    {**GOOD, "decision": None}, {**GOOD, "decision": ""}, {**GOOD, "decision": "ERROR"},
                    {**GOOD, "decision": 7}):
        found = judge_outcome(s, outcome, stderr="Traceback\nValueError: bad", returncode=1)
        assert found is not None and found.status == "not_run", outcome


def test_a_readable_decision_may_be_judged():
    assert judge_outcome(_scn(), GOOD) is None


def test_only_the_scenario_that_expects_refusal_may_hold_on_a_refusal():
    refused = {**GOOD, "decision": "", "refused": True, "error": "no"}
    assert judge_outcome(_scn("forged_self_authorization"), refused) is None
    assert judge_outcome(_scn("ordinary_docs_fix"), refused).status == "not_run"


def _stub_python(tmp_path, body):
    script = tmp_path / "py"
    script.write_text("#!/bin/sh\n" + body + "\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_probe_that_crashes_or_prints_nothing_is_not_run_in_the_real_runner(tmp_path):
    before = _debris()
    quiet = _stub_python(tmp_path, "exit 0")
    f = gov.run_scenario(_scn(), tmp_path, Path(__file__).resolve().parents[1], python=quiet)
    assert f.status == "not_run" and "no readable result" in f.detail
    crash = _stub_python(tmp_path, 'echo \'SWIZZLE_RESULT {"crashed": true, "error": "KeyError: x", "completed": false}\'')
    f = gov.run_scenario(_scn(), tmp_path, Path(__file__).resolve().parents[1], python=crash)
    assert f.status == "not_run" and f.detail == "Warden crashed before deciding: KeyError: x"
    assert _debris() == before


def test_garbled_result_line_is_not_run(tmp_path):
    junk = _stub_python(tmp_path, "echo 'SWIZZLE_RESULT {not json'")
    f = gov.run_scenario(_scn(), tmp_path, Path(__file__).resolve().parents[1], python=junk)
    assert f.status == "not_run"


# --------------------------------------------------------------- 4. cleanup

def test_timeout_kills_the_probe_and_leaves_no_temp_folder(tmp_path):
    before = _debris()
    marker = tmp_path / "child_alive"
    hang = _stub_python(tmp_path, "sleep 30 &\necho $! > %s\nwait" % marker)
    f = gov.run_scenario(_scn(), tmp_path, Path(__file__).resolve().parents[1], python=hang, timeout=1)
    assert f.status == "not_run" and "timed out" in f.detail
    assert _debris() == before
    pid = int(marker.read_text())
    import time
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    pytest.fail("the probe's child process is still running")


def test_an_exception_still_cleans_up(tmp_path, monkeypatch):
    before = _debris()

    def boom(*a, **k):
        raise RuntimeError("launch failed")
    monkeypatch.setattr(gov, "_launch", boom)
    with pytest.raises(RuntimeError):
        gov.run_scenario(_scn(), tmp_path, Path(__file__).resolve().parents[1])
    assert _debris() == before
    assert not gov._live_dirs


def test_a_relative_warden_path_is_made_absolute(tmp_path, monkeypatch):
    (tmp_path / "w" / "warden").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    root = gov.locate_warden(Path("w"))
    assert root.is_absolute() and root == (tmp_path / "w").resolve()
    with pytest.raises(gov.WardenNotFound):
        gov.locate_warden(Path("nowhere"))


# --------------------------------------------------------------- 2. exit codes

def _f(status):
    return Finding("n", "h", "high", status)


def test_governor_exit_code_contract():
    assert gov.exit_code([_f("held"), _f("held")]) == 0
    assert gov.exit_code([_f("held"), _f("not_run")]) == 2
    assert gov.exit_code([_f("not_run"), _f("not_run")]) == 2
    assert gov.exit_code([_f("held"), _f("violated")]) == 1
    assert gov.exit_code([_f("not_run"), _f("violated")]) == 1       # violated outranks not_run
    assert gov.exit_code([]) == 2                                      # nothing ran


def test_summary_counts_the_three_states_separately():
    text = gov.summary([_f("held"), _f("held"), _f("violated"), _f("not_run")])
    assert text == "4 attacks: 2 held, 1 violated, 1 not run"
    assert "1 not run" in gov.render([_f("not_run")])


def test_governor_cli_exit_codes_and_clean_json(monkeypatch, capsys):
    import swizzle.governor.run as g
    results = {"v": [_f("held"), _f("not_run")]}
    monkeypatch.setattr(g, "attack", lambda *a, **k: results["v"])
    assert cli.main(["governor", "--warden", ".", "--json"]) == 2
    out = capsys.readouterr()
    assert [i["status"] for i in json.loads(out.out)] == ["held", "not_run"]
    assert "1 held, 0 violated, 1 not run" in out.err
    results["v"] = [_f("held")]
    assert cli.main(["governor", "--warden", ".", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["status"] == "held"


def test_unknown_only_is_an_error_listing_valid_names(capsys, tmp_path):
    (tmp_path / "warden").mkdir()
    assert cli.main(["governor", "--warden", str(tmp_path), "--only", "no_such_thing"]) == 2
    err = capsys.readouterr()
    assert err.out == "" and "tests_weakened" in err.err
    assert cli.main(["prove", "--only", "no_such_thing"]) == 2
    err = capsys.readouterr()
    assert err.out == "" and "sql_through_a_name" in err.err
    with pytest.raises(gov.BadSelection):
        select("tests_weakened,typo")
    assert [s.name for s in select("tests_weakened")] == ["tests_weakened"]


def test_governor_help_states_the_exit_codes(capsys):
    with pytest.raises(SystemExit):
        cli.main(["governor", "--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "otherwise 2 if any did not run" in text and "otherwise 0" in text


def test_prove_that_ran_nothing_exits_2(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_selected", lambda pattern: [])
    assert cli.main(["prove"]) == 2
    assert "no proofs ran" in capsys.readouterr().err


# --------------------------------------------------------------- 6. prove wording

def test_prove_footer_says_it_does_not_run_ghost(capsys):
    assert cli.main(["prove", "--only", "sql_through_a_name"]) == 0
    out = capsys.readouterr().out
    assert "1 of 1 proofs hold." in out
    last_hold = [ln for ln in out.splitlines() if "proofs hold" in ln][-1]
    assert last_hold == "1 of 1 proofs hold."          # Warden reads the last such line
    assert "None of them runs Ghost" in out


def test_a_failed_sql_proof_does_not_claim_the_injection_worked(tmp_path):
    from swizzle.run import prove
    from swizzle.summon import summon
    from swizzle.warps import by_name
    warp = by_name("sql_through_a_name")
    root = summon(warp, tmp_path)
    (root / "app" / "queries.py").write_text(
        'def find_user(conn, uid):\n    return conn.execute("SELECT id, name FROM users WHERE id = ?", (uid,)).fetchall()\n',
        encoding="utf-8")
    proof = prove(warp, root)
    assert not proof.holds
    assert "became part of the statement" not in proof.account
    assert "returned 0" in proof.account or "returned 1" in proof.account
    assert "NOT" in proof.account


# --------------------------------------------------------------- 3. assay

def _fake_assay(tmp_path, verifier_output="29/29 manifest claims hold", code=0):
    root = tmp_path / "assay"
    (root / "assay_production").mkdir(parents=True)
    (root / "assay_production" / "registry.json").write_text(
        json.dumps({"m%d" % i: {"specimen_class": "FAILURE_MODE"} for i in range(5)}))
    (root / "verify_manifest.py").write_text("print(%r)\nraise SystemExit(%d)\n" % (verifier_output, code))
    return root


def test_explicit_assay_path_never_falls_back(tmp_path, monkeypatch, capsys):
    good = _fake_assay(tmp_path)
    monkeypatch.setenv("ASSAY", str(good))                  # a valid checkout is available...
    assert cli.main(["assay", "--assay", str(tmp_path / "missing")]) == 2   # ...and must not be used
    err = capsys.readouterr().err
    assert "Not falling back" in err
    assert ts.locate_assay(tmp_path / "missing") is None
    (tmp_path / "bare").mkdir()
    assert cli.main(["assay", "--assay", str(tmp_path / "bare")]) == 2      # no registry


def test_fallback_is_named_when_assay_is_not_given(tmp_path, monkeypatch):
    good = _fake_assay(tmp_path)
    monkeypatch.setenv("ASSAY", str(good))
    root, how = ts.resolve_assay(None)
    assert root == good.absolute() and how == "$ASSAY"


def test_bad_ghost_tools_path_is_a_plain_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ASSAY", str(_fake_assay(tmp_path)))
    assert cli.main(["assay", "--ghost-tools", str(tmp_path / "nope")]) == 2
    err = capsys.readouterr().err
    assert "not a ghost_tools checkout" in err and "ModuleNotFoundError" not in err
    assert cli.main(["run", "--ghost-tools", str(tmp_path / "nope")]) == 2
    assert "not a ghost_tools checkout" in capsys.readouterr().err


def test_answer_key_that_disagrees_with_itself_is_not_proven(tmp_path):
    ok, why = ts.prove_answer_key(_fake_assay(tmp_path / "a", "29/29 manifest claims hold"))
    assert ok
    ok, why = ts.prove_answer_key(_fake_assay(tmp_path / "b", "28/29 manifest claims hold", code=0))
    assert not ok and "28/29" in why
    ok, _ = ts.prove_answer_key(_fake_assay(tmp_path / "c", "29/29 manifest claims hold", code=1))
    assert not ok


def test_numbers_under_a_not_proven_banner_say_they_are_unreliable():
    card = ts.Scorecard("k", "NOT PROVEN: 28/29 manifest claims hold", [
        ts.Judgement("fm_3_1_silent_pass", "FAILURE_MODE", "REFUSE", ts.UNSUMMONED)])
    assert "unreliable" in card.render() and "NOT a score" in card.render()
    d = card.to_dict()
    assert d["key_proven"] is False and d["numbers_reliable"] is False


def _scored(caught):
    js = [ts.Judgement("m%d" % i, "FAILURE_MODE", "X", ts.BANISHED if i < caught else ts.ESCAPED)
          for i in range(5)]
    return ts.Scorecard("k", "29/29 manifest claims hold", js)


def test_floor(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ASSAY", str(_fake_assay(tmp_path)))
    ghost = tmp_path / "ghost"
    (ghost / "ghost_buster").mkdir(parents=True)
    (ghost / "ghost_buster" / "cli.py").write_text("")
    card = {"v": _scored(3)}
    monkeypatch.setattr(ts, "run", lambda *a, **k: card["v"])
    base = ["assay", "--ghost-tools", str(ghost)]
    assert cli.main(base) == 0
    assert "no floor set, exit 0 only means the key was scored" in capsys.readouterr().out
    assert cli.main(base + ["--floor", "3"]) == 0
    assert cli.main(base + ["--floor", "4"]) == 1
    capsys.readouterr()
    assert cli.main(base + ["--floor", "4", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["floor"] == 4 and "FLOOR NOT MET" in payload["floor_note"]
    assert payload["sources"]["ghost_tools_found_by"] == "--ghost-tools"


def test_unproven_key_exits_2_even_with_a_floor(tmp_path, monkeypatch):
    monkeypatch.setenv("ASSAY", str(_fake_assay(tmp_path, "28/29 manifest claims hold")))
    ghost = tmp_path / "ghost"
    (ghost / "ghost_buster").mkdir(parents=True)
    (ghost / "ghost_buster" / "cli.py").write_text("")
    monkeypatch.setattr(ts, "stage", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not score")))
    assert cli.main(["assay", "--ghost-tools", str(ghost), "--floor", "1"]) == 2


# --------------------------------------------------------------- live (needs a Warden checkout)

LIVE = os.environ.get("WARDEN_ROOT")


@pytest.mark.skipif(not LIVE, reason="set WARDEN_ROOT to a Warden checkout")
def test_live_sabotaged_warden_is_never_held(tmp_path):
    copy = tmp_path / "warden_copy"
    shutil.copytree(LIVE, copy, ignore=shutil.ignore_patterns("__pycache__", ".git"))
    path = copy / "warden" / "tagteam.py"
    text = path.read_text(encoding="utf-8")
    old = "        target = Path(target).resolve()\n        _refuse_self_authorization(target, authorization)"
    assert old in text
    path.write_text(text.replace(old, "        raise RuntimeError('boom')"), encoding="utf-8")
    findings = gov.attack(copy)
    assert len(findings) == len(SCENARIOS)
    assert {f.status for f in findings} == {"not_run"}
    assert gov.exit_code(findings) == 2


@pytest.mark.skipif(not LIVE, reason="set WARDEN_ROOT to a Warden checkout")
def test_live_warden_holds_all_with_a_relative_path(monkeypatch):
    before = _debris()
    monkeypatch.chdir(Path(LIVE).parent)
    findings = gov.attack(Path(LIVE).name)
    assert {f.status for f in findings} == {"held"}, gov.render(findings)
    assert _debris() == before
