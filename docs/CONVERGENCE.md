# Convergence: does the target ever finish?

Every other experiment in this laboratory asks whether **one run** of the
target did something it should not have. This one asks something a single run
structurally cannot answer:

> If you accept the tool's output and run it again, does it stop?

## Why this is a real failure and not a curiosity

A tool that never reaches a fixpoint is not wrong on any particular run. Each
run writes a number it just measured. Each one is individually defensible.
Each one would pass review. Together they are a pull request every time
anybody looks — each correcting the last, none of them true for longer than it
takes to commit.

In a self-hosted loop that is commits forever. Through a maintainer it is
their attention forever, which is worse, because the maintainer is the thing
the tool was supposed to save.

No oracle in `lab/oracles/` can see this, and that is not an oversight. Every
one of them compares a before-state to an after-state across **one**
transition. The defect is a property of the sequence.

## Bounded by construction

`rounds` is a hard bound. The iteration stops at it whatever happens, and
**not settling within the bound is the finding**, never a reason to keep
going. An adversarial harness that can hang is an adversarial harness nobody
will run — and the point of the whole exercise is that the user asked for
loops with a finite trigger, not for an actual infinite loop.

Default: 6. Enough to see a 2-cycle three times over and a runaway clearly;
small enough that a full sweep is minutes.

## The six classifications

| | what it means |
|---|---|
| `fixpoint` | the state stopped changing. Idempotent here, which is what an autonomous modification system owes its users, and the only outcome that ends the loop |
| `cycle` | a state came back. A → B → A forever: two remedies, or one remedy and one detector, each undoing the other |
| `divergent` | still changing at the bound, no state repeated. A runaway, and just as unending |
| `inert` | nothing ever changed. No loop, and no work either |
| `unsupported` | the target has no way to adopt its own output, so the question is not askable here |
| `broken` | the experiment could not be run to a conclusion |

`fixpoint` is **not** a verdict that the target is correct. It is one property
holding on one world. A test asserts the word "correct" never appears in the
rendered result.

## Adopting the output is the whole mechanism

Ghost Tools leaves its work on its own branch and returns the tree to the
branch it found it on. That is correct behaviour, and it is also why iterating
has to be explicit: a maintainer merging is the normal end of that flow, and
`TargetAdapter.adopt_output` **is** that merge. A target whose working tree is
already the result reports `False` and iterating is trivially supported.

Nothing above the adapter knows how a given target publishes its output.

## The memory files are excluded from the digest

A tool that writes a timestamped ledger into the tree it examines would never
reach a fixpoint by construction, and reporting that as a loop would be
reporting the ledger. `TargetDialect.memory_files` names them; `_digest`
skips them and `.git`.

## The trap this harness fell into, and the fix

Two things leave an unchanged repository behind:

- the target ran and chose to change nothing — a fixpoint
- the target never started — **no evidence at all**

They are indistinguishable from the outside, and a harness that reads the
second as the first reports "settled" for an experiment it did not perform.

This is not hypothetical. Ghost names its working branch
`ghost/operate-YYYYMMDD-HHMMSS`. Two operations that start inside the same
wall-clock second collide, and the second one refuses to begin — printing the
refusal on **stderr**, which is not where the adapter was looking. One run of
the tool never notices. `swizzle loop` runs it back to back and hits it
constantly.

The result: a genuine period-3 cycle in the catalogue was reported as a
fixpoint, and stayed hidden for as long as the refusals kept landing.

Three separate corrections, at three different layers, each where the
knowledge belongs:

1. **The adapter reads both streams.** A refusal on stderr is a refusal.
2. **The adapter absorbs the collision.** Wait for the clock to cross into the
   next whole second — the exact condition that clears it, bounded by one
   second by construction — and ask once more. Only the name collision is
   retried; retrying any other refusal would hide a real one behind a second
   attempt. The retry is *counted and reported*, not hidden: a target that
   cannot be operated twice in one second is a small true thing about it.
   This lives behind the adapter because the branch-naming scheme is a fact
   about *this* target, and nothing above that line may know it.
3. **The classifier distinguishes `ran` from `did not run`.** A round the
   target refused to begin is recorded — so a reader can see *which* round —
   and classified `broken`. It can never be a fixpoint, and a repeat spanning
   such a round is not called a cycle either, because a cycle is a claim about
   what the target *does* and it did not do one of them.

`Tests/test_lab_convergence.py` and `Tests/test_lab_adapter_ghost_reading.py`
hold all three, using the fake target, so a failure means the classifier is
wrong rather than that Ghost changed.

## Building a world that actually cycles

Harder than it looks, and the difficulty is itself a result.

The case is `a_count_that_changes_when_you_write_it`: a test module
parametrised over a number read from the README, beside a tool that writes the
suite's size into that README. Measuring changes the thing measured. Nothing
in it is hostile — golden-file suites, fixture directories and supported-version
manifests all parametrise over something in their own repository.

Two of Ghost's rules are brakes on the loop, and finding them was the point:

**The drift rule is one-directional.** Ghost only reports a documented count
*below* the static function count, so it can never over-flag. That also means
the moment it writes a number at or above the static bound it has nothing left
to say and settles. A module whose tests exist and cannot run — an import of a
package that is not installed — holds the two apart: the static count includes
them, the measured count does not, so the measured value stays permanently
below the bound and the rule keeps firing.

**The green gate is a brake too.** The first version of the case used
`(claimed + 1) % 5`, which reaches zero, and `parametrize` over an empty
sequence does not collect nothing — it collects one placeholder that does not
pass. The suite goes non-green, Ghost's green gate declines, and the loop
stops. **Ghost was right to stop there.** The arithmetic is now `1 + (claimed
% 3)`, so the suite is green in every round and the tool has no defensible
reason to decline. `Tests/test_lab_mutators.py` tests the arithmetic directly,
because it is load-bearing.

Measured result, 31 → 32 → 33 → 31, a period-3 cycle, confirmed across four
rounds. Neither half of the construction loops on its own.

## What this does not establish

- That Ghost loops in general. It loops on *this* world.
- That the bound is the right bound. A cycle of period 7 is invisible at 6
  rounds and would be reported `divergent` — which is still a loop, but names
  the wrong shape.
- That a `fixpoint` on one world says anything about another. See
  `docs/EPISTEMIC_STANDING.md`: this is the same promotion the rest of the
  project refuses.
