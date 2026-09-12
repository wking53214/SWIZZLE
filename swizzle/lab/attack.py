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

        # THE PRIMING RUN, AND WHY `before` MOVED.
        #
        # A case that attacks the target's memory needs the target to HAVE a
        # memory, so it runs once first, on the world as built, and whatever
        # it records is part of what it carries into the run being judged.
        #
        # The before-snapshot is therefore taken after priming and after the
        # deferred edits. The world the target is judged against is the one
        # it is actually handed, and taking the snapshot earlier would put
        # SWIZZLE's own edits into the diff and attribute them to the target
        # -- the same mistake `self_edits` exists to undo for during-tests
        # mutations, which is why it is avoided here rather than repaired.
        primed: Optional[Observation] = None
        priming_note = ""
        if any(m.phase is Phase.AFTER_BASELINE for m in genome.mutations):
            primed = adapter.prime_baseline(root, sandbox, timeout=timeout)
            if primed is None:
                priming_note = (
                    "the target keeps nothing between runs, so its memory "
                    "cannot be attacked here")
            elif primed.failed:
                broken = "the priming run failed: %s" % primed.failure
            else:
                _apply_after_baseline(draft, root, sandbox)

        before = read_tree(root)
        outside_before = _outside(sandbox)

        isolated = any(m.phase is Phase.DURING_TESTS for m in genome.mutations)
        if not isolated and not broken:
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
            post_checks=post_checks, primed=primed)

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


def _apply_after_baseline(draft, root: Path, sandbox: Sandbox) -> None:
    """Carry out the deferred edits on the materialised tree, and commit them.

    Declared at build time, applied here, so the genome is still a complete
    description of the case and the minimiser can still reason about it.

    THE COMMIT IS PART OF THE CASE, NOT HOUSEKEEPING.

    Left uncommitted, these edits are a dirty working tree, and a tool that
    refuses to operate on one refuses -- correctly -- before the question the
    case is asking has been put to it. Measured: the first run of the
    identity cases came back BROKEN for exactly that reason, and reading
    that as a finding would have been reporting a target for a guard working.

    It is also what actually happens. A renamed module, three new tests, a
    suite that stopped collecting: these arrive in a repository as commits,
    which is precisely why the tool's memory of the previous commit is the
    thing under test.
    """
    if not draft.after_baseline:
        return
    for path, text in draft.after_baseline:
        target = root / path
        if text is None:
            if target.exists() or target.is_symlink():
                target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    # Exactly the case's own paths, and nothing else.
    #
    # `git add -A` also sweeps up the memory file the priming run just wrote.
    # That makes it a TRACKED file, so every later write to it shows as a
    # dirty path, and a target that tolerates its own untracked notes but
    # refuses a dirty tracked tree then refuses to operate -- before the
    # question this case is asking has been put to it. Measured: the first
    # run of these cases came back BROKEN naming the target's own ledger.
    #
    # Committing a tool's memory file is a real thing people do, and a real
    # case could be built on it. It is not this case, and letting it in by
    # accident would mean every identity case was quietly also that one.
    for path, text in draft.after_baseline:
        if text is None:
            sandbox.run(("git", "rm", "-q", "--ignore-unmatch", "--", path),
                        cwd=root, timeout=120)
        else:
            sandbox.run(("git", "add", "--", path), cwd=root, timeout=120)
    sandbox.run(("git", "commit", "-q", "-m",
                 "the change the tool has no memory of"), cwd=root, timeout=120)


def _outside(sandbox: Sandbox) -> Dict[str, str]:
    """Hashes of everything staged outside the case repository."""
    snapshot = sandbox.snapshot("_outside")
    return {path[len("_outside/"):]: digest
            for path, digest in snapshot.items() if path.startswith("_outside/")}


def _post_checks(draft, sandbox: Sandbox, root: Path, after: Mapping[str, str],
                 result_source: str, rerun: bool) -> Dict[str, str]:
    """The checks an oracle needs but cannot run itself."""
    # A world built with tests that cannot run did not have a passing suite
    # before the target arrived, whatever the test shape says about the main
    # file. Reading `TestShape.green` alone reported the target for breaking
    # a suite SWIZZLE had broken on purpose.
    green_before = draft.genome.tests.green and "uncollectable_tests" not in draft.facts
    checks: Dict[str, str] = {
        "suite_before": "passed" if green_before
                        else "failed by construction: %s"
                             % (draft.facts.get("how_the_subject_was_broken")
                                or "the test shape is not green"),
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
