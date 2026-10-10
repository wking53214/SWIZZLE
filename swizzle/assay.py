"""ASSAY: scoring ghost_buster against damage nobody planted.

Every warp in the catalogue was written by SWIZZLE, so every warp carries
SWIZZLE's idea of what a defect looks like. ASSAY is the other half:
real code, damaged by real accidents, with the correct answer written down
by a person in MANIFEST.md and published as data in
`assay_production/registry.json`. This module reads that answer key,
runs ghost_buster over the specimens, and reports how the scanner did in
the four numbers MANIFEST.md asks for.

WHAT SWIZZLE ADDS AND WHAT IT DOES NOT

ASSAY says what is wrong with each specimen ("REFUSE", "SAME_CONTENT",
"UNREACHABLE"). It does not say which ghost_buster detector ought to say
so; that is a claim about the target, and claims about the target are
SWIZZLE's job. `TRUE_NAMES` below is that claim, one entry per failure
mode, and it is the only thing in this module a reviewer has to trust.

THE TWO HONESTY RULES, AGAIN

1. The answer key is proven before it is used. ASSAY's own
   `verify_manifest.py` asserts every recorded defect by execution. If it
   fails, every verdict is UNSUMMONED: the corpus has drifted and nothing
   scored against it means anything.
2. Nothing is skipped silently. A specimen class ghost_buster has no
   detector for (is this reconstruction faithful? is this the best
   implementation?) is reported as OUT_OF_SCOPE, with whatever the scanner
   did say, and counted as an abstention exactly as MANIFEST.md requires.
   A failure mode ASSAY adds that SWIZZLE has no true name for is
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

REGISTRY = Path("assay_production") / "registry.json"


class AssayUnavailable(RuntimeError):
    """The ASSAY checkout or its answer key could not be used."""


# Outcome names reuse the warp verdict vocabulary where the meaning is the
# same, and add the two that only make sense against an external corpus.
BANISHED = "banished"       # failure mode named: right detector, right place
MISNAMED = "misnamed"       # scanner spoke about the file, said the wrong thing
ESCAPED = "escaped"         # silence over a recorded defect
DISMISSED = "dismissed"     # a must-accept specimen, accepted
CONJURED = "conjured"       # a must-accept specimen, refused
OUT_OF_SCOPE = "out_of_scope"  # ghost_buster has no detector for this question
UNMAPPED = "unmapped"       # ASSAY knows a failure mode SWIZZLE does not
UNSUMMONED = "unsummoned"   # the answer key could not be proven
UNRELIABLE = "unreliable"   # a must-accept specimen Ghost passed while it had not fully looked

#: Higher is better, per specimen, for comparing two revisions of the target.
RANK = {ESCAPED: 0, MISNAMED: 1, BANISHED: 2, CONJURED: 0, DISMISSED: 2}

DUPLICATE_FAMILY = ("duplicate_file", "drifted_copy", "near_duplicate_function",
                    "flattened_copy")

#: Detectors whose firing on a must-accept specimen counts as refusing it.
#: Style findings (a long function, a placeholder name) are not refusals.
REFUSALS = ("unassessable_file",)


@dataclass(frozen=True)
class TrueName:
    """What ghost_buster should say about one ASSAY failure mode."""
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
    #: Set when naming this needs a kind of analysis a syntax-tree scanner
    #: does not do (value ranges, semantics). It never changes the outcome:
    #: an escape is still an escape. It tells the reader which escapes are a
    #: missing detector and which are a missing kind of reasoning.
    beyond_syntax: str = ""


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
            "to point at the branch that assigns it.",
        beyond_syntax="unreachable only because of how two computed scores relate "
                      "numerically (proved in ASSAY by 100k samples); the "
                      "branch is syntactically reachable"),
    "fm_3_5_reskinned_duplicate": TrueName(
        detectors=DUPLICATE_FAMILY, relation=True,
        why="One formula under two class names in two files. Duplicate "
            "detection has to see past the names.",
        beyond_syntax="the two implementations no longer share a shape (one uses "
                      "numpy arrays, the other delegates to the extracted kernel); "
                      "the sameness is the formula and its thresholds, not the code"),
}


@dataclass
class Judgement:
    specimen_id: str
    specimen_class: str
    expected: str
    outcome: str
    findings: List[Tuple[str, str]] = field(default_factory=list)
    account: str = ""
    #: Why Ghost's silence on this specimen cannot be taken as acceptance. Empty when it can.
    unreliable_because: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        out = {"specimen_id": self.specimen_id, "specimen_class": self.specimen_class,
               "expected_verdict": self.expected, "outcome": self.outcome,
               "findings": [list(f) for f in self.findings], "account": self.account}
        if self.unreliable_because:
            out["unreliable_because"] = list(self.unreliable_because)
        return out


# ------------------------------------------------------------------ inputs

def locate_assay(explicit: Optional[Path] = None) -> Optional[Path]:
    """Where ASSAY lives, or None.

    An explicit path is used or refused, never quietly replaced by another
    checkout: a score against a different answer key than the one asked for
    is worse than no score. Without one: $ASSAY, then a sibling checkout.
    """
    try:
        return resolve_assay(explicit)[0]
    except AssayUnavailable:
        return None


def resolve_assay(explicit: Optional[Path] = None) -> Tuple[Path, str]:
    """(path, how it was found). Raises AssayUnavailable with a plain reason."""
    here = Path(__file__).resolve().parents[2]
    if explicit is not None:
        if not (Path(explicit) / REGISTRY).is_file():
            raise AssayUnavailable(
                "--assay %s has no %s (not an ASSAY checkout, or its registry is not published). "
                "Not falling back to another checkout." % (explicit, REGISTRY))
        return Path(explicit).absolute(), "--assay"
    env = os.environ.get("ASSAY")
    if env:
        if not (Path(env) / REGISTRY).is_file():
            raise AssayUnavailable("$ASSAY=%s has no %s. Not falling back to another checkout." % (env, REGISTRY))
        return Path(env).absolute(), "$ASSAY"
    for sibling in (here / "ASSAY", here / "assay"):
        if (sibling / REGISTRY).is_file():
            return sibling.absolute(), "sibling checkout (--assay was not given)"
    raise AssayUnavailable("no ASSAY checkout with a published registry. Pass --assay PATH or set ASSAY.")


def load_answer_key(root: Path) -> Dict[str, dict]:
    path = Path(root) / REGISTRY
    if not path.is_file():
        raise AssayUnavailable(
            "%s has no %s; ASSAY publishes it with "
            "`python3 -m assay_production.manifest_registry --write`" % (root, REGISTRY))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssayUnavailable("%s could not be read: %s" % (path, exc)) from exc
    if not isinstance(data, dict) or not data:
        raise AssayUnavailable("%s is empty or malformed" % path)
    return data


@dataclass
class KeyProof:
    """What running ASSAY's verifier showed."""
    proven: bool
    #: One line: the verifier's own claim count, or why it could not be read.
    summary: str
    #: Why the key is not proven, in the verifier's own words where it gave any.
    reason: str = ""
    #: {"verified_by_execution", "verified_by_static_check", "unvalidated", "total"}
    #: from the verifier's summary line, or None when that line is absent.
    breakdown: Optional[Dict[str, int]] = None


def prove_answer_key(root: Path) -> Tuple[bool, str]:
    """Run ASSAY's own verifier. The corpus asserts its damage by execution."""
    proof = check_answer_key(root)
    return proof.proven, (proof.reason or proof.summary) if not proof.proven else proof.summary


def check_answer_key(root: Path) -> KeyProof:
    script = Path(root) / "verify_manifest.py"
    if not script.is_file():
        return KeyProof(False, "verify_manifest.py is missing", "verify_manifest.py is missing")
    try:
        done = subprocess.run((sys.executable, str(script)), cwd=str(root),
                              capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        why = "verify_manifest.py could not run: %s" % exc
        return KeyProof(False, why, why)
    tail = (done.stdout.strip().splitlines() or [""])[-1]
    summary = next((ln for ln in done.stdout.splitlines() if "claims hold" in ln), tail).strip()
    breakdown = parse_breakdown(done.stdout)
    if done.returncode != 0:
        return KeyProof(False, summary or "verify_manifest.py exited %d" % done.returncode,
                        _failure_reason(done.stdout, done.stderr, done.returncode, summary), breakdown)
    # The verifier's own words must agree with its exit code: "28/29 claims
    # hold" is not a proven key, whatever the exit status says.
    for line in done.stdout.splitlines():
        match = _CLAIMS.search(line)
        if match and match.group(1) != match.group(2):
            why = ("verify_manifest.py exited 0 but says %s/%s claims hold: %s"
                   % (match.group(1), match.group(2), line.strip()))
            return KeyProof(False, why, why, breakdown)
    return KeyProof(True, summary, "", breakdown)


_CLAIMS = re.compile(r"(\d+)\s*(?:/|of)\s*(\d+)\s+(?:manifest\s+)?claims?\s+hold", re.I)

#: The three ways ASSAY says how far an entry was proven. The verifier prints
#: the counts in a summary line; the exact wording has changed and may change
#: again, so each is read by any of its spellings and the line may also be JSON.
_LEVELS = {
    "verified_by_execution": ("verified_by_execution", "verified by execution", "by execution"),
    "verified_by_static_check": ("verified_by_static_check", "verified by static check",
                                 "by static check", "static_check", "static check"),
    "unvalidated": ("unvalidated",),
}


def _json_levels(line: str) -> Optional[Dict[str, int]]:
    start = line.find("{")
    if start < 0:
        return None
    try:
        value = json.loads(line[start:])
    except ValueError:
        return None
    found: Dict[str, int] = {}

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                norm = re.sub(r"[^a-z]+", "_", str(key).lower()).strip("_")
                for level, names in _LEVELS.items():
                    if norm in tuple(n.replace(" ", "_") for n in names) and isinstance(item, int) \
                            and not isinstance(item, bool):
                        found.setdefault(level, item)
                if isinstance(item, (dict, list)):
                    walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)
    walk(value)
    return found or None


def _text_levels(line: str) -> Dict[str, int]:
    found: Dict[str, int] = {}
    for level, names in _LEVELS.items():
        for name in sorted(names, key=len, reverse=True):
            spelled = re.escape(name).replace("\\ ", "[ _]")
            before = re.search(r"(\d+)\s*(?:entries\s+)?" + spelled, line, re.I)
            after = re.search(spelled + r"\s*[=:]\s*(\d+)", line, re.I)
            hit = after or before
            if hit:
                found[level] = int(hit.group(1))
                break
    return found


def parse_breakdown(output: str) -> Optional[Dict[str, int]]:
    """The per-entry status counts out of the verifier's output, or None.

    None means the verifier printed no such line (an older ASSAY, or a wording
    this cannot read). Callers must say "breakdown unavailable", never assume
    the entries were proven.
    """
    for raw in reversed(output.splitlines()):
        line = raw.strip()
        if not line:
            continue
        found = _json_levels(line) or {}
        if len(found) < 3:
            found = {**_text_levels(line), **found}
        if set(found) == set(_LEVELS):
            total = re.search(r"of\s+(\d+)\s+entries", line, re.I)
            if total is None:
                total = re.search(r"(?:total|entries)\W{1,3}(\d+)", line, re.I)
            found["total"] = int(total.group(1)) if total else sum(found.values())
            return found
    return None


def _failure_reason(stdout: str, stderr: str, code: int, summary: str) -> str:
    """Why the verifier said no, in its own words: which checks failed, and the first account of it."""
    lines = stdout.splitlines()
    failed = [ln.strip()[len("FAIL"):].strip() for ln in lines if ln.strip().startswith("FAIL ")]
    parts = ["verify_manifest.py exited %d" % code]
    if summary:
        parts.append(summary)
    if failed:
        shown = "; ".join(f[:140] for f in failed[:3])
        more = " (and %d more)" % (len(failed) - 3) if len(failed) > 3 else ""
        parts.append("failed: %s%s" % (shown, more))
        for index, ln in enumerate(lines):
            if ln.strip() == "* " + failed[0] or ln.strip().startswith("* " + failed[0][:60]):
                said = next((x.strip() for x in lines[index + 1:index + 6]
                             if x.strip().startswith("What happened:")), "")
                if said:
                    parts.append(said[:240])
                break
    elif not summary:
        err = [x.strip() for x in (stderr or "").splitlines() if x.strip()]
        out = [x.strip() for x in lines if x.strip()]
        said = err[-1] if err else (out[-1] if out else "it printed nothing")
        parts.append("it said: %s" % said[:240])
    return ": ".join([parts[0], " | ".join(parts[1:])]) if len(parts) > 1 else parts[0]


def stage(root: Path, into: Path) -> Path:
    """A clean copy of the specimens, as a fresh repository.

    Only `specimens/` is copied: ASSAY's accepted-findings baseline and
    archive marker would otherwise tell ghost_buster which findings to hide,
    and the score would measure the baseline instead of the scanner.
    """
    target = into / "assay"
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


def _blindness_of(findings, path: str) -> List[str]:
    """Reasons Ghost's silence about `path` cannot be read as a clean bill.

    Scan-wide ones (a failed check, an incomplete scan, a baseline that hid
    findings) apply to every specimen; a file Ghost could not parse applies to
    that file only. A plain list of findings, which cannot say, has none.
    """
    why = list(getattr(findings, "blind", None) or [])
    for name, reason in (getattr(findings, "unparsable", None) or {}).items():
        name = name[2:] if name.startswith("./") else name
        if name == path or ("/" in name and path.endswith("/" + name)):
            why.append("Ghost could not parse this file (%s)" % reason)
    return why


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
                j.account = "ASSAY records this failure mode; SWIZZLE has no true name for it"
            else:
                # A relation (duplicate) may be reported from either side; a
                # property of one file must be reported about that file.
                pool = on_primary if name.relation else owned
                j.outcome, j.account = _judge_failure(name, pool, companions, staged, path)
                if j.outcome == ESCAPED:
                    # Still an escape, but say so when Ghost had not fully looked: the miss may be
                    # blindness, not a missing detector, and a floor must not blame it for the former.
                    j.unreliable_because = _blindness_of(findings, path)
                    if j.unreliable_because:
                        j.account += " [Ghost had not fully looked: %s]" % "; ".join(j.unreliable_because[:3])
        elif cls == "REFERENCE":
            refused = [f["detector"] for f, _ in owned
                       if f["detector"] in REFUSALS or f.get("severity") == "critical"]
            j.outcome = CONJURED if refused else DISMISSED
            j.account = ("refused a working implementation: %s" % ", ".join(refused)
                         if refused else "accepted")
            blind = _blindness_of(findings, path) if j.outcome == DISMISSED else []
            if blind:
                # Silence from a Ghost that did not fully look is not acceptance.
                j.outcome = UNRELIABLE
                j.unreliable_because = blind
                j.account = ("Ghost said nothing against it, but it had not fully looked (%s), so this "
                             "is not counted as accepted" % "; ".join(blind[:3]))
        else:
            j.account = "ghost_buster has no detector for %s; abstention" % cls.lower()
        out.append(j)
    return out


def _judge_failure(name: TrueName, on_primary, companions, staged, path) -> Tuple[str, str]:
    reach = (" [beyond syntax: %s]" % name.beyond_syntax) if name.beyond_syntax else ""
    if not on_primary:
        return ESCAPED, "silent: " + name.why + reach
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
    return MISNAMED, ("spoke about the file (%s) but not in the terms that name it: %s%s"
                      % (", ".join(sorted({f["detector"] for f, _ in on_primary})), name.why,
                         reach))


# ----------------------------------------------------------------- running

@dataclass
class Scorecard:
    assay: str
    proof: str
    judgements: List[Judgement]
    #: Checks Ghost said it could not run during the scan, for reasons SWIZZLE
    #: did not ask for. The numbers stand; they are scored over what Ghost saw.
    gaps: List[str] = field(default_factory=list)
    #: Per-entry proof levels from ASSAY's verifier, or None when it printed none.
    breakdown: Optional[Dict[str, int]] = None
    #: Why the key is not proven, when it is not. `proof` carries the short form.
    reason: str = ""
    #: Reasons Ghost's silence cannot be trusted over the whole scan (see invoke.Findings.blind).
    blind: List[str] = field(default_factory=list)

    def possible_catches(self) -> int:
        """Failure modes caught, plus those missed while Ghost had not fully looked.

        The most Ghost could honestly be credited with. A floor that fails even
        at this number is failed for a reliable reason; one that only fails
        below it cannot be decided.
        """
        return self.count("FAILURE_MODE", BANISHED) + sum(
            1 for j in self.judgements
            if j.specimen_class == "FAILURE_MODE" and j.outcome == ESCAPED and j.unreliable_because)

    def count(self, cls: str, outcome: str) -> int:
        return sum(1 for j in self.judgements if j.specimen_class == cls and j.outcome == outcome)

    def total(self, cls: str) -> int:
        return sum(1 for j in self.judgements if j.specimen_class == cls)

    def of(self, outcome: str) -> int:
        return sum(1 for j in self.judgements if j.outcome == outcome)

    @property
    def proven(self) -> bool:
        return not self.proof.startswith("NOT PROVEN")

    def reliability(self) -> Tuple[bool, str]:
        """(numbers_reliable, one plain sentence). Proven is not the same as validated:
        a key can pass its verifier while most of its entries rest on a human's say-so."""
        if not self.proven:
            return False, "the answer key is NOT PROVEN, so these numbers are not a score"
        b = self.breakdown
        if b is None:
            return False, ("breakdown unavailable: the verifier printed no per-entry status counts, so how "
                           "many entries were actually proven by execution is unknown")
        total, bad = b.get("total", 0), b.get("unvalidated", 0)
        if total and bad * 2 > total:
            return False, ("mostly unvalidated: %d of %d entries are unvalidated (rest on human judgement, "
                           "not execution)" % (bad, total))
        if bad:
            return True, "partly validated: %d of %d entries are unvalidated" % (bad, total)
        return True, "every entry was validated by execution or static check"

    def breakdown_line(self) -> str:
        b = self.breakdown
        if b is None:
            return "breakdown unavailable"
        return ("%d verified by execution, %d by static check, %d unvalidated, of %d entries"
                % (b["verified_by_execution"], b["verified_by_static_check"], b["unvalidated"], b["total"]))

    def blind_all(self) -> List[str]:
        """Scan-wide reasons Ghost did not fully look, as recorded on the unreliable specimens."""
        seen: List[str] = []
        for j in self.judgements:
            for why in j.unreliable_because:
                if why not in seen:
                    seen.append(why)
        return seen

    def to_dict(self) -> dict:
        reliable, note = self.reliability()
        key_breakdown = ({"available": False, "note": "breakdown unavailable"} if self.breakdown is None
                         else {"available": True, **self.breakdown})
        return {"assay": self.assay, "proof": self.proof,
                "key_proven": self.proven,
                "key_breakdown": key_breakdown,
                "key_proof_reason": self.reason or None,
                "numbers_reliable": reliable,
                "numbers_reliability_note": note,
                "numbers": self.numbers(),
                "scan_gaps": list(self.gaps),
                "scan_blind": list(self.blind),
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
            "references_accepted_reliable": self.count("REFERENCE", DISMISSED),
            "references_accepted_but_ghost_did_not_fully_look": self.count("REFERENCE", UNRELIABLE),
            "abstentions": self.of(OUT_OF_SCOPE),
        }

    def number_lines(self) -> List[str]:
        out = []
        for label, value in self.numbers().items():
            if label.startswith("references_accepted_"):
                continue
            if label == "references_accepted":
                value = ("accepted (reliable) %d of %d, accepted but Ghost did not fully look %d"
                         % (self.count("REFERENCE", DISMISSED), self.total("REFERENCE"),
                            self.count("REFERENCE", UNRELIABLE)))
            out.append("  %-26s %s" % (label.replace("_", " "), value))
        return out

    def render(self) -> str:
        reliable, note = self.reliability()
        lines = ["SWIZZLE x ASSAY -- ghost_buster against the MANIFEST answer key",
                 "answer key: %s (%s)" % (self.assay, self.proof),
                 "key breakdown: %s" % self.breakdown_line(), ""]
        if not self.proven:
            lines += ["*** ANSWER KEY NOT PROVEN: the numbers below are unreliable and are NOT a score. ***"]
            if self.reason:
                lines.append("    why: %s" % self.reason)
            lines.append("")
        elif not reliable:
            lines += ["*** KEY PROVEN BUT NOT FULLY VALIDATED: %s. Read the numbers below with that in mind. ***"
                      % note, ""]
        elif self.breakdown is not None and self.breakdown.get("unvalidated"):
            lines += ["note: %s." % note, ""]
        lines += self.number_lines()
        lines.append("")
        if self.gaps:
            lines.append("Ghost reported it did not fully look (%d):" % len(self.gaps))
            lines += ["  %s" % gap for gap in self.gaps]
            lines.append("")
        for outcome in (ESCAPED, MISNAMED, CONJURED, UNMAPPED, UNSUMMONED, UNRELIABLE, BANISHED, DISMISSED):
            group = [j for j in self.judgements if j.outcome == outcome]
            if not group:
                continue
            lines.append("%s (%d)" % (outcome, len(group)))
            for j in group:
                lines.append("  %-44s expected %s" % (j.specimen_id, j.expected))
                lines.append("      %s" % j.account)
        return "\n".join(lines)


def run(assay: Path, ghost_tools: Optional[Path]) -> Scorecard:
    answer_key = load_answer_key(assay)
    proof = check_answer_key(assay)
    summary = proof.summary
    if not proof.proven:
        return Scorecard(str(assay), "NOT PROVEN: " + summary, [
            Judgement(sid, e.get("specimen_class", "UNKNOWN"), e.get("expected_verdict", ""),
                      UNSUMMONED, account="verify_manifest.py failed: " + proof.reason)
            for sid, e in sorted(answer_key.items())], breakdown=proof.breakdown, reason=proof.reason)
    with tempfile.TemporaryDirectory(prefix="swizzle-assay-") as scratch:
        staged = stage(assay, Path(scratch))
        findings = scan(staged, ghost_tools)
        judgements = judge(answer_key, findings, staged)
    return Scorecard(str(assay), summary, judgements, gaps=list(getattr(findings, "gaps", ())),
                     breakdown=proof.breakdown,
                     blind=list(getattr(findings, "blind", ()) or ()))


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
        lines = ["SWIZZLE x ASSAY -- baseline vs candidate"]
        changes = self.changes()
        if not changes:
            lines.append("  no specimen changed outcome")
        for kind, sid, old, new in changes:
            lines.append("  %-9s %-44s %s -> %s" % (kind, sid, old, new))
        lines.append("")
        lines.append("candidate:")
        lines += self.candidate.number_lines()
        return "\n".join(lines)


def blocked(card: Scorecard) -> List[str]:
    """Outcomes that mean the run itself is not trustworthy."""
    return [j.specimen_id for j in card.judgements if j.outcome in (UNMAPPED, UNSUMMONED)]
