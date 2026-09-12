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
                   sentence: str, reason: str, *, now_writable: bool) -> None:
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
            kept.append(claim)
    draft.claims[:] = sorted(kept, key=lambda c: (c.document, c.line))
    draft.permitted[:] = [p for p in draft.permitted
                          if not (p.path == document and p.line_start == line_no)]
    if now_writable:
        draft.permit(document, line_no, line_no, "rewrite_count_digits", reason)
    else:
        draft.protect(document, reason, line_no, line_no, text=sentence)


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
                   now_writable=False)


@mutator("make_historical_claim", version=1, category=AttackCategory.CLAIM_SHAPE,
         summary="Turn a live claim into one about an earlier release.",
         params={"document": "which document", "count": "the claim to reshape"})
def make_historical_claim(draft, params, rng):
    document = params.get("document", "README.md")
    count = int(params.get("count", draft.genome.tests.count // 2 or 1))
    _replace_claim(draft, document, count, _HISTORICAL_SENTENCE.format(count=count),
                   "a claim about a past release, which is correct as written",
                   now_writable=False)


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
                   now_writable=False)


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
                   now_writable=False)


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
                   now_writable=False)


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
