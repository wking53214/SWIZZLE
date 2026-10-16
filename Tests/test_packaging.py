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
