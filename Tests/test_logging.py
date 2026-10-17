"""Diagnostics go through `logging`, to stderr, and only when asked for."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import swizzle

ROOT = Path(__file__).resolve().parents[1]


def _run(*args, env_extra=None):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("SWIZZLE_LOG_LEVEL", None)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, "-m", "swizzle.cli", *args], capture_output=True, text=True,
                          timeout=300, cwd=str(ROOT), env=env)


def test_silent_by_default():
    done = _run("prove", "--only", "sql_through")
    assert done.returncode == 0
    assert "DEBUG" not in done.stderr and "INFO" not in done.stderr
    assert done.stderr == ""


def test_verbose_logs_to_stderr_and_leaves_stdout_alone():
    quiet = _run("prove", "--only", "sql_through")
    loud = _run("-vv", "prove", "--only", "sql_through")
    assert loud.stdout == quiet.stdout, "stdout is the report; logging must never change it"
    assert "DEBUG swizzle.summon" in loud.stderr
    assert "DEBUG swizzle.run: proving warp" in loud.stderr


def test_env_var_turns_logging_on():
    done = _run("prove", "--only", "sql_through", env_extra={"SWIZZLE_LOG_LEVEL": "DEBUG"})
    assert "DEBUG swizzle.summon" in done.stderr


def test_a_library_import_adds_no_handler_that_prints():
    root = logging.getLogger("swizzle")
    assert any(isinstance(h, logging.NullHandler) for h in root.handlers)
    assert swizzle.__name__ == "swizzle"


def test_more_than_one_module_logs():
    """The brief for this change: diagnostics are not confined to a single module."""
    users = [p for p in (ROOT / "swizzle").rglob("*.py") if "logging.getLogger(__name__)" in p.read_text("utf-8")]
    assert len(users) >= 8, [str(p.relative_to(ROOT)) for p in users]
