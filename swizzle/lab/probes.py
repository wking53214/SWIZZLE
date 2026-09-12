"""Asking the seven questions, rather than assuming their answers.

`standing.py` decomposes "it no longer reproduces" into the things that
sentence does not establish. This module turns each of them into something
that can actually be run, because a framework that only LABELS a conclusion
provisional has not done anything: it has written "probably" in front of the
same claim and carried on.

    THIS case        -> variant      mutate the genome and re-run
    THIS world       -> scope        re-run the world before it was minimised
    the surface      -> adjacency    re-run the siblings on the same surface
    THESE oracles    -> concealment  did the oracle that SAW it even look
    NO LONGER        -> recurrence   re-run at the revision in front of you

Each returns `defeated` when it found the thing its emphasis warned about,
`held` when it looked and did not, and neither when it was not run -- which
is a third state on purpose. "Not asked" and "asked, nothing found" are
different, and collapsing them is how a corpus fills up with conclusions
nobody reached.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import attack as attack_module
from . import search
from .adapter import TargetAdapter
from .genome import AttackCategory, RepositoryGenome
from .signals import Judgement, failure_class
from .standing import Observation, ProbeResult, unprobed

#: Every probe, in the order a reader should see them: the cheap and
#: conclusive first, the expensive and suggestive last.
PROBES = ("concealment", "recurrence", "scope", "adjacency", "variant")


@dataclass(frozen=True)
class ProbeContext:
    """Everything the probes need, gathered once."""

    genome: RepositoryGenome
    adapter: TargetAdapter
    #: The world before minimisation, when there was one. Without it the
    #: `THIS world` emphasis cannot be interrogated and says so.
    original: Optional[RepositoryGenome] = None
    #: Cases on the same surface, for `the surface`.
    siblings: Sequence[RepositoryGenome] = ()
    #: What was seen when it DID reproduce. Without it, `THESE oracles`
    #: cannot be interrogated: there is no record of which oracle saw it.
    when_it_reproduced: Optional[Observation] = None
    #: The failure this resolution is ABOUT, from the run that saw it. A
    #: variant reproducing something else has found a new case, not defeated
    #: this one.
    resolved_classes: Tuple[str, ...] = ()
    resolved_severity: str = "NONE"
    #: Variants to try. Small by default: each one runs the target.
    budget: int = 6
    timeout: float = 900.0
    seed: int = 0


def observe(genome: RepositoryGenome, adapter: TargetAdapter,
            timeout: float = 900.0) -> Observation:
    """Run one case and record what was literally seen, inferring nothing."""
    from .oracles import ORACLES
    result = attack_module.run(genome, adapter, timeout=timeout)
    version = dict(result.target_version)
    # EXECUTED, not "emitted something".
    #
    # The first version recorded the oracles that produced a signal, so an
    # oracle that looked and had nothing to say was indistinguishable from
    # one that was not looking -- and the concealment probe duly reported a
    # clean fix as concealed. Silence from an oracle that ran is a result;
    # absence from the run is not.
    ran = sorted(ORACLES) if not result.broken else []
    declined = sorted({s.oracle for s in result.signals
                       if s.judgement is Judgement.INCONCLUSIVE})
    return Observation(
        case=genome.name,
        genome_digest=genome.digest(),
        target_revision=version.get("commit", ""),
        observed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        reproduced=bool(result.fitness.interesting),
        oracles_ran=tuple(sorted(set(ran))),
        oracles_inconclusive=tuple(sorted(set(declined) - set(ran))),
        classes=tuple(sorted({failure_class(s.kind) for s in result.violations})),
        top_severity=result.fitness.top.name,
        broken=result.broken,
    )


# ===========================================================================
# THESE oracles -- did the one that saw it even look
# ===========================================================================

def concealment(context: ProbeContext, now: Observation) -> ProbeResult:
    """Whether the oracles that caught this are the ones that just cleared it.

    Costs nothing: it is a comparison of two records. It is first because a
    non-reproduction observed by a different set of oracles from the ones
    that originally saw the failure is not evidence of a fix -- it is
    evidence that nobody was looking in the same place.
    """
    before = context.when_it_reproduced
    if before is None:
        return unprobed("concealment",
                        "no record of the run that saw it; there is nothing to "
                        "compare the current oracle set against")

    watchers = set(before.oracles_ran)
    looking = set(now.oracles_ran)
    declined = set(now.oracles_inconclusive)

    missing = sorted(watchers - looking)
    silent = sorted(watchers & declined)
    if missing or silent:
        return ProbeResult(
            probe="concealment", defeated=True, held=False,
            account=("the oracle(s) that saw this failure are not agreeing now: "
                     + (("%s did not run" % ", ".join(missing)) if missing else "")
                     + ("; " if missing and silent else "")
                     + (("%s declined to say" % ", ".join(silent)) if silent else "")
                     + ". Silence from an oracle that was not looking is not a "
                       "clean result."),
            evidence={"saw_it": sorted(watchers), "looked_now": sorted(looking),
                      "missing": missing, "declined": silent})

    return ProbeResult(
        probe="concealment", defeated=False, held=True,
        account=("every oracle that saw this failure ran again and reported "
                 "nothing. Residual limit, unchanged and documented: a change "
                 "the target made and reverted is invisible to all of them "
                 "(docs/ORACLES.md)."),
        evidence={"saw_it": sorted(watchers), "looked_now": sorted(looking)})


# ===========================================================================
# NO LONGER -- at the revision in front of you
# ===========================================================================

def recurrence(context: ProbeContext, now: Observation) -> ProbeResult:
    """Re-run the case as it stands. Cheap, and the one that goes stale.

    `now` is already that run, so this probe interrogates it rather than
    repeating it: what it adds is the statement that the observation is
    about ONE revision, and the name of that revision, so a later reader
    can see whether it is still the one they are on.
    """
    if now.broken:
        return unprobed("recurrence", "the run could not be completed: %s" % now.broken)
    if now.reproduced:
        return ProbeResult(
            probe="recurrence", defeated=True, held=False,
            account="it reproduces at %s" % (now.target_revision[:10] or "this revision"),
            evidence={"revision": now.target_revision})
    return ProbeResult(
        probe="recurrence", defeated=False, held=True,
        account=("it does not reproduce at %s, and that is a statement about "
                 "that commit and no other"
                 % (now.target_revision[:10] or "this revision")),
        evidence={"revision": now.target_revision, "observed_at": now.observed_at})


# ===========================================================================
# THIS world -- the one minimisation left behind
# ===========================================================================

def scope(context: ProbeContext) -> ProbeResult:
    """Re-run the world as it was before minimisation stripped it.

    Minimisation removes everything that is not load-bearing FOR THE FAILURE
    AS IT WAS. A fix can close the minimal world and leave the larger one
    open -- the scenery that was irrelevant to the attack is not necessarily
    irrelevant to the repair.
    """
    original = context.original
    grown = False
    if original is None or original.digest() == context.genome.digest():
        # NEVER MINIMISED IS NOT THE SAME AS UNANSWERABLE.
        #
        # The first version returned "not asked" here, which meant no case
        # that had never been minimised could ever reach the strongest
        # standing -- the ceiling was unreachable for most of the corpus and
        # the distinction stopped meaning anything.
        #
        # The emphasis is "THIS world", and for a case that was never reduced
        # the analogous question is not "what did minimisation remove" but
        # "does this hold when the world is bigger". That is answerable: grow
        # one and run it.
        original = _grown(context.genome)
        grown = True
    where = "a world grown around it" if grown else "the world before minimisation"
    try:
        result = attack_module.run(original, context.adapter, timeout=context.timeout)
    except Exception as exc:
        return unprobed("scope", "%s could not be built: %s: %s"
                        % (where, type(exc).__name__, exc))
    if result.broken:
        return unprobed("scope", "%s could not be run: %s" % (where, result.broken))
    found = {failure_class(s.kind) for s in result.violations}
    resolved = set(context.resolved_classes)
    if found & resolved or (found and not resolved):
        return ProbeResult(
            probe="scope", defeated=True, held=False,
            account=("%s still reproduces %s at %s: the fix closed the small "
                     "world and not the large one"
                     % (where, ", ".join(sorted(found & resolved or found)),
                        result.fitness.top.name)),
            evidence={"digest": original.digest(), "grown": grown,
                      "classes": sorted(found)})
    return ProbeResult(
        probe="scope", defeated=False, held=True,
        account=("%s does not reproduce %s either"
                 % (where, " or ".join(sorted(resolved)) or "anything")
                 + ("; it produced %s instead, which is a case to file"
                    % ", ".join(sorted(found)) if found else "")),
        evidence={"digest": original.digest(), "grown": grown,
                  "other_findings": sorted(found)})


def _grown(genome: RepositoryGenome) -> RepositoryGenome:
    """The same case with scenery around it.

    Deliberately scenery and nothing else: extra modules, extra functions, a
    second document with prose in it, a bigger suite. Nothing that changes
    what the case is about, so a difference in outcome is a difference the
    SIZE of the world made.
    """
    from dataclasses import replace
    from .genome import DocumentSpec, FilesystemShape, TestShape
    documents = genome.documents or ()
    extra = DocumentSpec(path="CONTRIBUTING.md", title="Contributing",
                         prose=("Run the suite before opening a pull request.",
                                "Keep the layers separate."))
    if not any(d.path == extra.path for d in documents):
        documents = documents + (extra,)
    return genome.evolved(
        name=genome.name + "-grown",
        documents=documents,
        project=replace(genome.project, modules=("core", "extra", "more"),
                        functions_per_module=3, has_ci=True),
        filesystem=replace(genome.filesystem, filler_modules=4),
        tests=replace(genome.tests, count=max(genome.tests.count, 40)))


# ===========================================================================
# the surface -- the siblings a local fix would have missed
# ===========================================================================

def adjacency(context: ProbeContext) -> ProbeResult:
    """Re-run the other cases aimed at the same mechanism.

    A fix can be correct and local. Closing one case on a surface says
    nothing about the surface, and the cheapest way to find out is to ask
    the siblings that were already written.
    """
    siblings = [g for g in context.siblings
                if g.digest() != context.genome.digest()]
    if not siblings:
        return unprobed("adjacency", "no sibling cases on this surface")
    if not context.resolved_classes:
        return unprobed("adjacency",
                        "no record of which failure was resolved, so a sibling "
                        "reproducing something cannot be compared against it")
    resolved = set(context.resolved_classes)
    still: List[str] = []
    lesser: List[str] = []
    for sibling in siblings:
        try:
            result = attack_module.run(sibling, context.adapter,
                                       timeout=context.timeout)
        except Exception as exc:
            lesser.append("%s could not be run (%s)" % (sibling.name,
                                                        type(exc).__name__))
            continue
        if result.broken or not result.fitness.interesting:
            continue
        found = {failure_class(s.kind) for s in result.violations}
        # The same rule the variant probe uses, and it belongs here for the
        # same reason. A sibling reproducing a DIFFERENT and lesser failure
        # has found a case to file; it has not shown that the failure this
        # resolution is about is still open.
        #
        # Applying it in one probe and not the other was an inconsistency the
        # framework caught in itself: adjacency reported a CRITICAL escape
        # resolution as defeated on the strength of a sibling producing LOW
        # over-caution.
        if found & resolved:
            still.append("%s (%s at %s)" % (sibling.name,
                                            ", ".join(sorted(found & resolved)),
                                            result.fitness.top.name))
        else:
            lesser.append("%s (%s at %s)" % (sibling.name, ", ".join(sorted(found)),
                                             result.fitness.top.name))
    if still:
        return ProbeResult(
            probe="adjacency", defeated=True, held=False,
            account=("the surface is still open: %s" % ", ".join(still)),
            evidence={"reproducing_siblings": still, "other_findings": lesser,
                      "checked": [g.name for g in siblings]})
    account = ("%d sibling case(s) on the same surface were re-run and none "
               "reproduce %s" % (len(siblings),
                                 " or ".join(sorted(resolved)) or "anything"))
    if lesser:
        account += ("; %d produced a different and lesser finding (%s), which "
                    "is a case to file rather than a defeat of this one"
                    % (len(lesser), "; ".join(lesser[:3])))
    return ProbeResult(
        probe="adjacency", defeated=False, held=True, account=account,
        evidence={"checked": [g.name for g in siblings],
                  "other_findings": lesser})


# ===========================================================================
# THIS case -- the class it was only ever one member of
# ===========================================================================

def variant(context: ProbeContext) -> ProbeResult:
    """Mutate the genome and re-run, looking for a near neighbour that works.

    The sharpest of the five and the most expensive. A fix that keys on the
    exact shape of the case rather than on the mechanism behind it will close
    this world and fall to the one next door, and no amount of re-running the
    original will ever say so.
    """
    if context.budget < 1:
        return unprobed("variant", "no budget for variants")
    if not context.resolved_classes:
        return unprobed("variant",
                        "no record of which failure was resolved, so a variant "
                        "reproducing something cannot be compared against it")
    rng = random.Random("variant:%s:%d" % (context.genome.digest(), context.seed))
    stats = {name: search.MutatorStats() for name in search.mutator_registry.registry()}
    tried: List[str] = []
    incidental: List[str] = []
    unbuildable: List[str] = []
    for _ in range(context.budget):
        child = search.offspring(context.genome, rng, stats)
        if child is None:
            continue
        try:
            result = attack_module.run(child, context.adapter,
                                       timeout=context.timeout)
        except Exception as exc:
            # A generated combination that cannot be built is not a finding
            # and must not take the sweep down with it: one mutator can
            # remove the document another one targets. `evolve` already
            # tolerated this; this probe did not, and crashed the first full
            # run across the corpus.
            unbuildable.append("%s: %s" % (type(exc).__name__, exc))
            continue
        if result.broken:
            continue
        tried.append(child.digest())
        if not result.fitness.interesting:
            continue
        found = {failure_class(s.kind) for s in result.violations}
        # WHICH failure the variant reproduces decides whether this is a
        # defeat. The resolution being interrogated is about ONE failure; a
        # variant that produces a different and lesser one has found
        # something, and it has not shown that the resolved failure survives.
        #
        # Without this the probe cried wolf on its first real run: a variant
        # that made the target over-cautious -- LOW, a different class
        # entirely -- was reported as "the fix closed this case and not the
        # class", about a CRITICAL. That is the same unearned promotion this
        # whole module exists to refuse, committed by the thing refusing it.
        resolved = set(context.resolved_classes)
        same = found & resolved if resolved else set()
        worse = _severity_rank(result.fitness.top.name) >= _severity_rank(
            context.resolved_severity)
        if same or (worse and resolved and not found):
            return ProbeResult(
                probe="variant", defeated=True, held=False,
                account=("a variant reproduces %s at %s, which is the failure "
                         "this resolution is about: the fix closed this case "
                         "and not the class"
                         % (", ".join(sorted(same or found)), result.fitness.top.name)),
                evidence={"variant_digest": child.digest(),
                          "variant_genome": child.to_dict(),
                          "classes": sorted(found), "tried": tried})
        incidental.append("%s at %s" % (", ".join(sorted(found)),
                                        result.fitness.top.name))
    if not tried:
        return unprobed(
            "variant",
            "no legal variant of this genome could be built"
            + (" (%d candidate(s) were rejected as unbuildable)" % len(unbuildable)
               if unbuildable else ""))
    account = ("%d variant(s) were built and run; none reproduce %s. That is a "
               "sample of the neighbourhood, not a proof about it."
               % (len(tried), " or ".join(context.resolved_classes) or "the failure"))
    if incidental:
        account += (" Separately, %d of them produced a different and lesser "
                    "finding (%s), which is a case to file rather than a defeat "
                    "of this one." % (len(incidental), "; ".join(incidental[:3])))
    return ProbeResult(
        probe="variant", defeated=False, held=True, account=account,
        evidence={"tried": tried, "incidental": incidental,
                  "unbuildable": len(unbuildable)})


_SEVERITY_ORDER = ("NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL")


def _severity_rank(name: str) -> int:
    return _SEVERITY_ORDER.index(name) if name in _SEVERITY_ORDER else 0


# ===========================================================================
# Driver
# ===========================================================================

def interrogate(context: ProbeContext, now: Optional[Observation] = None,
                only: Sequence[str] = (),
                on_probe=None) -> Tuple[Observation, Tuple[ProbeResult, ...]]:
    """Observe the case, then ask every question of the answer."""
    if now is None:
        now = observe(context.genome, context.adapter, timeout=context.timeout)

    wanted = set(only) if only else set(PROBES)
    results: List[ProbeResult] = []
    for name in PROBES:
        if name not in wanted:
            results.append(unprobed(name, "not selected"))
            continue
        if now.reproduced and name in ("scope", "adjacency", "variant"):
            # It still reproduces. The expensive probes exist to interrogate
            # a NON-reproduction, and spending target invocations to confirm
            # a failure that is already in front of you is waste.
            results.append(unprobed(name, "the case reproduces; there is no "
                                          "non-reproduction to interrogate"))
            continue
        try:
            if name == "concealment":
                result = concealment(context, now)
            elif name == "recurrence":
                result = recurrence(context, now)
            elif name == "scope":
                result = scope(context)
            elif name == "adjacency":
                result = adjacency(context)
            else:
                result = variant(context)
        except Exception as exc:
            # A probe that broke asked nothing. Reporting that as "held"
            # would turn a crash into evidence of a fix, which is the single
            # worst thing this module could do.
            result = unprobed(name, "the probe raised %s: %s"
                              % (type(exc).__name__, exc))
        results.append(result)
        if on_probe:
            on_probe(result)
    return now, tuple(results)
