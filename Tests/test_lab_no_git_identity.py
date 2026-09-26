"""SWIZZLE's own commits must not depend on the machine's git identity.

Hosted CI runners have no user.name or user.email. The after-baseline commit
relied on them, failed without anyone looking, and left the case's edits
staged; a target that refuses a dirty tree then refused, and every case that
needed the commit read as unmeasured on both sides of a diff.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

from swizzle.lab.attack import _apply_after_baseline
from swizzle.lab.sandbox import Sandbox


def _git(root, *argv):
    return subprocess.run(("git",) + argv, cwd=root, capture_output=True, text=True)


def _no_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "no-identity"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for name in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME",
                 "GIT_COMMITTER_EMAIL", "EMAIL"):
        monkeypatch.delenv(name, raising=False)


def _repository(tmp_path):
    sandbox = Sandbox(tmp_path / "sandbox")
    root = tmp_path / "sandbox" / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "a.py").write_text("x = 1\n")
    _git(root, "add", "a.py")
    _git(root, "-c", "user.email=t@invalid", "-c", "user.name=t",
         "commit", "-q", "-m", "base")
    return sandbox, root


def test_the_after_baseline_commit_needs_no_configured_identity(tmp_path, monkeypatch):
    _no_identity(tmp_path, monkeypatch)
    sandbox, root = _repository(tmp_path)
    draft = SimpleNamespace(after_baseline=(("b.py", "y = 2\n"),))
    assert _apply_after_baseline(draft, root, sandbox) is None
    assert (_git(root, "log", "-1", "--format=%s").stdout.strip()
            == "the change the tool has no memory of")
    assert _git(root, "status", "--porcelain").stdout == ""


def test_a_commit_that_fails_is_reported_as_swizzles_own(tmp_path, monkeypatch):
    """Nothing to commit makes git refuse; that must not read as the target."""
    _no_identity(tmp_path, monkeypatch)
    sandbox, root = _repository(tmp_path)
    draft = SimpleNamespace(after_baseline=(("a.py", "x = 1\n"),))
    broken = _apply_after_baseline(draft, root, sandbox)
    assert broken is not None and broken.startswith("SWIZZLE could not commit")
