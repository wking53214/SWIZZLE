"""The command line, including the commands that came first.

The original four -- list, prove, run, summon -- are checked here as well
as the new ones. The laboratory was added around them and they must keep
working exactly as they did; a test that only covers the new surface would
not notice them breaking.
"""

from __future__ import annotations

import json

import pytest

from swizzle.cli import main


def run(argv, capsys):
    code = main(argv)
    return code, capsys.readouterr().out


# ---------------------------------------------- the original four commands

def test_list_still_works(capsys):
    code, out = run(["list"], capsys)
    assert code == 0
    assert "sql_through_a_name" in out


def test_summon_still_works(tmp_path, capsys):
    code, out = run(["summon", "sql_behind_a_comment", "--into", str(tmp_path)], capsys)
    assert code == 0
    assert (tmp_path / "sql_behind_a_comment" / "app" / "audit.py").is_file()


def test_no_command_prints_help(capsys):
    code, out = run([], capsys)
    assert code == 0
    assert "usage" in out.lower()


# ------------------------------------------------------ laboratory commands

def test_seed_lists_the_catalogue(capsys):
    code, out = run(["seed"], capsys)
    assert code == 0
    assert "prose_inside_the_maintained_block" in out


def test_seed_full_prints_the_hypothesis(capsys):
    code, out = run(["seed", "--only", "prose_inside", "--full"], capsys)
    assert code == 0
    assert "marker pair" in out or "count" in out


def test_mutators_documents_every_entry(capsys):
    from swizzle.lab.mutators import registry
    code, out = run(["mutators"], capsys)
    assert code == 0
    for name in registry():
        assert name in out


def test_corpus_on_an_empty_directory(tmp_path, capsys):
    code, out = run(["corpus", "--corpus-path", str(tmp_path / "c")], capsys)
    assert code == 0
    assert "empty" in out


def test_corpus_json_is_json(tmp_path, capsys):
    code, out = run(["corpus", "--corpus-path", str(tmp_path / "c"), "--json"], capsys)
    assert code == 0
    assert json.loads(out) == []


def test_reproduce_build_only_needs_no_target(tmp_path, capsys):
    """Rebuilding a world must not require the target to be installed.

    Somebody reading an archived attack should be able to look at the
    repository it describes without having the system under test to hand.
    """
    code, out = run(["reproduce", "prose_inside_the_maintained_block",
                     "--build-only", "--keep", str(tmp_path / "w")], capsys)
    assert code == 0
    root = tmp_path / "w" / "case"
    assert (root / "README.md").is_file()
    assert "tests, all passing" in (root / "README.md").read_text()


def test_an_unknown_case_is_refused(capsys):
    assert main(["reproduce", "no_such_case"]) == 2


def test_diff_needs_two_targets(capsys):
    assert main(["diff", "--ghost", "one"]) == 2


def test_diff_can_refuse_to_pass_what_it_could_not_measure(monkeypatch, capsys):
    """A candidate that cannot be run leaves every case unmeasured. Without
    the flag that is still exit 0; a CI gate needs it to be a failure."""
    from swizzle.lab import cli as lab_cli

    class _Result:
        def render(self):
            return "not_measured 26"

        def counts(self):
            return {"not_measured": 26}

    monkeypatch.setattr(lab_cli, "_adapter_for", lambda what, scratch: object())
    monkeypatch.setattr(lab_cli, "compare", lambda genomes, base, cand: _Result())
    argv = ["diff", "--ghost", "base", "--ghost", "candidate", "--seeds"]
    assert main(argv) == 0
    assert main(argv + ["--fail-on-unmeasured"]) == 1


def test_sandboxes_lists_without_deleting(capsys):
    code, out = run(["sandboxes"], capsys)
    assert code == 0
    assert "sandbox" in out
