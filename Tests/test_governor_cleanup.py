"""The governor runner leaves no temp folder behind, even when something is still writing into it."""

from __future__ import annotations

import logging
import os
import signal
import stat
import tempfile
import time
from pathlib import Path

import pytest

from swizzle.governor import run as gov
from swizzle.governor.scenarios import SCENARIOS

SWIZZLE_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def private_tempdir(tmp_path_factory, monkeypatch):
    private = tmp_path_factory.mktemp("private_tmp")
    monkeypatch.setattr(tempfile, "tempdir", str(private))
    return private


def _leftovers(root: Path):
    return sorted(p.name for p in root.glob("swizzle-governor-*"))


def test_remove_tree_retries_while_a_straggler_keeps_writing(tmp_path, monkeypatch):
    victim = tmp_path / "swizzle-governor-x"
    (victim / "work").mkdir(parents=True)
    real = gov.shutil.rmtree
    calls = []

    def rmtree_with_a_straggler(path, ignore_errors=False):
        calls.append(path)
        real(path, ignore_errors=ignore_errors)
        if len(calls) < 3:                                  # the straggler recreates the folder
            Path(path).mkdir(parents=True)
            (Path(path) / "late.txt").write_text("late")

    monkeypatch.setattr(gov.shutil, "rmtree", rmtree_with_a_straggler)
    monkeypatch.setattr(gov.time, "sleep", lambda s: None)
    assert gov._remove_tree(victim) is True
    assert not victim.exists()
    assert len(calls) == 3


def test_remove_tree_says_so_when_it_cannot(tmp_path, monkeypatch, caplog):
    victim = tmp_path / "swizzle-governor-stuck"
    victim.mkdir()
    monkeypatch.setattr(gov.shutil, "rmtree", lambda path, ignore_errors=False: None)
    monkeypatch.setattr(gov.time, "sleep", lambda s: None)
    with caplog.at_level(logging.WARNING, logger="swizzle.governor.run"):
        assert gov._remove_tree(victim, attempts=2) is False
    assert "could not remove" in caplog.text


def _stub(tmp_path: Path, body: str) -> str:
    script = tmp_path / "py"
    script.write_text("#!/bin/sh\n" + body + "\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_a_straggler_that_left_the_probe_group_does_not_wedge_the_runner_or_leak_the_folder(
        tmp_path, private_tempdir, monkeypatch):
    """The probe starts a child in a NEW session (so killing the probe's group misses it) that keeps the
    stdout pipe open. The runner must still return a not_run finding promptly and remove its folder."""
    monkeypatch.setattr(gov, "_REAP_TIMEOUT", 0.5)
    marker = tmp_path / "straggler.pid"
    stub = _stub(tmp_path, "setsid sleep 30 &\necho $! > %s\nsleep 30" % marker)
    scenario = next(s for s in SCENARIOS if s.name == "tests_weakened")
    started = time.monotonic()
    try:
        finding = gov.run_scenario(scenario, tmp_path, SWIZZLE_ROOT, python=stub, timeout=1)
    finally:
        if marker.exists():
            try:
                os.kill(int(marker.read_text()), signal.SIGKILL)
            except (ProcessLookupError, ValueError):
                pass
    assert time.monotonic() - started < 20
    assert finding.status == "not_run" and "timed out" in finding.detail
    assert _leftovers(private_tempdir) == []
    assert not gov._live_dirs
