# Adaptive search

## What is searched

The space of **genomes**, not the space of files. An offspring changes a typed
parameter or adds a mutation to a sequence, so every candidate is describable,
reproducible and minimisable by construction. A search over file bytes would
produce failures nobody can archive.

## The loop

```
seed genomes  ->  evaluate  ->  rank by dominance  ->  keep the elite
                                                            |
      re-evaluate <- new generation <- offspring <----------+
```

## What "adaptive" means here

The search keeps per-mutator statistics — how often adding this mutator to a
genome produced a case scoring higher than its parent — and biases selection
toward the ones that have been paying.

Each mutator's weight is `0.15 + hit_rate`. The floor matters: without it, a
mutator that missed on its first two genomes would never be tried again, and
the search would foreclose on an entire attack class in its first generation
on the strength of two samples.

## What is learned, and how it came to be known

Carrying a number forward is not the same as knowing something. Anything
this laboratory learns arrives one of three ways, and `swizzle knowledge`
shows which:

**Enhancement.** A structure exists and new evidence refines it. A mutator
offered against this revision has a real posterior: `improved / offered`.

**Connection.** Two things separately known turn out to be related. Recorded
as its own key (`a + b`) with a lift, *not* as a bigger number about either
member — neither member's tally can express "these two together beat
anything either has managed alone". Both open classes found this session
were that shape: `variant` connected two dimensions that were separately
unremarkable.

**Zero base.** Genuinely new, with no prior structure at all.

The third is the one a frequency table gets wrong. The first weighting here
gave a never-offered mutator a floor of `0.15` — a number invented and then
consumed as though it had been measured, which is the same unearned
promotion `docs/EPISTEMIC_STANDING.md` refuses about a fix, one layer down.

So **`Knowledge.weight()` returns `None` for a zero base.** Not a small
number: the absence of a measurement. A zero-base key is reached through a
reserved share of the budget (`EXPLORE_SHARE`) instead, which says plainly
that some effort is going on the unknown *because* it is unknown. That is an
experiment, not a bet, and it leaves the weights describing only what was
observed.

## Evidence is about a revision, not about a tool

A phase 3 result is evidence about a studied population. It is not a
post-market observation, and reporting it as one is how a claim acquires
standing it never earned.

Statistics gathered against one revision are the same kind of thing. When
the revision moves they become **inference about a substance that has
changed** — marked `CARRIED`, kept, and never merged into the new
revision's record.

Carried evidence is subordinate **structurally**, not by a discount. An
earlier version halved it, which put a perfect record from elsewhere level
with a coin flip measured here — a judgement disguised as arithmetic, in the
module whose subject is judgements disguised as arithmetic. It is now
lexicographic, the same idiom `fitness.py` uses for severity: anything
observed against this revision is chosen ahead of anything carried, however
good the carried record looks, and the rule cannot be tuned into saying
otherwise.

This matters right now rather than in principle. The seam that paid best
this session was writability; the writability bugs are closed. A table that
silently reported pre-fix evidence as describing the thing in front of you
would send the next run mining a seam that no longer exists.

## What it is deliberately not

Not machine learning. A learned model of a target's weak points would need far
more evaluations than a run can afford — each evaluation runs the target over
a repository, which is seconds, not microseconds — and it would be the least
trustworthy component in a framework whose selling point is that its
judgements can be checked.

A good search beats a fake AI adversary, and says so.

## Selection

By `Fitness.key()`, which compares lexicographically. A parent that found a
CRITICAL is never displaced by one that found six LOWs.

Elitism keeps the best few unchanged between generations, because an
adversarial search that can lose its best case to drift will.

## Novelty

Genomes are cached by digest. Re-running an identical world teaches nothing
and costs a full target invocation; without the cache a population converges
on one good genome and spends the rest of its budget re-proving it.

## What is tracked

`swizzle evolve --json` reports: evaluations, generations, distinct genomes,
the evaluation index at which each failure class was **first seen**,
rediscovered seed cases, and per-mutator offered/improved/critical/hit-rate.

Time-to-discovery is measured in evaluations rather than seconds, because
evaluations are the scarce resource and seconds depend on the machine.

## A run

`swizzle evolve --budget 18 --seed 42 --population 5`, against Ghost Tools
1.7.0, 15 evaluations in 23 seconds:

```
failure classes, and the evaluation each was first seen at:
  unauthorised_mutation      1
  unattributable_change      2
  stale_action               4
  escape                     5
rediscovered seed cases: prose_inside_the_maintained_block,
                         block_in_a_document_about_a_moment
```

Two things worth reading off it.

**All four failure classes appeared within five evaluations.** The seeds are
placed on known boundaries, so this is not a surprise — it is a check that the
search is exploring rather than sitting on its parents.

**The best offspring outscored every hand-written seed** (`critical 2, high 2`
against the seed's `critical 1, high 1`). The search composed mutations into
worlds that fail harder than anything in the catalogue, which is the entire
argument for having a search rather than a longer catalogue.

## Reproducibility

`--seed` fixes the search RNG. The same seed, budget and population against
the same target revision explores the same genomes in the same order. Each
discovered genome is independently reproducible from its own digest,
regardless of how the search arrived at it.
