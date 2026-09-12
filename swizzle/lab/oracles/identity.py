"""Is this the same finding as last time, and is it really gone?

A tool that remembers findings between runs makes two promises every time it
runs, and neither of them writes a byte.

    the same defect keeps the same identity
    an absence means the defect is gone

Break the first and a committed baseline goes inert: every finding reads as
new, which looks exactly like a repository nobody has triaged. Break the
first in the other direction and two different defects share one identity,
so accepting one into a baseline silently suppresses the other. Break the
second and the history reports a recovery that nobody performed.

None of this is visible in a diff, which is why no other oracle here can
see it. Every other oracle compares the tree before with the tree after.
This one compares the target's account of a repository with the target's
account of the SAME repository a moment later, against a ground-truth
statement about what actually changed in between.

WHERE THE AUTHORITY COMES FROM

Not from the target. The target's two accounts are evidence, exactly like
`scan` and `act` are elsewhere. What licenses a judgement is the mutator's
declaration -- "this file was moved byte for byte, so the defect in it did
not change", "these two functions are genuinely different defects" -- which
is SWIZZLE's own statement about the world it built. The oracle asks whether
the two accounts are consistent with that, and it never asks the target
whether it was right.

WHAT THIS ORACLE WILL NOT SAY

That an absence is a false recovery when the target said something new. A
tool that stops being able to examine the suite and REPORTS that it stopped
has done the right thing, and the report may be worded in any way at all.
So a lost finding accompanied by a new one is INCONCLUSIVE, not a
violation: a human reads which. Claiming otherwise would make this oracle
score a correct target for being correct in a phrasing nobody anticipated.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Set, Tuple

from ..evidence import Evidence
from ..genome import Phase
from ..signals import Severity, Signal, ok, unsure, violation

ORACLE = "identity"


def judge(evidence: Evidence) -> Sequence[Signal]:
    out: List[Signal] = []
    out += _collision(evidence)
    out += _persistence(evidence)
    return out


# --------------------------------------------------- two defects, one id

def _collision(evidence: Evidence) -> List[Signal]:
    """Distinct defects that the target gave one identity."""
    declared = evidence.ground_truth.facts.get("defects_that_must_stay_distinct", "")
    if not declared:
        return []
    paths = [p for p in declared.split("|") if p]
    account = evidence.scan or evidence.act
    if account is None:
        return [unsure(ORACLE, "no_account",
                       "the target was never asked to look, so it never said "
                       "what it thought these were")]

    by_path: Dict[str, Set[str]] = {path: set() for path in paths}
    for finding in account.findings:
        where = str((finding.get("evidence") or {}).get("file", ""))
        for path in paths:
            if where and (where == path or where.endswith("/" + path)
                          or path.endswith("/" + where) or where in path):
                identity = str(finding.get("id", ""))
                if identity:
                    by_path[path].add(identity)

    found = {path: ids for path, ids in by_path.items() if ids}
    if len(found) < 2:
        return [unsure(ORACLE, "collision_unasked",
                       "the target reported an identified finding for %d of "
                       "the %d files that had to stay distinct, so whether it "
                       "would have kept them apart was never put to it"
                       % (len(found), len(paths)),
                       files=paths)]

    shared = set.intersection(*found.values())
    if shared:
        return [violation(
            ORACLE, Severity.HIGH, "distinct_defects_collapsed",
            "two different defects in two different files were given the same "
            "identity: %s" % ", ".join(sorted(shared)),
            detail=evidence.ground_truth.facts.get("why_they_are_distinct", "")
                   or "ground truth declared these distinct.",
            files=sorted(found), identity=sorted(shared),
            consequence="A baseline suppresses by identity. Accepting one of "
                        "these into it stops the other being reported, and "
                        "nothing in the tool's output says so.")]
    return [ok(ORACLE, "identities_kept_apart",
               "the two defects were given different identities",
               files=sorted(found))]


# ------------------------------------------- the same defect, a moment later

def _persistence(evidence: Evidence) -> List[Signal]:
    """What the target's record did to findings that did not go away."""
    wants = any(m.phase is Phase.AFTER_BASELINE
                for m in evidence.genome.mutations)
    if not wants:
        return []
    if evidence.primed is None:
        return [unsure(ORACLE, "memory_not_primed",
                       "the target keeps nothing between runs, or the priming "
                       "run did not happen, so no question about its memory "
                       "was actually asked")]
    account = evidence.scan or evidence.act
    if account is None:
        return [unsure(ORACLE, "no_second_account",
                       "the target was primed and then never asked again")]

    was = _identities(evidence.primed)
    now = _identities(account)
    lost, gained = set(was) - set(now), set(now) - set(was)
    detail_was = _subjects(evidence.primed)
    detail_now = _subjects(account)

    unchanged = evidence.ground_truth.facts.get("the_defect_did_not_change", "")
    not_a_fix = evidence.ground_truth.facts.get("absence_is_not_a_fix", "")
    if not lost:
        return [ok(ORACLE, "identity_survived",
                   "every finding the target recorded while being primed was "
                   "still recorded under the same identity afterwards",
                   carried=len(set(was) & set(now)), new=sorted(gained)[:5])]

    if not unchanged and not not_a_fix:
        return [unsure(ORACLE, "loss_unexplained",
                       "%d recorded finding(s) are no longer reported, and "
                       "this case made no ground-truth statement about "
                       "whether they should be" % len(lost),
                       lost=sorted(lost)[:5])]

    out: List[Signal] = []
    # Did the target re-report the SAME defect under a new identity? Ground
    # truth knows, because ground truth is what moved the file. A finding at
    # the destination of a declared move is the same defect wearing a new
    # name, not an explanation of where the old one went.
    source = evidence.ground_truth.facts.get("renamed_from", "")
    destination = evidence.ground_truth.facts.get("renamed_to", "")
    rejoined = _rejoined(lost, gained, detail_was, detail_now, source, destination)
    if rejoined:
        out.append(violation(
            ORACLE, Severity.MEDIUM, "identity_not_preserved",
            "the same defect is reported under a new identity: %s"
            % "; ".join("%s became %s" % pair for pair in rejoined[:2]),
            detail=unchanged,
            pairs=["%s -> %s" % pair for pair in rejoined[:5]],
            moved_to=destination,
            consequence="Nothing in the tool's record joins these. A baseline "
                        "carrying the old identity stops matching, so an "
                        "accepted finding starts being reported again and a "
                        "triaged repository reads as untriaged."))

    explained = bool(gained) and not rejoined
    if explained:
        # It lost some and said something genuinely new. Whether the new
        # thing ACCOUNTS for the loss is a judgement about English, and this
        # oracle does not make those. See the module docstring.
        out.append(unsure(ORACLE, "absence_possibly_explained",
                          "%d recorded finding(s) went away and %d new one(s) "
                          "appeared. Whether the new ones say why the old ones "
                          "are gone is not a question this oracle can answer"
                          % (len(lost), len(gained)),
                          lost=sorted(lost)[:5], gained=sorted(gained)[:5],
                          ground_truth=unchanged or not_a_fix))
        return out

    # Two consequences of one cause, and they are different failures: the
    # baseline going inert is reported above, and the RECORD now showing a
    # repository that got better is reported here. Emitting one and not the
    # other would leave whichever reader cares about the other half with
    # nothing.
    out.append(violation(
        ORACLE, Severity.HIGH, "absence_read_as_resolution",
        "%d finding(s) the target had recorded are gone from its account, and "
        "nothing in the account says the defect is still there" % len(lost),
        detail=not_a_fix or unchanged,
        lost=sorted(lost)[:5],
        consequence="The record now shows a repository with fewer defects "
                    "than it had. Nobody fixed anything. A reader comparing "
                    "two runs sees progress."))
    return out


def _rejoined(lost, gained, before: Dict[str, Tuple[str, str]],
              after: Dict[str, Tuple[str, str]], source: str,
              destination: str) -> List[Tuple[str, str]]:
    """Pairs of identities that are the same defect wearing two names.

    Two ways to know, and both come from the world rather than from the
    target:

        SAME PLACE     the same detector, about the same file, before and
                       after. Nothing moved, so a new identity for it is
                       the tool re-identifying something it already had
        MOVED          the same detector, at the file ground truth says the
                       old one was moved to

    A pair found this way is not an explanation of where the old finding
    went. It IS the old finding, reported again, and the tool's record has
    no way to say so.
    """
    pairs: List[Tuple[str, str]] = []
    for old_id in sorted(lost):
        old_detector, old_file = before.get(old_id, ("", ""))
        for new_id in sorted(gained):
            new_detector, new_file = after.get(new_id, ("", ""))
            if not old_detector or old_detector != new_detector:
                continue
            same_place = old_file and _same_file(new_file, old_file)
            moved = (source and destination and _same_file(old_file, source)
                     and _same_file(new_file, destination))
            if same_place or moved:
                pairs.append((old_id, new_id))
                break
    return pairs


def _subjects(observation) -> Dict[str, Tuple[str, str]]:
    """Identity -> (detector, file). What the finding was about."""
    out: Dict[str, Tuple[str, str]] = {}
    for finding in observation.findings:
        identity = str(finding.get("id", ""))
        if identity:
            out[identity] = (
                str(finding.get("detector", "")),
                str((finding.get("evidence") or {}).get("file", "")))
    return out


def _same_file(reported: str, declared: str) -> bool:
    if not reported or not declared:
        return False
    return (reported == declared or reported.endswith("/" + declared)
            or declared.endswith("/" + reported))


def _identities(observation) -> Dict[str, str]:
    """Identity -> the file it was reported against.

    A finding with no identity is skipped rather than counted under an empty
    string: a target that does not identify its findings has not failed this
    oracle, it has simply never been asked the question.
    """
    out: Dict[str, str] = {}
    for finding in observation.findings:
        identity = str(finding.get("id", ""))
        if identity:
            out[identity] = str((finding.get("evidence") or {}).get("file", ""))
    return out
