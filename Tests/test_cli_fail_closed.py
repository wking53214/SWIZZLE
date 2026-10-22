"""The command line refuses, with exit 2 and a reason, when there is nothing real to work on.

Each of these used to exit 0: `verify` on a folder that does not exist printed a table of unaskable
oracles, `corpus --corpus-dir` on a path that does not exist said "the corpus is empty", and a bare
`swizzle` printed usage and succeeded. A caller reads exit 0 as "it worked".
"""

from __future__ import annotations

import json

import pytest

from swizzle import cli

VERIFY = ["--member", "x", "--provenance", "p", "--severity", "high"]


def _main(argv, capsys):
    code = cli.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_verify_refuses_a_directory_that_does_not_exist(tmp_path, capsys):
    code, out, err = _main(["verify", str(tmp_path / "nope"), *VERIFY], capsys)
    assert code == 2
    assert out == ""
    assert "does not exist" in err


def test_verify_refuses_a_file_that_is_not_a_directory(tmp_path, capsys):
    target = tmp_path / "file.txt"
    target.write_text("x = 1\n")
    code, out, err = _main(["verify", str(target), *VERIFY], capsys)
    assert code == 2 and out == ""
    assert "not a directory" in err


def test_verify_refuses_an_empty_directory(tmp_path, capsys):
    (tmp_path / "empty").mkdir()
    code, out, err = _main(["verify", str(tmp_path / "empty"), *VERIFY], capsys)
    assert code == 2 and out == ""
    assert "empty directory" in err


def test_verify_still_evaluates_a_real_directory(tmp_path, capsys):
    """A directory with something in it is evaluated and exits 0: an honest UNASKABLE is a result, not an error."""
    (tmp_path / "a.py").write_text("x = 1\n")
    code, out, _ = _main(["verify", str(tmp_path), *VERIFY], capsys)
    assert code == 0
    assert "oracle_results" in json.loads(out)


@pytest.mark.parametrize("name", ["missing", "no/such/deep/path"])
def test_corpus_refuses_a_named_directory_that_does_not_exist(tmp_path, capsys, name):
    code, out, err = _main(["corpus", "--corpus-dir", str(tmp_path / name)], capsys)
    assert code == 2
    assert "empty" not in out
    assert "does not exist" in err


def test_corpus_refuses_a_path_under_a_device_file(capsys):
    code, out, err = _main(["corpus", "--corpus-dir", "/dev/null/x"], capsys)
    assert code == 2 and "empty" not in out
    assert "--corpus-dir" in err


def test_corpus_refuses_a_named_path_that_is_a_file_with_json_too(tmp_path, capsys):
    target = tmp_path / "f"
    target.write_text("x")
    code, out, err = _main(["corpus", "--corpus-path", str(target), "--json"], capsys)
    assert code == 2 and out == ""
    assert "not a directory" in err


def test_corpus_still_reads_an_existing_empty_directory_as_empty(tmp_path, capsys):
    code, out, _ = _main(["corpus", "--corpus-dir", str(tmp_path)], capsys)
    assert code == 0 and "the corpus is empty" in out


def test_the_default_corpus_location_may_be_absent_and_reads_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code, out, _ = _main(["corpus"], capsys)
    assert code == 0 and "the corpus is empty" in out
    assert not (tmp_path / "corpus").exists(), "reading the default location must not create it"


def test_naming_the_default_path_explicitly_still_requires_it_to_exist(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code, _, err = _main(["corpus", "--corpus-dir", "corpus"], capsys)
    assert code == 2 and "does not exist" in err


# Every command that reads the corpus refuses a folder the caller named wrongly, with the same reason `corpus` gives.
CORPUS_READERS = {
    "history": ["history"],
    "knowledge": ["knowledge"],
    "handoff-list": ["handoff", "list"],
    "handoff-propose": ["handoff", "propose"],
    "report": ["report", "--bucket", "regression"],
    "diff": ["diff", "--ghost", "a", "--ghost", "b"],
    "standing": ["standing"],
    "holdout": ["holdout"],
}


@pytest.mark.parametrize("command", sorted(CORPUS_READERS))
@pytest.mark.parametrize("name", ["missing", "no/such/deep/path"])
def test_every_corpus_reader_refuses_a_named_directory_that_does_not_exist(tmp_path, capsys, command, name):
    code, out, err = _main([*CORPUS_READERS[command], "--corpus-dir", str(tmp_path / name)], capsys)
    assert code == 2, (code, out, err)
    assert "does not exist" in err and "--corpus-dir" in err
    assert out == ""
    assert not (tmp_path / name).exists()


@pytest.mark.parametrize("command", sorted(CORPUS_READERS))
def test_every_corpus_reader_refuses_a_named_path_that_is_a_file(tmp_path, capsys, command):
    target = tmp_path / "f"
    target.write_text("x")
    code, out, err = _main([*CORPUS_READERS[command], "--corpus-path", str(target)], capsys)
    assert code == 2 and out == ""
    assert "not a directory" in err


@pytest.mark.parametrize("command", ["history", "handoff-list"])
def test_corpus_readers_still_read_an_existing_empty_directory_as_empty(tmp_path, capsys, command):
    code, out, err = _main([*CORPUS_READERS[command], "--corpus-dir", str(tmp_path), "--json"], capsys)
    assert code == 0, err
    assert json.loads(out) in ([], {})


@pytest.mark.parametrize("command", ["history", "handoff-list"])
def test_corpus_readers_let_the_default_location_be_absent(tmp_path, monkeypatch, capsys, command):
    monkeypatch.chdir(tmp_path)
    code, out, err = _main(CORPUS_READERS[command], capsys)
    assert code == 0, err
    assert list(tmp_path.iterdir()) == [], "a read-only command created: %s" % list(tmp_path.iterdir())


def test_bare_swizzle_is_a_usage_error(capsys):
    code, out, err = _main([], capsys)
    assert code == 2
    assert out == ""
    assert "a command is required" in err and "usage:" in err


def test_help_and_version_still_exit_zero(capsys):
    for flag in ("--help", "--version"):
        with pytest.raises(SystemExit) as stop:
            cli.main([flag])
        assert stop.value.code == 0
        capsys.readouterr()


@pytest.mark.parametrize("extra", [[], ["--fail-on-escape"]])
def test_run_refuses_an_unknown_only_name(extra, capsys):
    """`run --only typo` used to print "0 warps" and exit 0, so a typo in a CI gate passed vacuously."""
    code, out, err = _main(["run", "--only", "nosuchwarp", *extra], capsys)
    assert code == 2
    assert out == ""
    assert "no warp matches 'nosuchwarp'" in err and "sql_through_a_name" in err


@pytest.mark.parametrize("extra", [[], ["--fail-on-escape"]])
def test_run_refuses_one_unknown_name_in_a_list(extra, capsys):
    code, out, err = _main(["run", "--only", "sql_through_a_name,nosuchwarp", *extra], capsys)
    assert code == 2 and out == ""
    assert "no warp matches 'nosuchwarp'" in err


def test_run_selects_a_comma_separated_list_like_prove(monkeypatch, capsys):
    seen = {}

    def fake_run_all(warps, ghost_tools, keep=None):
        seen["names"] = [w.name for w in warps]
        return []

    monkeypatch.setattr(cli, "run_all", fake_run_all)
    monkeypatch.setattr(cli, "render", lambda outcomes, warps: "")
    monkeypatch.setattr(cli, "_is_ghost_tools", lambda path: True)
    code, _, err = _main(["run", "--ghost-tools", ".", "--only", "sql_through_a_name,sql_behind_a_wrapper"], capsys)
    assert code == 0, err
    assert seen["names"] == ["sql_through_a_name", "sql_behind_a_wrapper"]
