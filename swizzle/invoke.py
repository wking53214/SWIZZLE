"""Running ghost_buster over a summoned warp and reading back what it said.

The scan is run in a subprocess, with the checks that reach outside the
warp switched off: the test suite, the git-history secrets scan, the
ledger, the branch comparison, the project-shape checks, the structural
model. None of them have an opinion about the defects in the catalogue,
all of them cost seconds or minutes, and the ledger in particular writes a
file into the scanned tree, which would make the second run of a warp
different from the first.

WHAT IS DELIBERATELY LEFT ON

Every file-level detector, which is the entire surface the warps are
written against.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence

#: Checks that reach outside the file set, and the reasons are in the module
#: docstring. `--single-repo` stops it asking about a joined repository.
QUIET = (
    "--json", "--single-repo",
    "--no-tests", "--no-secrets", "--no-ledger", "--no-branches",
    "--no-project", "--no-structure",
)


class InvocationFailed(RuntimeError):
    """ghost_buster could not be run, or said something unreadable."""


def locate_ghost_tools(explicit: Optional[Path] = None) -> Optional[Path]:
    """Where ghost_buster lives, if it is not already importable.

    Order: what the caller said, then GHOST_TOOLS in the environment, then
    the sibling checkout next to this repository, which is how it is
    usually laid out on a machine that has both.
    """
    for candidate in (explicit, os.environ.get("GHOST_TOOLS"),
                      Path(__file__).resolve().parents[2] / "ghost_tools"):
        if not candidate:
            continue
        path = Path(candidate)
        if (path / "ghost_buster" / "cli.py").is_file():
            # Absolute, because it goes on the PYTHONPATH of a scan that runs
            # inside the warp: a relative one is read against the warp and
            # finds nothing. CI's GHOST_TOOLS=../ghost_tools did exactly that.
            return path.absolute()
    return None


class Findings(list):
    """The findings from one scan, as a plain list, plus what it could not see.

    `gaps` holds one plain sentence for each check Ghost says it did not run
    for a reason SWIZZLE did not ask for (a file it could not parse, a check
    that broke). Checks switched off by QUIET, and opt-in checks nobody asked
    for, are not gaps. It is empty for a Ghost that prints a bare list, which
    has no way to say.
    """

    def __init__(self, items=(), gaps=()):
        super().__init__(items)
        self.gaps: List[str] = list(gaps)


#: Ghost's exit code for "I crashed". 0 is clean, 1 is findings, 2 is "did not
#: start". Older Ghosts never used 3.
CRASH_EXIT = 3


def scan(repo: Path, ghost_tools: Optional[Path] = None,
         timeout: float = 300.0) -> List[dict]:
    """Every finding ghost_buster reports inside `repo`.

    Findings come back as the tool's own dictionaries, untouched. SWIZZLE
    reads three keys out of them and stores the rest, so a report can quote
    the tool rather than paraphrase it.

    Both output shapes are read: the bare list older Ghosts print, and the
    object (status, findings, unmeasured, ...) current ones print. A Ghost
    crash raises InvocationFailed and is never read as a clean scan.
    """
    command: Sequence[str] = (sys.executable, "-m", "ghost_buster.cli",
                              str(repo)) + QUIET
    environment = dict(os.environ)
    if ghost_tools is not None:
        existing = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = (str(ghost_tools) + os.pathsep + existing
                                     if existing else str(ghost_tools))
    try:
        done = subprocess.run(command, capture_output=True, text=True,
                              timeout=timeout, env=environment, cwd=str(repo))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InvocationFailed("could not run ghost_buster: %s" % exc) from exc

    stderr_tail = (done.stderr or "").strip()[-400:]
    body = _json_body(done.stdout)
    if body is None:
        if done.returncode == CRASH_EXIT:
            raise InvocationFailed("ghost_buster crashed (exit %d) and printed no "
                                   "result. stderr: %s" % (done.returncode, stderr_tail))
        raise InvocationFailed(
            "no JSON in ghost_buster's output (exit %d). stderr: %s"
            % (done.returncode, stderr_tail))
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise InvocationFailed("ghost_buster's JSON did not parse: %s" % exc) from exc
    return _read(parsed, done.returncode, stderr_tail)


def _read(parsed, returncode: int, stderr_tail: str) -> Findings:
    """Findings (and gaps) out of either shape of Ghost's JSON."""
    if isinstance(parsed, list):
        if returncode == CRASH_EXIT:
            raise InvocationFailed("ghost_buster crashed (exit %d). stderr: %s"
                                   % (returncode, stderr_tail))
        return Findings(parsed)
    if not isinstance(parsed, dict):
        raise InvocationFailed("expected findings from ghost_buster, got %s"
                               % type(parsed).__name__)
    if parsed.get("status") == "error" or returncode == CRASH_EXIT:
        raise InvocationFailed("ghost_buster crashed (exit %d): %s"
                               % (returncode, _crash_message(parsed) or stderr_tail))
    findings = parsed.get("findings")
    if not isinstance(findings, list):
        raise InvocationFailed("ghost_buster's JSON has no list of findings")
    return Findings(findings, _gaps(parsed))


def _crash_message(parsed: dict) -> str:
    error = parsed.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("kind") or "")
    return str(error or "")


def _gaps(parsed: dict) -> List[str]:
    """Checks Ghost did not run for a reason nobody asked for."""
    rows = parsed.get("unmeasured")
    if not isinstance(rows, list):
        return []
    return ["%s: %s" % (row.get("check", "?"), row.get("reason", "did not run"))
            for row in rows if isinstance(row, dict) and not row.get("by_request")]


def _json_body(stdout: str) -> Optional[str]:
    """The JSON (an object or an array) out of a stream that may open with
    progress lines.

    ghost_buster prints progress to stderr and the JSON to stdout, so this
    is usually the whole string. It is written defensively anyway: a future
    version printing one line to stdout would otherwise turn every warp in
    the catalogue into an UNSUMMONED, which reads like SWIZZLE broke.
    """
    lines = stdout.splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith(("[", "{")):
            return "\n".join(lines[index:])
    return None


def git_available() -> bool:
    return shutil.which("git") is not None
