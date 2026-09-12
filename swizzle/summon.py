"""Writing a warp out as a repository.

SWIZZLE never edits the tool it measures and never edits anything the
user has. Each warp is written into a fresh directory, committed, scanned
and thrown away. That constraint is not politeness: a measurement taken by
modifying the thing being measured is not a measurement.

WHY IT COMMITS

ghost_buster treats a non-git directory as a hard stop rather than a clean
result -- one of its seven principles, and a good one. So a summoned warp
is a real repository with one commit in it, made with `-c user.*` so it
does not depend on the machine having a git identity configured.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .schema import Warp


class SummonFailed(RuntimeError):
    """The warp could not be written or committed. SWIZZLE's failure."""


def summon(warp: Warp, into: Path, as_name: str | None = None,
           files: "dict[str, str] | None" = None) -> Path:
    """Materialise `warp` under `into` and return its root.

    File contents are written exactly as the fixture declares them, with
    nothing added, because a fixture whose contents depend on this function
    is a fixture whose line numbers cannot be trusted.

    `as_name` and `files` exist for controls: the same warp, a different
    file set, its own directory beside the original.
    """
    root = Path(into) / (as_name or warp.name)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    for relative, contents in sorted((files or warp.files).items()):
        target = root / relative
        if not _inside(root, target):
            raise SummonFailed("%s escapes the warp root" % relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")

    _git(root, "init", "--quiet", ".")
    # Nobody signs a fixture. Inherited from whoever is running this, commit
    # signing makes summoning a warp depend on an external signer, and a
    # summon that fails for that reason has failed for a reason that is not
    # about the warp. See the same note in `lab/world.py`.
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "config", "tag.gpgsign", "false")
    _git(root, "add", "--all")
    _git(root, "-c", "user.email=swizzle@invalid", "-c", "user.name=SWIZZLE",
         "commit", "--quiet", "--message", "summon %s" % (as_name or warp.name))
    return root


def _inside(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _git(root: Path, *args: str) -> None:
    try:
        done = subprocess.run(("git",) + args, cwd=root, capture_output=True,
                              text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SummonFailed("git %s: %s" % (args[0], exc)) from exc
    if done.returncode != 0:
        raise SummonFailed("git %s failed: %s"
                           % (args[0], (done.stderr or done.stdout).strip()))
