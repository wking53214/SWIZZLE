"""WIZZLE runs git and Ghost with argv lists, never through a shell, and says when git failed."""

from __future__ import annotations

import ast
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


# --- the shell check ---------------------------------------------------------------------------------------
#
# This is an AST check, not a search for the text "shell=True". A text search is passed by
#     kw = {"shell": True}; subprocess.run(command, **kw)
# because the words never sit together. The rules, applied to every call in swizzle/ and tools/:
#   1. any call with a `shell` keyword whose value is not the constant False is an offender (any callee);
#   2. any dict display with a "shell" key whose value is not the constant False is an offender;
#   3. a `**` unpacking into a subprocess call is an offender unless it unpacks a dict display that is
#      shown, key by key, to leave `shell` out (a `**` inside that display is held to the same rule);
#   4. a call that always uses a shell (os.system, os.popen, subprocess.getoutput, getstatusoutput,
#      asyncio.create_subprocess_shell) is an offender.
# A "subprocess call" is a call to subprocess.run/call/check_call/check_output/Popen (or asyncio.create_subprocess_exec)
# reached by `import subprocess`, `import subprocess as x`, `from subprocess import run [as y]` or a simple
# `name = subprocess.run` assignment. Reaching it by getattr(), importlib or exec is not followed; that is a
# limit of the check, and the source has no such call.

_SUBPROCESS_CALLS = {"run", "call", "check_call", "check_output", "Popen", "create_subprocess_exec"}
_ALWAYS_SHELL = {("subprocess", "getoutput"), ("subprocess", "getstatusoutput"), ("os", "system"), ("os", "popen"),
                 ("asyncio", "create_subprocess_shell")}


def _is_false(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def _dict_omits_shell(node: ast.expr) -> bool:
    """True only for a dict display that provably has no `shell` key."""
    if not isinstance(node, ast.Dict):
        return False
    for key, value in zip(node.keys, node.values, strict=True):
        if key is None:                                   # a nested ** unpacking
            if not _dict_omits_shell(value):
                return False
        elif not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
            return False                                  # a computed key could be "shell"
        elif key.value == "shell":
            return False
    return True


def shell_offences(source: str, label: str = "<source>") -> list[str]:
    """Every place in ``source`` that could start a shell, as ``label:line: why``."""
    tree = ast.parse(source)
    modules: dict[str, str] = {}                          # local name -> module it names
    functions: dict[str, tuple[str, str]] = {}            # local name -> (module, function)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                modules[alias.asname or top] = alias.name if alias.asname else top
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                functions[alias.asname or alias.name] = (node.module, alias.name)
    for node in ast.walk(tree):                           # name = subprocess.run
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            ref = _resolve(node.value, modules, functions)
            if ref is not None:
                functions[node.targets[0].id] = ref

    offences = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=True):
                if (isinstance(key, ast.Constant) and key.value == "shell" and not _is_false(value)):
                    offences.append("%s:%d: a dict with a shell key that is not False" % (label, node.lineno))
        if not isinstance(node, ast.Call):
            continue
        ref = _resolve(node.func, modules, functions)
        for kw in node.keywords:
            if kw.arg == "shell" and not _is_false(kw.value):
                offences.append("%s:%d: shell= is not the constant False" % (label, node.lineno))
            elif kw.arg is None and ref is not None and ref[1] in _SUBPROCESS_CALLS and ref[0] in (
                    "subprocess", "asyncio") and not _dict_omits_shell(kw.value):
                offences.append("%s:%d: ** into %s.%s that cannot be shown to omit shell"
                                % (label, node.lineno, ref[0], ref[1]))
        if ref in _ALWAYS_SHELL:
            offences.append("%s:%d: %s.%s always uses a shell" % (label, node.lineno, ref[0], ref[1]))
    return sorted(set(offences))


def _resolve(node: ast.expr, modules: dict[str, str], functions: dict[str, tuple[str, str]]):
    """(module, function) for ``mod.func`` or a name imported or assigned from it, else None."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in modules:
        return modules[node.value.id], node.attr
    if isinstance(node, ast.Name) and node.id in functions:
        return functions[node.id]
    return None


def shell_offences_in(*folders: Path) -> list[str]:
    found = []
    for folder in folders:
        for path in sorted(folder.rglob("*.py")):
            found += shell_offences(path.read_text(encoding="utf-8"), str(path))
    return found


def test_no_shell_true_anywhere_in_the_source():
    assert shell_offences_in(ROOT / "swizzle", ROOT / "tools") == []


SHELL_SPELLINGS = {
    "the literal": "import subprocess\nsubprocess.run('ls', shell=True)\n",
    "a dict unpacked from a name": "import subprocess\nkw = {'shell': True}\nsubprocess.run('ls', **kw)\n",
    "a dict display unpacked": "import subprocess\nsubprocess.run('ls', **{'shell': True})\n",
    "an unpacked name that is not shown": "import subprocess\ndef f(kw):\n    return subprocess.Popen('ls', **kw)\n",
    "a variable value": "import subprocess\nuse = True\nsubprocess.check_output('ls', shell=use)\n",
    "an imported name": "from subprocess import run\nrun('ls', shell=True)\n",
    "an aliased module": "import subprocess as sp\nsp.call('ls', shell=1)\n",
    "an aliased function": "from subprocess import run as go\nkw = {}\ngo('ls', **kw)\n",
    "an assigned function": "import subprocess\nrunner = subprocess.run\nrunner('ls', shell=True)\n",
    "any other callee": "def helper(**kw): pass\nhelper(shell=True)\n",
    "a shell key in any dict": "options = {'shell': True}\n",
    "a call that is always a shell": "import os\nos.system('ls')\n",
    "getoutput": "import subprocess\nsubprocess.getoutput('ls')\n",
}


@pytest.mark.parametrize("spelling", sorted(SHELL_SPELLINGS))
def test_the_shell_check_rejects_every_spelling(spelling):
    assert shell_offences(SHELL_SPELLINGS[spelling], "snippet"), spelling


SAFE_SPELLINGS = {
    "no shell keyword": "import subprocess\nsubprocess.run(['ls'], check=True)\n",
    "the constant False": "import subprocess\nsubprocess.run(['ls'], shell=False)\n",
    "a dict display without shell": "import subprocess\nsubprocess.run(['ls'], **{'cwd': '.', 'timeout': 5})\n",
    "the word in text only": "NOTE = 'never pass shell=True'\n# shell=True is banned\n",
    "unpacking into a call that is not a subprocess call": "def f(**k): pass\nkw = {}\nf(**kw)\n",
}


@pytest.mark.parametrize("spelling", sorted(SAFE_SPELLINGS))
def test_the_shell_check_accepts_code_that_cannot_start_a_shell(spelling):
    assert shell_offences(SAFE_SPELLINGS[spelling], "snippet") == []


def test_a_mutated_copy_of_the_source_fails_the_scan_in_both_spellings(tmp_path):
    """The real scan, pointed at a throwaway copy of a real module with a shell added each way."""
    source = (ROOT / "swizzle" / "wizzle" / "_proc.py").read_text(encoding="utf-8")
    assert shell_offences(source, "_proc.py") == []
    literal = tmp_path / "literal"
    literal.mkdir()
    (literal / "mutant.py").write_text(source + "\n\ndef _mutant(c):\n    return subprocess.run(c, shell=True)\n")
    unpacked = tmp_path / "unpacked"
    unpacked.mkdir()
    (unpacked / "mutant.py").write_text(
        source + "\n\ndef _mutant(c):\n    kw = {'shell': True}\n    return subprocess.run(c, **kw)\n")
    assert shell_offences_in(literal)
    assert shell_offences_in(unpacked)
    # the text search this replaced would have missed the second
    assert "shell=True" in (literal / "mutant.py").read_text()
    assert "shell=True" not in (unpacked / "mutant.py").read_text()
