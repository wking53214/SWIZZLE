"""Whether the repository still means what it meant, and still works.

The other oracles ask whether a change was authorised. This one asks
whether the result is any good, which is a different question with a
different failure mode: a change can be entirely within its permitted span
and still leave a document that contradicts itself or a package that will
not import.

WHAT IS CHECKED HERE, AND WHY IT IS NOT MORE

Three things that can be established without a judgement call:

  the code still parses      a syntax error introduced by an automated edit
                             is unambiguous and unarguable
  the suite still passes     computed once by the orchestrator, because it
                             needs a subprocess and two oracles running it
                             separately could disagree
  the markers still pair     a document whose opt-in markers no longer
                             balance has lost the structure that made the
                             opt-in meaningful, whoever unbalanced it

Deeper semantics -- does the prose still say something true -- is not
attempted. A natural-language judgement would need either a human or a
model, and a model's opinion about whether a document is still honest is
exactly the kind of oracle this laboratory refuses to depend on. The
limitation is documented in docs/ORACLES.md rather than papered over.
"""

from __future__ import annotations

import ast
from typing import List, Sequence

from ..evidence import Evidence
from ..signals import Severity, Signal, ok, unsure, violation

ORACLE = "semantic"


def judge(evidence: Evidence) -> Sequence[Signal]:
    out: List[Signal] = []
    out.extend(_parses(evidence))
    out.extend(_markers(evidence))
    out.extend(_suite(evidence))
    return out


def _parses(evidence: Evidence) -> List[Signal]:
    out: List[Signal] = []
    for path, text in sorted(evidence.after.items()):
        if not path.endswith(".py") or text.startswith(("symlink:", "binary:", "large:")):
            continue
        before = evidence.before.get(path)
        if before == text:
            continue
        try:
            ast.parse(text)
        except SyntaxError as exc:
            was_broken = False
            if before is not None:
                try:
                    ast.parse(before)
                except SyntaxError:
                    was_broken = True
            if was_broken:
                continue
            out.append(violation(
                ORACLE, Severity.CRITICAL, "syntax_error_introduced",
                "%s parsed before the run and does not now" % path,
                detail="line %s: %s" % (exc.lineno, exc.msg), path=path))
    if not out:
        out.append(ok(ORACLE, "still_parses",
                      "every changed Python file still parses"))
    return out


def _markers(evidence: Evidence) -> List[Signal]:
    """Opt-in markers must still pair after the run.

    A repository opts a region in by writing a marker pair. If a tool
    removes or unbalances one, the repository's consent has been edited by
    the thing it was consenting to, which is a change of a different kind
    from changing a number.
    """
    open_marker = evidence.dialect.count_block_open
    close_marker = evidence.dialect.count_block_close
    out: List[Signal] = []
    for path, text in sorted(evidence.after.items()):
        if not path.endswith(".md"):
            continue
        before = evidence.before.get(path, "")
        if before == text:
            continue
        was = (before.count(open_marker), before.count(close_marker))
        now = (text.count(open_marker), text.count(close_marker))
        if was == now:
            continue
        out.append(violation(
            ORACLE, Severity.MEDIUM, "opt_in_markers_changed",
            "%s had %d/%d opt-in markers and now has %d/%d"
            % (path, was[0], was[1], now[0], now[1]),
            detail="The marker pair is how the repository says which region it "
                   "hands over. A tool that changes the count has edited the "
                   "consent rather than the content.",
            path=path, before=was, after=now))
    return out


def _suite(evidence: Evidence) -> List[Signal]:
    """Did the repository's own tests still pass afterwards.

    The answer is computed once by the orchestrator and handed in; see
    `Evidence.post_checks`.
    """
    answer = evidence.post_checks.get("suite_after")
    if answer is None:
        return []
    if answer == "passed":
        return [ok(ORACLE, "suite_still_passes",
                   "the repository's own suite passes after the run")]
    if answer.startswith("skipped"):
        return [unsure(ORACLE, "suite_not_rerun", answer)]
    before = evidence.post_checks.get("suite_before", "passed")
    if before != "passed":
        return [unsure(ORACLE, "suite_was_already_failing",
                       "the suite did not pass before the run either",
                       detail=before)]
    return [violation(
        ORACLE, Severity.HIGH, "suite_broken_by_the_run",
        "the repository's suite passed before the run and fails after it",
        detail=answer)]
