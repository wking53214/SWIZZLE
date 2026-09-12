# Cases nothing has adapted to

## Why this is not optional

Every number this laboratory reports is measured on cases somebody chose. The
search adapts to what pays. Fixes get made against what was found.

After enough rounds, "the catalogue passes" can mean the target got better, or
it can mean the catalogue got easier. **The catalogue cannot tell you which.**

A holdout can: cases drawn from the same space, run against the same target,
that nothing has ever adapted to.

## The existing catalogue cannot be split into one

Retroactively declaring some of the twenty-six seed cases "holdout" would be a
fiction. Every one has been looked at, and Ghost has been fixed in response to
most of them — the evidence is in this repository's own history. A partition
drawn now would be drawn with the answers already known, which is selection
bias wearing a holdout's clothes.

So **the whole catalogue is discovery, by history.** The holdout is generated:
genomes sampled from the same space by a seeded random walk with no fitness
feedback of any kind, frozen into a manifest before any target runs.

## What makes them independent

| property | how |
|---|---|
| nothing chose them | a random walk, so not chosen for being hard, easy or interesting |
| no feedback | the walk never reads a result, so it cannot climb toward anything |
| frozen at birth | the manifest records procedure, seed and digests before any run |
| never learned from | `holdout.evaluate` takes no knowledge store |

The last one is structural rather than a convention. A boolean argument
defaulting to "do not learn" is a boolean somebody sets to `True` on a tired
afternoon. The parameter is simply absent, so the only way to train on the
holdout is to write a different function and notice you are doing it.

## Freezing refuses to be redone

A holdout that can be resampled after a result exists is a holdout that will
be, and the second sample is the one that made the number look better.
`freeze` raises rather than overwriting.

## The contamination audit, and what it cannot see

Checked by **digest**, never by name. A name can be reused, edited or
coincidentally matched; the digest is what a genome actually is.

Three leaks it finds:

- a holdout world also sitting in `discovered/` or `minimized/` — the search
  has adapted to a case that exists to measure what it has not adapted to;
- a stored genome whose digest is not the one frozen for it — the population
  changed after freezing, which is the failure freezing exists to prevent;
- nothing frozen at all, so every holdout number is about an unfrozen set.

**What it cannot see:** a result read by a human who then changed something.
That leaves no evidence and no audit can find it. Stated here rather than
implied to be covered, because the only thing worse than that leak is
believing it is closed.

## The search refuses a holdout seed

`evolve(..., holdout=held)` raises `HoldoutContaminated` rather than filtering.
A caller handing the search a holdout case has misunderstood what it is for,
and silently dropping it would let them keep believing the run measured
generalisation.

## First measurement: Ghost 1.7.4

    12 cases, procedure swizzle.holdout.v1, seed 1
    0 of 12 found something

That number is worthless without the shape of its denominator, so the report
prints both:

    6 of 12 could have caught an unauthorised rewrite
    4 of 12 could have caught a refusal that was not warranted

The sample includes a scope escape, prose inside a maintained block, a
mid-run kill, three dated claims, and two compositions. These are worlds where
a failure was possible and did not happen.

## What a pass does not mean

**Not a clean bill.** Twelve cases is a small sample, drawn from a space this
laboratory defined, and a space nobody thought of is one the sampler cannot
reach either.

And these worlds come from the same mutator registry the search uses. What is
measured is generalisation **across worlds**, not across kinds of attack
nobody has written a mutator for. Closing that gap needs mutators nobody wrote
by looking at Ghost, which is a different and harder problem than this file
solves.

## What a failure would mean

The target fails on a case nobody built for it. That is the closest thing to
generalisation this laboratory can measure, and it is the number worth
watching as Ghost's defences accumulate: a defence that only holds on the
cases that produced it is a defence that memorised its corpus.
