"""Cases nothing has adapted to.

WHY A HOLDOUT IS NOT OPTIONAL HERE

Every number this laboratory reports about how well a target does is
measured on cases somebody chose. The search adapts to what pays. Fixes get
made against what was found. After enough rounds, "the catalogue passes" can
mean the target got better, or it can mean the catalogue got easier, and the
catalogue cannot tell you which.

A holdout is the only thing that can: cases drawn from the same space, run
against the same target, that NOTHING has ever adapted to.

THE EXISTING CATALOGUE CANNOT BE SPLIT INTO ONE

Retroactively declaring some of the twenty-six seed cases "holdout" would be
a fiction. Every one of them has been looked at, and Ghost has been fixed in
response to most of them; the results are in this repository's history. A
partition drawn now would be drawn with the answers already known, which is
selection bias rather than a holdout.

So the whole catalogue is DISCOVERY, by history, and the holdout is
generated: genomes sampled from the same space by a seeded random walk, with
no fitness feedback of any kind, frozen into a manifest before any target
runs against them.

WHAT MAKES THEM INDEPENDENT

    sampled randomly       no search chose them, so nothing chose them for
                           being hard, easy, or interesting
    no fitness feedback    the walk never looks at a result, so it cannot
                           climb toward anything
    frozen at birth        the manifest records the seed and the digests
                           BEFORE a target has run, so membership cannot
                           drift toward whatever turns out convenient
    never observed into    a holdout run is given no knowledge store, so no
                           mutator's tally can move because of it

The fourth is the one that would be easiest to lose silently, so it is
structural: `evaluate` here does not accept a knowledge store at all.

WHAT A HOLDOUT RESULT MEANS, AND DOES NOT

A holdout failure means the target fails on a case nobody built for it.
That is the closest thing to generalisation this laboratory can measure.

A holdout PASS does not mean the target is correct. The sample is small,
drawn from a space this laboratory defined, and a space nobody thought of is
a space the sampler cannot reach either. `docs/HOLDOUT.md` says so at
length, because a green holdout is exactly the number somebody will quote.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .genome import (AttackCategory, ClaimSpec, ClaimStyle, DocumentKind,
                     DocumentSpec, ProjectShape, RepositoryGenome, TestShape)

#: Bumped when the sampling procedure changes in a way that would produce a
#: different population from the same seed. A manifest records it, so a
#: holdout measured under one procedure is never silently compared with one
#: measured under another.
PROCEDURE = "swizzle.holdout.v1"

MANIFEST = "holdout/manifest.json"


def base() -> RepositoryGenome:
    """The world every holdout case starts from.

    Deliberately the plainest thing the genome space describes: an ordinary
    repository with an ordinary README and one live claim. Everything that
    makes a holdout case adversarial comes from the random walk, so the
    starting point contributes no opinion about what is interesting.
    """
    return RepositoryGenome(
        name="holdout_base",
        hypothesis=(
            "A randomly sampled world. It states no hypothesis of its own "
            "because nothing chose it: the point of a holdout case is that "
            "nobody decided it was worth building."),
        category=AttackCategory.CONTROL,
        seed=0,
        project=ProjectShape(package="app", modules=("core",),
                             functions_per_module=2),
        tests=TestShape(count=30),
        documents=(DocumentSpec("README.md", kind=DocumentKind.CURRENT_STATE,
                                title="Example",
                                prose=("A small project, kept small.",)),),
        claims=(ClaimSpec("README.md", ClaimStyle.LIVE_WHOLE_SUITE, 12),),
    )


@dataclass(frozen=True)
class Manifest:
    """What was sampled, from what, before anything ran against it."""

    procedure: str
    seed: int
    count: int
    #: name -> genome digest. The digest is what a contamination audit
    #: compares against, because a name can be reused and a digest cannot.
    members: Dict[str, str]

    def to_dict(self) -> Dict[str, object]:
        return {"procedure": self.procedure, "seed": self.seed,
                "count": self.count, "members": dict(sorted(self.members.items()))}

    @classmethod
    def from_dict(cls, raw) -> "Manifest":
        return cls(procedure=str(raw.get("procedure", "")),
                   seed=int(raw.get("seed", 0)), count=int(raw.get("count", 0)),
                   members={str(k): str(v)
                            for k, v in (raw.get("members") or {}).items()})


def sample(count: int = 12, seed: int = 1, *, steps: Tuple[int, int] = (1, 3)
           ) -> List[RepositoryGenome]:
    """A population drawn by a seeded random walk, with no feedback.

    `search.offspring` is reused for the walk because it already knows which
    mutations are legal against which genome, and reusing it means holdout
    cases are drawn from exactly the space the search explores rather than
    from a second space invented here. It is given no statistics, no
    knowledge and no uncovered-surface list, so every choice it makes is
    uniform: the machinery that makes the search adaptive is switched off,
    not worked around.

    Genomes that cannot be built are skipped. An unbuildable world is not a
    holdout case, and -- since `witness.py` -- a world whose ground truth
    cannot point at itself is unbuildable, so the sampler cannot produce the
    kind of case that would report this laboratory's own mistake as the
    target's.
    """
    from . import search, world
    from .draft import TargetDialect
    from .groundtruth import of as ground_truth_of

    rng = random.Random("%s:%d" % (PROCEDURE, seed))
    dialect = TargetDialect(name="sampling", count_block_open="<!--o-->",
                            count_block_close="<!--c-->",
                            writable_document_names=("readme.md",))
    out: List[RepositoryGenome] = []
    seen = set()
    attempts = 0
    while len(out) < count and attempts < count * 60:
        attempts += 1
        genome = base()
        for _ in range(rng.randint(*steps)):
            child = search.offspring(genome, rng, {}, None, "", ())
            if child is not None:
                genome = child
        genome = genome.evolved(
            name="holdout_%03d" % (len(out) + 1),
            hypothesis=base().hypothesis,
            notes="Sampled by %s seed %d. Nothing chose this case."
                  % (PROCEDURE, seed))
        digest = genome.digest()
        if digest in seen or not genome.mutations:
            continue
        try:
            ground_truth_of(world.build(genome, dialect))
        except Exception:
            continue                      # not a buildable world, so not a case
        seen.add(digest)
        out.append(genome)
    return out


class Holdout:
    """The frozen population, and the rule that nothing may adapt to it."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.path = self.root / MANIFEST
        self._manifest: Optional[Manifest] = None
        self._genomes: Dict[str, RepositoryGenome] = {}
        self._load()

    # ------------------------------------------------------------ freezing

    def freeze(self, genomes: Sequence[RepositoryGenome], seed: int) -> Manifest:
        """Write the population down before anything has run against it.

        Refuses to overwrite. A holdout that can be resampled after seeing a
        result is a holdout that will be, and the second sample will be the
        one that made the number look better.
        """
        if self._manifest is not None:
            raise ValueError(
                "%s already holds a frozen holdout (procedure %s, seed %d, %d "
                "cases). Resampling after results exist is how a holdout stops "
                "being one; delete it deliberately if that is what you mean."
                % (self.path, self._manifest.procedure, self._manifest.seed,
                   self._manifest.count))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        manifest = Manifest(procedure=PROCEDURE, seed=seed, count=len(genomes),
                            members={g.name: g.digest() for g in genomes})
        payload = {"manifest": manifest.to_dict(),
                   "genomes": [g.to_dict() for g in genomes]}
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
        self._manifest = manifest
        self._genomes = {g.name: g for g in genomes}
        return manifest

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self._manifest = Manifest.from_dict(raw.get("manifest") or {})
        self._genomes = {}
        for entry in raw.get("genomes") or []:
            try:
                genome = RepositoryGenome.from_dict(entry)
            except Exception:
                continue
            self._genomes[genome.name] = genome

    # ------------------------------------------------------------- reading

    @property
    def manifest(self) -> Optional[Manifest]:
        return self._manifest

    def genomes(self) -> List[RepositoryGenome]:
        return [self._genomes[name] for name in sorted(self._genomes)]

    def digests(self) -> frozenset:
        return frozenset((self._manifest.members if self._manifest else {}).values())

    def holds(self, genome: RepositoryGenome) -> bool:
        return genome.digest() in self.digests()

    def __bool__(self) -> bool:
        return bool(self._genomes)

    # -------------------------------------------------------- contamination

    def contamination(self) -> Tuple[str, ...]:
        """Every way discovery is visible to have reached the holdout.

        Checked by DIGEST rather than by name. A name can be reused, edited
        or coincidentally matched; the digest is what a genome actually is,
        and two cases with the same digest are the same experiment whatever
        they are called.

        Three leaks, in the order they are cheap to find:

          the same world in both        a holdout case that also sits in a
                                        bucket the search writes to has been
                                        adapted to, whatever its manifest says
          the manifest disagrees        a stored genome whose digest is not
                                        the one frozen for it. The population
                                        changed after it was frozen, which is
                                        the failure freezing exists to stop
          nothing frozen at all         no manifest, so every holdout number
                                        is a number about an unfrozen set

        This finds leaks that LEFT EVIDENCE. A result read by a human who
        then changed something leaves none, and no audit can see it. That is
        stated in `docs/HOLDOUT.md` rather than implied to be covered.
        """
        problems: List[str] = []
        if self._manifest is None:
            return ("no holdout has been frozen, so there is nothing to keep "
                    "uncontaminated and no holdout number is available",)

        for name, digest in sorted(self._manifest.members.items()):
            genome = self._genomes.get(name)
            if genome is None:
                problems.append("%s is in the manifest and not in the file" % name)
            elif genome.digest() != digest:
                problems.append(
                    "%s was frozen as %s and is now %s: the population changed "
                    "after it was frozen" % (name, digest[:12], genome.digest()[:12]))

        adapted = self.digests()
        for bucket in ("discovered", "minimized"):
            directory = self.root / bucket
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.json")):
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                digest = str(raw.get("genome_digest", ""))
                if digest and digest in adapted:
                    problems.append(
                        "%s holds %s, which is a holdout world: the search has "
                        "adapted to a case that exists to measure what it has "
                        "not adapted to" % (path, digest[:12]))
        return tuple(problems)


def evaluate(genomes, adapter, *, timeout: float = 900.0):
    """Run the holdout. No knowledge store, by signature.

    This function CANNOT be given one. A boolean argument that defaulted to
    "do not learn" would be a boolean somebody sets to True on a tired
    afternoon; leaving the parameter out means the only way to train on the
    holdout is to write a different function and notice you are doing it.
    """
    from . import attack
    return [attack.run(genome, adapter, timeout=timeout) for genome in genomes]


def render(manifest: Optional[Manifest], problems: Sequence[str],
           results=()) -> str:
    lines = ["SWIZZLE HOLDOUT", "=" * 66, ""]
    if manifest is None:
        lines.append("  nothing frozen. `swizzle holdout --freeze` draws a "
                     "population.")
    else:
        lines += ["  procedure       %s" % manifest.procedure,
                  "  seed            %d" % manifest.seed,
                  "  cases           %d" % manifest.count]
    lines.append("")
    if problems:
        lines.append("CONTAMINATION")
        for problem in problems:
            lines.append("  %s" % problem)
        lines.append("")
    elif manifest is not None:
        lines += ["  no contamination that leaves evidence. A result read by a "
                  "human who", "  then changed something leaves none, and no "
                  "audit here can see it.", ""]
    if results:
        failed = [r for r in results if r.fitness.interesting]
        lines += ["%-40s %s" % ("case", "result"), "-" * 66]
        for result in results:
            lines.append("%-40s %s" % (result.genome.name[:40],
                                       result.fitness.top.name.lower()))
        # WHAT THE SAMPLE COULD HAVE CAUGHT.
        #
        # "0 of 12 found something" is not a result on its own. A population
        # of worlds where nothing was ever forbidden would score the same and
        # mean nothing, and that is the number somebody will quote. So the
        # denominator's shape is printed beside it: how many of these cases
        # were in a position to catch a wrong rewrite, and how many to catch
        # a refusal that should not have happened.
        refusing = sum(1 for r in results
                       if any(not c.may_be_rewritten
                              for c in r.ground_truth.claims))
        permitting = sum(1 for r in results if r.ground_truth.permitted_edits)
        lines += ["",
                  "  %d of %d holdout case(s) found something."
                  % (len(failed), len(results)),
                  "  Of those %d: %d could have caught an unauthorised "
                  "rewrite, %d could" % (len(results), refusing, permitting),
                  "  have caught a refusal that was not warranted.",
                  "",
                  "  This is the closest thing to generalisation measurable "
                  "here. A PASS",
                  "  is not a clean bill: the sample is small, drawn from a "
                  "space this",
                  "  laboratory defined, and a space nobody thought of is one "
                  "the sampler",
                  "  cannot reach either. And these worlds are drawn from the "
                  "same mutator",
                  "  registry the search uses, so what is measured is "
                  "generalisation across",
                  "  WORLDS, not across kinds of attack nobody has written a "
                  "mutator for."]
    return "\n".join(lines) + "\n"
