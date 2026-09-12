"""Summon, scan, prove, judge -- once per warp, in that order.

The order matters. The scan runs BEFORE the proof, because the proof
imports the warp's modules and importing writes `__pycache__` into the
tree. Scanning a tree that SWIZZLE has already touched would mean the
second run of a warp could differ from the first for reasons that have
nothing to do with the scanner.

A failure anywhere in the sequence is attributed honestly: if the warp
cannot be written, or the scanner cannot be run, or the proof does not
hold, the verdict is UNSUMMONED and the account says which of the three
it was. None of those are blind spots and none of them are counted as
one.
"""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path
from typing import List, Optional, Sequence

from .invoke import InvocationFailed, scan
from .schema import Outcome, Proof, Verdict, Warp
from .summon import SummonFailed, summon
from .verdict import judge, placed_findings


def run_warp(warp: Warp, workspace: Path,
             ghost_tools: Optional[Path] = None) -> Outcome:
    """One warp, start to finish."""
    try:
        root = summon(warp, workspace)
    except SummonFailed as exc:
        return _unsummoned(warp, "could not be built: %s" % exc)

    try:
        findings = scan(root, ghost_tools)
    except InvocationFailed as exc:
        return _unsummoned(warp, "the scan could not be run: %s" % exc)

    proof = prove(warp, root)
    outcome = judge(warp, findings, proof)

    attribution = check_control(warp, workspace, ghost_tools)
    if attribution:
        outcome = replace(outcome, attribution=attribution)
    return outcome


def check_control(warp: Warp, workspace: Path,
                  ghost_tools: Optional[Path] = None) -> str:
    """Scan the warp with its trick removed, and report what that showed.

    This is the difference between "it escaped, and here is my theory" and
    "it escaped, and the same defect one line different did not". Only
    warps that claim a costume carry a control; the rest return "".
    """
    control = warp.control
    if control is None:
        return ""
    as_name = "%s__control" % warp.name
    try:
        root = summon(warp, workspace, as_name=as_name,
                      files=dict(control.files))
        findings = scan(root, ghost_tools)
    except (SummonFailed, InvocationFailed) as exc:
        return "the control could not be run (%s), so the escape is not "\
               "attributed" % exc

    wanted = control.true_name
    for detector, path, line in placed_findings(findings):
        if (detector == wanted.detector
                and path == wanted.file.replace("\\", "/").lstrip("./")
                and wanted.covers(line)):
            return ("control caught: removing %s brings back `%s` at %s:%s, so "
                    "that is what the warp is hiding behind"
                    % (control.removed, detector, path, line or "-"))
    return ("control ALSO missed: removing %s changed nothing, so this escape "
            "is not explained by the exclusion and needs another reading"
            % control.removed)


def prove(warp: Warp, root: Path, control: bool = False) -> Proof:
    """Run the warp's own proof, turning a crash into a failed proof.

    A proof that raises has not shown anything, and the distinction between
    "the defect is not there" and "the demonstration broke" is SWIZZLE's
    problem either way.

    With `control`, run the control's proof instead where it has one --
    taking a costume off can move the code to an import path the warp's own
    proof does not know.
    """
    runner = warp.prove
    if control and warp.control is not None and warp.control.prove is not None:
        runner = warp.control.prove
    try:
        return runner(root)
    except Exception as exc:                       # the proof is the subject
        return Proof(holds=False, kind="failed",
                     account="%s: %s" % (type(exc).__name__, exc))


def run_all(warps: Sequence[Warp], ghost_tools: Optional[Path] = None,
            keep: Optional[Path] = None) -> List[Outcome]:
    """Every warp, into a workspace that is thrown away unless `keep` is set."""
    if keep is not None:
        keep = Path(keep)
        keep.mkdir(parents=True, exist_ok=True)
        return [run_warp(w, keep, ghost_tools) for w in warps]
    with tempfile.TemporaryDirectory(prefix="swizzle-") as scratch:
        workspace = Path(scratch)
        return [run_warp(w, workspace, ghost_tools) for w in warps]


def _unsummoned(warp: Warp, account: str) -> Outcome:
    return Outcome(warp=warp.name, verdict=Verdict.UNSUMMONED, proof=None,
                   findings=(), account=account)
