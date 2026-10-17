"""Every package in the source tree is in the wheel.

pyproject.toml lists packages by hand. Three were missing (swizzle.governor, swizzle.integration and
swizzle.production), so an installed SWIZZLE ran `swizzle prove` but failed `swizzle governor` with
ModuleNotFoundError, and that is the command Warden runs for its attack step. It worked from a checkout
and from an editable install, which is why nothing noticed. This holds the list to the tree.
"""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _declared() -> set:
    with open(ROOT / "pyproject.toml", "rb") as fh:
        return set(tomllib.load(fh)["tool"]["setuptools"]["packages"])


def _on_disk() -> set:
    return {".".join(p.parent.relative_to(ROOT).parts) for p in (ROOT / "swizzle").rglob("__init__.py")}


def test_every_package_with_an_init_is_declared_for_the_wheel():
    assert _on_disk() - _declared() == set()


def test_the_packages_the_governor_command_imports_are_declared():
    assert {"swizzle.governor", "swizzle.integration", "swizzle.production"} <= _declared()


def test_the_wheel_ships_no_test_files_and_every_declared_package(tmp_path):
    """Build the wheel from a copy of the tree and read its contents."""
    import shutil
    import subprocess
    import sys
    import zipfile

    import pytest
    pytest.importorskip("setuptools")
    source = tmp_path / "src"
    source.mkdir()
    shutil.copytree(ROOT / "swizzle", source / "swizzle",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("pyproject.toml", "README.md", "LICENSE", "NOTICE"):
        shutil.copy(ROOT / name, source / name)
    out = tmp_path / "wheel"
    done = subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
                           "--wheel-dir", str(out), str(source)],
                          capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-2000:]
    (wheel,) = list(out.glob("swizzle-*.whl"))
    names = zipfile.ZipFile(wheel).namelist()
    # swizzle/integration/test_track.py is a library module (an experiment tracker whose class is
    # called TestTrack), not a pytest file; it is the one allowed name.
    tests = [n for n in names if (Path(n).name.startswith("test_") or "/tests/" in n.lower())
             and n != "swizzle/integration/test_track.py"]
    assert tests == [], "test files ship in the wheel: %s" % tests
    top = {n.split("/")[0] for n in names}
    assert "swizzle" in top and not any(t in top for t in ("Tests", "tools", "fixtures", "corpus"))
    for package in _declared():
        folder = package.replace(".", "/") + "/"
        # swizzle/lab has no __init__.py (it is a namespace folder inside the package), so ask for any module.
        assert any(n.startswith(folder) and n.endswith(".py") for n in names), package
