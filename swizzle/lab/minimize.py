"""The smallest world in which the target still breaks its own invariant.

WHY THIS IS THE MOST VALUABLE PART OF THE LABORATORY

"A forty-file generated repository made the tool misbehave" is not a bug
report. Nobody can act on it: the reader cannot tell which of the forty
files matters, cannot tell whether the behaviour is one defect or three
interacting, and cannot tell whether a fix worked. "A README with one
sentence inside a marked block makes the tool delete the sentence" is a bug
report, and the difference between them is this module.

HOW IT WORKS, AND WHY ON GENOMES RATHER THAN DIRECTORIES

Every reduction is a change to the genome, followed by a rebuild and a
re-run. That is slower per step than editing files in place and it is the
only version that stays correct: reducing a materialised directory can
produce a world no genome describes, which is then unreproducible, and an
unreproducible minimal case is worse than the large one it replaced.

The reduction is greedy over a fixed set of moves, run to a fixpoint. It is
not ddmin: ddmin's power is finding a minimal subset of INDEPENDENT deltas,
and these deltas are not independent -- removing a document invalidates the
claims inside it. Greedy-to-fixpoint over moves that each keep the genome
valid is the version that does not need a repair step, and the cost is that
the result is locally minimal rather than provably minimal. That is stated
in the report rather than implied away.

PRESERVING THE ATTACK

A reduction is kept only if the case still produces the same failure
CLASSES at the same top severity. Not the same signal count -- a smaller
world legitimately produces fewer signals of the same kind, and requiring
the count to match would reject every real reduction. Not the same kinds
either: dropping a document can move a failure from
`unauthorised_file_mutation` to `edit_outside_permitted_lines` without
changing what went wrong. Classes and severity are what "the same attack"
means here.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Callable, List, Optional, Sequence, Tuple

from . import attack as attack_module
from .adapter import TargetAdapter
from .attack import CaseResult
from .genome import (DocumentSpec, MutationSpec, ProjectShape, RepositoryGenome,
                     TestShape)
from .signals import Severity, failure_class

#: How many rebuild-and-run cycles a minimisation may spend before it stops
#: and reports what it has. A budget rather than a guarantee, because each
#: step runs the target over a repository and that is seconds, not
#: microseconds.
DEFAULT_BUDGET = 60


def signature_of(result: CaseResult) -> Tuple[str, Tuple[str, ...]]:
    """What must be preserved: the top severity and the classes that reached it."""
    top = result.fitness.top
    classes = {failure_class(s.kind) for s in result.violations
               if s.severity is top}
    return top.name, tuple(sorted(classes))


@dataclass(frozen=True)
class Minimisation:
    original: RepositoryGenome
    minimal: RepositoryGenome
    signature: Tuple[str, Tuple[str, ...]]
    steps_tried: int
    steps_kept: int
    seconds: float
    #: What the reduction actually removed, for the report.
    removed: Tuple[str, ...]
    #: The run of the minimal genome, so a caller need not re-run it.
    result: Optional[CaseResult] = None
    #: Set when the budget ran out before the fixpoint.
    exhausted: bool = False

    @property
    def ratio(self) -> float:
        """Size after over size before. Smaller is better; 1.0 is no reduction."""
        return _size(self.minimal) / max(1, _size(self.original))

    def to_dict(self):
        return {"original": self.original.to_dict(), "minimal": self.minimal.to_dict(),
                "signature": [self.signature[0], list(self.signature[1])],
                "steps_tried": self.steps_tried, "steps_kept": self.steps_kept,
                "removed": list(self.removed), "seconds": round(self.seconds, 1),
                "size_before": _size(self.original), "size_after": _size(self.minimal),
                "ratio": round(self.ratio, 3), "exhausted": self.exhausted}


def _size(genome: RepositoryGenome) -> int:
    """A blunt size measure: the things a reader has to hold in their head."""
    return (len(genome.mutations) * 4
            + len(genome.documents) * 3
            + len(genome.claims) * 2
            + len(genome.count_blocks) * 2
            + len(genome.project.modules)
            + genome.filesystem.filler_modules
            + max(1, genome.tests.count) // 10)


# --------------------------------------------------------------------- moves

def _moves(genome: RepositoryGenome) -> List[Tuple[str, RepositoryGenome]]:
    """Every single-step reduction of `genome`, largest effect first.

    Order matters for a greedy search: dropping a mutation can make three
    other reductions possible, so mutations are offered before cosmetics.
    """
    out: List[Tuple[str, RepositoryGenome]] = []

    for index, mutation in enumerate(genome.mutations):
        remaining = genome.mutations[:index] + genome.mutations[index + 1:]
        out.append(("drop mutation %s" % mutation.name,
                    genome.evolved(mutations=remaining)))

    if genome.filesystem.filler_modules:
        out.append(("drop filler modules",
                    genome.evolved(filesystem=replace(genome.filesystem,
                                                      filler_modules=0))))

    for index, doc in enumerate(genome.documents):
        if len(genome.documents) <= 1:
            break
        remaining = genome.documents[:index] + genome.documents[index + 1:]
        kept = {d.path for d in remaining}
        out.append(("drop document %s" % doc.path,
                    genome.evolved(
                        documents=remaining,
                        claims=tuple(c for c in genome.claims if c.document in kept),
                        count_blocks=tuple(b for b in genome.count_blocks
                                           if b.document in kept))))

    for index, doc in enumerate(genome.documents):
        if not doc.prose:
            continue
        stripped = replace(doc, prose=())
        out.append(("drop prose from %s" % doc.path,
                    genome.evolved(documents=genome.documents[:index] + (stripped,)
                                   + genome.documents[index + 1:])))

    for index, claim in enumerate(genome.claims):
        out.append(("drop claim in %s" % claim.document,
                    genome.evolved(claims=genome.claims[:index] + genome.claims[index + 1:])))

    for index, block in enumerate(genome.count_blocks):
        out.append(("drop count block in %s" % block.document,
                    genome.evolved(count_blocks=genome.count_blocks[:index]
                                   + genome.count_blocks[index + 1:])))

    if len(genome.project.modules) > 1:
        out.append(("drop a module",
                    genome.evolved(project=replace(
                        genome.project, modules=genome.project.modules[:-1]))))
    if genome.project.functions_per_module > 1:
        out.append(("one function per module",
                    genome.evolved(project=replace(genome.project,
                                                   functions_per_module=1))))
    if genome.project.has_ci:
        out.append(("drop CI configuration",
                    genome.evolved(project=replace(genome.project, has_ci=False))))

    # The test count is the one dimension worth halving rather than dropping:
    # the target's own drift thresholds need the real suite to be some
    # distance past the documented number, so zero is never reachable and a
    # binary walk finds the floor in a handful of steps.
    if genome.tests.count > 4:
        out.append(("halve the suite (%d -> %d)"
                    % (genome.tests.count, genome.tests.count // 2),
                    genome.evolved(tests=replace(genome.tests,
                                                 count=genome.tests.count // 2))))
    return out


# ------------------------------------------------------------------- driver

def minimise(genome: RepositoryGenome, adapter: TargetAdapter, *,
             budget: int = DEFAULT_BUDGET,
             baseline: Optional[CaseResult] = None,
             on_step: Optional[Callable[[str, bool, int], None]] = None,
             timeout: float = 900.0) -> Minimisation:
    """Reduce `genome` while it keeps producing the same failure."""
    started = time.perf_counter()
    if baseline is None:
        baseline = attack_module.run(genome, adapter, timeout=timeout)
    if not baseline.fitness.interesting:
        raise ValueError(
            "%s produced no violation, so there is nothing to minimise. "
            "Reducing a case that never failed would 'succeed' immediately "
            "and archive a world that proves nothing." % genome.name)

    target_signature = signature_of(baseline)
    current, best_result = genome, baseline
    removed: List[str] = []
    tried = kept = 0
    exhausted = False

    progressing = True
    while progressing:
        progressing = False
        for label, candidate in _moves(current):
            if tried >= budget:
                exhausted = True
                progressing = False
                break
            tried += 1
            try:
                result = attack_module.run(candidate, adapter, timeout=timeout)
            except Exception:
                if on_step:
                    on_step(label, False, tried)
                continue
            held = (not result.broken
                    and result.fitness.interesting
                    and signature_of(result) == target_signature)
            if on_step:
                on_step(label, held, tried)
            if held:
                current, best_result = candidate, result
                removed.append(label)
                kept += 1
                progressing = True
                break
        if exhausted:
            break

    minimal = current.evolved(
        name=current.name,
        notes=(current.notes + "\n" if current.notes else "")
        + "Minimised from %s: %d of %d reductions held."
        % (genome.digest(), kept, tried))
    return Minimisation(original=genome, minimal=minimal,
                        signature=target_signature, steps_tried=tried,
                        steps_kept=kept, seconds=time.perf_counter() - started,
                        removed=tuple(removed), result=best_result,
                        exhausted=exhausted)
