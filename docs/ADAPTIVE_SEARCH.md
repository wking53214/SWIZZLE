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
