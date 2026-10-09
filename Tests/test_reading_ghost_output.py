"""Reading what ghost_buster prints, in both shapes it has had.

Before Ghost PR #97 `--json` printed a bare list of findings and exited 0 or 1.
After it, `--json` prints an object (status, error, exit_code, findings, scan,
unmeasured) and a crash exits 3. SWIZZLE reads both, so a pinned old Ghost and
a current one both work, and it never reads a crash as a clean scan.

These use a stand-in ghost_tools checkout that prints canned output, so they
need neither the real tool nor git.
"""

from __future__ import annotations

import json
import textwrap

import pytest

from swizzle import assay as assay_mod
from swizzle.invoke import InvocationFailed, _json_body, scan
from swizzle.lab.adapters import ghost as lab_ghost
from swizzle.lab.sandbox import Completed

FINDING = {"detector": "dead_code", "id": "ghost-abc123", "severity": "minor",
           "summary": "x", "evidence": {"file": "a.py", "line_start": 1}}


def _stub(tmp_path, stdout: str, exit_code: int, stderr: str = ""):
    """A ghost_tools checkout whose scanner prints `stdout` and exits."""
    package = tmp_path / "stub_ghost" / "ghost_buster"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "cli.py").write_text(textwrap.dedent("""
        import sys
        sys.stdout.write(%r)
        sys.stderr.write(%r)
        sys.exit(%d)
    """ % (stdout, stderr, exit_code)))
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    return tmp_path / "stub_ghost", repo


def _envelope(findings=(), status="ok", exit_code=0, error=None, unmeasured=()):
    return json.dumps({"status": status, "error": error, "exit_code": exit_code,
                       "findings": list(findings),
                       "scan": {"files_scanned": 1, "files_skipped": 0,
                                "files_unparsable": 0, "unparsable": []},
                       "unmeasured": list(unmeasured)}, indent=2)


BY_REQUEST = {"check": "tests", "state": "declined", "by_request": True,
              "reason": "skipped at your request (--no-tests)"}
REAL_GAP = {"check": "parse", "state": "unparsable", "by_request": False,
            "reason": "1 file(s) could not be parsed, so the code detectors skipped them"}


def test_a_bare_list_still_reads(tmp_path):
    ghost, repo = _stub(tmp_path, json.dumps([FINDING], indent=2), 1)
    assert list(scan(repo, ghost)) == [FINDING]


def test_an_object_reads_as_its_findings(tmp_path):
    ghost, repo = _stub(tmp_path, _envelope([FINDING], exit_code=1), 1)
    assert list(scan(repo, ghost)) == [FINDING]


def test_a_clean_object_is_an_empty_list(tmp_path):
    ghost, repo = _stub(tmp_path, _envelope(), 0)
    assert list(scan(repo, ghost)) == []


def test_progress_lines_before_an_object_are_skipped(tmp_path):
    ghost, repo = _stub(tmp_path, "scanning 1 file\n" + _envelope([FINDING], exit_code=1), 1)
    assert list(scan(repo, ghost)) == [FINDING]


def test_json_body_finds_an_object_too():
    assert _json_body('scanning\n{\n "a": 1\n}\n') == '{\n "a": 1\n}'
    assert _json_body("[1]") == "[1]"
    assert _json_body("nothing\n") is None


def test_exit_3_is_a_ghost_crash_not_a_clean_scan(tmp_path):
    body = _envelope(status="error", exit_code=3,
                     error={"kind": "internal", "message": "boom in detector"})
    ghost, repo = _stub(tmp_path, body, 3)
    with pytest.raises(InvocationFailed) as raised:
        scan(repo, ghost)
    text = str(raised.value).lower()
    assert "crash" in text and "boom in detector" in text


def test_status_error_alone_is_a_crash(tmp_path):
    body = _envelope(status="error", exit_code=0,
                     error={"kind": "internal", "message": "boom"})
    ghost, repo = _stub(tmp_path, body, 0)
    with pytest.raises(InvocationFailed):
        scan(repo, ghost)


def test_exit_3_with_no_json_is_still_a_crash(tmp_path):
    ghost, repo = _stub(tmp_path, "", 3, stderr="Traceback ...")
    with pytest.raises(InvocationFailed) as raised:
        scan(repo, ghost)
    assert "crash" in str(raised.value).lower()


def test_exit_2_is_ghost_not_starting(tmp_path):
    ghost, repo = _stub(tmp_path, "", 2, stderr="not a directory")
    with pytest.raises(InvocationFailed) as raised:
        scan(repo, ghost)
    assert "exit 2" in str(raised.value)


def test_incomplete_only_because_of_requests_is_not_a_failure_and_has_no_gaps(tmp_path):
    body = _envelope([FINDING], status="incomplete", exit_code=1, unmeasured=[BY_REQUEST])
    ghost, repo = _stub(tmp_path, body, 1)
    found = scan(repo, ghost)
    assert list(found) == [FINDING]
    assert found.gaps == []


def test_real_gaps_keep_the_findings_and_are_exposed(tmp_path):
    body = _envelope([FINDING], status="incomplete", exit_code=1,
                     unmeasured=[BY_REQUEST, REAL_GAP])
    ghost, repo = _stub(tmp_path, body, 1)
    found = scan(repo, ghost)
    assert list(found) == [FINDING]
    assert len(found.gaps) == 1 and "could not be parsed" in found.gaps[0]


def test_a_bare_list_has_no_gaps(tmp_path):
    ghost, repo = _stub(tmp_path, "[]", 0)
    assert scan(repo, ghost).gaps == []


def test_a_scorecard_shows_the_gaps_it_was_scored_through():
    card = assay_mod.Scorecard("a", "proven", [], gaps=["parse: 1 file(s) could not be parsed"])
    assert "could not be parsed" in card.render()
    assert card.to_dict()["scan_gaps"] == ["parse: 1 file(s) could not be parsed"]
    clean = assay_mod.Scorecard("a", "proven", [])
    assert clean.to_dict()["scan_gaps"] == []


# ------------------------------------------------------------ the lab adapter

def _done(stdout: str, code: int) -> Completed:
    return Completed(argv=("x",), returncode=code, stdout=stdout, stderr="",
                     seconds=0.1, timed_out=False)


def test_lab_adapter_reads_both_shapes():
    assert lab_ghost._findings(json.dumps([FINDING]))[0]["id"] == "ghost-abc123"
    assert lab_ghost._findings(_envelope([FINDING], exit_code=1))[0]["id"] == "ghost-abc123"


def test_lab_adapter_calls_exit_3_a_failure_even_with_an_object():
    body = _envelope(status="error", exit_code=3, error={"kind": "internal", "message": "boom"})
    findings = lab_ghost._findings(body)
    assert lab_ghost._failed(_done(body, 3), findings)
    assert "crash" in lab_ghost._failure(_done(body, 3), findings).lower()


def test_lab_adapter_does_not_fail_findings_exit_1():
    body = _envelope([FINDING], exit_code=1)
    assert not lab_ghost._failed(_done(body, 1), lab_ghost._findings(body))


def test_a_warp_scanned_through_a_real_gap_says_so(tmp_path, monkeypatch):
    from swizzle import run as run_mod
    from swizzle.invoke import Findings
    from swizzle.warps import by_name
    monkeypatch.setattr(run_mod, "scan",
                        lambda root, ghost_tools=None: Findings([], ["parse: 1 file(s) could not be parsed"]))
    outcome = run_mod.run_warp(by_name("sql_through_a_name"), tmp_path, None)
    assert "did not fully look" in outcome.account and "could not be parsed" in outcome.account
