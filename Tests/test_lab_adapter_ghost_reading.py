"""Reading the target's exit correctly, without running it.

An adapter's job is to turn "what the tool printed and exited with" into
"what the tool did". Get that wrong in one direction and the laboratory
invents findings; get it wrong in the other and it misses them.

The specific confusion these tests pin down:

    ran, and chose to change nothing      a real outcome, and often correct
    never started at all                  not an outcome. No evidence.

Both leave the repository untouched, and `swizzle loop` asks a question
where they lead to opposite answers -- so the distinction is made here,
once, at the boundary, rather than guessed at by everything above it.

Measured, before this existed: the target names its working branch to the
second, two rounds inside one second collided, the refusal went to stderr
where nothing looked for it, and the harness read a period-3 cycle as a
settled fixpoint.
"""
from __future__ import annotations

import re

import pytest

from swizzle.lab.adapters import ghost
from swizzle.lab.sandbox import Completed

REPORT = "OPERATIVE REPORT  /tmp/x\n  table      : ghost/operate-20260912-131053\n"
COLLISION = ("refused: git checkout -q -b ghost/operate-20260912-131053: "
             "fatal: a branch named 'ghost/operate-20260912-131053' already exists")


def _done(returncode=0, stdout="", stderr="", timed_out=False, seconds=1.0):
    return Completed(("ghost",), returncode, stdout, stderr, timed_out, seconds)


def _table(stdout):
    return ghost._TABLE.search(stdout)


# ------------------------------------------------------- the refusal is read

def test_a_refusal_on_stderr_is_seen():
    """It was only ever looked for on stdout, and the tool prints it on
    stderr. A guard that looks in the wrong stream is not a guard."""
    both = "" + "\n" + COLLISION
    assert ghost._REFUSED.search(both) is not None


def test_a_collision_is_recognised_as_one():
    assert ghost._collided(_done(returncode=2, stderr=COLLISION)) is True


def test_an_ordinary_run_is_not_a_collision():
    assert ghost._collided(_done(returncode=0, stdout=REPORT)) is False


def test_a_run_that_found_something_is_not_a_collision():
    """Exit 1 is how this tool says "I found findings", not "I failed"."""
    assert ghost._collided(_done(returncode=1, stdout=REPORT)) is False


def test_a_timeout_is_not_a_collision():
    """A timeout must reach the classifier as a timeout. Retrying it after
    a one-second wait would burn the whole budget re-running a hang."""
    assert ghost._collided(_done(returncode=2, stderr=COLLISION,
                                 timed_out=True)) is False


def test_some_other_refusal_is_not_retried():
    """Only the name collision clears by waiting. Retrying anything else
    hides a real refusal behind a second attempt."""
    other = "refused: the working tree has uncommitted changes"
    assert ghost._collided(_done(returncode=2, stderr=other)) is False


# ------------------------------------------ ran-and-abstained vs never-began

def test_a_report_with_no_cuts_is_a_run_that_chose_not_to_act():
    done = _done(returncode=1, stdout=REPORT)
    assert ghost._never_began(done, _table(done.stdout)) is False
    assert ghost._act_failure(done, _table(done.stdout), None) == ""


def test_no_report_and_a_status_the_tool_does_not_use_never_began():
    done = _done(returncode=2, stderr=COLLISION)
    assert ghost._never_began(done, _table(done.stdout)) is True


def test_what_never_began_says_names_the_reason():
    done = _done(returncode=2, stderr=COLLISION)
    refused = ghost._REFUSED.search(done.stderr)
    said = ghost._act_failure(done, None, refused)
    assert "never began" in said
    assert "already exists" in said


def test_a_failure_with_no_refusal_line_still_says_something_usable():
    done = _done(returncode=3, stderr="Traceback ...\nMemoryError\n")
    said = ghost._act_failure(done, None, None)
    assert "never began" in said and "exit 3" in said


def test_a_timeout_is_reported_as_a_timeout_not_as_a_refusal():
    done = _done(returncode=2, stderr=COLLISION, timed_out=True, seconds=900.0)
    said = ghost._act_failure(done, None, ghost._REFUSED.search(done.stderr))
    assert "timed out" in said


# ------------------------------------------------------------ the waiting

def test_the_wait_is_bounded_by_one_second_by_construction():
    """A harness that sleeps a fixed interval to make a race go away will
    sleep through a real hang. This waits for the exact condition."""
    import time
    started = time.time()
    ghost._wait_for_the_next_second()
    assert time.time() - started <= 1.05


def test_a_collision_is_reported_rather_than_hidden():
    """The laboratory absorbs the collision; it does not decide on the
    reader's behalf that it did not happen."""
    assert "collision" in ghost._act_notes(None, 1)
    assert ghost._act_notes(None, 0) == ""
    assert "refused" in ghost._act_notes(ghost._REFUSED.search(COLLISION), 0)
