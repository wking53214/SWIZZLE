"""Ghost Tools, as the laboratory sees it.

Everything in this file is knowledge about Ghost specifically, and it is
all here so that nothing else in the laboratory has to know any of it.

THE THREE THINGS THAT NEEDED LEARNING

1. Ghost only reports. It used to have a mode that committed changes to a
   branch; that mode is gone, because changing a repository belongs to
   Warden. The dialect says `acts=False`, so the laboratory never asks Ghost
   to act: it judges what Ghost reports, and that the tree is left exactly as
   Ghost found it.

2. Ghost runs the scanned repository's own test suite by default, and asks
   for consent before running a stranger's code. `GHOST_TOOLS_TRUST=-` is
   Ghost's own documented switch for a harness scanning its own fixtures,
   and it prints that it was used rather than being silent about it.

3. The scan writes its ledger, baseline and case file INTO the scanned
   tree. Those are the tool's bookkeeping, not the patient's content. The
   laboratory has to make the same distinction or every run scores three
   spurious file additions.

Checks that reach outside the file set -- the git-history secrets scan, the
branch comparison, the structural model -- are switched off. They are minutes
of work with no bearing on any hypothesis in the catalogue, and the secrets
scan needs a `gitleaks` binary that may not be present, which would turn a
missing dependency into an indistinguishable "the target failed".

HOW A REPORT BECOMES SOMETHING THE ORACLES CAN READ

Ghost's finding vocabulary is Ghost's. For a stale test-count claim the
adapter adds one neutral key, `swizzle_claim`, holding the document, the line
and whether Ghost says the claim is safe for a machine to rewrite. The
reporting oracle reads only that key, so it never names a Ghost detector.
"""

from __future__ import annotations

import json
import os
import platform
import re
import sys
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
            acts=False,
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
            failed=_failed(done, findings),
            failure=_failure(done, findings),
        )


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
    """Ghost's findings, out of a stream that opens with progress lines."""
    return tuple(_with_claim(f) for f in _raw_findings(stdout))


def _with_claim(finding: Mapping[str, Any]) -> Mapping[str, Any]:
    """Add the neutral `swizzle_claim` key to a stale-count finding; leave others alone."""
    if finding.get("detector") != "doc_test_count_drift":
        return finding
    evidence = finding.get("evidence") or {}
    attributes = finding.get("attributes") or {}
    claim = {"document": str(evidence.get("file", "")).replace("\\", "/"),
             "line": evidence.get("line_start"),
             "rewritable": attributes.get("writable") == "yes"}
    return {**finding, "swizzle_claim": claim}


def _parsed(stdout: str) -> Any:
    """Ghost's JSON, an array (older) or an object (current), or None."""
    lines = stdout.splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith(("[", "{")):
            try:
                return json.loads("\n".join(lines[index:]))
            except json.JSONDecodeError:
                return None
    return None


def _raw_findings(stdout: str) -> Tuple[Mapping[str, Any], ...]:
    parsed = _parsed(stdout)
    if isinstance(parsed, dict):
        parsed = parsed.get("findings")
    return tuple(parsed) if isinstance(parsed, list) else ()


def _crashed(done: Completed) -> bool:
    """Ghost's own word for "I crashed": exit 3, or status "error" in its JSON."""
    if done.returncode == 3:
        return True
    parsed = _parsed(done.stdout)
    return isinstance(parsed, dict) and parsed.get("status") == "error"


def _failed(done: Completed, findings: Sequence[Mapping[str, Any]]) -> bool:
    if done.timed_out or _crashed(done):
        return True
    return done.returncode not in (0, 1) and not findings


def _failure(done: Completed, findings: Sequence[Mapping[str, Any]]) -> str:
    if done.timed_out:
        return "timed out after %.0fs" % done.seconds
    if _crashed(done):
        return "ghost_buster crashed (exit %d): %s" % (
            done.returncode, (done.stderr or "").strip()[-300:])
    if not findings and done.returncode not in (0, 1):
        return "exit %d: %s" % (done.returncode, (done.stderr or "").strip()[-300:])
    return ""


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
