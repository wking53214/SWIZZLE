"""The governor scenarios added for the holes the red team found in Warden.

A tiny stand-in Warden is written to disk with switches for each check, so each scenario can be
shown to (1) be skipped against a Warden that predates the check, (2) be violated against one
that claims to have it and fails, and (3) hold against one that does it right. The real Warden is
attacked only when WARDEN_ROOT is set (test_governor.py does that).
"""
import json
import textwrap
from pathlib import Path

import pytest

from swizzle import cli
from swizzle.governor import run as gov
from swizzle.governor.scenarios import SCENARIOS, NEW_CHECKS_SINCE

SWIZZLE_ROOT = Path(__file__).resolve().parents[1]

ORIGINAL_15 = {
    "seat_writes_the_tree", "finisher_writes_the_tree", "grant_scope_ignored", "edit_escapes_target",
    "tests_weakened", "config_weakened", "finisher_plants_conftest", "removal_reached_by_name",
    "forged_self_authorization", "accept_without_measuring", "ghost_unreachable", "ordinary_docs_fix",
    "formatting_only_tidy", "config_change_keeps_pass_count", "removal_invisible_to_suite_after"}

NEW = {
    "baseline_file_edited", "pytest_dotini_edited", "gitlab_ci_edited", "circleci_config_edited",
    "hidden_prose_file_edit_allowed", "symlink_into_protected_file", "dirty_folder_start",
    "clean_git_folder_start_allowed", "sigterm_mid_apply", "judge_raises", "judge_accepts_change_applies"}


def _scenario(name):
    return next(s for s in SCENARIOS if s.name == name)


# ---------------------------------------------------------------- a stand-in Warden

FAKE = '''
import json, os, signal, subprocess
from dataclasses import dataclass, field
from pathlib import Path

CFG = json.loads(Path(__file__).with_name("cfg.json").read_text())
'''


def make_warden(root: Path, version="0.8.0", protect=(), symlinks=False, dirty=False,
                sigterm=False, judge_safe=False):
    """A Warden that applies the one edit it is handed, unless a switch says it should not."""
    pkg = root / "warden"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('__version__ = "%s"\n' % version)
    (pkg / "cfg.json").write_text(json.dumps({"protect": list(protect), "symlinks": symlinks, "dirty": dirty,
                                              "sigterm": sigterm, "judge_safe": judge_safe}))
    (pkg / "guard.py").write_text(FAKE + textwrap.dedent('''
        def is_protected(rel):
            return rel in CFG["protect"] or rel.startswith("tests/")
    '''))
    (pkg / "authorization.py").write_text(textwrap.dedent('''
        from dataclasses import dataclass

        class Unauthorized(Exception):
            pass

        @dataclass
        class Authorization:
            actor: str
            operation: str
            subject: str
            scope: str
            reason: str
            granted: bool
            at: str

        def grant(actor, operation, subject, scope, reason):
            return Authorization(actor, operation, subject, scope, reason, True, "now")
    '''))
    (pkg / "models.py").write_text(textwrap.dedent('''
        from dataclasses import dataclass, field
        from enum import Enum

        class DefectSeverity(Enum):
            LOW = 1

        class TransformationStatus(Enum):
            PROPOSED = 1

        @dataclass
        class Defect:
            summary: str = ""
            severity: object = None
            ghost_id: str = ""
            identity: str = ""

        @dataclass
        class FileEdit:
            path: str
            kind: str
            new: str = ""
            old: str = ""

        @dataclass
        class Transformation:
            target: str = ""
            intent: str = ""
            architectural_reason: str = ""
            affected_files: tuple = ()
            expected_behavior: str = ""
            preservation_requirements: tuple = ()
            known_defects: tuple = ()
            transformation_scope: str = ""
            baseline_reference: str = ""
            evidence: tuple = ()
            edits: tuple = ()
            status: object = None
    '''))
    (pkg / "roles.py").write_text(textwrap.dedent('''
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class Verdict:
            decision: str
            reasons: tuple
            judge: str = ""
    '''))
    (pkg / "tagteam.py").write_text(FAKE + textwrap.dedent('''
        from .authorization import Unauthorized
        from .guard import is_protected

        def ghost_scan(*a, **k):
            return ()

        @dataclass
        class Result:
            decision: str
            notes: tuple = ()
            unmeasured: tuple = ()

        class TagTeam:
            def __init__(self, drafter=None, finisher=None, ghost_tools_root=None, judge=None, **kw):
                self.drafter, self.judge = drafter, judge

            def _suite(self, target, python, notes, when):
                return None

            def run(self, target, authorization=None, findings=None):
                target = Path(target)
                if CFG["dirty"]:
                    status = subprocess.run(("git", "status", "--porcelain"), cwd=str(target),
                                            capture_output=True, text=True).stdout.strip()
                    if status:
                        return Result("REFUSED", ("folder has uncommitted changes",))
                saved = {}
                if CFG["sigterm"]:
                    def on_term(signum, frame):
                        for path, text in saved.items():
                            path.write_text(text)
                        raise SystemExit(143)
                    signal.signal(signal.SIGTERM, on_term)
                proposal = self.drafter.propose(target, (), "b")
                if proposal and proposal.edits:
                    edit = proposal.edits[0]
                    where = target / edit.path
                    if CFG["symlinks"]:
                        where = where.resolve()
                        edit_path = where.relative_to(target.resolve()).as_posix()
                    else:
                        edit_path = edit.path
                    if is_protected(edit_path):
                        return Result("REJECT", ("protected file",))
                    self._suite(target, "py", [], "cycle 1 before")
                    saved[where] = where.read_text() if where.exists() else ""
                    where.write_text(edit.new)
                    self._suite(target, "py", [], "cycle 1 after")
                if self.judge is not None:
                    try:
                        verdict = self.judge.decide(None)
                    except Exception:
                        if CFG["judge_safe"]:
                            for path, text in saved.items():
                                path.write_text(text)
                            return Result("ERROR", ("The Judge failed",))
                        return Result("ACCEPT_UNVERIFIED", ("The Judge failed",))
                    return Result(verdict.decision, tuple(verdict.reasons))
                return Result("ACCEPT")
    '''))
    return root


def _run(tmp_path, name, assume=False, **fake):
    root = make_warden(tmp_path / "w", **fake)
    return gov.run_scenario(_scenario(name), root, SWIZZLE_ROOT, assume_new_checks=assume, timeout=120)


# ------------------------------------------------------------------- the catalogue

def test_the_original_fifteen_are_kept_and_the_new_ones_added():
    names = {s.name for s in SCENARIOS}
    assert ORIGINAL_15 <= names and NEW <= names
    assert len(SCENARIOS) == len(names) == 26


def test_every_new_attack_has_an_over_caution_twin_or_a_layer_note():
    for name in NEW:
        assert _scenario(name).layers


def test_list_says_which_scenarios_need_a_newer_warden(capsys):
    assert cli.main(["governor", "--list"]) == 0
    out = capsys.readouterr().out
    assert "dirty_folder_start" in out and "needs a Warden that has: dirty_start_refusal" in out
    assert NEW_CHECKS_SINCE in out


# ---------------------------------------------------------------- version and feature

def test_version_parsing_and_the_feature_rule():
    assert gov.parse_version("0.8.0") < gov.parse_version("0.9.0") < gov.parse_version("0.10.0")
    assert gov.parse_version("1.2") == (1, 2, 0) and gov.parse_version("junk") is None
    sc = _scenario("dirty_folder_start")
    assert "predates" not in (gov.feature_check(sc, {}, "0.9.0") or "")
    assert gov.feature_check(sc, {}, "0.9.0") is None
    assert "older than 0.9.0" in gov.feature_check(sc, {}, "0.8.0")
    assert "could not be read" in gov.feature_check(sc, {}, None)              # unknown is not assumed new
    assert gov.feature_check(sc, {}, "0.8.0", assume=True) is None
    assert gov.feature_check(sc, {"features": {"dirty_start_refusal": True}}, "0.8.0") is None
    assert gov.feature_check(_scenario("ordinary_docs_fix"), {}, "0.0.1") is None   # no feature, always judged


# ---------------------------------------------------------- protected files and symlinks

PROTECTED_CASES = [
    ("baseline_file_edited", ".ghost_baseline.json"),
    ("pytest_dotini_edited", ".pytest.ini"),
    ("gitlab_ci_edited", ".gitlab-ci.yml"),
    ("circleci_config_edited", ".circleci/config.yml"),
]


@pytest.mark.parametrize("name,path", PROTECTED_CASES)
def test_protected_file_scenarios_across_three_wardens(tmp_path, name, path):
    old = _run(tmp_path / "old", name, version="0.8.0")
    assert old.status == "not_run" and old.kind == "feature_absent" and "older than" in old.detail
    failing = _run(tmp_path / "new", name, version="0.9.0")
    assert failing.status == "violated" and path in failing.detail
    right = _run(tmp_path / "right", name, version="0.9.0", protect=[path])
    assert right.status == "held"


def test_a_warden_that_shows_the_protection_is_judged_whatever_its_version(tmp_path):
    held = _run(tmp_path / "a", "baseline_file_edited", version="0.8.0", protect=[".ghost_baseline.json"])
    assert held.status == "held"                                   # probed, not assumed from the version
    assumed = _run(tmp_path / "b", "baseline_file_edited", version="0.8.0", assume=True)
    assert assumed.status == "violated"


def test_the_hidden_prose_twin_catches_a_fix_that_protects_every_dotfile(tmp_path):
    assert _run(tmp_path / "a", "hidden_prose_file_edit_allowed").status == "held"
    over = _run(tmp_path / "b", "hidden_prose_file_edit_allowed", protect=[".notes.md"])
    assert over.status == "violated" and "hidden prose" in over.detail


def test_symlink_into_a_protected_file(tmp_path):
    assert _run(tmp_path / "a", "symlink_into_protected_file", version="0.8.0").kind == "feature_absent"
    bad = _run(tmp_path / "b", "symlink_into_protected_file", version="0.9.0")
    assert bad.status == "violated"
    good = _run(tmp_path / "c", "symlink_into_protected_file", version="0.9.0", symlinks=True)
    assert good.status == "held"


# ----------------------------------------------------------------------- dirty folder

def test_dirty_folder_start(tmp_path):
    old = _run(tmp_path / "a", "dirty_folder_start", version="0.8.0")
    assert old.status == "not_run" and old.kind == "feature_absent"
    bad = _run(tmp_path / "b", "dirty_folder_start", version="0.9.0")
    assert bad.status == "violated" and "uncommitted" in bad.detail
    good = _run(tmp_path / "c", "dirty_folder_start", version="0.9.0", dirty=True)
    assert good.status == "held" and good.decision == "REFUSED"


def test_clean_repository_twin_catches_a_dirty_check_that_refuses_everything(tmp_path):
    assert _run(tmp_path / "a", "clean_git_folder_start_allowed", version="0.9.0", dirty=True).status == "held"


# -------------------------------------------------------------------------- SIGTERM

def test_sigterm_mid_apply(tmp_path):
    old = _run(tmp_path / "a", "sigterm_mid_apply", version="0.8.0")
    assert old.status == "not_run" and old.kind == "feature_absent"
    bad = _run(tmp_path / "b", "sigterm_mid_apply", version="0.9.0")
    assert bad.status == "violated" and "not put back" in bad.detail
    good = _run(tmp_path / "c", "sigterm_mid_apply", version="0.9.0", sigterm=True)
    assert good.status == "held"


def test_a_warden_that_handles_sigterm_is_judged_even_when_its_version_is_old(tmp_path):
    assert _run(tmp_path / "a", "sigterm_mid_apply", version="0.8.0", sigterm=True).status == "held"


# ---------------------------------------------------------------------------- Judge

def test_a_judge_that_raises_must_leave_no_change_standing(tmp_path):
    bad = _run(tmp_path / "a", "judge_raises")
    assert bad.status == "violated" and "left standing" in bad.detail
    good = _run(tmp_path / "b", "judge_raises", judge_safe=True)
    assert good.status == "held"


def test_a_judge_that_accepts_still_gets_its_change(tmp_path):
    assert _run(tmp_path / "a", "judge_accepts_change_applies").status == "held"
    assert _run(tmp_path / "b", "judge_accepts_change_applies", judge_safe=True).status == "held"


# ------------------------------------------------------------------- exit rules intact

def _f(status, kind=""):
    return gov.Finding("n", "h", "high", status, kind=kind)


def test_a_skipped_scenario_is_exit_2_like_any_not_run_and_never_exit_0():
    assert gov.exit_code([_f("held"), _f("not_run", "feature_absent")]) == 2
    assert gov.exit_code([_f("violated"), _f("not_run", "feature_absent")]) == 1
    assert "skipped" in gov.render([_f("not_run", "feature_absent")])


def test_assume_new_checks_reaches_the_attack(monkeypatch, capsys):
    seen = {}
    monkeypatch.setattr(gov, "attack", lambda *a, **k: seen.update(k) or [_f("held")])
    assert cli.main(["governor", "--warden", ".", "--assume-new-checks", "--json"]) == 0
    assert seen["assume_new_checks"] is True
    capsys.readouterr()


# --------------------------------------------------------------------------- Ctrl-C

def test_ctrl_c_in_the_governor_reports_what_ran_and_marks_the_rest_not_run(tmp_path, monkeypatch, capsys):
    (tmp_path / "warden").mkdir()
    calls = []

    def fake_run(scenario, *a, **k):
        calls.append(scenario.name)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return gov.Finding(scenario.name, scenario.hypothesis, scenario.severity, "held")
    monkeypatch.setattr(gov, "run_scenario", fake_run)
    assert cli.main(["governor", "--warden", str(tmp_path), "--json"]) == 130
    captured = capsys.readouterr()
    rows = json.loads(captured.out)                                   # still one valid JSON list
    assert len(rows) == len(SCENARIOS)
    assert rows[0]["status"] == "held" and {r["status"] for r in rows[1:]} == {"not_run"}
    assert rows[1]["kind"] == "interrupted"
    assert "interrupted" in captured.err and "Traceback" not in captured.err


def test_ctrl_c_in_the_governor_text_mode_is_a_message(tmp_path, monkeypatch, capsys):
    (tmp_path / "warden").mkdir()
    monkeypatch.setattr(gov, "run_scenario", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert cli.main(["governor", "--warden", str(tmp_path)]) == 130
    captured = capsys.readouterr()
    assert "interrupted" in captured.err and "Traceback" not in captured.err + captured.out


# ------------------------------------------------------------------ says which Warden

def test_the_warden_used_is_printed(tmp_path, monkeypatch, capsys):
    (tmp_path / "warden").mkdir()
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "warden"\nversion = "0.8.0"\n')
    monkeypatch.setattr(gov, "attack", lambda *a, **k: [_f("held")])
    cli.main(["governor", "--warden", str(tmp_path)])
    assert str(tmp_path.resolve()) in capsys.readouterr().out
    cli.main(["governor", "--warden", str(tmp_path), "--json"])
    captured = capsys.readouterr()
    assert json.loads(captured.out)[0]["status"] == "held"             # stdout stays a bare JSON list
    assert "version 0.8.0" in captured.err
