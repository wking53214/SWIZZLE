"""WIZZLE runs git and Ghost with argv lists, never through a shell, and says when git failed."""

from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from swizzle.wizzle import _proc
from swizzle.wizzle.additional_oracles import HistoricalUsageOracle
from swizzle.wizzle.ghost_invoker import GhostInvoker
from swizzle.wizzle.history_generator import CommitSpec, HistoryGenerator
from swizzle.wizzle.oracles import HistoryOracle

ROOT = Path(__file__).resolve().parents[1]

# Every one of these is a plain directory name to a program that does not use a shell,
# and a command to a program that does.
HOSTILE_NAMES = [
    "with space",
    "semi; touch pwned",
    "amp && touch pwned",
    "sub $(touch pwned)",
    "tick `touch pwned`",
    "quote ' and \" marks",
]


def _no_pwned(*directories: Path) -> None:
    for directory in directories:
        assert not (directory / "pwned").exists(), "a shell ran a command out of a path"
    assert not Path("pwned").exists()


@pytest.mark.parametrize("name", HOSTILE_NAMES)
def test_history_generator_builds_a_repository_at_a_hostile_path(tmp_path, name):
    repo = tmp_path / name
    gen = HistoryGenerator(repo)
    gen.init_repo()
    hashes = gen.create_commits([
        CommitSpec(message='first "quoted" $(touch pwned) commit', files={"a.py": "x = 1\n"}),
        CommitSpec(message="second; touch pwned", files={"b.py": "y = 2\n"}, intent_signal="refactor"),
    ])
    assert len(hashes) == 2
    _no_pwned(tmp_path, repo)
    log = subprocess.run(["git", "log", "--format=%s", "--reverse"], cwd=repo, capture_output=True,
                         text=True, timeout=60, check=True).stdout.splitlines()
    # the message is stored literally, shell syntax and all
    assert log[0] == 'first "quoted" $(touch pwned) commit'
    assert log[1] == "second; touch pwned"
    assert gen.get_history_digest()


@pytest.mark.parametrize("name", HOSTILE_NAMES)
def test_oracles_read_history_at_a_hostile_path(tmp_path, name):
    repo = tmp_path / name
    gen = HistoryGenerator(repo)
    gen.init_repo()
    gen.create_commits([CommitSpec(message="refactor: tidy", files={"a.py": "x = 1\n"})])
    history = HistoryOracle.analyze(repo)
    assert "error" not in history
    assert history["evidence"]["message_analysis"]["total_commits"] == 1
    usage = HistoricalUsageOracle.analyze(repo)
    assert "error" not in usage
    assert usage["member_age"] == "NEW"
    _no_pwned(tmp_path, repo)


def test_a_git_failure_is_an_unmeasured_oracle_not_an_empty_history(tmp_path):
    not_a_repository = tmp_path / "plain folder"
    not_a_repository.mkdir()
    usage = HistoricalUsageOracle.analyze(not_a_repository)
    assert "error" in usage and "git log" in usage["error"]
    assert usage["confidence"] == 0.0
    assert usage["member_age"] == "UNKNOWN"
    history = HistoryOracle.analyze(not_a_repository)
    assert "error" in history
    assert history["confidence"] == 0.0
    assert history["inferred_intent"] == "UNKNOWN_INTENT"


def test_a_missing_directory_and_a_missing_git_are_failures_too(tmp_path, monkeypatch):
    assert "error" in HistoricalUsageOracle.analyze(tmp_path / "does not exist")
    repo = tmp_path / "r"
    HistoryGenerator(repo).init_repo()
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    usage = HistoricalUsageOracle.analyze(repo)
    assert "error" in usage and usage["confidence"] == 0.0
    assert "error" in HistoryOracle.analyze(repo)


def test_history_generator_reports_a_failed_git_command(tmp_path):
    gen = HistoryGenerator(tmp_path / "r")
    gen.init_repo()
    with pytest.raises(RuntimeError, match="Git command failed"):
        gen._run_git("rev-parse", "--verify", "no-such-ref")


def test_run_times_out_and_does_not_start_a_missing_program(tmp_path):
    with pytest.raises(_proc.CommandFailed, match="timed out"):
        _proc.run([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.5)
    with pytest.raises(_proc.CommandFailed, match="could not be run"):
        _proc.run([str(tmp_path / "no-such-program")])


def test_split_command_does_not_interpret_shell_syntax():
    argv = _proc.split_command('tool --flag "a b" ; touch pwned && echo $HOME')
    assert argv == ["tool", "--flag", "a b", ";", "touch", "pwned", "&&", "echo", "$HOME"]


def _fake_ghost(tmp_path: Path) -> Path:
    script = tmp_path / "fake ghost; touch pwned"
    script.write_text("#!%s\nimport json, sys\n"
                      "open(%r, 'w').write(json.dumps(sys.argv[1:]))\n"
                      "print(json.dumps({'findings': [{'member': 'M', 'file': 'f.py', 'severity': 'MAJOR',"
                      " 'category': 'REGRESSION', 'message': 'm'}]}))\n"
                      % (sys.executable, str(tmp_path / "argv.json")))
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def test_ghost_is_invoked_with_the_path_as_one_argument(tmp_path):
    import json
    repo = tmp_path / "repo with space; touch pwned"
    repo.mkdir()
    ghost = _fake_ghost(tmp_path)
    analysis = GhostInvoker(ghost_path=ghost).invoke(repo)
    assert analysis.status == "success", analysis.error_message
    assert json.loads((tmp_path / "argv.json").read_text()) == ["analyze", "--json", str(repo)]
    _no_pwned(tmp_path, repo)


def test_ghost_lookup_uses_the_path_search_not_a_shell(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin dir; touch pwned"
    bin_dir.mkdir()
    ghost = bin_dir / "ghost"
    ghost.write_text("#!/bin/sh\nexit 0\n")
    ghost.chmod(ghost.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    assert GhostInvoker._find_ghost() == ghost
    monkeypatch.setenv("PATH", str(tmp_path / "nothing here"))
    with pytest.raises(RuntimeError, match="Ghost not found"):
        GhostInvoker._find_ghost()


def _load_tool(name: str):
    path = ROOT / "tools" / "wizzle" / ("%s.py" % name)
    spec = importlib.util.spec_from_file_location("tools_wizzle_%s" % name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_scenarios_builds_into_a_hostile_directory_and_rebuilds(tmp_path):
    from swizzle.wizzle.history_generator import PhantomScenario
    build = _load_tool("build_scenarios")
    out = tmp_path / "out dir; touch pwned"
    out.mkdir()
    first = build.build_scenario(PhantomScenario, out)
    assert (first / ".git").is_dir()
    second = build.build_scenario(PhantomScenario, out)      # removes the old one without a shell
    assert second == first and (second / ".git").is_dir()
    _no_pwned(tmp_path, out, first)


def test_reconstruct_history_run_refuses_a_shell_string():
    reconstruct = _load_tool("reconstruct_history")
    with pytest.raises(TypeError):
        reconstruct.run("echo hi; touch pwned")
    assert reconstruct.run(["git", "--version"]).startswith("git version")


def test_no_shell_true_anywhere_in_the_source():
    offenders = []
    for folder in ("swizzle", "tools"):
        for path in (ROOT / folder).rglob("*.py"):
            if "shell=True" in path.read_text(encoding="utf-8"):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
