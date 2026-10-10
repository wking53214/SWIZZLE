"""Which copy of another tool SWIZZLE actually used, said out loud.

SWIZZLE finds Ghost, ASSAY and Warden from a flag, an environment variable,
a sibling folder or whatever is importable. A score computed against a stale
sibling checkout looks exactly like one computed against the right one, so
every command that reads another tool says which folder it used and, when it
can be read, which commit that folder is on.

Everything here is read from files. Nothing is run, and a value that cannot be
found is None, never a guess.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Dict, Optional

_SHA = re.compile(r"^[0-9a-f]{40}$")


def git_commit(path: Path) -> Optional[str]:
    """The commit a checkout is on, read from its own .git, or None.

    Only `path` itself is looked at, never a parent: a folder that happens to
    sit inside some other repository must not be credited with that one's commit.
    """
    try:
        dot = Path(path) / ".git"
        if dot.is_file():                      # a worktree or submodule
            text = dot.read_text(encoding="utf-8").strip()
            if not text.startswith("gitdir:"):
                return None
            gitdir = (Path(path) / text[len("gitdir:"):].strip()).resolve()
        elif dot.is_dir():
            gitdir = dot
        else:
            return None
        head = (gitdir / "HEAD").read_text(encoding="utf-8").strip()
        if _SHA.match(head):
            return head
        if not head.startswith("ref:"):
            return None
        ref = head[4:].strip()
        common = gitdir
        if (gitdir / "commondir").is_file():
            common = (gitdir / (gitdir / "commondir").read_text(encoding="utf-8").strip()).resolve()
        for base in (gitdir, common):
            loose = base / ref
            if loose.is_file():
                sha = loose.read_text(encoding="utf-8").strip()
                return sha if _SHA.match(sha) else None
        packed = common / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[1] == ref and _SHA.match(parts[0]):
                    return parts[0]
    except (OSError, ValueError):
        return None
    return None


def package_version(path: Path) -> Optional[str]:
    """The `version` in pyproject.toml, or the first `__version__ = "..."` in an
    `__init__.py` one level down. None when neither is there."""
    root = Path(path)
    try:
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        value = (data.get("project") or {}).get("version")
        if isinstance(value, str) and value:
            return value
    except (OSError, ValueError):
        pass
    try:
        for init in sorted(root.glob("*/__init__.py")):
            found = re.search(r"""^__version__\s*=\s*['"]([^'"]+)['"]""",
                              init.read_text(encoding="utf-8"), re.M)
            if found:
                return found.group(1)
    except OSError:
        pass
    return None


def describe(path: Optional[Path], found_by: str) -> Dict[str, object]:
    """{path, found_by, commit, version} for one tool; commit/version None if unreadable."""
    if path is None:
        return {"path": None, "found_by": found_by, "commit": None, "version": None}
    resolved = Path(path).absolute()
    return {"path": str(resolved), "found_by": found_by,
            "commit": git_commit(resolved), "version": package_version(resolved)}


def importable_ghost_root() -> Optional[Path]:
    """The folder holding an importable `ghost_buster`, without importing it."""
    import importlib.util
    try:
        spec = importlib.util.find_spec("ghost_buster")
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.origin or spec.origin == "namespace":
        return None
    return Path(spec.origin).resolve().parents[1]


def line(label: str, info: Dict[str, object]) -> str:
    """One plain line for the text report."""
    commit = info.get("commit")
    version = info.get("version")
    return "%-15s %s (%s; commit %s%s)" % (
        label + ":", info.get("path") or "(none)", info.get("found_by") or "?",
        str(commit)[:12] if commit else "unreadable",
        ", version %s" % version if version else "")
