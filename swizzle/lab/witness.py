"""Independent evidence, in the world, for what ground truth claims about it.

THE CIRCLE THIS BREAKS

A mutator edits the world and declares what the edit means. Ground truth
records the declaration. An oracle checks the target against ground truth.
Every link holds, and the whole chain can consistently validate a wrong
interpretation, because the mutator was the only authority on its own
semantics and nothing downstream is in a position to disagree.

This is not theoretical. Measured, this session: `DocumentKind.CHANGELOG`
rendered a document indistinguishable from an ordinary README, ground truth
refused the rewrite on the grounds that a changelog entry is about the past,
and the target -- correctly -- rewrote a live claim in a file named
README.md. Two independent oracles corroborated a CRITICAL that was this
laboratory's own mistake. Corroboration does not help when both oracles are
reading the same wrong premise.

WHERE A WITNESS IS REQUIRED, AND WHERE IT IS NOT

Not everywhere. Most protections are the DEFAULT state of a file: nobody
authorised this to change, so nothing may change it. There is no textual
evidence to demand for that, and demanding it would be noise.

A witness is required exactly where ground truth makes a DISCRIMINATING
judgement -- where the world would otherwise look permissible and SWIZZLE
asserts that it is not. Concretely: a claim sitting in a document a target
would ordinarily be allowed to maintain, which ground truth says must not
be rewritten.

That is the whole family that went wrong, and it is the family where
SWIZZLE is asserting something about English rather than about structure.

WHAT INDEPENDENCE MEANS HERE

The checkers live in this module, are registered by name, and read only the
rendered bytes. A mutator NAMES a witness; it does not supply one. It cannot
implement, weaken, or satisfy its own evidence. If the renderer forgets the
marker, or the mutator names the wrong witness, or the declaration is real
but invisible, the case refuses to build rather than producing a finding.

WHAT A WITNESS IS NOT

Proof that the judgement is right. `dated_sentence_visible` finding a date
beside a claim does not establish that a machine must not rewrite it -- that
is still SWIZZLE's judgement about English, and nothing here can tell that
such a judgement is mistaken. What a witness establishes is narrower and
still worth having: whatever the judgement rests on is VISIBLE to the thing
being judged. A target that gets this wrong got it wrong with the evidence
in front of it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, Mapping, Optional, Tuple


@dataclass(frozen=True)
class Witness:
    """A named checker, the file it is about, and what it should find."""

    name: str
    document: str
    #: The line the claim sits on, 1-based, when the witness is about a line.
    line: int = 0
    #: What the mutator expects the checker to find, for the report. Never
    #: used to satisfy the check.
    expectation: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {"witness": self.name, "document": self.document,
                "line": self.line, "expectation": self.expectation}


#: name -> checker. A checker returns None when the evidence is there, or a
#: sentence saying what is missing.
CHECKERS: Dict[str, Callable[[Mapping[str, str], Witness], Optional[str]]] = {}
_WHY: Dict[str, str] = {}


def checker(name: str, why: str):
    def register(fn):
        if name in CHECKERS:
            raise ValueError("two witnesses named %s" % name)
        CHECKERS[name] = fn
        _WHY[name] = why
        return fn
    return register


def _line(files: Mapping[str, str], w: Witness) -> Optional[str]:
    text = files.get(w.document)
    if text is None:
        return None
    lines = text.splitlines()
    if not 1 <= w.line <= len(lines):
        return None
    return lines[w.line - 1]


def _head(files: Mapping[str, str], w: Witness, chars: int = 400) -> str:
    return (files.get(w.document) or "")[:chars]


# ===========================================================================
# The checkers. Each reads bytes and nothing else.
# ===========================================================================

_DATE = re.compile(r"\b(?:as of|recorded|back in|on)\b|\d{4}-\d{2}-\d{2}"
                   r"|\b(?:19|20)\d\d\b", re.I)


@checker("dated_sentence_visible",
         "the claim's own line says it is about a named moment")
def _dated(files, w):
    line = _line(files, w)
    if line is None:
        return "no line %d in %s" % (w.line, w.document)
    if not _DATE.search(line):
        return ("the claim is protected as a dated sentence and its line "
                "carries no date: %r" % line[:70])
    return None


@checker("document_declares_itself_not_current",
         "the document's own head says it is not a live current-state document")
def _declared(files, w):
    head = _head(files, w)
    if not head.strip():
        return "no such document: %s" % w.document
    marks = ("generated", "do not edit", "recorded", "record of a moment",
             "not updated", "no longer", "archived", "snapshot")
    dated_heading = re.search(r"^#+ .*\d{4}-\d{2}-\d{2}", head, re.M)
    dated_version = re.search(r"^#+ .*\bv?\d+\.\d+", head, re.M)
    if dated_heading or dated_version:
        return None
    if any(mark in head.lower() for mark in marks):
        return None
    return ("the document is protected as not-current and its first %d "
            "characters say nothing to that effect" % len(head))


@checker("subject_named_in_the_claim",
         "the claim's own line names a subject other than this repository")
def _attributed(files, w):
    line = _line(files, w)
    if line is None:
        return "no line %d in %s" % (w.line, w.document)
    # A capitalised name, a backticked path, or a quotation: something on the
    # line that says the number belongs to somebody else.
    if re.search(r"`[^`]+`|\"[^\"]+\"|\b[A-Z]{3,}\b|\|", line):
        return None
    return ("the claim is protected as being about another subject and its "
            "line names none: %r" % line[:70])


@checker("not_a_total",
         "the claim's own line says it is a change or a comparison, not a total")
def _not_a_total(files, w):
    line = _line(files, w)
    if line is None:
        return "no line %d in %s" % (w.line, w.document)
    if re.search(r"\bgained\b|\badded\b|\bfrom\b.*\bto\b|\||\bonly\b|\balone\b",
                 line, re.I):
        return None
    return ("the claim is protected as not being a total and its line reads "
            "like one: %r" % line[:70])


@checker("nothing_says_what_is_counted",
         "the claim's own line never says what the number counts")
def _bare(files, w):
    line = _line(files, w)
    if line is None:
        return "no line %d in %s" % (w.line, w.document)
    if re.search(r"\bsuite\b|\ball tests\b|\brepository\b", line, re.I):
        return ("the claim is protected as saying nothing about what it "
                "counts, and its line says: %r" % line[:70])
    return None


@checker("the_suite_visibly_does_not_all_pass",
         "the world contains a test that visibly will not produce a pass: an "
         "import the world does not provide, a module that will not parse, or "
         "a test the repository itself marks as skipped or expected to fail")
def _not_all_passing(files, w):
    """Evidence that lives in the SUITE, not in the document.

    The claim being refused is "N tests, all passing". What makes that
    unwritable is not the sentence or the document -- both are perfectly
    ordinary -- but the fact that part of the suite will not produce a
    passing result. So the witness reads the test files.

    Three forms, one class of evidence, deliberately kept as one checker:
    the GROUNDS are identical in all three ("all passing" is false), and
    only the mechanism differs. Splitting them would suggest three
    independent reasons where there is one.

    Deliberately coarse. It establishes that the world visibly contains
    something that will not pass, which is what a target executing the
    suite would also find out. It does not decide whether that makes the
    claim false; that is still SWIZZLE's judgement about English, and
    nothing here can tell that such a judgement is mistaken.
    """
    provided = {path.rsplit("/", 1)[-1][:-3] for path in files
                if path.endswith(".py")}
    provided |= {path.split("/", 1)[0] for path in files if "/" in path}
    for path, text in sorted(files.items()):
        if not path.endswith(".py"):
            continue
        lowered = text.lower()
        if "xfail" in lowered or "expectedfailure" in lowered:
            return None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("pytest.skip", "raise SkipTest",
                                    "@pytest.mark.skip")):
                return None
            if stripped.startswith(("import ", "from ")):
                name = stripped.split()[1].split(".")[0]
                if name not in provided and name not in _STDLIB:
                    return None
        try:
            compile(text, path, "exec")
        except SyntaxError:
            return None
    return ("the claim is refused because part of the suite does not pass, "
            "and every module in the world imports only what the world "
            "provides, parses cleanly, and declares no skip or xfail")


#: Names an import of which proves nothing about the world. Short on
#: purpose: a long list would start absorbing real missing dependencies.
_STDLIB = frozenset({
    "os", "sys", "re", "json", "time", "math", "random", "pathlib", "typing",
    "dataclasses", "enum", "collections", "functools", "itertools", "hashlib",
    "subprocess", "tempfile", "shutil", "datetime", "textwrap", "io",
    "pytest", "unittest", "warnings", "logging", "abc", "contextlib",
})


def why(name: str) -> str:
    return _WHY.get(name, "")


# ===========================================================================
# Checking
# ===========================================================================

def check(files: Mapping[str, str], w: Optional[Witness]) -> Optional[str]:
    """None when the evidence is there, or a sentence saying what is not."""
    if w is None:
        return ("ground truth refuses a rewrite here and names no witness. "
                "A judgement the world does not carry is a judgement the "
                "target could not have made.")
    fn = CHECKERS.get(w.name)
    if fn is None:
        return "no witness called %r; witness.CHECKERS lists them" % w.name
    return fn(files, w)


def audit(files: Mapping[str, str], claims) -> Tuple[str, ...]:
    """Every discriminating claim that cannot point at the world.

    A claim ground truth PERMITS needs no witness: permitting is what the
    world already looked like, so there is nothing being overridden.
    """
    problems = []
    for claim in claims:
        if claim.may_be_rewritten:
            continue
        missing = check(files, getattr(claim, "witness", None))
        if missing:
            problems.append("%s:%d %s" % (claim.document, claim.line, missing))
    return tuple(problems)
