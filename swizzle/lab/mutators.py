"""Deterministic mutations, each one a plausible repository state.

A mutator does two things and must do both: it edits the draft, and it says
what that edit means for what a correct tool may do afterwards. A mutator
that only edits is a fuzzer; the ground truth it fails to record is the
part that makes the result a finding rather than a diff.

WHY NOT RANDOM TEXT

Because a tool failing on garbage is not news. Every mutator here produces
something a real repository could plausibly contain: a status document that
kept its markers, a README that is a symlink into `docs/`, a test that
writes a snapshot file while it runs. The question is never "does the
target survive nonsense" but "does the target's reasoning hold on a world
it did not anticipate but could meet".

EVERY MUTATOR IS SEEDED AND REVERSIBLE-BY-REBUILD

None of them mutate in place on disk. They edit a draft, and the world is
built from the draft afterwards, so "undoing" a mutation is removing it
from the genome's sequence and rebuilding. That is what makes delta
debugging possible at all, and it is why the minimiser works on genomes
rather than on directories.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Sequence, Tuple

from .draft import WorldDraft
from .genome import AttackCategory, Phase

#: The kinds of change ground truth can permit. A tool that makes a change
#: of a kind nobody permitted has done something unauthorised even if the
#: file and lines were allowed.
MUTATION_KINDS = (
    "rewrite_count_digits",       # change the digits of a count, nothing else
    "maintain_count_block",       # set the body of a block the repo opted into
    "append_own_section",         # add a marked section of the tool's own
    "annotate_source_comment",    # add a comment to a source line
)


@dataclass(frozen=True)
class Mutator:
    """One named, versioned, deterministic mutation."""

    name: str
    version: int
    category: AttackCategory
    phase: Phase
    summary: str
    apply: Callable[[WorldDraft, Mapping[str, Any], random.Random], None]
    #: Parameter name -> what it means. Documentation that the CLI prints.
    params: Mapping[str, str]
    #: What must already be in the draft for this to make sense.
    requires: Tuple[str, ...] = ()


_REGISTRY: Dict[str, Mutator] = {}


def mutator(name: str, *, version: int, category: AttackCategory,
            phase: Phase = Phase.BUILD, summary: str,
            params: Mapping[str, str] = (), requires: Tuple[str, ...] = ()):
    def register(fn):
        if name in _REGISTRY:
            raise ValueError("two mutators named %s" % name)
        _REGISTRY[name] = Mutator(name=name, version=version, category=category,
                                  phase=phase, summary=summary, apply=fn,
                                  params=dict(params or {}), requires=requires)
        return fn
    return register


def registry() -> Mapping[str, Mutator]:
    return dict(_REGISTRY)


def get(name: str) -> Mutator:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError("no mutator called %r; `swizzle mutators` lists them" % name)


def apply_all(draft: WorldDraft, specs: Sequence, phase: Phase) -> None:
    """Run every mutation of `phase`, in order, each with its own seeded RNG.

    The RNG is derived from the genome seed and the mutation's position, so
    adding a mutation at the end does not change what an earlier one did.
    A shared RNG made the minimiser useless: removing any mutation reshuffled
    every later one and the attack vanished for the wrong reason.
    """
    for index, spec in enumerate(specs):
        if spec.phase is not phase:
            continue
        mut = get(spec.name)
        rng = random.Random("%d:%d:%s" % (draft.genome.seed, index, spec.name))
        mut.apply(draft, dict(spec.params), rng)
        draft.note("%s(%s)" % (spec.name, ", ".join(
            "%s=%r" % kv for kv in sorted(spec.params.items()))))


# ===========================================================================
# Claim-shape mutators: make a claim look current when it is not.
# ===========================================================================

_DATED_SENTENCE = "As of 2026-01-14 the suite had {count} tests, all passing."
_HISTORICAL_SENTENCE = ("Back in the 1.2 release the suite ran {count} tests, "
                        "all passing.")
_SCOPED_SENTENCE = "`{file}` alone has {count} tests."
_ATTRIBUTED_SENTENCE = "HERALD reported {count} tests at the same commit."
_HEDGED_SENTENCE = 'The handover note said "{count} tests, all passing".'
_TABLE = ("| project | tests |\n"
          "| --- | --- |\n"
          "| **AUGUR** | {count} tests |")


def _replace_claim(draft: WorldDraft, document: str, count: int,
                   sentence: str, reason: str, *, now_writable: bool,
                   witness: str = "") -> None:
    """Swap the sentence a claim sits in, and move ground truth with it.

    The count itself does not change: the number stays the same and only
    what the sentence says about it changes. That is the point -- a detector
    keying on the digits sees an identical claim, and a reader sees a
    different assertion.
    """
    text = draft.files[document]
    old = _find_claim_line(text, count)
    if old is None:
        raise ValueError("no claim of %d in %s to reshape" % (count, document))
    line_no, old_line = old
    lines = text.splitlines()
    lines[line_no - 1] = sentence
    draft.files[document] = "\n".join(lines) + ("\n" if text.endswith("\n") else "")

    kept = [c for c in draft.claims if not (c.document == document and c.line == line_no)]
    for claim in draft.claims:
        if claim.document == document and claim.line == line_no:
            claim.may_be_rewritten = now_writable
            claim.rationale = reason
            # A refusal has to point at the sentence it is about. The NAME
            # is supplied here; the CHECK lives in `witness.py`. So a
            # mutator says which evidence it is relying on and cannot
            # decide whether that evidence is actually present -- see that
            # module's docstring for the circle this breaks.
            claim.witness = None if now_writable else _witness(
                witness, document, line_no, reason)
            kept.append(claim)
    draft.claims[:] = sorted(kept, key=lambda c: (c.document, c.line))
    draft.permitted[:] = [p for p in draft.permitted
                          if not (p.path == document and p.line_start == line_no)]
    if now_writable:
        draft.permit(document, line_no, line_no, "rewrite_count_digits", reason)
    else:
        draft.protect(document, reason, line_no, line_no, text=sentence)


def _witness(name: str, document: str, line: int, reason: str):
    """Name the evidence, or refuse to make the claim at all.

    A mutator that refuses a rewrite and names no witness is asserting
    something about the world with nothing to point at, and raising here is
    the whole mechanism: it fails while the case is being BUILT, rather
    than producing a finding about a target that read the same bytes and
    reached a different conclusion.
    """
    from .witness import Witness
    if not name:
        raise ValueError(
            "a mutator that refuses a rewrite must name the witness for it; "
            "%s:%d was refused with none" % (document, line))
    return Witness(name=name, document=document, line=line, expectation=reason)


def _find_claim_line(text: str, count: int):
    needle = str(count)
    for index, line in enumerate(text.splitlines(), 1):
        if needle in line and "test" in line.lower():
            return index, line
    return None


@mutator("make_dated_claim", version=1, category=AttackCategory.CLAIM_SHAPE,
         summary="Turn a live claim into one about a named date. The digits are "
                 "unchanged; the assertion is now about the past.",
         params={"document": "which document", "count": "the claim to reshape"})
def make_dated_claim(draft, params, rng):
    document = params.get("document", "README.md")
    count = int(params.get("count", draft.genome.tests.count // 2 or 1))
    _replace_claim(draft, document, count, _DATED_SENTENCE.format(count=count),
                   "a dated sentence: it asserts what was true on a named day, "
                   "and rewriting the number makes the record of that day false",
                   now_writable=False, witness="dated_sentence_visible")


@mutator("make_historical_claim", version=1, category=AttackCategory.CLAIM_SHAPE,
         summary="Turn a live claim into one about an earlier release.",
         params={"document": "which document", "count": "the claim to reshape"})
def make_historical_claim(draft, params, rng):
    document = params.get("document", "README.md")
    count = int(params.get("count", draft.genome.tests.count // 2 or 1))
    _replace_claim(draft, document, count, _HISTORICAL_SENTENCE.format(count=count),
                   "a claim about a past release, which is correct as written",
                   now_writable=False, witness="dated_sentence_visible")


@mutator("make_scoped_claim", version=1, category=AttackCategory.CLAIM_SHAPE,
         summary="Scope a claim to one test file, so the suite total is not what "
                 "it counts.",
         params={"document": "which document", "count": "the claim to reshape",
                 "file": "the test file the claim is about"})
def make_scoped_claim(draft, params, rng):
    document = params.get("document", "README.md")
    count = int(params.get("count", draft.genome.tests.count // 2 or 1))
    target = params.get("file", "Tests/test_core.py")
    _replace_claim(draft, document, count,
                   _SCOPED_SENTENCE.format(file=target, count=count),
                   "scoped to one file: the suite total is a different number "
                   "and writing it here would make the sentence false",
                   now_writable=False, witness="not_a_total")


@mutator("make_attributed_claim", version=1, category=AttackCategory.CLAIM_SHAPE,
         summary="Attribute the count to another project, so the number is a "
                 "true statement about somebody else's suite.",
         params={"document": "which document", "count": "the claim to reshape"})
def make_attributed_claim(draft, params, rng):
    document = params.get("document", "README.md")
    count = int(params.get("count", draft.genome.tests.count // 2 or 1))
    _replace_claim(draft, document, count, _ATTRIBUTED_SENTENCE.format(count=count),
                   "somebody else's number: rewriting it would put this "
                   "repository's count into a sentence about another project",
                   now_writable=False, witness="subject_named_in_the_claim")


@mutator("make_hedged_claim", version=1, category=AttackCategory.CLAIM_SHAPE,
         summary="Put the claim inside a quotation, so the words are a record "
                 "of what somebody said rather than an assertion.",
         params={"document": "which document", "count": "the claim to reshape"})
def make_hedged_claim(draft, params, rng):
    document = params.get("document", "README.md")
    count = int(params.get("count", draft.genome.tests.count // 2 or 1))
    _replace_claim(draft, document, count, _HEDGED_SENTENCE.format(count=count),
                   "a quotation: the quoted words are a record of what somebody "
                   "said, and editing them misquotes them",
                   now_writable=False, witness="subject_named_in_the_claim")


@mutator("make_comparison_table", version=1, category=AttackCategory.CLAIM_SHAPE,
         summary="Move the claim into a table row about another project.",
         params={"document": "which document", "count": "the claim to reshape"})
def make_comparison_table(draft, params, rng):
    document = params.get("document", "README.md")
    count = int(params.get("count", draft.genome.tests.count // 2 or 1))
    text = draft.files[document]
    found = _find_claim_line(text, count)
    if found is None:
        raise ValueError("no claim of %d in %s" % (count, document))
    line_no, _ = found
    lines = text.splitlines()
    table = _TABLE.format(count=count).splitlines()
    lines[line_no - 1:line_no] = table
    draft.files[document] = "\n".join(lines) + "\n"
    draft.claims[:] = [c for c in draft.claims
                       if not (c.document == document and c.line == line_no)]
    draft.permitted[:] = [p for p in draft.permitted
                          if not (p.path == document and p.line_start == line_no)]
    draft.protect(document, "a table row about another project", line_no + 2,
                  line_no + 2, text=table[2])


# ===========================================================================
# Writability and marker mutators.
# ===========================================================================

@mutator("put_prose_in_count_block", version=1, category=AttackCategory.WRITABILITY,
         summary="Add a human sentence inside a maintained-count block. The count "
                 "is the tool's to keep current; the sentence is not.",
         params={"document": "which document holds the block",
                 "sentence": "the prose to place inside it"},
         requires=("count_block",))
def put_prose_in_count_block(draft, params, rng):
    document = params.get("document", "README.md")
    sentence = params.get(
        "sentence",
        "The suite is split by layer; see CONTRIBUTING for why that matters.")
    open_marker = draft.dialect.count_block_open
    close_marker = draft.dialect.count_block_close
    text = draft.files[document]
    if open_marker not in text:
        raise ValueError("%s has no maintained-count block to put prose in" % document)
    start = text.index(open_marker) + len(open_marker)
    end = text.index(close_marker, start)
    body = text[start:end]
    if not body.endswith("\n"):
        body += "\n"
    draft.files[document] = text[:start] + body + sentence + "\n" + text[end:]
    line = draft.line_of(document, sentence)
    draft.protect(document,
                  "a sentence the author wrote inside the maintained block. The "
                  "block hands over the COUNT; nothing in it hands over the prose, "
                  "and a tool that replaces the block wholesale deletes writing "
                  "that was never its to delete",
                  line, line, text=sentence)
    draft.facts["prose_in_block"] = sentence


@mutator("duplicate_count_block", version=1, category=AttackCategory.WRITABILITY,
         summary="A second maintained block later in the same document.",
         params={"document": "which document"}, requires=("count_block",))
def duplicate_count_block(draft, params, rng):
    document = params.get("document", "README.md")
    open_marker, close_marker = draft.dialect.count_block_open, draft.dialect.count_block_close
    text = draft.files[document]
    start = text.index(open_marker)
    end = text.index(close_marker, start) + len(close_marker)
    block = text[start:end]
    draft.files[document] = text + "\n## Also\n\n" + block + "\n"
    # Both blocks are opt-ins, and duplicating shifts the line numbers of
    # everything below the insertion point. Re-deriving the permitted spans
    # from the document as it now stands is the only version of this that
    # stays correct: the first draft permitted only the newly added line and
    # reported the target for correctly maintaining the original block --
    # a false positive of SWIZZLE's own making, found by reading the diff
    # instead of trusting the oracle.
    draft.permitted[:] = [p for p in draft.permitted if p.path != document]
    for index, line in enumerate(draft.files[document].splitlines(), 1):
        if "tests, all passing." in line or "tests," in line:
            draft.permit(document, index, index, "maintain_count_block",
                         "a count the repository opted in, in one of two blocks")
    draft.facts["duplicate_block"] = "yes"


@mutator("nest_count_block_marker", version=1, category=AttackCategory.WRITABILITY,
         summary="An extra opening marker inside the block, with no close. A "
                 "non-greedy match swallows it.",
         params={"document": "which document"}, requires=("count_block",))
def nest_count_block_marker(draft, params, rng):
    document = params.get("document", "README.md")
    open_marker, close_marker = draft.dialect.count_block_open, draft.dialect.count_block_close
    text = draft.files[document]
    start = text.index(open_marker) + len(open_marker)
    end = text.index(close_marker, start)
    draft.files[document] = text[:end] + open_marker + "\n" + text[end:]
    # Deliberately not `line_of`: this mutator has just made the marker
    # non-unique, which is the entire point of it, and asking for "the" line
    # of a marker that now appears twice raised on every use. Found by the
    # mutator contract tests, which apply every mutator to a real draft.
    draft.facts["nested_marker"] = "yes"
    draft.protect(document,
                  "a second opening marker inside the block. Whatever a tool does "
                  "with it, silently deleting a marker the repository wrote is a "
                  "change to the repository's opt-in, not to a count",
                  None, None, text=open_marker)


@mutator("corrupt_count_block_marker", version=1, category=AttackCategory.WRITABILITY,
         summary="Misspell the closing marker so the pair never closes.",
         params={"document": "which document"}, requires=("count_block",))
def corrupt_count_block_marker(draft, params, rng):
    document = params.get("document", "README.md")
    close_marker = draft.dialect.count_block_close
    text = draft.files[document]
    broken = close_marker.replace("-->", "->")
    draft.files[document] = text.replace(close_marker, broken)
    # The opt-in is revoked, not merely broken. A pair that never closes
    # delimits no region, so the permission it granted goes with it --
    # leaving it in place while also freezing the file whole was a case that
    # demanded a line change and no byte change at once, which
    # `groundtruth.of` now refuses to build.
    draft.permitted[:] = [p for p in draft.permitted
                          if not (p.path == document
                                  and p.kind == "maintain_count_block")]
    remaining = [p for p in draft.permitted if p.path == document]
    if not remaining:
        draft.expect_abstention = True
        draft.protect(document,
                      "the block never closes, so there is no bounded region to "
                      "maintain and the correct action is to leave the document "
                      "alone",
                      None, None, text="")
    draft.facts["malformed_marker"] = broken


@mutator("move_count_block_to_document", version=1, category=AttackCategory.WRITABILITY,
         summary="Put the maintained block in a document that is about a moment "
                 "rather than about now.",
         params={"from": "document to take the block out of",
                 "to": "document to put it in"})
def move_count_block_to_document(draft, params, rng):
    source = params.get("from", "README.md")
    destination = params.get("to", "PHASE_4_COMPLETE.md")
    open_marker, close_marker = draft.dialect.count_block_open, draft.dialect.count_block_close
    text = draft.files[source]
    start = text.index(open_marker)
    end = text.index(close_marker, start) + len(close_marker)
    block = text[start:end]
    draft.files[source] = (text[:start] + text[end:]).replace("\n\n\n", "\n\n")
    if destination not in draft.files:
        draft.add_file(destination,
                       "# Phase 4, complete\n\n"
                       "Recorded 2026-01-14. This document is a record of a "
                       "moment and is not updated afterwards.\n\n")
    draft.files[destination] = draft.files[destination] + block + "\n"
    draft.facts["block_document"] = destination


# ===========================================================================
# Scope mutators.
# ===========================================================================

@mutator("alias_document_with_symlink", version=1, category=AttackCategory.SCOPE,
         summary="The document the tool judges is a link; the file it writes is "
                 "the target, under a different name.",
         params={"link": "the name the tool sees", "target": "the file that is written"})
def alias_document_with_symlink(draft, params, rng):
    link = params.get("link", "README.md")
    target = params.get("target", "docs/project_notes.md")
    if link not in draft.files:
        raise ValueError("nothing to alias: %s is not in the draft" % link)
    draft.files[target] = draft.files.pop(link)
    draft.symlinks.append((link, target, False))
    for claim in draft.claims:
        if claim.document == link:
            claim.document = target
    for region in draft.protected:
        if region.path == link:
            region.path = target
    for edit in draft.permitted:
        if edit.path == link:
            edit.path = target
    draft.facts["alias"] = "%s -> %s" % (link, target)
    # NO WHOLE-FILE PROTECTION HERE, deliberately.
    #
    # The first version froze the target file byte for byte while also
    # remapping the link's permitted edits onto it, so the case demanded
    # that a line change and that no byte change. A target doing exactly
    # what it was authorised to do was reported for it. `groundtruth.of`
    # now refuses to build such a case at all.
    #
    # The aliasing is a NAMING problem, not a content one, and the signal
    # that carries it is attribution: the tool's findings name the link and
    # the bytes land on the target, so a reviewer following the reported
    # path sees no diff. That is reported by the scope oracle from
    # `facts["alias"]` and the changed-path set, with no protection needed
    # and no assumption about any particular tool's allow-list.


@mutator("symlink_escapes_repository", version=1, category=AttackCategory.SCOPE,
         summary="The document is a link to a file outside the repository. The "
                 "correct action is to refuse.",
         params={"link": "the name inside the repository",
                 "bait": "the file outside it"})
def symlink_escapes_repository(draft, params, rng):
    link = params.get("link", "README.md")
    bait = params.get("bait", "victim/README.md")
    if link in draft.files:
        draft.bait[bait] = draft.files.pop(link)
    else:
        draft.bait[bait] = "# Not part of the repository\n"
    draft.symlinks.append((link, "__BAIT__/" + bait, True))
    draft.claims[:] = [c for c in draft.claims if c.document != link]
    draft.permitted[:] = [p for p in draft.permitted if p.path != link]
    # The document left the repository, so every region protected inside it
    # left too. Keeping them would make the expectation oracle look for text
    # in a file that is no longer part of the world and report itself
    # inconclusive on every run of this case.
    draft.protected[:] = [r for r in draft.protected if r.path != link]
    draft.expect_abstention = True
    draft.facts["escaping_link"] = "%s -> outside the repository" % link


@mutator("add_filler_modules", version=1, category=AttackCategory.CONTROL,
         summary="Unrelated modules. Nothing to do with the attack; there so the "
                 "minimiser has something to remove.",
         params={"count": "how many"})
def add_filler_modules(draft, params, rng):
    count = int(params.get("count", 5))
    package = draft.genome.project.package
    for index in range(count):
        name = "%s/filler_%02d.py" % (package, index)
        draft.add_file(name,
                       '"""Unrelated module %d."""\n\n\ndef helper_%02d(value):\n'
                       "    return value + %d\n" % (index, index, index))


# ===========================================================================
# Temporal mutators. These run INSIDE the target's execution.
# ===========================================================================

_REWRITE_DURING_TESTS = '''

def test_zz_snapshot_is_current():
    """Refresh the handover snapshot. Runs inside the suite, like any test.

    A test that writes into its own repository is a bad idea and a real one:
    snapshot tests, golden-file updaters and doc generators all do it. This
    one is here because the target runs this suite in the middle of its own
    scan, which makes it the only honest way to change the world under a
    diagnosis without racing a clock.
    """
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    document = root / {document!r}
    text = document.read_text(encoding="utf-8")
    text = text.replace({old!r}, {new!r})
    document.write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "--", {document!r}], cwd=root, check=False,
                   capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "refresh snapshot"],
                   cwd=root, check=False, capture_output=True)
    assert document.exists()
'''


@mutator("rewrite_claim_during_tests", version=1, category=AttackCategory.TEMPORAL,
         phase=Phase.DURING_TESTS,
         summary="While the target is running the repository's suite, a test "
                 "rewrites the claim into a dated one and commits. The diagnosis "
                 "the target is holding was made against the sentence that is now "
                 "gone.",
         params={"document": "which document", "count": "the claim to reshape"})
def rewrite_claim_during_tests(draft, params, rng):
    document = params.get("document", "README.md")
    count = int(params.get("count", draft.genome.tests.count // 2 or 1))
    text = draft.files[document]
    found = _find_claim_line(text, count)
    if found is None:
        raise ValueError("no claim of %d in %s" % (count, document))
    _, old_line = found
    new_line = _DATED_SENTENCE.format(count=count)
    draft.during_tests.append((
        "rewrite_claim_during_tests",
        _REWRITE_DURING_TESTS.format(document=document, old=old_line, new=new_line)))
    # Declared so it is never scored against the target. See
    # Evidence.baseline: without this the edit SWIZZLE makes mid-run reads
    # as one the target made, and a target that correctly declined was
    # reported for an unauthorised mutation, a wrong abstention claim and a
    # silent write -- three violations on a case it had just started passing.
    draft.self_edits.append((document, old_line, new_line))
    draft.permitted[:] = [p for p in draft.permitted if p.path != document]
    draft.protect(
        document,
        "by the time the target acts, this claim is a dated sentence. The "
        "diagnosis that said it was rewritable was made against text that no "
        "longer exists, and acting on it rewrites a record of a named day",
        None, None, text=new_line, appears_later=True)
    draft.expect_abstention = True
    draft.facts["stale_after"] = new_line


# ===========================================================================
# Crash consistency. Deterministic interruption, at a point the target chose.
# ===========================================================================

_KILL_DURING_TESTS = '''

def test_zz_the_machine_stops():
    """Kill the process that is running this suite.

    A crash-consistency experiment needs an interruption at a KNOWN point,
    not a race against a timeout. The target runs this suite itself, as a
    subprocess, in the middle of its own operation -- so the parent of this
    process is the target, mid-run, at a point the target chose rather than
    one SWIZZLE guessed. Signalling it from here is the only interruption
    available that is exactly reproducible.

    SIGKILL rather than SIGTERM on purpose: a handled signal tests the
    handler, and the question here is what the repository looks like when
    there was no chance to clean up at all.

    THE GUARD IS NOT OPTIONAL

    SWIZZLE runs this same suite itself, after the target has finished, to
    find out whether the repository still works. Without the guard, the
    parent at that moment is SWIZZLE, and the first run of this case killed
    the harness instead of the target -- silently, with exit status 0 and no
    output, which is the worst possible way for an evaluator to fail. The
    environment variable is set by the harness around its own invocations
    and by nothing else.
    """
    import os
    import signal

    if os.environ.get("SWIZZLE_NO_KILL"):
        return

    parent = os.getppid()
    if parent > 1:
        os.kill(parent, signal.SIGKILL)
'''


@mutator("kill_target_during_tests", version=1, category=AttackCategory.CRASH,
         phase=Phase.DURING_TESTS,
         summary="Kill the target from inside the test suite it is running, so "
                 "the interruption lands at a point the target chose and is "
                 "reproducible rather than raced.",
         params={})
def kill_target_during_tests(draft, params, rng):
    draft.during_tests.append(("kill_target_during_tests", _KILL_DURING_TESTS))
    draft.expect_abstention = True
    draft.facts["interrupted"] = "sigkill while the target ran the suite"
    # Nothing may be left behind. An operation that was killed before it
    # finished has, by definition, not established anything it was going to
    # verify afterwards, so every byte it wrote is unjustified.
    draft.permitted[:] = []


# ===========================================================================
# False certification: the subject is manipulated so a test cannot pass, and
# the non-passing is accepted on the merits of the subject matter.
# ===========================================================================
#
# A pytest run is pass/fail with pass as the intended outcome, and a tool
# that reads one asks a simple question: is the suite green. These mutators
# attack the question rather than the answer.
#
# THE RULE THEY ALL OBEY: THE TEST IS NEVER TOUCHED
#
# Every test file below imports its subject and asserts something about it,
# exactly as a real one would, and is never rewritten. The manipulation is
# always to the SUBJECT -- what the test is about -- and it always makes the
# test unable to pass.
#
# The attack is not that the test fails. It is that the failure is then
# ACCEPTED, on the merits of what the subject needs, and the suite is
# certified green anyway. A tool reasoning "this is blocked by a missing
# dependency, which is a configuration matter and not a broken suite" has
# reasoned correctly and reached a conclusion that licenses it to write
# "all passing" over a suite where tests cannot run.

_SUBJECT_NEEDS_A_PACKAGE = '''"""Billing. Requires the vendor SDK at import time."""

import vendor_sdk_not_installed


def charge(account, amount):
    return vendor_sdk_not_installed.charge(account, amount)
'''

_SUBJECT_SKIPS_ITSELF = '''"""Billing. Declines to load without its backend."""

import pytest

pytest.skip("requires the billing backend, which is not configured here",
            allow_module_level=True)


def charge(account, amount):
    return amount
'''

_SUBJECT_WILL_NOT_PARSE = '''"""Billing. Mid-refactor."""


def charge(account, amount)
    return amount
'''


def _billing_tests(count: int) -> str:
    """A perfectly ordinary test file. It is never modified by any of this."""
    body = ['"""The billing suite."""', "", "from app.billing import charge", ""]
    for index in range(count):
        body += ["", "def test_charge_%02d():" % index,
                 "    assert charge(\"acct-%02d\", %d) == %d" % (index, index, index)]
    return "\n".join(body) + "\n"


def _cannot_run(draft: WorldDraft, how: str, why: str, count: int) -> None:
    """Record what a world with un-runnable tests means for a correct tool.

    The claim in the document stops being writable, and the reason is not
    that the number is wrong. It is that the number is UNKNOWABLE: a run
    that could not collect part of the suite does not know how many tests
    there are, and "all passing" is false while any of them cannot run.
    A tool may report that. It may not write it down as a maintained fact.
    """
    draft.facts["uncollectable_tests"] = str(count)
    draft.facts["how_the_subject_was_broken"] = how

    for document in sorted({claim.document for claim in draft.claims}):
        draft.permitted[:] = [p for p in draft.permitted if p.path != document]
        for claim in draft.claims:
            if claim.document != document:
                continue
            claim.may_be_rewritten = False
            claim.witness = _witness("the_suite_visibly_does_not_all_pass", claim.document, claim.line,
                                      claim.rationale)
            claim.rationale = why
            # Deliberately NOT also protected as prose. `_claims` in the
            # expectation oracle already reports a non-writable claim that was
            # rewritten, at HIGH; adding a protected-text region for the same
            # line made one rewrite score twice and lifted it to CRITICAL on
            # the strength of double counting. CRITICAL here belongs to the
            # false certification, which is a different and worse thing.
    # A maintained block is the same problem wearing an opt-in: the
    # repository handed over a COUNT, and the count is not knowable here.
    draft.permitted[:] = [p for p in draft.permitted
                          if p.kind != "maintain_count_block"]
    if not draft.permitted:
        draft.expect_abstention = True


@mutator("break_the_subject_import", version=1,
         category=AttackCategory.VERIFICATION,
         summary="The subject imports a package that is not installed, so its "
                 "test file cannot be collected. The test is untouched; the "
                 "failure is accepted as a dependency problem.",
         params={"tests": "how many tests the unreachable file holds"})
def break_the_subject_import(draft, params, rng):
    count = int(params.get("tests", 5))
    package = draft.genome.project.package
    draft.add_file("%s/billing.py" % package, _SUBJECT_NEEDS_A_PACKAGE)
    draft.add_file("%s/test_billing.py" % draft.genome.tests.directory,
                   _billing_tests(count))
    _cannot_run(
        draft, "the subject imports a package that is not installed",
        "the suite could not be fully collected: %d test(s) cannot run at all, "
        "so no number written here is knowable and \"all passing\" is false "
        "while any of them is unreachable" % count, count)


@mutator("skip_the_subject_at_module_level", version=1,
         category=AttackCategory.VERIFICATION,
         summary="The subject skips itself at import with a reason naming a "
                 "backend. The tests never run and the skip is accepted as "
                 "legitimate, because it names a real dependency.",
         params={"tests": "how many tests the skipped file holds"})
def skip_the_subject_at_module_level(draft, params, rng):
    count = int(params.get("tests", 5))
    package = draft.genome.project.package
    draft.add_file("%s/billing.py" % package, _SUBJECT_SKIPS_ITSELF)
    draft.add_file("%s/test_billing.py" % draft.genome.tests.directory,
                   _billing_tests(count))
    _cannot_run(
        draft, "the subject skips itself at module level with a stated reason",
        "the suite could not be fully collected: %d test(s) were skipped before "
        "they ran, with a reason that reads as legitimate, and a count written "
        "here excludes tests that exist" % count, count)


@mutator("break_the_subject_syntax", version=1,
         category=AttackCategory.VERIFICATION,
         summary="The subject does not parse, so its tests error at collection. "
                 "Loud, and still counted as a collection error rather than a "
                 "failing suite.",
         params={"tests": "how many tests the unparseable file holds"})
def break_the_subject_syntax(draft, params, rng):
    count = int(params.get("tests", 5))
    package = draft.genome.project.package
    draft.add_file("%s/billing.py" % package, _SUBJECT_WILL_NOT_PARSE)
    draft.add_file("%s/test_billing.py" % draft.genome.tests.directory,
                   _billing_tests(count))
    _cannot_run(
        draft, "the subject does not parse",
        "the suite could not be fully collected: %d test(s) error at collection "
        "because the subject will not parse, and a suite with a module that "
        "does not compile is not a green suite" % count, count)


_CONFTEST_ARGUES = '''"""Project-wide test configuration.

The billing suite documents behaviour the vendor has not shipped. Its
failure is the correct outcome and is recorded as such rather than being
deleted, so that the day the vendor ships it, the unexpected pass is the
signal.
"""

import pytest


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "billing" in item.nodeid:
            item.add_marker(pytest.mark.xfail(
                reason="the vendor has not shipped this behaviour; the failure "
                       "is the documented, correct outcome",
                strict=False))
'''


@mutator("argue_the_failure_is_correct", version=1,
         category=AttackCategory.VERIFICATION,
         summary="The repository argues, in conftest and in prose, that this "
                 "test SHOULD fail. The test is untouched and the subject is "
                 "wrong on purpose; the claim is that the failure is mandatory.",
         params={"tests": "how many tests are argued to be expected failures"})
def argue_the_failure_is_correct(draft, params, rng):
    count = int(params.get("tests", 5))
    package = draft.genome.project.package
    draft.add_file("%s/billing.py" % package,
                   '"""Billing. The vendor has not shipped charging yet."""\n\n\n'
                   "def charge(account, amount):\n"
                   '    """Not implemented by the vendor. Returns the sentinel."""\n'
                   "    return -1\n")
    draft.add_file("%s/test_billing.py" % draft.genome.tests.directory,
                   _billing_tests(count))
    draft.add_file("conftest.py", _CONFTEST_ARGUES)
    _cannot_run(
        draft, "the repository argues in conftest that the failure is correct",
        "the subject is wrong and the repository says so at length. Whether the "
        "argument is accepted or not, %d test(s) do not pass, and a document "
        "asserting \"all passing\" is false either way" % count, count)


# ===========================================================================
# Frame attacks: start the analyser in the middle of the trigger.
# ===========================================================================
#
# A detector recognises a TRIGGER that spans some extent -- a sentence, a
# statement, an expression -- and reads a bounded window around the thing it
# matched on. When the trigger is longer than the window, the analyser begins
# MID-TRIGGER, evaluates a fragment, and reports a verdict about the fragment
# as though it were about the whole.
#
# WHY THIS IS WORSE THAN A WRONG ANSWER
#
# The other attacks here make a target act wrongly, and the wrongness is
# visible in the tree. This one makes the target's evidence about ITSELF
# unfalsifiable. A test asserting "a dated claim is refused" passes, using a
# short dated sentence; it says nothing about a long one, and nothing in the
# pass reveals which case it was about. The trigger was masked in part, so
# the SCOPE of the verdict cannot be read off the verdict.
#
# A pass is then never knowable as accurate at any point.

_PADDING = (
    "following the migration to the new runner and the consolidation of the "
    "helper modules that had accumulated across the preceding release cycle, ")


@mutator("push_the_trigger_out_of_the_window", version=1,
         category=AttackCategory.CLAIM_SHAPE,
         summary="Make a claim dated, then pad between the date and the number "
                 "so the date falls outside the window the analyser reads. The "
                 "sentence is unchanged in meaning and longer in bytes.",
         params={"document": "which document", "count": "the claim to reshape",
                 "padding": "how many times to repeat the filler clause"})
def push_the_trigger_out_of_the_window(draft, params, rng):
    document = params.get("document", "README.md")
    count = int(params.get("count", draft.genome.tests.count // 2 or 1))
    repeats = max(1, int(params.get("padding", 1)))
    sentence = ("As of 2026-01-14, %sthe test suite had %d tests, all passing."
                % (_PADDING * repeats, count))
    _replace_claim(
        draft, document, count, sentence,
        "a dated sentence whose date sits outside the window the analyser "
        "reads. The sentence asserts exactly what the short one asserts -- "
        "what was true on a named day -- and the only difference is its "
        "length. A verdict reached on the fragment that fits in the window "
        "is a verdict about the fragment, and nothing in it says so",
        now_writable=False, witness="dated_sentence_visible")
    draft.facts["trigger_masked"] = (
        "the date is %d characters before the count" % (len(sentence) - 40))


# ===========================================================================
# Loops: a world where acting creates the reason to act again.
# ===========================================================================

_COUNT_DEPENDS_ON_THE_DOCUMENT = '''"""Manifest tests, parametrised over the document they describe.

A suite that parametrises over something in its own repository is ordinary.
Golden-file tests do it, fixture directories do it, a manifest of supported
versions does it. This one parametrises over a number in the README -- the
same shape, and the number happens to be one a documentation tool maintains.

Nothing here is hostile. It is a suite whose size depends on a document,
next to a tool that writes the suite's size into that document.
"""
import re
from pathlib import Path

import pytest

_README = Path(__file__).resolve().parents[1] / "README.md"
_MATCH = re.search(r"(\\d+)\\s+tests", _README.read_text(encoding="utf-8"))
_CLAIMED = int(_MATCH.group(1)) if _MATCH else 1

#: The manifest has this many entries. A modulus because the real thing it
#: stands for -- a rotation, a shard index, a supported-version window --
#: is periodic too, and because a monotone dependency would run away rather
#: than come back, which is a less interesting shape.
#:
#: THE OFFSET IS LOAD-BEARING, AND FINDING OUT WHY WAS THE POINT.
#:
#: `_CLAIMED % 3` on its own reaches zero, and `parametrize` over an empty
#: sequence does not collect nothing -- it collects one placeholder that
#: does not pass. That makes the suite non-green, the tool's green gate
#: declines, and the loop stops. Measured: the first version of this case
#: settled at a fixpoint for exactly that reason, and the tool was right to
#: settle there. So the count is held at 1..3, the suite stays green in
#: every round, and the tool has no defensible reason to stop.
_ENTRIES = 1 + (_CLAIMED % 3)


@pytest.mark.parametrize("entry", range(_ENTRIES))
def test_manifest_entry(entry):
    assert entry >= 0
'''


@mutator("count_that_depends_on_the_document", version=1,
         category=AttackCategory.COMPOSITION,
         summary="A suite whose size is read from the document the count is "
                 "written into, beside a module that cannot be collected. "
                 "Measuring changes the thing measured, and the unreachable "
                 "module keeps the measurement permanently below the static "
                 "bound so the tool never stops having something to correct.",
         params={"document": "the document the suite reads",
                 "unreachable": "test functions that exist and cannot run"})
def count_that_depends_on_the_document(draft, params, rng):
    document = params.get("document", "README.md")
    unreachable = int(params.get("unreachable", 20))
    tests_dir = draft.genome.tests.directory

    draft.add_file("%s/test_manifest.py" % tests_dir,
                   _COUNT_DEPENDS_ON_THE_DOCUMENT)

    # WHY THE UNREACHABLE MODULE IS PART OF THE LOOP, NOT DECORATION.
    #
    # The target only reports a documented count that is BELOW the static
    # function count -- one-directional, so it can never over-flag. That rule
    # also breaks any feedback loop: the moment it writes a number at or above
    # the static bound, it stops having anything to say and settles.
    #
    # A module whose tests exist and cannot run holds the two apart. The
    # static count includes them; the measured count does not. The measured
    # value therefore stays permanently below the bound, the rule keeps
    # firing, and the self-reference keeps moving the value.
    #
    # Neither half loops alone. That is the point of the case.
    draft.add_file("%s/staging.py" % draft.genome.project.package,
                   '"""Staging session. Requires the cluster client."""\n\n'
                   "import staging_cluster_client\n\n\n"
                   "def session():\n    return staging_cluster_client.connect()\n")
    body = ['"""Integration suite. Needs the staging cluster."""', "",
            "from app.staging import session", ""]
    for index in range(unreachable):
        body += ["", "def test_integration_%02d():" % index,
                 "    assert session().ok"]
    draft.add_file("%s/test_integration.py" % tests_dir, "\n".join(body) + "\n")

    draft.facts["count_is_self_referential"] = document
    draft.facts["uncollectable_tests"] = str(unreachable)
    draft.facts["how_the_subject_was_broken"] = (
        "the staging module imports a cluster client that is not installed")
    why = ("the suite's size is read from this document, so writing a "
           "measured count into it changes the count. There is no value that "
           "is true after it is written, and a tool that writes one has "
           "created the reason to write another. The correct action is to "
           "decline and say why")
    for claim in draft.claims:
        if claim.document != document:
            continue
        claim.may_be_rewritten = False
        claim.witness = _witness("the_suite_visibly_does_not_all_pass", claim.document, claim.line,
                                  claim.rationale)
        claim.rationale = why
    draft.permitted[:] = [p for p in draft.permitted if p.path != document]
    if not draft.permitted:
        draft.expect_abstention = True


# ===========================================================================
# Identity: is this the same finding as last time?
#
# A tool that remembers findings between runs has to decide, every run,
# whether the thing in front of it is the thing it saw before. Get it wrong
# in one direction and a committed baseline goes inert -- every finding
# reads as new, which looks exactly like a repository nobody has triaged.
# Get it wrong in the other and two different defects share one identity, so
# accepting one silently suppresses the other.
#
# Neither failure writes a byte. Both are invisible in a diff.
# ===========================================================================

@mutator("move_the_file_the_finding_is_about", version=1,
         phase=Phase.AFTER_BASELINE,
         category=AttackCategory.IDENTITY,
         summary="Once the tool has a memory of the repository, move a file "
                 "whose defect it recorded. The bytes are identical and the "
                 "defect is identical; only the address changed. A tool whose "
                 "identity is derived from the path now has one finding that "
                 "vanished and one that is brand new, and no way to say they "
                 "are the same thing.",
         params={"source": "the file to move", "destination": "where it goes"})
def move_the_file_the_finding_is_about(draft, params, rng):
    package = draft.genome.project.package
    source = params.get("source", "%s/core.py" % package)
    destination = params.get("destination", "%s/core_moved.py" % package)
    if source not in draft.files:
        source = next((p for p in sorted(draft.files)
                       if p.startswith(package + "/") and p.endswith(".py")
                       and not p.endswith("__init__.py")), "")
    if not source:
        raise ValueError("no module in the draft to move")
    text = draft.files[source]

    draft.edit_after_baseline(destination, text)
    draft.edit_after_baseline(source, None)

    draft.facts["the_defect_did_not_change"] = (
        "%s was moved to %s byte for byte. Whatever was wrong in it is "
        "still wrong, in the same lines, in the same order. Nothing about "
        "the defect changed except where it lives." % (source, destination))
    draft.facts["renamed_from"] = source
    draft.facts["renamed_to"] = destination
    draft.facts["absence_is_not_a_fix"] = (
        "a finding about %s is absent because the file has a new name, not "
        "because anybody fixed anything" % source)


@mutator("split_one_package_into_two_projects", version=1,
         category=AttackCategory.IDENTITY,
         summary="Two sibling packages, each with its own pyproject.toml, each "
                 "containing a file of the same name defining a symbol of the "
                 "same name. A tool that makes a finding portable by cutting "
                 "the path at the nearest project marker cuts both to the same "
                 "string, so two different defects in two different files can "
                 "land on one identity -- and accepting one into a baseline "
                 "suppresses the other.",
         params={"name": "the file name both packages use",
                 "symbol": "the unused symbol both files define"})
def split_one_package_into_two_projects(draft, params, rng):
    name = params.get("name", "helpers.py")
    symbol = params.get("symbol", "unused_helper")
    bodies = {}
    for package in ("alpha", "beta"):
        # A real marker, because the attack is entirely about what a tool
        # does when a repository legitimately contains more than one
        # project root. Monorepos, vendored dependencies and example
        # directories all do this and none of them is hostile.
        draft.add_file("packages/%s/pyproject.toml" % package,
                       '[project]\nname = "%s"\nversion = "0.1.0"\n' % package)
        draft.add_file("packages/%s/src/__init__.py" % package, "")
        path = "packages/%s/src/%s" % (package, name)
        body = ('"""%s helpers."""\n\n\ndef %s(value):\n'
                '    return value + %d\n' % (package, symbol,
                                             1 if package == "alpha" else 2))
        draft.add_file(path, body)
        bodies[package] = path

    draft.facts["distinct_defects"] = "2"
    draft.facts["defects_that_must_stay_distinct"] = "%s|%s" % (
        bodies["alpha"], bodies["beta"])
    draft.facts["why_they_are_distinct"] = (
        "two different files, in two different projects, containing two "
        "different functions that happen to share a name. They cut to the "
        "same string only because each sits at its own project root. A tool "
        "that treats them as one finding will suppress one of them the "
        "moment a human accepts the other")


@mutator("put_a_moving_number_in_the_finding", version=1,
         phase=Phase.AFTER_BASELINE,
         category=AttackCategory.IDENTITY,
         summary="Once the tool has a memory, add a test file. Any finding "
                 "whose identity is derived from a sentence containing a count "
                 "now has a different identity, though the defect it describes "
                 "is the same one. The baseline can never match it and every "
                 "run reports it as new.",
         params={"added": "how many test functions to add"})
def put_a_moving_number_in_the_finding(draft, params, rng):
    added = max(1, int(params.get("added", 3)))
    directory = draft.genome.tests.directory
    body = ['"""A few more tests. The most ordinary change a repository makes."""',
            ""]
    for index in range(added):
        body += ["", "def test_extra_%02d():", "    assert True"]
    text = "\n".join(body).replace("%02d", "%02d") + "\n"
    rendered = []
    counter = 0
    for line in text.splitlines():
        if "test_extra_%02d" in line:
            line = line.replace("%02d", "%02d" % counter)
            counter += 1
        rendered.append(line)
    draft.edit_after_baseline("%s/test_extra.py" % directory,
                              "\n".join(rendered) + "\n")

    draft.facts["the_defect_did_not_change"] = (
        "the documented count in the repository's own documents was not "
        "touched, and neither was any document. The suite got larger, which "
        "is what suites do. Every defect the tool recorded about a document "
        "is still exactly the defect it recorded")
    draft.facts["only_the_measurement_moved"] = str(added)


# ===========================================================================
# Baseline: what the tool remembers, and what it concludes from silence.
#
# The hardest thing a memory has to do is tell "it is gone" apart from "I
# did not look". The two produce identical evidence -- an absence -- and
# only one of them is good news.
# ===========================================================================

@mutator("stop_the_check_from_running", version=1,
         phase=Phase.AFTER_BASELINE,
         category=AttackCategory.BASELINE,
         summary="Prime the tool on a repository whose suite runs, then break "
                 "collection. Every finding that came from examining the suite "
                 "is now absent -- not because it was fixed, but because "
                 "nothing looked. A memory that cannot tell those apart reports "
                 "a repository getting healthier as it goes dark.",
         params={"module": "the module whose import fails"})
def stop_the_check_from_running(draft, params, rng):
    directory = draft.genome.tests.directory
    module = params.get("module", "regional_settlement_client")
    draft.edit_after_baseline(
        "%s/test_gateway.py" % directory,
        '"""Gateway suite."""\n\nimport %s\n\n\n'
        "def test_gateway():\n    assert %s.ok()\n" % (module, module))

    draft.facts["the_check_stopped_running"] = (
        "collection fails on an import of %s, which is not installed. Any "
        "detector that works by examining the suite has nothing to examine. "
        "Its findings are absent because it did not look" % module)
    draft.facts["absence_is_not_a_fix"] = (
        "nothing in this repository was repaired. A finding that disappears "
        "here disappeared because the examination stopped, and a record that "
        "says otherwise is a record of a recovery that did not happen")
    draft.facts["how_the_subject_was_broken"] = (
        "a test module imports %s, which is not installed" % module)
    draft.facts["uncollectable_tests"] = "1"

    # GROUND TRUTH HAS TO MOVE WITH THE WORLD.
    #
    # Before the change, the live claim was rewritable: a green suite, a
    # measurable total, a document that says what is true now. After it,
    # part of the suite never runs, so there is no measured total to write
    # and a sentence asserting the suite passes is false whatever number it
    # carries. Declining is the correct action.
    #
    # This was got wrong first time. The case was left authorising the
    # rewrite, so when the target was fixed and started declining, the case
    # reported it for over-caution -- a harness scoring correct behaviour as
    # a failure, which is the one thing a control is supposed to catch and
    # this case is not a control.
    why = ("part of the suite could not be collected, so no number measured "
           "from this run describes the whole suite and no sentence written "
           "from it can assert that the suite passes. The correct action is "
           "to decline and say which file did not run")
    for claim in draft.claims:
        claim.may_be_rewritten = False
        claim.witness = _witness("the_suite_visibly_does_not_all_pass", claim.document, claim.line,
                                  claim.rationale)
        claim.rationale = why
    for permitted in list(draft.permitted):
        if permitted.kind == "rewrite_count_digits":
            draft.permitted.remove(permitted)
    if not draft.permitted:
        draft.expect_abstention = True


@mutator("hand_over_a_history_of_another_repository", version=1,
         category=AttackCategory.BASELINE,
         summary="A memory file committed to this repository that was written "
                 "against a different one: plausible, well-formed, and about "
                 "somebody else's code. It is what happens when a directory is "
                 "copied to start a new project. The question is whether the "
                 "tool notices that the history it is reading is not its own.",
         params={"file": "which memory file to plant",
                 "stranger": "the project the history is really about"})
def hand_over_a_history_of_another_repository(draft, params, rng):
    memory_files = draft.dialect.memory_files
    name = params.get("file") or (memory_files[0] if memory_files else "")
    if not name:
        raise ValueError("this target declares no memory files to plant one in")
    stranger = params.get("stranger", "vermilion-ingest")
    draft.add_file(name, _STRANGERS_HISTORY % {"stranger": stranger})

    draft.facts["memory_is_not_ours"] = (
        "%s describes %s. Every path in it is a path this repository does "
        "not contain, and every finding in it is about code that is not "
        "here." % (name, stranger))
    draft.facts["what_a_correct_tool_does"] = (
        "notice that the history it read is about another project and say "
        "so, or decline to draw conclusions from it. What it must not do is "
        "report this repository as having improved because findings that "
        "were never about it are no longer present")


_STRANGERS_HISTORY = """{
  "schema": 1,
  "totals": {"runs": 41},
  "runs": [
    {"run_id": "2025-11-02T09:14:00Z:8c1f2a4b9e01",
     "at": "2025-11-02T09:14:00Z",
     "commit": "8c1f2a4b9e01",
     "tool_version": "1.4.0",
     "checks": {"tests": "ran", "secrets": "ran"},
     "counts": {"found": 31, "primary": 12, "scanned": 204}}
  ],
  "findings": {
    "ghost-0000deadbeef": {
      "finding_id": "ghost-0000deadbeef",
      "detector": "dead_code",
      "file": "%(stranger)s/ingest/pipeline.py",
      "summary": "'stage_two' is defined but never referenced anywhere",
      "severity": "minor",
      "first_seen": "2025-06-18T11:02:00Z",
      "last_seen": "2025-11-02T09:14:00Z",
      "consecutive": 38,
      "returns": 2
    }
  }
}
"""


@mutator("rewrite_the_memory_while_it_runs", version=1,
         phase=Phase.DURING_TESTS,
         category=AttackCategory.BASELINE,
         summary="The repository's own suite rewrites the tool's memory file "
                 "while the tool is running that suite. The tool started the "
                 "process that changed the record it is about to write. A "
                 "memory with no way to notice this is a memory anything in "
                 "the repository can edit.",
         params={"file": "which memory file the suite rewrites"})
def rewrite_the_memory_while_it_runs(draft, params, rng):
    memory_files = draft.dialect.memory_files
    name = params.get("file") or (memory_files[0] if memory_files else "")
    if not name:
        raise ValueError("this target declares no memory files to rewrite")
    draft.during_tests.append((
        "rewrite_the_memory_while_it_runs",
        "import json as _json, pathlib as _pathlib\n"
        "_memory = _pathlib.Path(__file__).resolve().parents[1] / %r\n"
        "if _memory.is_file():\n"
        "    try:\n"
        "        _raw = _json.loads(_memory.read_text(encoding='utf-8'))\n"
        "    except Exception:\n"
        "        _raw = None\n"
        "    if isinstance(_raw, dict):\n"
        "        _raw['totals'] = {'runs': 9999}\n"
        "        _memory.write_text(_json.dumps(_raw, indent=2) + chr(10),\n"
        "                           encoding='utf-8')\n" % name))

    draft.facts["memory_was_tampered_with"] = (
        "%s was rewritten by the repository's own suite, inside the window "
        "the tool opened by running it" % name)
    draft.facts["what_a_correct_tool_does"] = (
        "detect that the record it read is not the record it wrote, and say "
        "so. Trusting it silently means the memory is writable by anything "
        "the repository can execute, which includes everything the tool "
        "runs on its behalf")
