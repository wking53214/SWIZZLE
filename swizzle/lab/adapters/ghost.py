"""Ghost Tools, as the laboratory sees it.

Everything in this file is knowledge about Ghost specifically, and it is
all here so that nothing else in the laboratory has to know any of it.

THE FOUR THINGS THAT NEEDED LEARNING

1. `--operate` does not leave its work in the working tree. It opens a
   branch, commits each cut to it, and returns the tree to the branch it
   came in on. Diffing the working directory after an operation shows
   nothing, every time, no matter what was written. The output state is the
   operate branch, and `export_output` checks it out into a worktree.

2. Ghost runs the scanned repository's own test suite by default, and asks
   for consent before running a stranger's code. `GHOST_TOOLS_TRUST=-` is
   Ghost's own documented switch for a harness scanning its own fixtures,
   and it prints that it was used rather than being silent about it.

3. The scan writes its ledger, baseline and case file INTO the scanned
   tree. Those are the tool's bookkeeping, not the patient's content, and
   Ghost itself excludes them from the commits it makes. The laboratory has
   to make the same distinction or every run scores three spurious file
   additions.

4. Checks that reach outside the file set -- the git-history secrets scan,
   the branch comparison, the structural model -- are switched off. Not to
   be kind: they are minutes of work with no bearing on any hypothesis in
   the catalogue, and the secrets scan needs a `gitleaks` binary that may
   not be present, which would turn a missing dependency into an
   indistinguishable "the target failed".
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from ..adapter import Observation, TargetAdapter, TargetUnavailable
from ..draft import TargetDialect
from ..sandbox import Completed, Sandbox

#: The marker pair Ghost once maintained a count inside. Ghost no longer
#: writes into any document, so worlds that carry the pair now test that it
#: is left alone: the spelling is kept so those worlds still read as the old
#: ones did, and so a regression back to rewriting is caught.
COUNT_BLOCK_OPEN = "<!-- ghost_buster:test-count -->"
COUNT_BLOCK_CLOSE = "<!-- /ghost_buster:test-count -->"

#: Ghost's own bookkeeping, which it writes into the tree it examines and
#: excludes from its own commits.
MEMORY_FILES = (".ghost_ledger.json", ".ghost_baseline.json", ".ghost_casefile.json")

#: Documents Ghost's `why_not_writable` would judge writable. Ghost no longer
#: rewrites any document; the judgement survives as detection (it decides
#: whether a claim is reported as a live contradiction). Recorded as a FACT
#: ABOUT GHOST for building worlds on the boundary. Ground truth does not
#: consult it.
WRITABLE_DOCUMENT_NAMES = ("readme.md", "contributing.md", "index.md")

_COMMON = ("--single-repo", "--no-secrets", "--no-branches", "--no-structure")

_CUT = re.compile(r"^cut (\d+): (\S+)\s+->\s+(\S+)", re.M)
_TABLE = re.compile(r"^\s*table\s*:\s*(\S+)", re.M)
_REFUSED = re.compile(r"^refused: (.+)$", re.M)


class GhostToolsAdapter(TargetAdapter):
    """Invoke Ghost, and read back what it did rather than what it said."""

    name = "ghost_tools"

    def __init__(self, checkout: Optional[Path] = None,
                 python: Optional[str] = None) -> None:
        found = _locate(checkout)
        if found is None:
            raise TargetUnavailable(
                "no ghost_tools checkout found. Pass --ghost-tools PATH or set "
                "GHOST_TOOLS. SWIZZLE never reports an attack it could not run.")
        self.checkout = found
        self.python = python or sys.executable
        self._version: Optional[Dict[str, str]] = None

    # ------------------------------------------------------------ dialect

    def dialect(self) -> TargetDialect:
        return TargetDialect(
            name=self.name,
            count_block_open=COUNT_BLOCK_OPEN,
            count_block_close=COUNT_BLOCK_CLOSE,
            writable_document_names=WRITABLE_DOCUMENT_NAMES,
            memory_files=MEMORY_FILES,
            rewrites_documents=False,
        )

    # ------------------------------------------------------------ version

    def version(self) -> Mapping[str, str]:
        if self._version is not None:
            return self._version
        commit = _run_here(self.checkout, ("git", "rev-parse", "HEAD"))
        dirty = _run_here(self.checkout, ("git", "status", "--porcelain"))
        package = ""
        pyproject = self.checkout / "pyproject.toml"
        if pyproject.is_file():
            match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(),
                              re.M)
            package = match.group(1) if match else ""
        self._version = {
            "target": self.name,
            "checkout": str(self.checkout),
            "commit": commit.strip() or "unknown",
            "commit_dirty": "yes" if dirty.strip() else "no",
            "package_version": package or "unknown",
            "python": platform.python_version(),
            "platform": platform.platform(),
        }
        return self._version

    # ------------------------------------------------------------ running

    def _env(self) -> Dict[str, str]:
        existing = os.environ.get("PYTHONPATH", "")
        return {
            "PYTHONPATH": (str(self.checkout) + os.pathsep + existing
                           if existing else str(self.checkout)),
            # Ghost's own documented switch for a harness scanning fixtures.
            # It prints a receipt line rather than being silent, which is
            # captured in the observation like everything else.
            "GHOST_TOOLS_TRUST": "-",
            # Keep the target's own bytecode out of the case repository, so a
            # __pycache__ directory is never scored as a mutation.
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def scan(self, root: Path, sandbox: Sandbox, timeout: float = 900.0) -> Observation:
        argv = (self.python, "-m", "ghost_buster.cli", str(root), "--json") + _COMMON
        done = sandbox.run(argv, cwd=root, timeout=timeout, env=self._env())
        findings = _findings(done.stdout)
        return Observation(
            target=self.name, mode="scan", version=self.version(),
            invocations=(done,), findings=findings,
            abstained=True, memory=_memory(root),
            failed=done.timed_out or (done.returncode not in (0, 1) and not findings),
            failure=_failure(done, findings),
        )

    def act(self, root: Path, sandbox: Sandbox, timeout: float = 900.0) -> Observation:
        argv = (self.python, "-m", "ghost_buster.cli", str(root), "--operate") + _COMMON
        done = sandbox.run(argv, cwd=root, timeout=timeout, env=self._env())

        # THE TARGET NAMES ITS WORKING BRANCH BY THE SECOND, AND WE DRIVE IT
        # FASTER THAN THAT.
        #
        # `ghost/operate-YYYYMMDD-HHMMSS`. Two operations that start inside
        # the same wall-clock second collide, and the second one refuses to
        # begin. One run of the tool never notices; `swizzle loop` runs it
        # back to back and hits it constantly.
        #
        # This is the laboratory outrunning the target, so it is the
        # laboratory's to absorb -- here, behind the adapter, because the
        # branch-naming scheme is a fact about THIS target and nothing above
        # this line may know it. Wait for the clock to tick and ask once
        # more. It is still reported (`collisions`) rather than hidden: a
        # target that cannot be operated twice in one second is a small true
        # thing about it, and a harness that silently papered over it would
        # be deciding on the reader's behalf that it did not matter.
        collisions = 0
        if _collided(done):
            collisions = 1
            _wait_for_the_next_second()
            done = sandbox.run(argv, cwd=root, timeout=timeout, env=self._env())

        cuts = _CUT.findall(done.stdout)
        table = _TABLE.search(done.stdout)
        refused = _REFUSED.search(done.stdout + "\n" + (done.stderr or ""))
        branch = table.group(1) if table else _operate_branch(sandbox, root)
        return Observation(
            target=self.name, mode="act", version=self.version(),
            invocations=(done,),
            claimed_changes=tuple("cut %s: %s -> %s" % c for c in cuts),
            abstained=not cuts,
            output_ref=branch,
            memory=_memory(root),
            notes=_act_notes(refused, collisions),
            failed=done.timed_out or _never_began(done, table),
            failure=_act_failure(done, table, refused),
        )

    # ------------------------------------------------------------- output

    def adopt_output(self, root: Path, sandbox: Sandbox,
                     observation: Observation) -> bool:
        """Fast-forward the branch the patient came in on to the cuts.

        Ghost returns the tree to the branch it found it on and leaves the
        work on its own branch, so nothing is adopted by default -- which is
        correct and is also why iterating has to be explicit. A maintainer
        who merges is the normal end of that flow, and this is that merge.
        """
        ref = observation.output_ref
        if not ref:
            return False
        done = sandbox.run(("git", "merge", "--ff-only", "--quiet", ref),
                           cwd=root, timeout=180)
        if not done.ok:
            done = sandbox.run(("git", "reset", "--hard", "--quiet", ref),
                               cwd=root, timeout=180)
        return done.ok

    def export_output(self, root: Path, sandbox: Sandbox,
                      observation: Observation, into: str) -> Optional[Path]:
        """Check the operate branch out into its own directory.

        A worktree rather than a checkout, because checking the branch out in
        place would change the repository the next observation is about.
        """
        ref = observation.output_ref
        if not ref:
            return None
        destination = sandbox.resolve(into)
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        done = sandbox.run(("git", "worktree", "add", "--quiet", "--detach",
                            str(destination), ref), cwd=root, timeout=180)
        if not done.ok:
            return None
        return destination


# --------------------------------------------------------------- helpers


def _locate(explicit: Optional[Path]) -> Optional[Path]:
    from ...invoke import locate_ghost_tools
    return locate_ghost_tools(explicit)


def _run_here(cwd: Path, argv: Sequence[str]) -> str:
    import subprocess
    try:
        done = subprocess.run(list(argv), cwd=str(cwd), capture_output=True,
                              text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout


def _findings(stdout: str) -> Tuple[Mapping[str, Any], ...]:
    """Ghost's JSON array, out of a stream that opens with progress lines."""
    lines = stdout.splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith("["):
            try:
                parsed = json.loads("\n".join(lines[index:]))
            except json.JSONDecodeError:
                return ()
            return tuple(parsed) if isinstance(parsed, list) else ()
    return ()


def _collided(done: Completed) -> bool:
    """The operation refused to begin because its branch name was taken."""
    if done.timed_out or done.returncode in (0, 1):
        return False
    both = (done.stdout or "") + "\n" + (done.stderr or "")
    hit = _REFUSED.search(both)
    return bool(hit) and "already exists" in hit.group(1)


def _wait_for_the_next_second() -> None:
    """Block until the wall clock crosses into the next whole second.

    Bounded by one second by construction, and the bound is the point: a
    harness that sleeps a fixed interval to make a race go away is a harness
    that will sleep through a real hang. This waits for the exact condition
    that clears the collision and not one tick longer.
    """
    now = time.time()
    time.sleep(max(0.01, (int(now) + 1) - now))


def _never_began(done: Completed, table) -> bool:
    """The operation did not open a table, and did not exit like a tool that
    chose not to.

    An operation that ran and found nothing to do still prints its report.
    No report and a status the tool does not use for ordinary outcomes means
    it never started -- which is not the same as "it ran and changed
    nothing", and must never be read as one.

    A THIRD STATE, WHICH THE FIRST VERSION OF THIS SWALLOWED

    Ran and chose not to act. Never started. And: started, and was killed.

    The crash cases kill the target from inside the suite it is running, on
    purpose, at a point the target chose. That leaves no report and a status
    the tool never produces itself -- which is exactly the shape of "never
    began", and the first version of this function said so. The case that
    exists to ask what a killed tool leaves behind stopped being askable,
    and reported BROKEN instead.

    A signal is evidence of the opposite: something has to be running to be
    killed. Negative returncodes are how Python reports a signal; 128+N is
    how a shell does.
    """
    if done.returncode < 0 or done.returncode >= 128:
        return False                      # killed, so it began
    return table is None and done.returncode not in (0, 1)


def _act_notes(refused, collisions: int) -> str:
    notes = []
    if refused:
        notes.append("refused: " + refused.group(1))
    if collisions:
        notes.append("%d branch-name collision(s) retried after waiting for "
                     "the clock to tick" % collisions)
    return "; ".join(notes)


def _act_failure(done: Completed, table, refused) -> str:
    if done.timed_out:
        return "timed out after %.0fs" % done.seconds
    if not _never_began(done, table):
        return ""
    if refused:
        return "the operation never began: %s" % refused.group(1)
    return "the operation never began: exit %d: %s" % (
        done.returncode, (done.stderr or "").strip()[-300:])


def _failure(done: Completed, findings: Sequence[Mapping[str, Any]]) -> str:
    if done.timed_out:
        return "timed out after %.0fs" % done.seconds
    if not findings and done.returncode not in (0, 1):
        return "exit %d: %s" % (done.returncode, (done.stderr or "").strip()[-300:])
    return ""


def _operate_branch(sandbox: Sandbox, root: Path) -> Optional[str]:
    done = sandbox.run(("git", "branch", "--list", "ghost/operate-*",
                        "--format=%(refname:short)"), cwd=root, timeout=60)
    names = [n.strip() for n in done.stdout.splitlines() if n.strip()]
    return names[-1] if names else None


def _memory(root: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for name in MEMORY_FILES:
        path = root / name
        if path.is_file():
            try:
                out[name] = path.read_text(encoding="utf-8")
            except OSError:
                out[name] = ""
    return out
