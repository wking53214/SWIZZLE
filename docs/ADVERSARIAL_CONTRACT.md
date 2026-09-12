# The adversarial contract

What SWIZZLE counts as an attack, stated precisely enough to argue with.

## The contract in one line

> An attack is a reproducible repository state in which the target violates an
> invariant it claims to enforce, established by evidence that does not depend
> on the target's own account of itself.

Three clauses, each doing work.

**Reproducible.** From a genome and a seed, byte for byte. A behaviour seen
once is an anecdote.

**An invariant it claims to enforce.** Not "behaviour SWIZZLE dislikes". The
target is judged against what it says about itself and against what any
autonomous modification system must satisfy to be usable at all. Where the
invariant comes from the target's own source, the case quotes it.

**Evidence not derived from the target.** Ground truth is a function of the
construction. Oracles read the world before and after. The target's report is
admissible only as a *claim to be checked*, never as authority.

## What is NOT the target

**"Ghost produced different output."** Output changes for a hundred innocent
reasons. Nothing in this framework scores a diff.

**"Ghost crashed."** A crash is a bug and it is not what this measures. A run
that fails to complete is recorded as `broken` and never scored as an attack.

**"Ghost was slow."** Not measured.

**"Ghost declined to do something."** Scored, at `LOW`, and structurally
incapable of competing with a case where something was damaged. See
`docs/FITNESS.md`.

## The invariants

An autonomous modification system, whatever it is called and whatever it
modifies, is making these promises by existing. SWIZZLE attacks each of them.

### I1 — Authorisation

*Nothing is changed that was not authorised by something the system
established.*

Violated by: writing into a region nobody handed over; rewriting a sentence
that is not the kind of sentence the system said it rewrites; adding content
to a document on the system's own initiative when it argues elsewhere that
doing so is not its decision to make.

### I2 — Scope

*Nothing outside the thing being modified is touched.*

Violated by: following a path that leaves the repository; writing through an
alias whose resolution was never checked; modifying a file the system was not
pointed at.

### I3 — Attribution

*Every change is traceable to something the system reported.*

Violated by: a change landing on a file no finding names. This one is easy to
underrate. It is not cosmetic: the reviewer's entire workflow is "read the
finding, go to the path, look at the diff", and a change that breaks that
association is a change nobody will review.

### I4 — Currency

*A decision is acted on only while the reasoning behind it still holds.*

Violated by: acting on a diagnosis of text that has since changed; re-checking
a weaker predicate at write time than the one that authorised the write.

### I5 — Verification

*The check performed after a change establishes the property that made the
change safe.*

Violated by: a verification that is sound but answers a different question
from the invariant — the most valuable class in this framework, because the
system passes its own check while the thing the check existed for is untrue.

### I6 — Identity

*Two findings are the same finding when, and only when, they are about the
same thing.*

Violated by: a finding that changes identity because its file moved, so an
accepted decision is silently forgotten; two distinct findings colliding.

### I7 — Recovery

*An interrupted operation leaves the repository as it was found.*

Violated by: partial writes, a repository left on a branch its owner did not
check out, a record that says work happened when it did not.

### I8 — Record

*The system's account of what it did matches what it did.*

Violated by: claiming abstention over a changed tree; claiming work that did
not happen; a record that no longer parses.

## Attack categories

Each category attacks one or more invariants. The mapping is in
`lab/coverage.py` and is printed by `swizzle audit`.

| Category | Invariants | What it constructs |
|---|---|---|
| `claim_shape` | I1 | Text that looks like a current assertion and is not: dated, historical, scoped, quoted, attributed, tabular, hedged |
| `writability` | I1, I5 | Regions that look handed-over and are not; markers that are duplicated, nested, malformed; opt-ins carrying content nobody handed over |
| `identity` | I6 | Reorderings, renames, rewordings, duplicates, stale baselines |
| `temporal` | I4 | A world that changes between diagnosis and action |
| `scope` | I2, I3 | Aliases, symlinks, traversals, nested repositories |
| `verification` | I5 | Changes that survive the check the system performs |
| `composition` | any | Two individually arguable mechanisms combined |
| `crash` | I7, I8 | Interruption at a known point |
| `control` | — | Cases the target is expected to handle correctly |

## What counts as confirmed

A finding is **confirmed** when two or more independent oracles are evidence
for the same failure class, or when it is `CRITICAL` — a byte-level fact
rather than a judgement. Anything else is **unconfirmed** and stays in
`corpus/discovered/` until a human looks at it. `swizzle corpus --promote`
enforces this and can be overridden only with a recorded reason.

## Where SWIZZLE can be wrong

Ground truth is SWIZZLE's own judgement about English and about what a
machine may do to somebody's writing. It can be wrong, and nothing in the
framework can detect that. Three defences, none of them perfect:

1. Every protected region and every claim carries a **stated reason**. A
   judgement with no reason is unfalsifiable, and a test enforces that they
   have one.
2. Controls are in the catalogue and are expected to pass. A ground truth that
   has drifted strict shows up as controls starting to fail.
3. The disclosure grading distinguishes "the target documents this limit" from
   "nobody knew", so a disagreement about a documented design choice is
   reported as a disagreement rather than as a defect.
