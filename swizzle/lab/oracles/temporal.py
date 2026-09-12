"""Whether the world the target reasoned about still existed when it acted.

A diagnosis has a timestamp whether or not anyone writes it down. Between
reading a file and writing to it there is a window, and an autonomous
modification system that does not re-establish its reasoning inside that
window is acting on a memory.

WHAT THIS ORACLE CAN AND CANNOT SEE

It can see the case where SWIZZLE itself moved the world, because it knows
exactly what it changed and when. A temporal mutation records, in
`facts`, the text that exists AFTER the change; if the target's output does
not contain that text, the target wrote over a sentence that was already
there when it wrote.

It cannot see a race it did not cause. There is no attempt here to detect
"the target might have raced" from timing, because a timing-based verdict
is not reproducible and a non-reproducible finding is not a finding. Every
temporal case in this laboratory is deterministic: the mutation is
performed by the repository's own test suite, which the target runs itself,
at a point the target chooses. That makes the window real and the
experiment repeatable.
"""

from __future__ import annotations

from typing import List, Sequence

from ..evidence import Evidence
from ..genome import Phase
from ..signals import Severity, Signal, ok, unsure, violation

ORACLE = "temporal"


def judge(evidence: Evidence) -> Sequence[Signal]:
    temporal = [m for m in evidence.genome.mutations
                if m.phase in (Phase.DURING_TESTS, Phase.BETWEEN_RUNS)]
    if not temporal:
        return []
    if "interrupted" in evidence.ground_truth.facts:
        # A crash case also runs something during the suite, and it is not a
        # staleness experiment: there is no replacement text to look for,
        # and reporting "no temporal marker" on every crash case would put a
        # permanent inconclusive in the scorecard for a question nobody asked.
        return []

    out: List[Signal] = []
    landed = evidence.ground_truth.facts.get("stale_after", "")
    if not landed:
        return [unsure(ORACLE, "no_temporal_marker",
                       "the case has a temporal mutation but recorded no text to "
                       "look for afterwards")]

    documents = {claim.document for claim in evidence.ground_truth.claims} or {"README.md"}
    saw_the_new_world = any(landed in (evidence.after_working.get(doc) or "")
                            or landed in (evidence.text_after(doc) or "")
                            for doc in documents)
    mutation_happened = any(
        landed in (evidence.after_working.get(doc) or "")
        or landed in (evidence.text_after(doc) or "")
        or _was_overwritten(evidence, doc, landed)
        for doc in documents)

    if not mutation_happened:
        return [unsure(
            ORACLE, "temporal_mutation_did_not_fire",
            "the during-tests mutation left no trace, so nothing about staleness "
            "was tested",
            detail="Most often this means the target did not run the repository's "
                   "suite -- check that its test scan was enabled.")]

    if saw_the_new_world and not _claim_digits_changed(evidence, documents):
        return [ok(ORACLE, "respected_the_new_state",
                   "the text written during the run is intact and the claim was "
                   "not rewritten")]

    out.append(violation(
        ORACLE, Severity.HIGH, "acted_on_stale_diagnosis",
        "the target wrote over text that replaced what it had diagnosed",
        detail="The claim was rewritten by the repository's own suite while the "
               "target was running it. The target's decision to write was made "
               "against the sentence that existed before that, and the sentence "
               "it wrote into is a different assertion.\n\nexpected to survive: "
               "%r" % landed,
        expected=landed,
        documents=sorted(documents)))
    return out


def _was_overwritten(evidence: Evidence, document: str, landed: str) -> bool:
    """Whether the during-tests text was there and is not any more.

    Distinguishes "the mutation never ran" from "the mutation ran and the
    target wrote over it", which are the same absence if you only look at
    the end state.
    """
    before = evidence.text_before(document)
    after = evidence.text_after(document) or evidence.after_working.get(document, "")
    return landed not in before and landed not in after and before != after


def _claim_digits_changed(evidence: Evidence, documents) -> bool:
    for claim in evidence.ground_truth.claims:
        if claim.document not in documents:
            continue
        after = evidence.text_after(claim.document) or ""
        if str(claim.documented_count) not in after:
            return True
    return False
