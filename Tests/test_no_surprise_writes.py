"""SWIZZLE writes only where it was told to: no ./corpus appears as a side effect of a command."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from swizzle.lab import attack
from swizzle.lab.corpus import Corpus
from Tests import lab_cases
from Tests.fake_target import FakeTarget

ROOT = Path(__file__).resolve().parents[1]


def _swizzle(cwd: Path, *args):
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-m", "swizzle.cli", *args], capture_output=True, text=True,
                          timeout=300, cwd=str(cwd), env=env)


def _listing(folder: Path):
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*"))


@pytest.mark.parametrize("args", [
    ("list",),
    ("prove", "--only", "sql_through"),
    ("corpus",),
    ("corpus", "--bucket", "regression", "--json"),
    ("seed",),
    ("mutators",),
    ("--contract",),
    ("--version",),
])
def test_a_command_leaves_the_working_directory_as_it_found_it(tmp_path, args):
    work = tmp_path / "work"
    work.mkdir()
    done = _swizzle(work, *args)
    assert done.returncode in (0, 1), done.stderr
    assert _listing(work) == [], "created: %s" % _listing(work)


def test_corpus_dir_is_accepted_and_nothing_is_created_by_reading_it(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    named = tmp_path / "elsewhere" / "memory"
    done = _swizzle(work, "corpus", "--corpus-dir", str(named))
    assert done.returncode == 0, done.stderr
    assert _listing(work) == []
    assert not named.exists()
    done = _swizzle(work, "corpus", "--corpus-path", str(named))      # the older spelling still works
    assert done.returncode == 0, done.stderr


def test_recording_writes_only_under_the_given_directory(tmp_path):
    named = tmp_path / "memory"
    work = tmp_path / "cwd"
    work.mkdir()
    previous = os.getcwd()
    os.chdir(work)
    try:
        result = attack.run(lab_cases.with_prose_in_block(), FakeTarget("replace_block"))
        entry = Corpus(named).record(result)
    finally:
        os.chdir(previous)
    assert entry.path.is_relative_to(named)
    assert _listing(work) == []
    assert (named / "discovered").is_dir()
    assert not (named / "regression").exists()          # only the bucket that was written to


def test_the_default_location_is_documented_and_is_the_current_directory():
    from swizzle.lab.cli import DEFAULT_CORPUS
    assert DEFAULT_CORPUS == Path("corpus")
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "--corpus-dir" in text and "./corpus" in text
