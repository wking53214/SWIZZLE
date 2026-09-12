"""Disposable workspaces, and the rule that nothing leaves them.

Every adversarial case is a repository that SWIZZLE wrote, in a directory
SWIZZLE created, which SWIZZLE deletes. The target under test is handed
that directory and nothing else. This module is where that is enforced
rather than intended.

THE THREE THINGS THAT ARE ACTUALLY GUARANTEED

1. A `Sandbox` owns one directory under the system temporary area (or a
   caller-named workspace) and refuses every write whose resolved path is
   not inside it. Refuses, not logs: `SandboxViolation` is an exception.
2. Every subprocess the sandbox starts is given a timeout and a working
   directory inside the sandbox, and is killed on the way out.
3. Deleting a sandbox deletes exactly one directory, the one it made, and
   only after re-checking that the path is still the one it made.

WHAT IS NOT GUARANTEED, STATED PLAINLY

This is not an OS-level jail. A target invoked inside a sandbox is an
ordinary subprocess with the ambient permissions of the user running
SWIZZLE; if it decides to write to the home directory, nothing here stops
it. The isolation is over the INPUT -- what the target is pointed at and
what SWIZZLE itself will touch -- not over the target's syscalls.

That distinction matters for one real reason: a case in this repository
can make a target follow a symlink out of the case directory, and the
scope oracle's job is to notice when it did. Hiding that behind a jail
would remove the very signal the experiment exists to collect. So the
sandbox makes escape VISIBLE rather than impossible, and stages the bait
inside the sandbox where a real file can be harmed without harming
anything of the user's.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence


class SandboxViolation(RuntimeError):
    """A path outside the sandbox was about to be written or deleted."""


@dataclass(frozen=True)
class Completed:
    """What a subprocess did, with nothing thrown away."""

    argv: Sequence[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool
    seconds: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


class Sandbox:
    """One disposable directory, and everything that happens inside it."""

    #: Everything SWIZZLE creates lives under a directory with this prefix,
    #: so a stray sandbox is identifiable at a glance and `purge` has
    #: something safe to key on.
    PREFIX = "swizzle-lab-"

    def __init__(self, root: Optional[Path] = None, keep: bool = False) -> None:
        if root is None:
            self._root = Path(tempfile.mkdtemp(prefix=self.PREFIX)).resolve()
            self._owned = True
        else:
            self._root = Path(root).resolve()
            self._root.mkdir(parents=True, exist_ok=True)
            self._owned = False
        self.keep = keep

    # ---------------------------------------------------------------- paths

    @property
    def root(self) -> Path:
        return self._root

    def resolve(self, relative: str) -> Path:
        """A path inside the sandbox, or `SandboxViolation`.

        Checked twice, because the two failures are different. The lexical
        check catches `../` before anything touches the filesystem. The
        resolved check catches a symlink already on disk that points out,
        which the lexical check cannot see.
        """
        candidate = self._root / relative
        if ".." in Path(relative).parts or Path(relative).is_absolute():
            raise SandboxViolation("%r leaves the sandbox lexically" % relative)
        parent = candidate.parent
        try:
            parent.resolve().relative_to(self._root)
        except ValueError as exc:
            raise SandboxViolation(
                "%r resolves outside the sandbox (%s)" % (relative, parent)) from exc
        return candidate

    def contains(self, path: Path) -> bool:
        """Whether `path`, fully resolved, is inside this sandbox."""
        try:
            Path(path).resolve().relative_to(self._root)
        except (OSError, ValueError):
            return False
        return True

    # ----------------------------------------------------------- filesystem

    def write(self, relative: str, text: str) -> Path:
        target = self.resolve(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def symlink(self, relative: str, points_to: str) -> Path:
        """Create a symlink. The TARGET is deliberately not validated.

        A link that points out of the sandbox is a legitimate experiment --
        it is how a scope attack is staged -- and refusing to create it
        would make the scope oracle untestable. What is validated is where
        the LINK ITSELF goes, which is inside, and the bait it points at is
        staged inside the sandbox too (see `stage_bait`).
        """
        link = self.resolve(relative)
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(points_to)
        return link

    def stage_bait(self, relative: str, text: str) -> Path:
        """A file outside the case repository but inside the sandbox.

        Scope attacks need something to hit that is not supposed to be hit.
        Pointing them at a real file of the user's would be unforgivable, and
        pointing them at nothing makes the attack unobservable, so the bait
        lives in the sandbox beside the case.
        """
        return self.write(os.path.join("_outside", relative), text)

    def snapshot(self, subdir: str = "") -> Dict[str, str]:
        """Path -> sha256 for every regular file under `subdir`.

        Symlinks are recorded by their TARGET TEXT rather than their
        contents, prefixed `symlink:`. Hashing what a link points at would
        make a link and its target indistinguishable, which is precisely
        the confusion the scope oracle is looking for.
        """
        base = (self._root / subdir) if subdir else self._root
        out: Dict[str, str] = {}
        if not base.exists():
            return out
        for path in sorted(base.rglob("*")):
            relative = path.relative_to(self._root).as_posix()
            if path.is_symlink():
                out[relative] = "symlink:" + os.readlink(path)
                continue
            if not path.is_file():
                continue
            try:
                out[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError as exc:                       # unreadable is a fact
                out[relative] = "unreadable:%s" % type(exc).__name__
        return out

    # ------------------------------------------------------------ processes

    def run(self, argv: Sequence[str], cwd: Optional[Path] = None,
            timeout: float = 600.0,
            env: Optional[Mapping[str, str]] = None) -> Completed:
        """Run a subprocess inside the sandbox, always with a timeout."""
        import time
        where = Path(cwd) if cwd is not None else self._root
        if not self.contains(where):
            raise SandboxViolation("refusing to run with cwd outside the sandbox: %s" % where)
        environment = dict(os.environ)
        if env:
            environment.update(env)
        started = time.perf_counter()
        try:
            done = subprocess.run(list(argv), cwd=str(where), capture_output=True,
                                  text=True, timeout=timeout, env=environment)
            return Completed(tuple(argv), done.returncode, done.stdout, done.stderr,
                             False, time.perf_counter() - started)
        except subprocess.TimeoutExpired as exc:
            return Completed(tuple(argv), -1, exc.stdout or "", exc.stderr or "",
                             True, time.perf_counter() - started)
        except OSError as exc:
            return Completed(tuple(argv), -1, "", "%s: %s" % (type(exc).__name__, exc),
                             False, time.perf_counter() - started)

    # ------------------------------------------------------------- lifetime

    def dispose(self) -> None:
        """Delete the sandbox, if this object made it and was not told to keep it."""
        if self.keep or not self._owned:
            return
        root = self._root
        if not root.name.startswith(self.PREFIX):
            raise SandboxViolation(
                "refusing to delete %s: not a directory this sandbox created" % root)
        shutil.rmtree(root, ignore_errors=True)

    def __enter__(self) -> "Sandbox":
        return self

    def __exit__(self, *exc_info) -> None:
        self.dispose()


def changed_paths(before: Mapping[str, str],
                  after: Mapping[str, str]) -> Dict[str, str]:
    """Every path whose content differs between two snapshots.

    The value is what happened -- "added", "removed", "modified" -- rather
    than the hashes, because every caller wants the verb and the hashes are
    still in the snapshots for anything that wants them.
    """
    out: Dict[str, str] = {}
    for path in sorted(set(before) | set(after)):
        was, now = before.get(path), after.get(path)
        if was == now:
            continue
        out[path] = "added" if was is None else "removed" if now is None else "modified"
    return out


def purge(older_than_seconds: float = 0.0) -> Iterable[Path]:
    """Delete stray sandboxes left by a crashed run. Yields what it removed."""
    import time
    now = time.time()
    for candidate in sorted(Path(tempfile.gettempdir()).glob(Sandbox.PREFIX + "*")):
        if not candidate.is_dir():
            continue
        if now - candidate.stat().st_mtime < older_than_seconds:
            continue
        shutil.rmtree(candidate, ignore_errors=True)
        yield candidate
