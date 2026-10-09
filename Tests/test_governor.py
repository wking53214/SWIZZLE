"""The governor attacks: each invariant must catch its violation and pass honest behavior."""

import os
from pathlib import Path

import pytest

from swizzle.governor.run import Finding, attack, render, snapshot
from swizzle.governor.scenarios import BASE, SCENARIOS


def _scenario(name):
    return next(s for s in SCENARIOS if s.name == name)


def _after(**changes):
    tree = dict(BASE)
    tree.update(changes)
    return tree


def test_every_attack_names_a_hypothesis_and_a_severity():
    assert len({s.name for s in SCENARIOS}) == len(SCENARIOS)
    for s in SCENARIOS:
        assert s.hypothesis and s.severity in {"high", "medium", "low"}


def test_a_tree_that_changed_is_a_violation_and_one_that_did_not_is_not():
    s = _scenario("seat_writes_the_tree")
    assert s.invariant(BASE, _after(**{"SNEAK.txt": "x"}), {}) is not None
    assert s.invariant(BASE, dict(BASE), {}) is None


def test_scope_attack_catches_code_changed_under_a_documentation_grant():
    s = _scenario("grant_scope_ignored")
    assert "pkg/__init__.py" in s.invariant(BASE, _after(**{"pkg/__init__.py": "X = 1\n"}), {})
    assert s.invariant(BASE, _after(**{"NOTE.md": "new\n"}), {}) is None


def test_escape_attack_catches_a_file_beside_the_case():
    s = _scenario("edit_escapes_target")
    assert s.invariant(BASE, _after(**{"../outside.txt": "x"}), {}) is not None
    assert s.invariant(BASE, dict(BASE), {}) is None


def test_label_attack_judges_by_what_was_configured_not_by_the_governors_field():
    s = _scenario("accept_without_measuring")
    bare = {"decision": "ACCEPT", "unmeasured": [], "configured": {"ghost": False, "swizzle": False, "suite": True}}
    assert s.invariant(BASE, BASE, bare) is not None
    assert s.invariant(BASE, BASE, {**bare, "decision": "ACCEPT_UNVERIFIED"}) is None


def test_ghost_attack_wants_a_clean_failure_not_a_crash_or_a_shrug():
    s = _scenario("ghost_unreachable")
    assert s.invariant(BASE, BASE, {"crashed": True, "error": "JSONDecodeError"}) is not None
    assert s.invariant(BASE, BASE, {"decision": "ACCEPT"}) is not None
    assert s.invariant(BASE, BASE, {"decision": "INCONCLUSIVE"}) is None


def test_removal_attack_catches_code_that_was_commented_out_or_deleted():
    s = _scenario("removal_reached_by_name")
    assert s.invariant(BASE, _after(**{"pkg/dead.py": "# def unused():\n#     return 2\n"}), {}) is not None
    assert s.invariant(BASE, dict(BASE), {}) is None


def test_the_over_caution_checks_are_low_severity():
    assert {s.severity for s in SCENARIOS if s.name in {"ordinary_docs_fix", "formatting_only_tidy"}} == {"low"}


def test_snapshot_sees_files_beside_the_case(tmp_path):
    (tmp_path / "case").mkdir()
    (tmp_path / "case" / "a.py").write_text("x", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("y", encoding="utf-8")
    assert snapshot(tmp_path) == {"a.py": "x", "../outside.txt": "y"}


def test_render_never_issues_a_verdict_about_acceptance():
    text = render([Finding("n", "h", "high", "violated", "d")])
    assert "VIOLATED" in text and "does not decide" in text


@pytest.mark.skipif(not os.environ.get("WARDEN_ROOT"), reason="set WARDEN_ROOT to a Warden checkout to attack it live")
def test_live_warden_holds_every_invariant():
    findings = attack(Path(os.environ["WARDEN_ROOT"]))
    assert not [f for f in findings if f.status != "held"], render(findings)


def test_only_the_probe_touches_the_governors_types():
    import ast
    import swizzle.governor as pkg
    root = Path(pkg.__file__).parent
    for path in root.glob("*.py"):
        names = {n.module.split(".")[0] for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                 if isinstance(n, ast.ImportFrom) and n.module and n.level == 0}
        names |= {a.name.split(".")[0] for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                  if isinstance(n, ast.Import) for a in n.names}
        if path.name == "probe.py":
            continue  # imports warden inside a function, in a subprocess
        assert "warden" not in names, f"{path.name} imports the governor it is judging"
