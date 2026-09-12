# Identity and memory: the two surfaces nothing had tested

Both rows of the coverage matrix sat at zero from the first version of this
laboratory to the fifth, and they sat at zero for a structural reason: every
oracle here compares the tree before a run with the tree after it, and
**neither of these failures moves a byte.**

## What a tool with a memory promises

Two things, every run:

    the same defect keeps the same identity
    an absence means the defect is gone

Break the first in one direction and a committed baseline goes inert: every
finding reads as new, which looks exactly like a repository nobody has
triaged. Break it in the other and two different defects share one identity,
so accepting one into a baseline silently suppresses the other. Break the
second and the history reports a recovery nobody performed.

None of it is visible in a diff. All of it is visible to a human six months
later, as a triage queue that never shrinks or a defect everybody thought was
closed.

## The phase that makes the question askable

`Phase.AFTER_BASELINE`. A baseline, a ledger, a set of accepted finding ids:
none of them exist until the tool has seen the repository once. A mutation
applied at build time is a change to a world the tool has no history of, so
every interesting question is unaskable.

    materialise -> prime (the target runs, and records)
                -> apply the deferred edits, and COMMIT them
                -> the target runs again, and is judged

Mutators still only *declare* their edits at build time, so a genome is still
a complete description of a case and the minimiser can still reason about it.
A mutator that reached out and touched the disk would not survive
serialisation.

`TargetAdapter.prime_baseline` returns None for a target that keeps nothing
between runs, and the case then says the question was never asked rather than
pretending it ran and passed.

Two things had to be got right for the cases to run at all, and both were
found by running them:

**The deferred edits are committed.** Left uncommitted they are a dirty
working tree, and a target that refuses to operate on one refuses correctly,
before the question has been put to it. Reading that as a finding would be
reporting a target for having a guard that works. It is also what actually
happens: a renamed module arrives as a commit.

**The commit takes the case's paths and nothing else.** `git add -A` also
sweeps up the memory file the priming run just wrote, which makes it a
*tracked* file, which changes the target's dirty-tree behaviour. Every
identity case would then quietly also have been a case about committing the
tool's ledger. That is a real case; it is not this one.

## The oracle, and what it refuses to say

`lab/oracles/identity.py` compares the target's account of a repository with
its account of the same repository a moment later, against a ground-truth
statement about what actually changed in between. The authority is the
mutator's declaration, never the target's opinion.

Two lost-and-gained findings are **the same defect re-identified** when they
share a detector and either the same file, or the file ground truth says the
old one was moved to. That is not an explanation of where the old finding
went. It *is* the old finding.

What it will not say: that an absence is a false recovery when the target
reported something genuinely new. A tool that stops being able to examine the
suite and *says so* has done the right thing, in wording nobody can
anticipate. So a lost finding beside an unrelated new one is INCONCLUSIVE and
a human reads which. Claiming otherwise would make the oracle grade English.

## Measured against ghost_tools 1.7.2

| case | result |
|---|---|
| `the_same_defect_at_a_new_address` | **HIGH + MEDIUM** |
| `an_identity_that_counts_something` | **HIGH + MEDIUM** |
| `two_projects_one_portable_name` | pass (correct behaviour) |
| `an_absence_that_is_not_a_fix` | **CRITICAL**, since fixed |
| `a_history_of_somebody_elses_repository` | a defect in the target, found before the case could run |
| `memory_rewritten_by_the_suite_it_runs` | pass |

### One defect, two levers

Ghost's finding identity is `sha256(detector | portable path | summary)`.
Both of the last two are mutable while the defect is not.

*The path moves.* A module renamed byte for byte produces one finding that
vanished and one that is brand new. Measured.

*The summary moves.* Three findings were re-identified by adding three tests
to the suite, with the documented claim untouched at 12 in every one of them:

    no_ci_configuration            "1 test file(s)"   -> "2 test file(s)"
    doc_count_contradicted_by_run  "collects 30"      -> "collects 33"
    doc_test_count_drift           "at least 30"      -> "at least 33"

A user who accepts any of these into a baseline has accepted it until the
next commit that changes a count. For these detectors the baseline is
permanently inert.

There is no purely content-derived identity that is both stable under a
rename and distinct across files, so this is not a one-line fix. It is two
separate pieces of work, and `docs/THREAT_MODEL.md` records them as open.

### The control that passed

`two_projects_one_portable_name` builds a monorepo: two packages, each with
its own `pyproject.toml`, each containing `helpers.py` defining
`unused_helper`. A tool that cuts a path at the nearest project marker would
cut both to `src/helpers.py` and give two different defects one identity.

Ghost checks `.git` before `pyproject.toml`, so the repository root wins and
the two stay distinct. The attack is well founded and the tool holds. Worth
recording: a checkout with no `.git` (a tarball, a vendored copy) falls
through to the packaging marker, where the collision is live.

### A defect found before its case could run

`a_history_of_somebody_elses_repository` came back BROKEN, naming Ghost's own
ledger as a dirty path. Chasing that produced a defect needing no harness at
all: **a repository that commits `.ghost_ledger.json` can never be operated
on.** The workup writes the ledger, that dirties the tracked file, and the
tool's own dirty-tree guard refuses. Every time, forever. The tool's own
documentation recommends committing the record.

Reproduced in one command from a clean checkout, and fixed in ghost_tools
1.7.3: the distinction was never tracked versus untracked, it is whose edit
it is.
