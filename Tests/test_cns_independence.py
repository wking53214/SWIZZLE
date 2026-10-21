"""SWIZZLE is independent of CNS, and these tests hold whether or not CNS is installed.

Each subprocess test runs in a fresh interpreter in which ``cns`` is blocked outright
(``sys.modules['cns'] = None`` makes any import of it fail), so the result does not depend on
what the test environment happens to contain.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BLOCK = "import sys; sys.modules['cns'] = None; sys.modules['cns.gate'] = None; "
BLOCK += "sys.modules['cns.attack'] = None\n"

#: The v1.9.0 tag, pinned by its full commit (the pin policy: a SHA, with the tag in a comment).
EXTRA = ('cns = ["cns @ git+https://github.com/wking53214/CNS.git@da18e411743d4e3b0e783105394d845fb1c16746"]'
         '  # v1.9.0')


def _run(code: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [sys.executable, "-c", BLOCK + textwrap.dedent(code)],
        capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=120,
    )


def _ok(done: subprocess.CompletedProcess[str]) -> None:
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().splitlines()[-1] == "ok"


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())


def test_swizzle_and_its_adapter_import_with_cns_blocked():
    _ok(_run("import swizzle, swizzle.cns_adapter, swizzle.cli; print('ok')"))


def test_swizzle_still_proves_its_warps_with_cns_blocked():
    done = _run(
        """
        from swizzle.cli import main
        code = main(['prove', '--only', 'sql'])
        assert code == 0, code
        print('ok')
        """
    )
    _ok(done)
    assert "proofs hold" in done.stdout


def test_the_adapter_still_translates_a_verdict_with_cns_blocked():
    _ok(_run(
        """
        from swizzle.cns_adapter import translate_verdict
        from swizzle.schema import Verdict
        r = translate_verdict(Verdict.ESCAPED, {'warp': 'x'})
        assert r.translation.cns_outcome == 'terminal_breach'
        assert r.translation.authority == 'advisory_only' and r.gate_result is None
        print('ok')
        """
    ))


def test_a_gate_says_what_is_missing_at_construction_when_cns_is_blocked():
    _ok(_run(
        """
        from swizzle.cns_adapter import AttackGate, CnsNotInstalled, ProofGate, attack_rows
        for build in (ProofGate, AttackGate, lambda: attack_rows([])):
            try:
                build()
            except CnsNotInstalled as exc:
                assert isinstance(exc, ImportError)
                assert "pip install 'swizzle[cns]'" in str(exc), str(exc)
            else:
                raise SystemExit('built without cns')
        print('ok')
        """
    ))


def test_nothing_loads_cns_when_the_package_is_imported():
    # Not blocked: if CNS is installed here, importing SWIZZLE must still not load it.
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    done = subprocess.run(
        [sys.executable, "-c",
         "import sys, swizzle, swizzle.cns_adapter, swizzle.cli\n"
         "print([m for m in sys.modules if m == 'cns' or m.startswith('cns.')])"],
        capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=120,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "[]"


def test_no_module_imports_cns_by_statement():
    # importlib.import_module("cns.gate") inside a function is the one allowed way in.
    offenders = []
    for path in sorted((ROOT / "swizzle").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            if any(n == "cns" or n.startswith("cns.") for n in names):
                offenders.append("%s:%d" % (path.relative_to(ROOT), node.lineno))
    assert offenders == []


def test_the_package_declares_no_runtime_dependency():
    assert _pyproject()["project"]["dependencies"] == []
    assert "cns" in _pyproject()["project"]["optional-dependencies"]


def test_the_cns_extra_is_pinned_to_the_v1_8_0_commit():
    text = (ROOT / "pyproject.toml").read_text()
    assert EXTRA in text.splitlines()
    (spec,) = _pyproject()["project"]["optional-dependencies"]["cns"]
    assert re.fullmatch(
        r"cns @ git\+https://github\.com/wking53214/CNS\.git@[0-9a-f]{40}", spec
    ), spec


def test_ci_installs_the_cns_extra_so_the_cns_tests_run():
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text()
    assert 'pip install -e ".[dev,cns]"' in workflow


def test_the_module_the_gates_live_in_is_packaged():
    # swizzle.cns_adapter is a module of the top-level package, which is listed.
    assert "swizzle" in _pyproject()["tool"]["setuptools"]["packages"]
    assert (ROOT / "swizzle" / "cns_adapter.py").is_file()
