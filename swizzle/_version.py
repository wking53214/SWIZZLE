"""The one place SWIZZLE's version is resolved.

The version is declared once, in ``pyproject.toml``. At runtime it is read
from the installed distribution metadata (``importlib.metadata``), which is
what ``pip`` wrote from that declaration. When the package is imported from a
plain source tree with nothing installed (``PYTHONPATH=.``), the metadata is
absent, so the fallback reads the same ``pyproject.toml`` next to the package.
If neither is available the version is ``0+unknown`` rather than a made-up
number: a wrong version is worse than an honest unknown.
"""

from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path

DISTRIBUTION = "swizzle"
UNKNOWN = "0+unknown"


def _from_pyproject() -> str | None:
    path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    section = re.search(r"^\[project\]\s*$(.*?)(?=^\[|\Z)", text, re.M | re.S)
    if section is None:
        return None
    found = re.search(r'^version\s*=\s*"([^"]+)"', section.group(1), re.M)
    return found.group(1) if found else None


def resolve_version() -> str:
    try:
        return metadata.version(DISTRIBUTION)
    except metadata.PackageNotFoundError:
        return _from_pyproject() or UNKNOWN


__version__ = resolve_version()
