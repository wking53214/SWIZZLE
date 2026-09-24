"""The laboratory's half of the command line.

Kept separate from `swizzle/cli.py` so the original four commands keep
working exactly as they did. `swizzle list`, `prove`, `run` and `summon`
are the first version of this project and still do what they always did;
everything here is additional.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence

from . import (catalogue, convergence, coverage, metrics, minimize, probes,
               reporting, search)
from . import standing as standing_model
from .adapter import TargetUnavailable
from .adapters import GhostToolsAdapter
from .attack import run as run_case
from .corpus import Corpus, PromotionRefused
from .differential import compare
from .genome import AttackCategory, RepositoryGenome
from .mutators import registry
from .sandbox import Sandbox, purge

DEFAULT_CORPUS = Path("corpus")


def add_parsers(sub) -> None:
    """Register the laboratory commands on an existing subparser set."""
    audit = sub.add_parser("audit", help="check the laboratory can run, and "
                                         "print what it currently attacks")
    audit.add_argument("--ghost-tools", type=Path, default=None, metavar="PATH")

    seed = sub.add_parser("seed", help="the seed catalogue, with hypotheses")
    seed.add_argument("--only", default="", metavar="SUBSTRING")
    seed.add_argument("--full", action="store_true",
                      help="print each hypothesis in full")

    muts = sub.add_parser("mutators", help="the deterministic mutation registry")
    muts.add_argument("--only", default="", metavar="SUBSTRING")

    attack = sub.add_parser("attack", help="build cases, run the target, judge")
    attack.add_argument("--case", default="", metavar="NAME",
                        help="one seed case by name")
    attack.add_argument("--category", default="", metavar="CATEGORY",
                        help="every seed case in a category")
    attack.add_argument("--seed", type=int, default=None, metavar="N",
                        help="override the genome seed, for reproducibility runs")
    attack.add_argument("--from-corpus", default="", metavar="BUCKET",
                        help="run archived cases instead of the seed catalogue")
    attack.add_argument("--minimize", action="store_true",
                        help="minimise every case that finds something")
    attack.add_argument("--corpus", action="store_true",
                        help="archive results (attacks to discovered, clean "
                             "cases to rejected)")
    attack.add_argument("--corpus-path", type=Path, default=DEFAULT_CORPUS)
    attack.add_argument("--report", action="store_true",
                        help="print the full report for every case that fails")
    attack.add_argument("--json", action="store_true")
    attack.add_argument("--keep", action="store_true",
                        help="leave each sandbox on disk and print where")
    attack.add_argument("--ghost-tools", type=Path, default=None, metavar="PATH")
    attack.add_argument("--timeout", type=float, default=900.0, metavar="SECONDS")

    evolve = sub.add_parser("evolve", help="adaptive search for new cases")
    evolve.add_argument("--budget", type=int, default=30, metavar="N",
                        help="target invocations to spend (default 30)")
    evolve.add_argument("--population", type=int, default=6, metavar="N")
    evolve.add_argument("--seed", type=int, default=0, metavar="N")
    evolve.add_argument("--from", dest="start", default="", metavar="SUBSTRING",
                        help="seed the population from these catalogue cases")
    evolve.add_argument("--from-corpus", default="", metavar="BUCKET",
                        help="seed the population from archived cases instead "
                             "of the catalogue (minimized, regression, "
                             "discovered, rejected, or `all`)")
    evolve.add_argument("--corpus", action="store_true")
    evolve.add_argument("--corpus-path", type=Path, default=DEFAULT_CORPUS)
    evolve.add_argument("--json", action="store_true")
    evolve.add_argument("--ghost-tools", type=Path, default=None, metavar="PATH")
    evolve.add_argument("--no-knowledge", action="store_true",
                        help="do not read or write the persistent knowledge "
                             "file; every key starts at a zero base")

    minimise = sub.add_parser("minimize", help="reduce a case to the smallest "
                                               "world that still fails")
    minimise.add_argument("case")
    minimise.add_argument("--budget", type=int, default=minimize.DEFAULT_BUDGET)
    minimise.add_argument("--corpus", action="store_true")
    minimise.add_argument("--corpus-path", type=Path, default=DEFAULT_CORPUS)
    minimise.add_argument("--json", action="store_true")
    minimise.add_argument("--ghost-tools", type=Path, default=None, metavar="PATH")

    reproduce = sub.add_parser("reproduce", help="rebuild and re-run one case "
                                                 "from its genome")
    reproduce.add_argument("case")
    reproduce.add_argument("--corpus-path", type=Path, default=DEFAULT_CORPUS)
    reproduce.add_argument("--keep", type=Path, default=None, metavar="DIR",
                           help="materialise the world here and leave it")
    reproduce.add_argument("--build-only", action="store_true",
                           help="write the world and stop, without running "
                                "the target")
    reproduce.add_argument("--json", action="store_true")
    reproduce.add_argument("--ghost-tools", type=Path, default=None, metavar="PATH")

    corpus_cmd = sub.add_parser("corpus", help="the attack memory")
    corpus_cmd.add_argument("--bucket", default="", metavar="NAME")
    corpus_cmd.add_argument("--corpus-path", type=Path, default=DEFAULT_CORPUS)
    corpus_cmd.add_argument("--promote", default="", metavar="CASE")
    corpus_cmd.add_argument("--force", action="store_true",
                            help="promote a case only one oracle saw")
    corpus_cmd.add_argument("--reason", default="", metavar="TEXT")
    corpus_cmd.add_argument("--json", action="store_true")

    diff = sub.add_parser("diff", help="compare two revisions of the target")
    diff.add_argument("--ghost", action="append", default=[], metavar="PATH_OR_REV",
                      help="give twice: baseline then candidate")
    diff.add_argument("--bucket", default="regression", metavar="NAME",
                      help="which archived cases to run (default regression)")
    diff.add_argument("--seeds", action="store_true",
                      help="use the seed catalogue instead of the corpus")
    diff.add_argument("--corpus-path", type=Path, default=DEFAULT_CORPUS)
    diff.add_argument("--json", action="store_true")
    diff.add_argument("--fail-on-unmeasured", action="store_true",
                      help="exit 1 when a case could not be measured on either "
                           "side (for a CI gate: a target that cannot be run "
                           "must not pass as unchanged)")

    report = sub.add_parser("report", help="scorecard and coverage")
    report.add_argument("--from-json", type=Path, default=None, metavar="FILE",
                        help="read a machine report instead of running anything")
    report.add_argument("--bucket", default="", metavar="NAME",
                        help="run archived cases from this bucket")
    report.add_argument("--corpus-path", type=Path, default=DEFAULT_CORPUS)
    report.add_argument("--json", action="store_true")
    report.add_argument("--ghost-tools", type=Path, default=None, metavar="PATH")

    standing = sub.add_parser(
        "standing",
        help="what the evidence currently supports about a case, and what it "
             "does not establish")
    standing.add_argument("case", nargs="?", default="",
                          help="one case; omit for every archived case")
    standing.add_argument("--probe", action="append", default=[], metavar="NAME",
                          help="ask only these (concealment, recurrence, scope, "
                               "adjacency, variant); repeatable")
    standing.add_argument("--budget", type=int, default=6, metavar="N",
                          help="variants to build and run (default 6)")
    standing.add_argument("--corpus-path", type=Path, default=DEFAULT_CORPUS)
    standing.add_argument("--record", action="store_true",
                          help="write the resolution back into the corpus entry")
    standing.add_argument("--json", action="store_true")
    standing.add_argument("--ghost-tools", type=Path, default=None, metavar="PATH")
    standing.add_argument("--timeout", type=float, default=900.0, metavar="SECONDS")

    hold = sub.add_parser(
        "holdout",
        help="cases nothing has adapted to: freeze, audit, or measure against")
    hold.add_argument("--freeze", action="store_true",
                      help="draw a population and write it down, once")
    hold.add_argument("--count", type=int, default=12, metavar="N")
    hold.add_argument("--seed", type=int, default=1, metavar="N")
    hold.add_argument("--run", action="store_true",
                      help="measure the frozen population against the target")
    hold.add_argument("--corpus-path", type=Path, default=DEFAULT_CORPUS)
    hold.add_argument("--json", action="store_true")
    hold.add_argument("--ghost-tools", type=Path, default=None, metavar="PATH")
    hold.add_argument("--timeout", type=float, default=900.0, metavar="SECONDS")

    hist = sub.add_parser(
        "history",
        help="what has happened to each case across revisions of the target")
    hist.add_argument("case", nargs="?", default="",
                      help="one case; omit for all")
    hist.add_argument("--returned", action="store_true",
                      help="only cases that went quiet and came back")
    hist.add_argument("--corpus-path", type=Path, default=DEFAULT_CORPUS)
    hist.add_argument("--json", action="store_true")

    know = sub.add_parser(
        "knowledge",
        help="what the laboratory has learned, and how it came to know it")
    know.add_argument("--corpus-path", type=Path, default=DEFAULT_CORPUS)
    know.add_argument("--json", action="store_true")
    know.add_argument("--ghost-tools", type=Path, default=None, metavar="PATH")

    loop = sub.add_parser(
        "loop",
        help="run the target, adopt its output, run again: does it settle?")
    loop.add_argument("case", nargs="?", default="",
                      help="one case; omit for every catalogue case")
    loop.add_argument("--rounds", type=int, default=convergence.DEFAULT_ROUNDS,
                      metavar="N",
                      help="the bound. Not settling within it is the finding, "
                           "never a reason to keep going (default %d)"
                           % convergence.DEFAULT_ROUNDS)
    loop.add_argument("--corpus-path", type=Path, default=DEFAULT_CORPUS)
    loop.add_argument("--json", action="store_true")
    loop.add_argument("--ghost-tools", type=Path, default=None, metavar="PATH")
    loop.add_argument("--timeout", type=float, default=900.0, metavar="SECONDS")

    tidy = sub.add_parser("sandboxes", help="list or delete stray sandboxes")
    tidy.add_argument("--purge", action="store_true")


HANDLERS = {}


def handle(command: str, args) -> int:
    return HANDLERS[command](args)


def _register(name):
    def wrap(fn):
        HANDLERS[name] = fn
        return fn
    return wrap


def _adapter(args) -> GhostToolsAdapter:
    return GhostToolsAdapter(getattr(args, "ghost_tools", None))


def _genomes(args) -> List[RepositoryGenome]:
    if getattr(args, "from_corpus", ""):
        return Corpus(args.corpus_path).genomes(args.from_corpus)
    if getattr(args, "case", ""):
        return [catalogue.get(args.case)]
    if getattr(args, "category", ""):
        return [g for g in catalogue.CATALOGUE if g.category.value == args.category]
    return list(catalogue.CATALOGUE)


# ------------------------------------------------------------------- audit

@_register("audit")
def _audit(args) -> int:
    print("SWIZZLE SELF-CHECK")
    print("=" * 66)
    ok = True
    if shutil.which("git"):
        print("  git                   found")
    else:
        print("  git                   MISSING -- a case is a repository")
        ok = False
    try:
        adapter = _adapter(args)
        version = adapter.version()
        print("  target                %s %s at %s"
              % (version["target"], version["package_version"],
                 version["commit"][:10]))
        if version.get("commit_dirty") == "yes":
            print("                        (checkout has uncommitted changes; "
                  "results are not attributable to that commit)")
    except TargetUnavailable as exc:
        print("  target                MISSING -- %s" % exc)
        ok = False
    with Sandbox() as box:
        box.write("probe/a.txt", "x")
        try:
            box.resolve("../escape.txt")
            print("  sandbox               BROKEN: accepted a path outside itself")
            ok = False
        except Exception:
            print("  sandbox               refuses paths outside itself")
    print("  mutators              %d registered" % len(registry()))
    print("  seed cases            %d" % len(catalogue.CATALOGUE))
    print("  oracles               %d independent" % len(_oracle_names()))
    print()
    print(coverage.render(coverage.matrix()))
    print("Documentation: docs/ARCHITECTURE.md, docs/ADVERSARIAL_CONTRACT.md,")
    print("docs/THREAT_MODEL.md, docs/ORACLES.md, docs/FITNESS.md.")
    return 0 if ok else 2


def _oracle_names():
    from .oracles import ORACLES
    return list(ORACLES)


# -------------------------------------------------------------------- seed

@_register("seed")
def _seed(args) -> int:
    for genome in catalogue.select(args.only):
        print("%-40s %-12s seed=%-4d %d mutation(s)"
              % (genome.name, genome.category.value, genome.seed,
                 len(genome.mutations)))
        if args.full:
            import textwrap
            print(textwrap.fill(genome.hypothesis, width=74,
                                initial_indent="    ", subsequent_indent="    "))
            print()
    return 0


@_register("mutators")
def _mutators(args) -> int:
    for name, mutator in sorted(registry().items()):
        if args.only and args.only not in name and args.only not in mutator.category.value:
            continue
        print("%-32s v%d  %-13s %s"
              % (name, mutator.version, mutator.category.value, mutator.phase.value))
        import textwrap
        print(textwrap.fill(mutator.summary, width=74,
                            initial_indent="    ", subsequent_indent="    "))
        if mutator.params:
            print("    params: " + ", ".join("%s (%s)" % kv
                                             for kv in sorted(mutator.params.items())))
        print()
    return 0


# ------------------------------------------------------------------ attack

@_register("attack")
def _attack(args) -> int:
    try:
        adapter = _adapter(args)
    except TargetUnavailable as exc:
        print("swizzle: %s" % exc, file=sys.stderr)
        return 2

    genomes = _genomes(args)
    if args.seed is not None:
        genomes = [g.evolved(seed=args.seed) for g in genomes]
    if not genomes:
        print("swizzle: no cases selected", file=sys.stderr)
        return 2

    store = Corpus(args.corpus_path) if args.corpus else None
    results, minimisations = [], {}
    for genome in genomes:
        result = run_case(genome, adapter, keep=args.keep, timeout=args.timeout)
        results.append(result)
        if not args.json:
            print(reporting.summary_table([result]).splitlines()[-1])
        if result.fitness.interesting and args.minimize:
            reduction = minimize.minimise(genome, adapter, baseline=result)
            minimisations[genome.name] = reduction
            if not args.json:
                print("    minimised: %d of %d reductions held, size ratio %.2f"
                      % (reduction.steps_kept, reduction.steps_tried, reduction.ratio))
        if store is not None:
            bucket = "discovered" if result.fitness.interesting else "rejected"
            entry = store.record(result, bucket,
                                 minimisation=minimisations.get(genome.name))
            if minimisations.get(genome.name):
                store.record(
                    result.__class__(**{**result.__dict__,
                                        "genome": minimisations[genome.name].minimal}),
                    "minimized", minimisation=minimisations[genome.name])
            if not args.json:
                print("    archived: %s" % entry.path)

    card = metrics.scorecard(results, list(minimisations.values()))
    if args.json:
        print(reporting.machine_report(results, minimisations, card))
        return 0

    print()
    if args.report:
        for result in results:
            if result.fitness.interesting or result.broken:
                print(reporting.attack_report(result, minimisations.get(result.genome.name)))
    print(metrics.render(card))
    return 0


# ------------------------------------------------------------------ evolve

def _seed_population(args) -> List[RepositoryGenome]:
    """Where a search starts.

    From the corpus when asked, because the catalogue is twelve worlds a
    human wrote and the corpus is every world that has been found to matter
    since -- already minimised, already known productive, and already the
    end point of the last run. Starting from the catalogue every time makes
    each search re-walk ground the previous one covered.

    Preference order within `all` is the same order the corpus uses for
    reading an entry back: a minimised case is a better seed than the large
    one it came from, and a rejected case is still a seed, because a world
    the target handled is a world one mutation from one it might not.
    """
    if not args.from_corpus:
        return list(catalogue.select(args.start))

    store = Corpus(args.corpus_path)
    buckets = (("minimized", "regression", "discovered", "rejected")
               if args.from_corpus == "all" else (args.from_corpus,))
    seeds: List[RepositoryGenome] = []
    seen = set()
    for bucket in buckets:
        for genome in store.genomes(bucket):
            if genome.digest() in seen:
                continue
            if args.start and args.start not in genome.name:
                continue
            seen.add(genome.digest())
            seeds.append(genome)
    return seeds


@_register("evolve")
def _evolve(args) -> int:
    try:
        adapter = _adapter(args)
    except TargetUnavailable as exc:
        print("swizzle: %s" % exc, file=sys.stderr)
        return 2
    seeds = _seed_population(args)
    if not seeds:
        print("swizzle: no seed cases matched", file=sys.stderr)
        return 2

    def announce(result, index):
        if args.json:
            return
        mark = result.fitness.top.name if result.fitness.interesting else "pass"
        print("  %3d  %-40s %-9s %s" % (index, result.genome.name[:40], mark,
                                        result.fitness.render()))

    if not args.json:
        print("evolving from %d seed(s) (%s), budget %d evaluation(s)"
              % (len(seeds),
                 "corpus/%s" % args.from_corpus if args.from_corpus
                 else "the catalogue", args.budget))
    store = None
    if not args.no_knowledge:
        from .knowledge import Store
        store = Store(args.corpus_path / "knowledge.json")
    report = search.evolve(seeds, adapter, budget=args.budget,
                           population=args.population, seed=args.seed,
                           knowledge=store, on_case=announce)
    if args.corpus:
        store = Corpus(args.corpus_path)
        for result in report.best:
            store.record(result, "discovered", note="found by search")

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return 0

    print()
    print("%d evaluation(s) over %d generation(s) in %.0fs"
          % (report.evaluations, report.generations, report.seconds))
    print("failure classes, and the evaluation each was first seen at:")
    for name, index in sorted(report.first_seen.items(), key=lambda kv: kv[1]):
        print("  %-26s %d" % (name, index))
    if report.rediscovered:
        print("rediscovered seed cases: %s" % ", ".join(report.rediscovered))
    if report.connections:
        print()
        print("connections found -- a pairing that beat every one of its "
              "members' best:")
        for pair in report.connections:
            print("  %s" % pair)
    if report.surfaces_opened:
        print()
        print("surfaces opened -- nothing had ever landed on these before "
              "this run:")
        for surface in report.surfaces_opened:
            print("  %s" % surface)
    if report.surfaces_still_empty:
        print()
        print("still never exercised: %s"
              % ", ".join(report.surfaces_still_empty))
        print("An empty row is the one thing a pass rate cannot tell you.")
    print()
    print("mutator      offered  improved  critical  hit rate")
    for name, stats in sorted(report.stats.items()):
        if stats.offered:
            print("  %-30s %3d      %3d       %3d      %.2f"
                  % (name, stats.offered, stats.improved, stats.critical,
                     stats.hit_rate))
    print()
    print(reporting.summary_table(report.best))
    return 0


# ---------------------------------------------------------------- minimize

@_register("minimize")
def _minimize(args) -> int:
    try:
        adapter = _adapter(args)
    except TargetUnavailable as exc:
        print("swizzle: %s" % exc, file=sys.stderr)
        return 2
    genome = _find_genome(args.case, args.corpus_path)
    if genome is None:
        print("swizzle: no case called %r in the catalogue or the corpus"
              % args.case, file=sys.stderr)
        return 2

    def step(label, held, index):
        if not args.json:
            print("  %-3d %-9s %s" % (index, "kept" if held else "dropped", label))

    reduction = minimize.minimise(genome, adapter, budget=args.budget, on_step=step)
    if args.corpus and reduction.result is not None:
        Corpus(args.corpus_path).record(reduction.result, "minimized",
                                        minimisation=reduction)
    if args.json:
        print(json.dumps(reduction.to_dict(), indent=2, sort_keys=True))
        return 0
    print()
    print("minimised %s: %d of %d reductions held (size %d -> %d, ratio %.2f)"
          % (genome.name, reduction.steps_kept, reduction.steps_tried,
             minimize._size(reduction.original), minimize._size(reduction.minimal),
             reduction.ratio))
    if reduction.exhausted:
        print("the budget ran out before the fixpoint; the result is reduced, "
              "not locally minimal")
    for removed in reduction.removed:
        print("  removed: %s" % removed)
    if reduction.result is not None:
        print()
        print(reporting.attack_report(reduction.result, reduction))
    return 0


# --------------------------------------------------------------- reproduce

@_register("reproduce")
def _reproduce(args) -> int:
    genome = _find_genome(args.case, args.corpus_path)
    if genome is None:
        print("swizzle: no case called %r" % args.case, file=sys.stderr)
        return 2

    if args.build_only:
        from . import world
        from .draft import TargetDialect
        try:
            dialect = _adapter(args).dialect()
        except TargetUnavailable:
            dialect = TargetDialect("generic", "<!-- count -->", "<!-- /count -->")
        draft = world.build(genome, dialect)
        destination = args.keep or Path(tempfile.mkdtemp(prefix="swizzle-case-"))
        box = Sandbox(root=destination, keep=True)
        root = world.materialise(draft, box)
        print(root)
        return 0

    try:
        adapter = _adapter(args)
    except TargetUnavailable as exc:
        print("swizzle: %s" % exc, file=sys.stderr)
        return 2
    result = run_case(genome, adapter, keep=args.keep is not None,
                      workspace=args.keep)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0
    print(reporting.attack_report(result))
    return 0 if not result.broken else 2


# ------------------------------------------------------------------ corpus

@_register("corpus")
def _corpus(args) -> int:
    store = Corpus(args.corpus_path)
    if args.promote:
        try:
            entry = store.promote(args.promote, force=args.force, reason=args.reason)
        except (KeyError, PromotionRefused) as exc:
            print("swizzle: %s" % exc, file=sys.stderr)
            return 2
        print("promoted %s to regression: %s" % (entry.name, entry.path))
        return 0

    entries = store.entries(args.bucket)
    if args.json:
        print(json.dumps([{"bucket": e.bucket, "name": e.name,
                           "severity": e.severity,
                           "corroborated": list(e.corroborated),
                           "path": str(e.path)} for e in entries],
                         indent=2, sort_keys=True))
        return 0
    if not entries:
        print("the corpus is empty%s." % (" in %s" % args.bucket if args.bucket else ""))
        return 0
    for entry in entries:
        print("%-12s %-38s %-9s %s"
              % (entry.bucket, entry.name[:38], entry.severity,
                 ", ".join(entry.corroborated) or "single oracle"))
    print()
    print("%d entr(ies). Promote with: swizzle corpus --promote NAME" % len(entries))
    return 0


# -------------------------------------------------------------------- diff

@_register("diff")
def _diff(args) -> int:
    if len(args.ghost) != 2:
        print("swizzle: give --ghost twice, baseline first", file=sys.stderr)
        return 2
    scratch: List[Path] = []
    try:
        baseline = _adapter_for(args.ghost[0], scratch)
        candidate = _adapter_for(args.ghost[1], scratch)
    except (TargetUnavailable, RuntimeError) as exc:
        print("swizzle: %s" % exc, file=sys.stderr)
        return 2
    genomes = (list(catalogue.CATALOGUE) if args.seeds
               else Corpus(args.corpus_path).genomes(args.bucket))
    if not genomes:
        print("swizzle: nothing to run. Pass --seeds, or archive some cases "
              "first.", file=sys.stderr)
        return 2
    try:
        result = compare(genomes, baseline, candidate)
    finally:
        for path in scratch:
            shutil.rmtree(path, ignore_errors=True)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0
    print(result.render())
    counts = result.counts()
    if counts.get("regressed") or counts.get("worsened"):
        return 1
    return 1 if args.fail_on_unmeasured and counts.get("not_measured") else 0


def _adapter_for(what: str, scratch: List[Path]) -> GhostToolsAdapter:
    """A target adapter for a checkout path or a git revision of one."""
    path = Path(what)
    if (path / "ghost_buster" / "cli.py").is_file():
        return GhostToolsAdapter(path)
    base = GhostToolsAdapter().checkout
    destination = Path(tempfile.mkdtemp(prefix="swizzle-ghost-"))
    scratch.append(destination)
    done = subprocess.run(("git", "worktree", "add", "--quiet", "--detach",
                           str(destination / "ghost_tools"), what),
                          cwd=str(base), capture_output=True, text=True, timeout=300)
    if done.returncode != 0:
        raise RuntimeError("%r is neither a checkout nor a revision of %s: %s"
                           % (what, base, done.stderr.strip()))
    return GhostToolsAdapter(destination / "ghost_tools")


# ------------------------------------------------------------------ report

@_register("report")
def _report(args) -> int:
    if args.from_json is not None:
        payload = json.loads(args.from_json.read_text(encoding="utf-8"))
        card = payload.get("scorecard")
        if card:
            print(metrics.render(card))
        print(coverage.render(coverage.matrix()))
        return 0
    try:
        adapter = _adapter(args)
    except TargetUnavailable as exc:
        print("swizzle: %s" % exc, file=sys.stderr)
        return 2
    genomes = (Corpus(args.corpus_path).genomes(args.bucket) if args.bucket
               else list(catalogue.CATALOGUE))
    results = [run_case(g, adapter) for g in genomes]
    card = metrics.scorecard(results)
    if args.json:
        print(reporting.machine_report(results, {}, card))
        return 0
    print(reporting.summary_table(results))
    print()
    print(metrics.render(card))
    print(coverage.render(coverage.matrix(results)))
    return 0


@_register("standing")
def _standing(args) -> int:
    try:
        adapter = _adapter(args)
    except TargetUnavailable as exc:
        print("swizzle: %s" % exc, file=sys.stderr)
        return 2

    store = Corpus(args.corpus_path)
    ledger = None
    if args.record:
        from .history import History
        ledger = History(args.corpus_path / "standings.json")
    revision = str(dict(adapter.version()).get("commit", ""))
    if args.case:
        entries = [e for e in store.entries() if e.name == args.case]
        if not entries:
            genome = _find_genome(args.case, args.corpus_path)
            if genome is None:
                print("swizzle: no case called %r" % args.case, file=sys.stderr)
                return 2
            entries = [None]
            targets = [(args.case, genome, None, None, None)]
        else:
            targets = [(e.name, e.genome, e.original_genome, e.observation, e)
                       for e in _newest(entries)]
    else:
        targets = [(e.name, e.genome, e.original_genome, e.observation, e)
                   for e in _newest(store.entries())]

    if ledger is not None:
        for _, _, _, before, entry in targets:
            _seed_ledger(ledger, entry, before)

    payload, defeated = [], 0
    for name, genome, original, before, entry in targets:
        siblings = [g for g in catalogue.CATALOGUE
                    if g.category is genome.category and g.name != genome.name]
        context = probes.ProbeContext(
            genome=genome, adapter=adapter, original=original,
            siblings=siblings,
            when_it_reproduced=before if before and before.reproduced else None,
            resolved_classes=tuple(before.classes) if before else (),
            resolved_severity=before.top_severity if before else "NONE",
            budget=args.budget, timeout=args.timeout, seed=genome.seed)
        observed, results = probes.interrogate(context, only=args.probe)
        resolution = standing_model.Resolution(
            observation=observed, probes=results,
            previously_reproduced=before if before and before.reproduced else None)
        if resolution.defeated_by:
            defeated += 1
        payload.append(resolution)
        if args.record:
            entry = store.get(name)
            if entry is not None:
                record = dict(entry.record)
                record["resolution"] = resolution.to_dict()
                record["standing"] = resolution.standing.value
                entry.path.write_text(
                    json.dumps(record, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
            # The entry holds the LATEST resolution; the ledger holds every
            # one of them. Overwriting is what makes a regression invisible,
            # so the append happens whether or not the case is in the corpus.
            if ledger is not None:
                ledger.record(resolution, revision, digest=genome.digest())
        if not args.json:
            print(resolution.render())

    if args.json:
        print(json.dumps([r.to_dict() for r in payload], indent=2, sort_keys=True))
        return 0

    if ledger is not None:
        ledger.save()
    print("=" * 66)
    for resolution in payload:
        line = "  %-40s %s" % (resolution.observation.case,
                               resolution.standing.value)
        if ledger is not None:
            arc = ledger.of(resolution.observation.case).arc
            line += "   [%s]" % arc.value
        print(line)
    print()
    if ledger is not None:
        came_back = ledger.returned()
        if came_back:
            print("%d case(s) went quiet and came back. `swizzle history "
                  "--returned`." % len(came_back))
            print()
    print("Nothing above is `fixed`. The strongest standing available is that "
          "the")
    print("current structure supports the conclusion, and it is defeasible by "
          "every")
    print("probe listed beside it.")
    return 1 if defeated else 0


def _seed_ledger(ledger, entry, before) -> None:
    """Put the corpus entry's own archival episode into the ledger first.

    The entry records what the case did at the revision it was archived
    against, which for most cases is the ONLY episode that exists. Starting
    the ledger empty would mean no case could show an arc until it had been
    interrogated twice more -- not caution, just discarding evidence already
    in hand. Skipped when the ledger already has that revision, so repeated
    runs do not stack duplicates of one archival fact.
    """
    from .history import Episode
    if entry is None or before is None:
        return
    revision = str((entry.record.get("target") or {}).get("commit", ""))
    if not revision or ledger.knows(entry.name, revision):
        return
    ledger.note(Episode(
        case=entry.name, revision=revision,
        standing=(standing_model.Standing.REPRODUCES.value if before.reproduced
                  else standing_model.Standing.NEVER_REPRODUCED.value),
        at=str(entry.record.get("recorded_at", "")),
        classes=tuple(before.classes), severity=before.top_severity,
        digest=str(entry.record.get("genome_digest", ""))))


def _newest(entries):
    """One entry per case, preferring the most interrogated bucket."""
    order = {"regression": 0, "minimized": 1, "discovered": 2, "rejected": 3}
    best = {}
    for entry in entries:
        current = best.get(entry.name)
        if current is None or order.get(entry.bucket, 9) < order.get(current.bucket, 9):
            best[entry.name] = entry
    return [best[name] for name in sorted(best)]


@_register("holdout")
def _holdout(args) -> int:
    from .holdout import Holdout, render, sample
    held = Holdout(args.corpus_path)

    if args.freeze:
        try:
            manifest = held.freeze(sample(args.count, args.seed), args.seed)
        except ValueError as exc:
            print("swizzle: %s" % exc, file=sys.stderr)
            return 2
        print("froze %d case(s) under %s, seed %d"
              % (manifest.count, manifest.procedure, manifest.seed))
        print("Nothing has adapted to these. Nothing may.")
        return 0

    problems = held.contamination()
    results = []
    if args.run and held:
        try:
            adapter = _adapter(args)
        except TargetUnavailable as exc:
            print("swizzle: %s" % exc, file=sys.stderr)
            return 2
        from .holdout import evaluate
        results = evaluate(held.genomes(), adapter, timeout=args.timeout)

    if args.json:
        print(json.dumps({
            "manifest": held.manifest.to_dict() if held.manifest else None,
            "contamination": list(problems),
            "results": [r.to_dict() for r in results]},
            indent=2, sort_keys=True))
        return 1 if problems else 0

    print(render(held.manifest, problems, results))
    if problems:
        return 2
    return 1 if any(r.fitness.interesting for r in results) else 0


@_register("history")
def _history(args) -> int:
    from .history import History, render
    ledger = History(args.corpus_path / "standings.json")
    if args.returned:
        histories = ledger.returned()
    elif args.case:
        histories = [ledger.of(args.case)]
    else:
        histories = ledger.all()
    if args.json:
        print(json.dumps([h.to_dict() for h in histories],
                         indent=2, sort_keys=True))
        return 0
    if not histories:
        print("No standing has been recorded yet. `swizzle standing --record` "
              "writes them.")
        return 0
    print(render(histories))
    return 1 if any(h.arc.wants_attention for h in histories) else 0


@_register("knowledge")
def _knowledge(args) -> int:
    from .knowledge import Store, render
    from .mutators import registry
    revision = ""
    try:
        revision = str(dict(_adapter(args).version()).get("commit", ""))
    except TargetUnavailable:
        pass
    store = Store(args.corpus_path / "knowledge.json")
    rows = store.table(revision, registry())
    if args.json:
        print(json.dumps({"revision": revision,
                          "knowledge": [r.to_dict() for r in rows]},
                         indent=2, sort_keys=True))
        return 0
    print(render(rows, revision))
    return 0


@_register("loop")
def _loop(args) -> int:
    try:
        adapter = _adapter(args)
    except TargetUnavailable as exc:
        print("swizzle: %s" % exc, file=sys.stderr)
        return 2
    if args.case:
        genome = _find_genome(args.case, args.corpus_path)
        if genome is None:
            print("swizzle: no case called %r" % args.case, file=sys.stderr)
            return 2
        genomes = [genome]
    else:
        genomes = list(catalogue.CATALOGUE)

    results, looping = [], 0
    for genome in genomes:
        result = convergence.iterate(genome, adapter, rounds=args.rounds,
                                     timeout=args.timeout)
        results.append(result)
        looping += int(result.settling.is_a_loop)
        if not args.json:
            print(result.render())

    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2, sort_keys=True))
        return 1 if looping else 0

    print("=" * 66)
    for result in results:
        print("  %-40s %s" % (result.genome.name[:40], result.settling.value))
    print()
    print("A tool that never reaches a fixpoint is not wrong on any single "
          "run. It is")
    print("a pull request every time anyone looks, each one correcting the "
          "last.")
    return 1 if looping else 0


@_register("sandboxes")
def _sandboxes(args) -> int:
    if args.purge:
        removed = list(purge())
        for path in removed:
            print("removed %s" % path)
        print("%d sandbox(es) removed." % len(removed))
        return 0
    found = sorted(Path(tempfile.gettempdir()).glob(Sandbox.PREFIX + "*"))
    for path in found:
        print(path)
    print("%d sandbox(es). Remove them with --purge." % len(found))
    return 0


def _find_genome(name: str, corpus_path: Path) -> Optional[RepositoryGenome]:
    """A case by name: the seed catalogue first, then the corpus.

    The catalogue is asked by membership rather than by catching its KeyError.
    An `except KeyError: pass` here would also swallow a KeyError raised from
    somewhere deeper inside the lookup, and reported it as "no such case" --
    which is the defect this project's own catalogue is built to report in
    other people's code.
    """
    known = catalogue.by_name()
    if name in known:
        return known[name]
    entry = Corpus(corpus_path).get(name)
    return entry.genome if entry is not None else None
