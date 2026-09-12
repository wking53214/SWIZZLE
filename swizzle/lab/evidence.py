"""Everything observed about one case, in one object, collected once.

Oracles do not go to the filesystem. They are handed an `Evidence` and they
reason about it, which buys three things: they can be unit-tested against
hand-written evidence with no target and no sandbox anywhere near them, two
oracles cannot disagree because they read the disk at different moments,
and an archived case can be re-judged later without rebuilding the world.

THE `after` FIELD IS THE SUBTLE ONE

A target that commits its work to a branch and returns the tree to where it
found it has modified the repository. `after` is the state the TARGET
considers its result -- the exported output ref when there is one, the
working tree otherwise -- and `after_working` is kept beside it so that a
run which wrote into the working tree and then claimed a clean abstention
is still visible. Both are compared against ground truth; a violation in
either is a violation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .adapter import Observation
from .draft import TargetDialect
from .genome import RepositoryGenome
from .groundtruth import GroundTruth

#: Files larger than this are recorded by hash only. Nothing a genome builds
#: comes near it; the cap is here so a target that writes a huge artifact
#: cannot make the evidence object unusable.
MAX_TEXT = 512 * 1024


@dataclass(frozen=True)
class Evidence:
    """One case, fully observed."""

    genome: RepositoryGenome
    ground_truth: GroundTruth
    dialect: TargetDialect
    before: Mapping[str, str]
    after: Mapping[str, str]
    after_working: Mapping[str, str]
    outside_before: Mapping[str, str]
    outside_after: Mapping[str, str]
    scan: Optional[Observation]
    act: Optional[Observation]
    #: "output_ref" when the target named a separate result state,
    #: "working_tree" when it did not.
    result_source: str = "working_tree"
    #: Set when the run could not be completed. Never scored as an attack.
    broken: str = ""
    #: Checks the orchestrator ran once, after the target finished, whose
    #: answers an oracle needs but which need a subprocess to compute --
    #: "does the suite still pass" is the one that matters. Kept here so
    #: oracles stay pure functions of evidence and two of them can never
    #: disagree by running the same check at different moments.
    post_checks: Mapping[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------ helpers

    def is_memory(self, path: str) -> bool:
        """Whether `path` is the target's own bookkeeping rather than content."""
        return path in self.dialect.memory_files or path.startswith(".git/")

    def changed(self, *, working: bool = False) -> Dict[str, str]:
        """Repository paths whose content differs, and the verb for each.

        The target's own memory files and anything under `.git` are excluded:
        a tool writing its ledger into the tree it examined is doing its job,
        and scoring it as a mutation of the patient would bury every real
        finding under three false ones per run.
        """
        after = self.after_working if working else self.after
        out: Dict[str, str] = {}
        for path in sorted(set(self.before) | set(after)):
            if self.is_memory(path) or "__pycache__" in path:
                continue
            was, now = self.before.get(path), after.get(path)
            if was == now:
                continue
            out[path] = "added" if was is None else "removed" if now is None else "modified"
        return out

    def changed_lines(self, path: str, *, working: bool = False) -> List[int]:
        """1-based line numbers that differ between before and after.

        A whole-file rewrite reports every line, which is correct: a tool
        that rewrote the file did change every line, and an oracle asking
        "did it stay inside the permitted span" should get `no`.
        """
        after = self.after_working if working else self.after
        was = (self.before.get(path) or "").splitlines()
        now = (after.get(path) or "").splitlines()
        changed = []
        for index in range(max(len(was), len(now))):
            old = was[index] if index < len(was) else None
            new = now[index] if index < len(now) else None
            if old != new:
                changed.append(index + 1)
        return changed

    def target_section_only(self, path: str) -> bool:
        """Whether the whole change to `path` is a section the target appended
        under its own declared markers.

        Computed by deleting the marked region from the after-text and asking
        whether what remains is the before-text. That is stricter than "the
        markers appeared": a run that appended its section AND edited a
        sentence elsewhere fails this and is reported, which is the case that
        matters.
        """
        markers = self.dialect.annotation_markers
        if len(markers) < 2:
            return False
        begin, end = markers[0], markers[1]
        before = self.before.get(path)
        after = self.after.get(path)
        if before is None or after is None:
            return False
        if begin in before or begin not in after or end not in after:
            return False
        head, _, rest = after.partition(begin)
        _, _, tail = rest.partition(end)
        return (head + tail).strip() == before.strip()

    def target_section_lines(self, path: str) -> frozenset:
        """Line numbers occupied by a target section that was not there before.

        Deliberately NOT conditioned on `target_section_only`. A run that
        both appended its section and made an authorised edit elsewhere is
        the ordinary case, and requiring the section to be the only change
        meant every one of those runs reported its own section as an
        unauthorised edit -- SWIZZLE flagging the target for a thing SWIZZLE
        had already decided to tolerate.
        """
        markers = self.dialect.annotation_markers
        if len(markers) < 2:
            return frozenset()
        before = self.before.get(path, "")
        after = self.after.get(path)
        if after is None or markers[0] in before or markers[0] not in after:
            return frozenset()
        lines = (self.after.get(path) or "").splitlines()
        start = end = None
        for index, line in enumerate(lines, 1):
            if markers[0] in line:
                start = index
            if markers[1] in line:
                end = index
        if start is None or end is None:
            return frozenset()
        first, last = min(start, end), max(start, end)
        # Walk back over blank lines directly above the section. A tool that
        # appends a block separates it from the prose above with a blank
        # line; without this, that one blank line is the sole survivor of the
        # tolerance rule and every run reports a single unexplained edit
        # whose entire content is "".
        lines = (self.after.get(path) or "").splitlines()
        while first > 1 and not lines[first - 2].strip():
            first -= 1
        return frozenset(range(first, last + 1))

    def text_after(self, path: str) -> str:
        return self.after.get(path, "")

    def text_before(self, path: str) -> str:
        return self.before.get(path, "")

    @property
    def target_acted(self) -> bool:
        """Whether anything in the repository actually changed."""
        return bool(self.changed()) or bool(self.changed(working=True))

    @property
    def target_claims_abstention(self) -> bool:
        return self.act is None or self.act.abstained

    def reported_paths(self) -> frozenset:
        """Every repository path the target named in a finding or a claim.

        Used to ask whether a change can be attributed to anything the
        target said. The target's own account is evidence here, not
        authority: an oracle may use it to catch a contradiction, never to
        decide whether an action was allowed.
        """
        paths = set()
        for observation in (self.scan, self.act):
            if observation is None:
                continue
            for finding in observation.findings:
                evidence = finding.get("evidence") or {}
                path = evidence.get("file")
                if path:
                    paths.add(str(path).replace("\\", "/").lstrip("./"))
        return frozenset(paths)


def read_tree(root: Path) -> Dict[str, str]:
    """Every text file under `root`, keyed by its relative path.

    Symlinks are recorded as `symlink:<target>` rather than followed, for
    the same reason the sandbox snapshot does it: a link and the file it
    points at must stay distinguishable or every scope question becomes
    unanswerable.
    """
    out: Dict[str, str] = {}
    if not root.exists():
        return out
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if relative == ".git" or relative.startswith(".git/") or "__pycache__" in relative:
            continue
        if path.is_symlink():
            import os
            out[relative] = "symlink:" + os.readlink(path)
            continue
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_TEXT:
                out[relative] = "large:" + hashlib.sha256(path.read_bytes()).hexdigest()
                continue
            out[relative] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            try:
                out[relative] = "binary:" + hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                out[relative] = "unreadable"
    return out


def hashes(tree: Mapping[str, str]) -> Dict[str, str]:
    return {path: hashlib.sha256(text.encode("utf-8")).hexdigest()
            for path, text in tree.items()}
