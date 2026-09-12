"""Adaptive search: let the laboratory find what the catalogue did not.

WHAT IS BEING SEARCHED

The space of genomes, not the space of files. An offspring is produced by
changing a typed parameter or adding a mutation to a sequence, which means
every candidate is describable, reproducible and minimisable by
construction. A search over file bytes would produce failures nobody can
archive.

WHAT "ADAPTIVE" MEANS HERE, AND WHAT IT DOES NOT

It means the search keeps statistics per mutator -- how often adding this
one to a genome produced a case that scored higher than its parent -- and
biases its choices toward the ones that have been paying. That is enough
to concentrate effort on productive combinations within a run, and it is
deliberately not machine learning. A learned model of a target's weak
points would need far more evaluations than a run of this thing can afford
(each evaluation runs the target over a repository: seconds, not
microseconds) and would be the least trustworthy component in a framework
whose whole selling point is that its judgements can be checked.

SELECTION IS BY DOMINANCE, NOT BY SCALAR

`fitness.Fitness` compares lexicographically, so a parent that found a
CRITICAL is never displaced by one that found six LOWs. Elitism keeps the
best few unchanged between generations, because an adversarial search that
can lose its best case to drift will.

NOVELTY

Genomes are cached by digest. Re-running an identical world teaches
nothing and costs a full target invocation, and without the cache a
population converges to one good genome and then spends its whole budget
re-proving it.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from . import attack as attack_module
from . import coverage
from . import mutators as mutator_registry
from .adapter import TargetAdapter
from .attack import CaseResult
from .fitness import Fitness
from .genome import (AttackCategory, ClaimSpec, ClaimStyle, CountBlockSpec,
                     DocumentKind, DocumentSpec, MutationSpec, Phase,
                     RepositoryGenome, TestShape)
from .signals import Severity


@dataclass
class MutatorStats:
    """How a mutator has been paying, this run."""

    offered: int = 0
    improved: int = 0
    #: Cases where adding it produced a CRITICAL that the parent did not have.
    critical: int = 0

    @property
    def hit_rate(self) -> float:
        return self.improved / self.offered if self.offered else 0.0

    def weight(self) -> float:
        """Selection weight. The floor keeps every mutator reachable.

        Without the floor, a mutator that failed on the first two genomes it
        was offered would never be tried again, and the search would foreclose
        on an attack class in its first generation on the strength of two
        samples.
        """
        return 0.15 + self.hit_rate


@dataclass
class SearchReport:
    generations: int
    evaluations: int
    seconds: float
    best: List[CaseResult]
    stats: Dict[str, MutatorStats]
    #: Evaluation index at which each failure class was first seen.
    first_seen: Dict[str, int]
    #: Genome digests evaluated, so a caller can tell novelty from repetition.
    seen: int
    rediscovered: List[str] = field(default_factory=list)
    #: Combinations that beat every one of their members' best. Structural
    #: findings, not bigger numbers about either member.
    connections: Tuple[str, ...] = ()
    #: Surfaces of the target that no case had ever landed on when the search
    #: started, and that a case landed on before it finished. The outcome of
    #: `UNCOVERED_SHARE`, measured rather than intended: a counter of how
    #: often the search MEANT to aim somewhere new would be a report about
    #: this module's own policy, which is not a result.
    surfaces_opened: Tuple[str, ...] = ()
    #: Still empty when the budget ran out. The honest other half.
    surfaces_still_empty: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generations": self.generations,
            "evaluations": self.evaluations,
            "seconds": round(self.seconds, 1),
            "distinct_genomes": self.seen,
            "first_seen_at_evaluation": dict(sorted(self.first_seen.items())),
            "rediscovered_seed_cases": list(self.rediscovered),
            "connections_found": list(self.connections),
            "surfaces_opened": list(self.surfaces_opened),
            "surfaces_still_empty": list(self.surfaces_still_empty),
            "mutator_stats": {
                name: {"offered": s.offered, "improved": s.improved,
                       "critical": s.critical, "hit_rate": round(s.hit_rate, 3)}
                for name, s in sorted(self.stats.items()) if s.offered},
            "best": [r.to_dict() for r in self.best],
        }


# --------------------------------------------------------------- offspring

def _satisfied(genome: RepositoryGenome, name: str) -> bool:
    """Whether a mutator's stated prerequisites hold for this genome."""
    mutator = mutator_registry.get(name)
    for requirement in mutator.requires:
        if requirement == "count_block" and not genome.count_blocks:
            return False
    if name in {m.name for m in genome.mutations}:
        return False                      # one of each; sequences, not stacks
    if name == "move_count_block_to_document" and not genome.count_blocks:
        return False
    if name in ("make_dated_claim", "make_historical_claim", "make_scoped_claim",
                "make_attributed_claim", "make_hedged_claim",
                "make_comparison_table", "rewrite_claim_during_tests"):
        # A claim mutator needs a claim AND the document it lives in to still
        # be where the genome says. `alias_document_with_symlink` and
        # `symlink_escapes_repository` both move or remove one, so composing
        # either with a claim mutator builds a world that cannot be built.
        moved = {m.name for m in genome.mutations} & {
            "alias_document_with_symlink", "symlink_escapes_repository"}
        return bool(genome.claims) and not moved
    if name == "alias_document_with_symlink":
        # Not after a claim mutator either: the alias renames the document
        # out from under the claim's recorded path.
        return bool(genome.documents) and not any(
            m.name in ("symlink_escapes_repository", "rewrite_claim_during_tests")
            for m in genome.mutations)
    if name == "symlink_escapes_repository":
        return not any(m.name == "alias_document_with_symlink"
                       for m in genome.mutations)
    return True


def _params_for(name: str, genome: RepositoryGenome,
                rng: random.Random) -> Dict[str, Any]:
    documents = [d.path for d in genome.documents] or ["README.md"]
    document = rng.choice(documents)
    if name in ("make_dated_claim", "make_historical_claim", "make_scoped_claim",
                "make_attributed_claim", "make_hedged_claim",
                "make_comparison_table", "rewrite_claim_during_tests"):
        claim = rng.choice(genome.claims)
        return {"document": claim.document, "count": claim.documented_count}
    if name == "put_prose_in_count_block":
        return {"document": genome.count_blocks[0].document,
                "sentence": rng.choice(_SENTENCES)}
    if name in ("duplicate_count_block", "nest_count_block_marker",
                "corrupt_count_block_marker"):
        return {"document": genome.count_blocks[0].document}
    if name == "move_count_block_to_document":
        return {"from": genome.count_blocks[0].document,
                "to": rng.choice(("PHASE_4_COMPLETE.md", "STATUS_2026-01.md",
                                  "RELEASE_NOTES.md"))}
    if name == "alias_document_with_symlink":
        return {"link": document, "target": rng.choice(
            ("docs/project_notes.md", "docs/handbook.md", "meta/overview.md"))}
    if name == "symlink_escapes_repository":
        return {"link": document, "bait": "victim/README.md"}
    if name == "add_filler_modules":
        return {"count": rng.randint(2, 6)}
    return {}


_SENTENCES = (
    "The suite is split by layer; see CONTRIBUTING for why that matters.",
    "Do not collapse the layers to make this number tidier.",
    "This paragraph is here because a reviewer asked for it in 2025.",
)


#: The share of mutator choices spent on keys with a TRUE ZERO BASE against
#: this target: never offered, so no prior exists.
#:
#: A reserved share rather than a floor on their weight, and the difference
#: is the whole point. A floor invents a number and then treats the result as
#: evidence. A reserved share says plainly that some of the budget is being
#: spent on the unknown BECAUSE it is unknown, which is an experiment and not
#: a bet, and leaves the weights to describe only what was measured.
EXPLORE_SHARE = 0.35

#: The share of mutator choices spent reaching a SURFACE of the target that
#: no case in this run has landed on yet.
#:
#: Productivity weighting alone is rich-get-richer. It concentrates the
#: search exactly where it has already succeeded, which is where new
#: information is least likely to be, and a search that has found four
#: writability bugs will keep finding writability bugs while the identity
#: and baseline rows sit at zero forever. The empty row is the one thing the
#: coverage table can say that a pass rate cannot, and a search that never
#: aims at it guarantees the row stays empty.
#:
#: Taken FIRST, ahead of the zero-base share, and the order is a claim:
#: never having tested a mechanism of the target is ignorance about the
#: SUBJECT, while a mutator with no record is ignorance about the
#: INSTRUMENT. The first is the more expensive one to keep.
UNCOVERED_SHARE = 0.25


def offspring(parent: RepositoryGenome, rng: random.Random,
              stats: Mapping[str, MutatorStats],
              knowledge=None, revision: str = "",
              uncovered: Sequence[str] = ()) -> Optional[RepositoryGenome]:
    """One child of `parent`, or None if no legal change was available."""
    moves: List[Callable[[], Optional[RepositoryGenome]]] = []

    available = [name for name in mutator_registry.registry()
                 if _satisfied(parent, name)]
    if available:
        def add() -> RepositoryGenome:
            name = _choose(available, rng, stats, knowledge, revision,
                           uncovered)
            spec = MutationSpec(
                name=name, params=_params_for(name, parent, rng),
                phase=mutator_registry.get(name).phase)
            return parent.evolved(mutations=parent.mutations + (spec,))
        moves.append(add)
        moves.append(add)              # offered twice: growth is the point

    if parent.mutations:
        def drop() -> RepositoryGenome:
            index = rng.randrange(len(parent.mutations))
            return parent.evolved(
                mutations=parent.mutations[:index] + parent.mutations[index + 1:])
        moves.append(drop)

    if parent.documents:
        def retitle() -> RepositoryGenome:
            index = rng.randrange(len(parent.documents))
            doc = parent.documents[index]
            kind = rng.choice(tuple(DocumentKind))
            changed = replace(doc, kind=kind)
            return parent.evolved(documents=parent.documents[:index] + (changed,)
                                  + parent.documents[index + 1:])
        moves.append(retitle)

    if parent.claims:
        def restyle() -> RepositoryGenome:
            index = rng.randrange(len(parent.claims))
            claim = parent.claims[index]
            style = rng.choice(tuple(ClaimStyle))
            changed = replace(claim, style=style)
            return parent.evolved(claims=parent.claims[:index] + (changed,)
                                  + parent.claims[index + 1:])
        moves.append(restyle)

    def toggle_block() -> RepositoryGenome:
        if parent.count_blocks:
            return parent.evolved(count_blocks=())
        document = parent.documents[0].path if parent.documents else "README.md"
        return parent.evolved(count_blocks=(CountBlockSpec(document, 12),))
    moves.append(toggle_block)

    def resize() -> RepositoryGenome:
        return parent.evolved(tests=replace(parent.tests,
                                            count=rng.choice((20, 30, 45, 60))))
    moves.append(resize)

    if not moves:
        return None
    child = rng.choice(moves)()
    if child is None:
        return None
    return child.evolved(
        name="%s-g%04d" % (_stem(parent.name), rng.randrange(10000)),
        seed=rng.randrange(1_000_000),
        hypothesis=parent.hypothesis,
        notes="Evolved from %s (%s)." % (parent.name, parent.digest()))


def _choose(available, rng, stats, knowledge, revision,
            uncovered: Sequence[str] = ()) -> str:
    """Which mutator to add, and on what grounds.

    Three grounds, taken in order, and the order is the design:

        the target has a mechanism nothing has ever attacked
        this mutator has never been offered against this revision
        the evidence says it pays

    The first two are reserved shares, not weights. A floor on a weight
    invents a number and then consumes it as evidence; a reserved share says
    plainly that part of the budget is being spent on the unknown BECAUSE it
    is unknown. See `UNCOVERED_SHARE` for why ignorance about the subject is
    taken ahead of ignorance about the instrument.

    Without a knowledge store the last ground is the old in-run weighting,
    which is fine for a single run: everything starts at zero together and
    the floor is doing no epistemic work because nothing has a history yet.
    """
    if uncovered:
        reaching = [n for n in available
                    if set(coverage.surfaces_of(n)) & set(uncovered)]
        if reaching and rng.random() < UNCOVERED_SHARE:
            return rng.choice(reaching)

    if knowledge is None:
        weights = [stats.get(n, MutatorStats()).weight() for n in available]
        return rng.choices(available, weights=weights, k=1)[0]

    from .knowledge import Acquisition
    unmeasured = [n for n in available
                  if knowledge.about(n, revision).acquisition
                  is Acquisition.ZERO_BASE]
    if unmeasured and rng.random() < EXPLORE_SHARE:
        return rng.choice(unmeasured)

    # Observation before inference, lexicographically. Anything measured
    # against THIS revision is chosen ahead of anything carried from another,
    # however good the carried record looks -- the same dominance idiom
    # `fitness.py` uses, and for the same reason: a discount factor is a
    # judgement disguised as arithmetic.
    known = [(n, knowledge.about(n, revision)) for n in available]
    here = [(n, k.weight()) for n, k in known
            if k.outranks_carried and k.weight() is not None]
    elsewhere = [(n, k.weight()) for n, k in known
                 if not k.outranks_carried and k.weight() is not None]
    pool = here or elsewhere
    if not pool:
        return rng.choice(unmeasured or available)
    return rng.choices([n for n, _ in pool],
                       weights=[max(w, 0.01) for _, w in pool], k=1)[0]


def _stem(name: str) -> str:
    return name.split("-g")[0]


# ------------------------------------------------------------------ driver

def evolve(seeds: Sequence[RepositoryGenome], adapter: TargetAdapter, *,
           budget: int = 40, population: int = 6, elite: int = 2,
           seed: int = 0, timeout: float = 900.0,
           knowledge=None,
           on_case: Optional[Callable[[CaseResult, int], None]] = None
           ) -> SearchReport:
    """Run the search until the evaluation budget is spent."""
    rng = random.Random(seed)
    revision = str(dict(adapter.version()).get("commit", ""))
    #: The best score any evaluated genome containing each mutator has
    #: reached. A combination that beats every one of its members' bests is
    #: a CONNECTION: a structural fact about the pair that neither member's
    #: own tally can hold.
    best_with: Dict[str, int] = {}
    connections: List[str] = []
    started = time.perf_counter()
    stats: Dict[str, MutatorStats] = {name: MutatorStats()
                                      for name in mutator_registry.registry()}
    evaluated: Dict[str, CaseResult] = {}
    first_seen: Dict[str, int] = {}
    rediscovered: List[str] = []
    seed_names = {g.name for g in seeds}

    def evaluate(genome: RepositoryGenome) -> Optional[CaseResult]:
        digest = genome.digest()
        if digest in evaluated:
            return None
        try:
            result = attack_module.run(genome, adapter, timeout=timeout)
        except Exception:
            evaluated[digest] = None            # type: ignore[assignment]
            return None
        evaluated[digest] = result
        index = len(evaluated)
        from .signals import failure_class
        for signal in result.violations:
            name = failure_class(signal.kind)
            first_seen.setdefault(name, index)
        if on_case:
            on_case(result, index)
        return result

    current: List[Tuple[RepositoryGenome, Fitness]] = []
    for genome in seeds[:population]:
        result = evaluate(genome)
        if result is not None and not result.broken:
            current.append((genome, result.fitness))
        if len(evaluated) >= budget:
            break

    def _live() -> List[CaseResult]:
        return [r for r in evaluated.values() if r is not None]

    #: Measured once, before the search has had a chance to change it.
    empty_at_the_start = coverage.unexercised(coverage.matrix(_live()))

    generations = 0
    elite_size = max(1, elite)
    while len(evaluated) < budget and current:
        generations += 1
        # Recomputed every generation: a surface stops being uncovered the
        # moment a case lands on it, and continuing to aim there would be
        # spending the reserved share on something no longer unknown.
        uncovered = coverage.unexercised(coverage.matrix(_live()))
        current.sort(key=lambda pair: pair[1].key(), reverse=True)
        keep = current[:elite_size]
        children: List[Tuple[RepositoryGenome, Fitness]] = list(keep)

        while len(children) < population and len(evaluated) < budget:
            parent, parent_fitness = keep[rng.randrange(len(keep))] if rng.random() < 0.7 \
                else current[rng.randrange(len(current))]
            child = offspring(parent, rng, stats, knowledge, revision,
                              uncovered)
            if child is None:
                continue
            added = [m.name for m in child.mutations
                     if m.name not in {p.name for p in parent.mutations}]
            result = evaluate(child)
            if result is None or result.broken:
                for name in added:
                    stats.setdefault(name, MutatorStats()).offered += 1
                continue
            improved = parent_fitness < result.fitness
            newly_critical = (result.fitness.top is Severity.CRITICAL
                              and parent_fitness.top is not Severity.CRITICAL)
            for name in added:
                record = stats.setdefault(name, MutatorStats())
                record.offered += 1
                record.improved += int(improved)
                record.critical += int(newly_critical)
                if knowledge is not None:
                    knowledge.observe(name, revision, improved=improved,
                                      critical=newly_critical)

            members = sorted({m.name for m in child.mutations})
            if knowledge is not None and len(members) >= 2:
                try:
                    scalar = result.fitness.scalar()
                except ValueError:
                    scalar = 0
                prior = max((best_with.get(m, 0) for m in members), default=0)
                if scalar > prior and prior >= 0:
                    lift = max(0.05, (int(result.fitness.top)
                                      - _rank_of(prior)) / 4.0)
                    knowledge.connect(members, revision, lift)
                    connections.append(" + ".join(members))
                for m in members:
                    best_with[m] = max(best_with.get(m, 0), scalar)
            if (result.fitness.interesting
                    and _stem(child.name) in seed_names
                    and _stem(child.name) not in rediscovered):
                rediscovered.append(_stem(child.name))
            children.append((child, result.fitness))
        current = children

    if knowledge is not None:
        knowledge.save()

    empty_at_the_end = coverage.unexercised(coverage.matrix(_live()))
    ranked = sorted((r for r in evaluated.values() if r is not None and not r.broken),
                    key=lambda r: r.fitness.key(), reverse=True)
    return SearchReport(
        generations=generations,
        evaluations=len([r for r in evaluated.values() if r is not None]),
        seconds=time.perf_counter() - started,
        best=[r for r in ranked if r.fitness.interesting][:10],
        stats=stats, first_seen=first_seen, seen=len(evaluated),
        rediscovered=rediscovered, connections=tuple(dict.fromkeys(connections)),
        surfaces_opened=tuple(s for s in empty_at_the_start
                              if s not in empty_at_the_end),
        surfaces_still_empty=tuple(empty_at_the_end))


def _rank_of(scalar: int) -> int:
    """The top severity a packed fitness scalar represents."""
    from .fitness import CAP
    for level in (4, 3, 2, 1):
        if scalar // (CAP ** (4 - level)) % CAP:
            return level
    return 0
