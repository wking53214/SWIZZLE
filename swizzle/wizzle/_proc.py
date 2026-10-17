"""Subprocess helpers for WIZZLE: argv lists, an explicit cwd, a timeout.

Nothing here goes through a shell. A repository path is passed as ``cwd=``
and never interpolated into a command string, so a path containing spaces,
quotes or ``;`` is just a path. A command that cannot start, times out or
exits non-zero is reported to the caller as such; it is never turned into an
empty result.
"""

from __future__ import annotations

import logging
import shlex
import subprocess
from pathlib import Path
from typing import Sequence, Union

log = logging.getLogger(__name__)

#: Seconds a single git command may take before it is treated as failed.
GIT_TIMEOUT = 60.0


class CommandFailed(RuntimeError):
    """A command did not start, timed out, or exited non-zero."""


def run(argv: Sequence[str], cwd: Union[str, Path, None] = None, *,
        timeout: float = GIT_TIMEOUT, check: bool = False) -> "subprocess.CompletedProcess[str]":
    """Run ``argv`` without a shell and return the completed process.

    A command that cannot start (``OSError``) or runs past ``timeout`` raises
    :class:`CommandFailed`: the caller never sees a half-run command as a
    result. With ``check=True`` a non-zero exit raises it too.
    """
    argv = [str(a) for a in argv]
    log.debug("run %s in %s", argv, cwd)
    try:
        done = subprocess.run(argv, cwd=None if cwd is None else str(cwd),
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise CommandFailed("%s timed out after %ss" % (argv[0], timeout)) from exc
    except OSError as exc:
        raise CommandFailed("%s could not be run: %s" % (argv[0], exc)) from exc
    if check and done.returncode != 0:
        raise CommandFailed("%s exited %d: %s"
                            % (" ".join(argv), done.returncode, done.stderr.strip()))
    return done


def git(repo: Union[str, Path], *args: str, timeout: float = GIT_TIMEOUT,
        check: bool = False) -> "subprocess.CompletedProcess[str]":
    """``git <args>`` inside ``repo``; see :func:`run`."""
    return run(("git",) + args, cwd=repo, timeout=timeout, check=check)


def split_command(command: str) -> "list[str]":
    """Split a user-supplied command string into an argv list.

    This is the one place a string command is accepted. It uses POSIX
    ``shlex`` rules, so quoting works but no shell syntax (``;``, ``&&``,
    pipes, expansion) is interpreted: those characters become literal
    arguments. Callers that can build an argv directly should do that instead.
    """
    return shlex.split(command)
