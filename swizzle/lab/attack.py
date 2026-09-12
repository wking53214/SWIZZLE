"""One genome, end to end: build it, run the target at it, judge what happened.

THE ORDER OF OPERATIONS IS LOAD-BEARING

Two decisions here were made the hard way and both are about not destroying
the experiment while setting it up.

A case with a during-tests mutation gets NO separate read-only scan. The
mutation is carried out by the repository's own suite, and the target runs
that suite itself; a preliminary scan would fire the mutation early, so by
the time the target ran for real it would be diagnosing the new world and
there would be no staleness left to detect. For those cases the target is
invoked exactly once, the attribution question becomes unanswerable, and
the scope oracle is told so rather than guessing.

The "did the suite pass before" half of the semantic check is read from the
genome rather than measured. It is known by construction -- the test shape
says how many tests pass -- and measuring it would mean a third full test
run per case to learn something SWIZZLE decided itself.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from . import world
from .adapter import Observation, TargetAdapter, TargetUnavailable
from .evidence import Evidence, read_tree
from .fitness import Fitness, confirmed, corroboration, score
from .genome import Phase, RepositoryGenome
from .groundtruth import GroundTruth, of as ground_truth_of
from .oracles import judge_all
from .sandbox import Sandbox
from .signals import Judgement, Severity, Signal

#: Where the exported result state is put inside the sandbox.
RESULT_DIR = "result"


@dataclass(frozen=True)
class CaseResult:
    """Everything about one run, enough to report it and to reproduce it."""

    genome: RepositoryGenome
    ground_truth: GroundTruth
    evidence: Evidence
    signals: Tuple[Signal, ...]
    fitness: Fitness
    target_version: Mapping[str, str]
    seconds: float
    #: Set when the sandbox was kept, for a human to go and look.
    workspace: Optional[str] = None
    #: Set when the run itself failed. A failed run is never an attack.
    broken: str = ""

    @property
    def violations(self) -> Tuple[Signal, ...]:
        return tuple(s for s in self.signals if s.judgement is Judgement.VIOLATION)

    @property
    def inconclusive(self) -> Tuple[Signal, ...]:
        return tuple(s for s in self.signals if s.judgement is Judgement.INCONCLUSIVE)

    @property
    def kinds(self) -> Tuple[str, ...]:
        return tuple(sorted({s.kind for s in self.violations}))

    @property
    def corroborated(self) -> Tuple[str, ...]:
        """Failure kinds two or more independent oracles both saw."""
        return confirmed(self.signals, minimum_oracles=2)

    @property
    def signature(self) -> Tuple[str, ...]:
        """What makes this case THIS attack, for the minimiser and the corpus.

        The set of violated kinds plus the top severity. Deliberately not the
        signal count: a minimised case usually produces fewer signals of the
        same kind, and requiring the count to match would reject every
        successful reduction.
        """
        return tuple(sorted(self.kinds)) + (self.fitness.top.name,)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "genome": self.genome.to_dict(),
            "genome_digest": self.genome.digest(),
            "hypothesis": self.genome.hypothesis,
            "category": self.genome.category.value,
            "target": dict(self.target_version),
            "fitness": self.fitness.to_dict(),
            "top_severity": self.fitness.top.name,
            "signature": list(self.signature),
            "corroborated": list(self.corroborated),
            "corroboration": dict(corroboration(self.signals)),
            "signals": [s.to_dict() for s in self.signals],
            "ground_truth": self.ground_truth.to_dict(),
            "changed": self.evidence.changed(),
            "changed_working": self.evidence.changed(working=True),
            "target_claimed": list(self.evidence.act.claimed_changes) if self.evidence.act else [],
            "target_abstained": self.evidence.target_claims_abstention,
            "seconds": round(self.seconds, 2),
            "broken": self.broken,
            "workspace": self.workspace,
        }


def run(genome: RepositoryGenome, adapter: TargetAdapter, *,
        keep: bool = False, workspace: Optional[Path] = None,
        timeout: float = 900.0, rerun_suite: bool = True) -> CaseResult:
    """Build the world, run the target at it, and judge the result."""
    if not genome.hypothesis.strip():
        raise ValueError(
            "genome %r has no hypothesis. A case that does not say what it "
            "expects to go wrong cannot produce a finding, only a diff."
            % genome.name)

    started = time.perf_counter()
    dialect = adapter.dialect()
    draft = world.build(genome, dialect)
    truth = ground_truth_of(draft)
    sandbox = Sandbox(root=workspace, keep=keep or workspace is not None)

    scan: Optional[Observation] = None
    act: Optional[Observation] = None
    broken = ""
    try:
        root = world.materialise(draft, sandbox)
        before = read_tree(root)
        outside_before = _outside(sandbox)

        isolated = any(m.phase is Phase.DURING_TESTS for m in genome.mutations)
        if not isolated:
            scan = adapter.scan(root, sandbox, timeout=timeout)
            if scan.failed:
                broken = "the read-only scan failed: %s" % scan.failure

        if not broken:
            act = adapter.act(root, sandbox, timeout=timeout)
            if act.failed:
                broken = "the acting run failed: %s" % act.failure

        after_working = read_tree(root)
        result_source = "working_tree"
        after = after_working
        if act is not None and not broken:
            exported = adapter.export_output(root, sandbox, act, RESULT_DIR)
            if exported is not None:
                after = read_tree(exported)
                result_source = "output_ref"

        post_checks = _post_checks(draft, sandbox, root, after, result_source,
                                   rerun_suite and not broken)
        evidence = Evidence(
            genome=genome, ground_truth=truth, dialect=dialect,
            before=before, after=after, after_working=after_working,
            outside_before=outside_before, outside_after=_outside(sandbox),
            scan=scan, act=act, result_source=result_source, broken=broken,
            post_checks=post_checks)

        signals = () if broken else judge_all(evidence)
        return CaseResult(
            genome=genome, ground_truth=truth, evidence=evidence,
            signals=tuple(signals), fitness=score(signals),
            target_version=dict(adapter.version()),
            seconds=time.perf_counter() - started,
            workspace=str(sandbox.root) if sandbox.keep else None,
            broken=broken)
    finally:
        sandbox.dispose()


def _outside(sandbox: Sandbox) -> Dict[str, str]:
    """Hashes of everything staged outside the case repository."""
    snapshot = sandbox.snapshot("_outside")
    return {path[len("_outside/"):]: digest
            for path, digest in snapshot.items() if path.startswith("_outside/")}


def _post_checks(draft, sandbox: Sandbox, root: Path, after: Mapping[str, str],
                 result_source: str, rerun: bool) -> Dict[str, str]:
    """The checks an oracle needs but cannot run itself."""
    checks: Dict[str, str] = {
        "suite_before": "passed" if draft.genome.tests.green else "failed by construction",
        "result_source": result_source,
    }
    # The repository's git state afterwards. Cheap, and the only way to see
    # what an interrupted operation left behind: a target that opens a branch
    # and restores it in a cleanup path leaves the branch switched when the
    # cleanup never runs.
    branch = sandbox.run(("git", "branch", "--show-current"), cwd=root, timeout=60)
    checks["git_branch_after"] = branch.stdout.strip() or "(detached)"
    checks["git_branch_expected"] = draft.genome.git.branch
    status = sandbox.run(("git", "status", "--porcelain"), cwd=root, timeout=60)
    dirt = [line[3:] for line in status.stdout.splitlines()
            if line[3:] not in draft.dialect.memory_files]
    checks["git_dirty_after"] = ", ".join(sorted(dirt)) if dirt else ""
    if not rerun:
        checks["suite_after"] = "skipped: not requested"
        return checks
    where = root if result_source == "working_tree" else sandbox.root / RESULT_DIR
    if not (where / draft.genome.tests.directory).exists():
        checks["suite_after"] = "skipped: no test directory in the result state"
        return checks
    import sys
    done = sandbox.run((sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                        draft.genome.tests.directory),
                       cwd=where, timeout=300,
                       # SWIZZLE is the parent of this pytest. A case whose
                       # suite kills its parent must not kill the harness
                       # when the harness is the one running it.
                       env={"PYTHONDONTWRITEBYTECODE": "1",
                            "SWIZZLE_NO_KILL": "1"})
    if done.timed_out:
        checks["suite_after"] = "skipped: the suite timed out"
    elif done.returncode == 0:
        checks["suite_after"] = "passed"
    elif done.returncode == 5:
        checks["suite_after"] = "skipped: no tests collected"
    else:
        checks["suite_after"] = "exit %d\n%s" % (done.returncode,
                                                 done.stdout.strip()[-800:])
    return checks
