"""TOUCHSTONE: scoring ghost_buster against damage nobody planted.

Every warp in the catalogue was written by SWIZZLE, so every warp carries
SWIZZLE's idea of what a defect looks like. TOUCHSTONE is the other half:
real code, damaged by real accidents, with the correct answer written down
by a person in MANIFEST.md and published as data in
`touchstone_production/registry.json`. This module reads that answer key,
runs ghost_buster over the specimens, and reports how the scanner did in
the four numbers MANIFEST.md asks for.

WHAT SWIZZLE ADDS AND WHAT IT DOES NOT

TOUCHSTONE says what is wrong with each specimen ("REFUSE", "SAME_CONTENT",
"UNREACHABLE"). It does not say which ghost_buster detector ought to say
so; that is a claim about the target, and claims about the target are
SWIZZLE's job. `TRUE_NAMES` below is that claim, one entry per failure
mode, and it is the only thing in this module a reviewer has to trust.

THE TWO HONESTY RULES, AGAIN

1. The answer key is proven before it is used. TOUCHSTONE's own
   `verify_manifest.py` asserts every recorded defect by execution. If it
   fails, every verdict is UNSUMMONED: the corpus has drifted and nothing
   scored against it means anything.
2. Nothing is skipped silently. A specimen class ghost_buster has no
   detector for (is this reconstruction faithful? is this the best
   implementation?) is reported as OUT_OF_SCOPE, with whatever the scanner
   did say, and counted as an abstention exactly as MANIFEST.md requires.
   A failure mode TOUCHSTONE adds that SWIZZLE has no true name for is
   UNMAPPED and makes the run exit non-zero.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .invoke import InvocationFailed, scan

REGISTRY = Path("touchstone_production") / "registry.json"


class TouchstoneUnavailable(RuntimeError):
    """The TOUCHSTONE checkout or its answer key could not be used."""


# Outcome names reuse the warp verdict vocabulary where the meaning is the
# same, and add the two that only make sense against an external corpus.
BANISHED = "banished"       # failure mode named: right detector, right place
MISNAMED = "misnamed"       # scanner spoke about the file, said the wrong thing
ESCAPED = "escaped"         # silence over a recorded defect
DISMISSED = "dismissed"     # a must-accept specimen, accepted
CONJURED = "conjured"       # a must-accept specimen, refused
OUT_OF_SCOPE = "out_of_scope"  # ghost_buster has no detector for this question
UNMAPPED = "unmapped"       # TOUCHSTONE knows a failure mode SWIZZLE does not
UNSUMMONED = "unsummoned"   # the answer key could not be proven

#: Higher is better, per specimen, for comparing two revisions of the target.
RANK = {ESCAPED: 0, MISNAMED: 1, BANISHED: 2, CONJURED: 0, DISMISSED: 2}

DUPLICATE_FAMILY = ("duplicate_file", "drifted_copy", "near_duplicate_function")

#: Detectors whose firing on a must-accept specimen counts as refusing it.
#: Style findings (a long function, a placeholder name) are not refusals.
REFUSALS = ("unassessable_file",)


@dataclass(frozen=True)
class TrueName:
    """What ghost_buster should say about one TOUCHSTONE failure mode."""
    #: Detectors that count as naming it. Empty means any finding on the
    #: primary file does: the defect is "this file is not what it claims"
    #: and ghost_buster has no narrower word for that yet.
    detectors: Tuple[str, ...] = ()
    #: True when the finding must connect the primary file to its companion
    #: (a duplicate is a relation, not a property of one file).
    relation: bool = False
    #: A regex locating the defect's line in the primary file. A finding
    #: elsewhere in the file is MISNAMED. None: whole-file defect.
    anchor: Optional[str] = None
    slack: int = 3
    why: str = ""


TRUE_NAMES: Dict[str, TrueName] = {
    "fm_3_1_silent_pass": TrueName(
        why="The whole file is one comment: it imports and defines nothing. "
            "Any finding on it beats silence; silence is the failure."),
    "fm_3_2_overclaim": TrueName(
        anchor=r"self\._check_node_compliance\(",
        why="Its only method calls `_check_node_compliance`, defined nowhere. "
            "The finding has to point at that call; a remark about the class "
            "being unused is true and is not the defect."),
    "fm_3_3_flattening_duplicate": TrueName(
        detectors=DUPLICATE_FAMILY, relation=True,
        why="The same content twice, one copy flattened. Duplicate detection "
            "has to connect the two files."),
    "fm_3_4_unreachable_branch": TrueName(
        detectors=("unreachable_declared_state", "dead_code"),
        anchor=r"verdict\s*=\s*EvaluationVerdict\.CRITICAL",
        why="EvaluationVerdict.CRITICAL cannot be reached; the finding has "
            "to point at the branch that assigns it."),
    "fm_3_5_reskinned_duplicate": TrueName(
        detectors=DUPLICATE_FAMILY, relation=True,
        why="One formula under two class names in two files. Duplicate "
            "detection has to see past the names."),
}


@dataclass
class Judgement:
    specimen_id: str
    specimen_class: str
    expected: str
    outcome: str
    findings: List[Tuple[str, str]] = field(default_factory=list)
    account: str = ""

    def to_dict(self) -> dict:
        return {"specimen_id": self.specimen_id, "specimen_class": self.specimen_class,
                "expected_verdict": self.expected, "outcome": self.outcome,
                "findings": [list(f) for f in self.findings], "account": self.account}


# ------------------------------------------------------------------ inputs

def locate_touchstone(explicit: Optional[Path] = None) -> Optional[Path]:
    """Where TOUCHSTONE lives: argument, then TOUCHSTONE env, then a sibling."""
    here = Path(__file__).resolve().parents[2]
    for candidate in (explicit, os.environ.get("TOUCHSTONE"),
                      here / "TOUCHSTONE", here / "touchstone"):
        if candidate and (Path(candidate) / REGISTRY).is_file():
            return Path(candidate).absolute()
    return None


def load_answer_key(root: Path) -> Dict[str, dict]:
    path = Path(root) / REGISTRY
    if not path.is_file():
        raise TouchstoneUnavailable(
            "%s has no %s; TOUCHSTONE publishes it with "
            "`python3 -m touchstone_production.manifest_registry --write`" % (root, REGISTRY))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TouchstoneUnavailable("%s could not be read: %s" % (path, exc)) from exc
    if not isinstance(data, dict) or not data:
        raise TouchstoneUnavailable("%s is empty or malformed" % path)
    return data


def prove_answer_key(root: Path) -> Tuple[bool, str]:
    """Run TOUCHSTONE's own verifier. The corpus asserts its damage by execution."""
    script = Path(root) / "verify_manifest.py"
    if not script.is_file():
        return False, "verify_manifest.py is missing"
    try:
        done = subprocess.run((sys.executable, str(script)), cwd=str(root),
                              capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, "verify_manifest.py could not run: %s" % exc
    tail = (done.stdout.strip().splitlines() or [""])[-1]
    summary = next((ln for ln in done.stdout.splitlines() if "claims hold" in ln), tail)
    return done.returncode == 0, summary.strip()


def stage(root: Path, into: Path) -> Path:
    """A clean copy of the specimens, as a fresh repository.

    Only `specimens/` is copied: TOUCHSTONE's accepted-findings baseline and
    archive marker would otherwise tell ghost_buster which findings to hide,
    and the score would measure the baseline instead of the scanner.
    """
    target = into / "touchstone"
    shutil.copytree(Path(root) / "specimens", target / "specimens",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    subprocess.run(("git", "init", "--quiet"), cwd=str(target), check=False,
                   capture_output=True)
    return target


# ----------------------------------------------------------------- judging

def _files_of(finding: dict, staged: Path) -> List[str]:
    """Every file a finding touches, relative to the staged root.

    Index 0 is always the finding's own file ("" when it has none inside the
    staged tree); the rest are the files it relates that one to.
    """
    evidence = finding.get("evidence") or {}
    own = ""
    absolute = evidence.get("absolute_file")
    if absolute:
        try:
            own = Path(absolute).resolve().relative_to(staged.resolve()).as_posix()
        except ValueError:
            pass
    out = [own]
    # related_files are reported relative to whatever ghost_buster took as its
    # root; match them by suffix against the specimen paths instead.
    for rel in evidence.get("related_files") or []:
        out.append(str(rel).split(":")[0])
    return out


def _touches(finding_files: Sequence[str], path: str) -> bool:
    """Exact match, or a path reported relative to a deeper root.

    A bare filename never matches: `artifact_1.py` exists in two specimen
    directories and guessing which one was meant would credit the scanner
    with a finding it did not make.
    """
    for f in finding_files:
        f = f[2:] if f.startswith("./") else f
        if not f:
            continue
        if f == path or ("/" in f and path.endswith("/" + f)):
            return True
    return False


def _owns(finding_files: Sequence[str], path: str) -> bool:
    """The finding is ABOUT this file: it is the finding's own file, not a relation."""
    return bool(finding_files) and _touches(finding_files[:1], path)  # index 0 = own file


def _anchor_line(staged: Path, path: str, pattern: str) -> Optional[int]:
    text = (staged / path).read_text(encoding="utf-8", errors="replace")
    hits = [i for i, line in enumerate(text.splitlines(), 1) if re.search(pattern, line)]
    return hits[0] if len(hits) == 1 else None


def judge(answer_key: Dict[str, dict], findings: List[dict], staged: Path) -> List[Judgement]:
    indexed = [(f, _files_of(f, staged)) for f in findings]
    out: List[Judgement] = []
    for sid, entry in sorted(answer_key.items()):
        cls = entry.get("specimen_class", "UNKNOWN")
        path = entry.get("path", "")
        companions = list((entry.get("metadata") or {}).get("companions") or [])
        on_primary = [(f, fs) for f, fs in indexed if _touches(fs, path)]
        owned = [(f, fs) for f, fs in on_primary if _owns(fs, path)]
        said = [(f["detector"], f.get("severity", "")) for f, _ in on_primary]
        j = Judgement(sid, cls, entry.get("expected_verdict", "UNKNOWN"), OUT_OF_SCOPE, said)

        if cls == "FAILURE_MODE":
            name = TRUE_NAMES.get(sid)
            if name is None:
                j.outcome = UNMAPPED
                j.account = "TOUCHSTONE records this failure mode; SWIZZLE has no true name for it"
            else:
                # A relation (duplicate) may be reported from either side; a
                # property of one file must be reported about that file.
                pool = on_primary if name.relation else owned
                j.outcome, j.account = _judge_failure(name, pool, companions, staged, path)
        elif cls == "REFERENCE":
            refused = [f["detector"] for f, _ in owned
                       if f["detector"] in REFUSALS or f.get("severity") == "critical"]
            j.outcome = CONJURED if refused else DISMISSED
            j.account = ("refused a working implementation: %s" % ", ".join(refused)
                         if refused else "accepted")
        else:
            j.account = "ghost_buster has no detector for %s; abstention" % cls.lower()
        out.append(j)
    return out


def _judge_failure(name: TrueName, on_primary, companions, staged, path) -> Tuple[str, str]:
    if not on_primary:
        return ESCAPED, "silent: " + name.why
    candidates = [(f, fs) for f, fs in on_primary
                  if not name.detectors or f["detector"] in name.detectors]
    if name.relation:
        candidates = [(f, fs) for f, fs in candidates
                      if any(_touches(fs, c) for c in companions)]
    if name.anchor:
        line = _anchor_line(staged, path, name.anchor)
        if line is None:
            return UNSUMMONED, "the true-name anchor %r is not unique in %s" % (name.anchor, path)
        candidates = [(f, fs) for f, fs in candidates
                      if (f.get("evidence") or {}).get("line_start") is not None
                      and abs(f["evidence"]["line_start"] - line) <= name.slack]
    if candidates:
        f = candidates[0][0]
        return BANISHED, "%s: %s" % (f["detector"], f.get("summary", "")[:160])
    return MISNAMED, ("spoke about the file (%s) but not in the terms that name it: %s"
                      % (", ".join(sorted({f["detector"] for f, _ in on_primary})), name.why))


# ----------------------------------------------------------------- running

@dataclass
class Scorecard:
    touchstone: str
    proof: str
    judgements: List[Judgement]

    def count(self, cls: str, outcome: str) -> int:
        return sum(1 for j in self.judgements if j.specimen_class == cls and j.outcome == outcome)

    def total(self, cls: str) -> int:
        return sum(1 for j in self.judgements if j.specimen_class == cls)

    def of(self, outcome: str) -> int:
        return sum(1 for j in self.judgements if j.outcome == outcome)

    def to_dict(self) -> dict:
        return {"touchstone": self.touchstone, "proof": self.proof,
                "numbers": self.numbers(),
                "judgements": [j.to_dict() for j in self.judgements]}

    def numbers(self) -> dict:
        """The four numbers MANIFEST.md says a verifier is reported as."""
        return {
            "faithful_pairs_accepted": "abstained on all %d (out of scope)"
                                       % self.total("RECONSTRUCTION_PAIR"),
            "failure_modes_caught": "%d of %d" % (self.count("FAILURE_MODE", BANISHED),
                                                  self.total("FAILURE_MODE")),
            "references_accepted": "%d of %d" % (self.count("REFERENCE", DISMISSED),
                                                 self.total("REFERENCE")),
            "abstentions": self.of(OUT_OF_SCOPE),
        }

    def render(self) -> str:
        lines = ["SWIZZLE x TOUCHSTONE -- ghost_buster against the MANIFEST answer key",
                 "answer key: %s (%s)" % (self.touchstone, self.proof), ""]
        for label, value in self.numbers().items():
            lines.append("  %-26s %s" % (label.replace("_", " "), value))
        lines.append("")
        for outcome in (ESCAPED, MISNAMED, CONJURED, UNMAPPED, UNSUMMONED, BANISHED, DISMISSED):
            group = [j for j in self.judgements if j.outcome == outcome]
            if not group:
                continue
            lines.append("%s (%d)" % (outcome, len(group)))
            for j in group:
                lines.append("  %-44s expected %s" % (j.specimen_id, j.expected))
                lines.append("      %s" % j.account)
        return "\n".join(lines)


def run(touchstone: Path, ghost_tools: Optional[Path]) -> Scorecard:
    answer_key = load_answer_key(touchstone)
    proven, summary = prove_answer_key(touchstone)
    if not proven:
        return Scorecard(str(touchstone), "NOT PROVEN: " + summary, [
            Judgement(sid, e.get("specimen_class", "UNKNOWN"), e.get("expected_verdict", ""),
                      UNSUMMONED, account="verify_manifest.py failed: " + summary)
            for sid, e in sorted(answer_key.items())])
    with tempfile.TemporaryDirectory(prefix="swizzle-touchstone-") as scratch:
        staged = stage(touchstone, Path(scratch))
        findings = scan(staged, ghost_tools)
        judgements = judge(answer_key, findings, staged)
    return Scorecard(str(touchstone), summary, judgements)


@dataclass
class Comparison:
    baseline: Scorecard
    candidate: Scorecard

    def changes(self) -> List[Tuple[str, str, str, str]]:
        before = {j.specimen_id: j.outcome for j in self.baseline.judgements}
        out = []
        for j in self.candidate.judgements:
            old = before.get(j.specimen_id)
            if old is None or old == j.outcome:
                continue
            if old in RANK and j.outcome in RANK:
                kind = "regressed" if RANK[j.outcome] < RANK[old] else "improved"
            else:
                kind = "changed"
            out.append((kind, j.specimen_id, old, j.outcome))
        return out

    def regressed(self) -> bool:
        return any(kind == "regressed" for kind, *_ in self.changes())

    def render(self) -> str:
        lines = ["SWIZZLE x TOUCHSTONE -- baseline vs candidate"]
        changes = self.changes()
        if not changes:
            lines.append("  no specimen changed outcome")
        for kind, sid, old, new in changes:
            lines.append("  %-9s %-44s %s -> %s" % (kind, sid, old, new))
        lines.append("")
        lines.append("candidate:")
        for label, value in self.candidate.numbers().items():
            lines.append("  %-26s %s" % (label.replace("_", " "), value))
        return "\n".join(lines)


def blocked(card: Scorecard) -> List[str]:
    """Outcomes that mean the run itself is not trustworthy."""
    return [j.specimen_id for j in card.judgements if j.outcome in (UNMAPPED, UNSUMMONED)]
