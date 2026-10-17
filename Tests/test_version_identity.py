"""One version, said the same everywhere: pyproject, __version__, --version, corpus records."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from importlib import metadata
from pathlib import Path

import pytest

import swizzle
from swizzle import _version

ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def test_cli_version_dunder_version_and_pyproject_agree():
    declared = _pyproject_version()
    done = subprocess.run([sys.executable, "-m", "swizzle.cli", "--version"],
                          capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "swizzle %s" % declared
    assert swizzle.__version__ == declared, (
        "swizzle.__version__ is %r but pyproject.toml says %r; if you just bumped the version, "
        "reinstall (pip install -e .) so the installed metadata follows" % (swizzle.__version__, declared))


def test_installed_metadata_is_where_the_version_comes_from():
    try:
        installed = metadata.version("swizzle")
    except metadata.PackageNotFoundError:
        pytest.skip("swizzle is not installed; the pyproject fallback is tested separately")
    assert swizzle.__version__ == installed


def test_corpus_records_carry_the_real_version():
    from swizzle.lab.corpus import _swizzle_version
    assert _swizzle_version()["version"] == _pyproject_version()


def test_fallback_reads_pyproject_when_nothing_is_installed(monkeypatch):
    def missing(name):
        raise metadata.PackageNotFoundError(name)
    monkeypatch.setattr(_version.metadata, "version", missing)
    assert _version.resolve_version() == _pyproject_version()


def test_unknown_is_said_as_unknown_not_invented(monkeypatch):
    def missing(name):
        raise metadata.PackageNotFoundError(name)
    monkeypatch.setattr(_version.metadata, "version", missing)
    monkeypatch.setattr(_version, "_from_pyproject", lambda: None)
    assert _version.resolve_version() == _version.UNKNOWN == "0+unknown"


def test_the_changelog_names_the_current_version():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [%s]" % _pyproject_version() in text
