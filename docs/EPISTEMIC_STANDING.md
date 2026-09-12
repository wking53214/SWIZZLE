# Epistemic standing

What a resolved finding is entitled to claim, and what it is not.

## The sentence

> "I didn't say she stole my money."

Seven words, seven meanings, one text. Which word carries the stress decides
which of seven different things was said:

| stress | reading |
|---|---|
| **I** | someone else said it |
| **didn't** | the statement was never made |
| **say** | it may have been written, hinted, or implied |
| **she** | a different person |
| **stole** | acquired some other way |
| **my** | someone else's money |
| **money** | something else of mine |

A system that records only the text has recorded none of them.

## The same sentence, here

The moment an attack stops reproducing, this laboratory can say:

> "This case no longer reproduces against this revision under these oracles
> in this world."

Flat, it sounds like `fixed`. Stressed anywhere, it names something that was
not established:

| stress | what is not established | probe |
|---|---|---|
| **THIS** case | a variant may still reproduce; the case is not the class | `variant` |
| this **CASE** | the case is the *observable*, not the defect | `concealment` |
| **NO LONGER** | at this moment; it reproduced before | `recurrence` |
| **REPRODUCES** | the oracles saw nothing, bounded by what they can see | `concealment` |
| **THIS** revision | one commit, and no statement about any other | `recurrence` |
| **THESE** oracles | an inconclusive oracle declined to say, it did not agree | `concealment` |
| **THIS** world | the minimised genome; a larger world may differ | `scope` |

And an eighth, stressing a word that is not in the sentence at all — the
*surface* the case is one of several on. A fix can be correct and local.
That one is `adjacency`.

## SOURCE, INTERPRETATION, CLAIM

Three things, kept apart, because collapsing them is the failure:

**SOURCE** — what was literally observed. A revision, a date, a genome
digest, a set of oracles, a verdict. Nothing inferred.

**INTERPRETATION** — what a reader takes that to mean.

**CLAIM** — what the system records and carries forward.

An observation that silently becomes a claim has acquired **authority,
provenance, certainty and historical status it never earned**. `fixed` is
exactly that promotion: one run's silence, wearing the clothes of a settled
fact, for as long as anyone reads the corpus.

So nothing in `swizzle/lab/standing.py` ever emits the word as an assertion.
The strongest thing available is:

> the current structure supports the conclusion that this has been resolved

and it is printed next to a list of everything that does not establish.

## The standings

| standing | means |
|---|---|
| `reproduces` | the attack works, here, now |
| `unreproduced, unprobed` | it did not reproduce and nothing else was asked. **The honest default after a fix** |
| `current structure supports resolved` | every probe was asked and none overturned it. The ceiling |
| `unreproduced, but a probe defeated it` | a probe found what its emphasis warned about |
| `ambiguous` | an oracle declined to say, or the run broke |
| `recurred` | unreproduced at an earlier revision, reproduces again |
| `never reproduced` | no evidence it ever worked |

`Standing.settles_anything` returns `False` for every member. The method
exists so the answer is written down once rather than assumed differently in
five places.

**Ambiguous is a result.** A system that picks a reading the evidence does
not justify has failed, even when it picks the flattering one. Especially
then.

**"Never reproduced" is not "resolved."** Without a record of the case
working, a fix and a case that never worked are the same observation, and
calling the second one resolved is the same promotion pointed the other way.

## The probes are runnable

A framework that only *labels* a conclusion provisional has done nothing —
it has written "probably" in front of the same claim and carried on. Each
emphasis is a question the tool asks:

```
swizzle standing prose_inside_the_maintained_block --budget 5
```

```
concealment   did the oracle that SAW this failure run again, or is its
              silence the silence of something not looking
recurrence    re-run at the revision in front of you
scope         re-run the world as it was BEFORE minimisation stripped it
adjacency     re-run the sibling cases on the same surface
variant       mutate the genome and re-run, looking for a near neighbour
```

Each returns *defeated*, *held*, or **neither**. Three states, not two: "not
asked" and "asked, nothing found" are different, and collapsing them is how a
corpus fills up with conclusions nobody reached.

## Two lessons from the first real run

Both were the module committing the failure it exists to refuse. They are
recorded here rather than quietly fixed, because a framework about unearned
claims that hides its own is worth nothing.

**An oracle that ran and found nothing is not an oracle that did not look.**
The first `observe()` recorded the oracles that *emitted a signal*, so an
oracle with nothing to say was indistinguishable from an absent one — and
concealment duly reported a clean fix as concealed. Fixed twice over: the
observation now records the oracles that *executed*, and the expectation
oracle now emits a positive `protected_text_survived` rather than staying
silent when the sentence it guards is intact.

**A variant reproducing something lesser is not a defeat.** The first
`variant` probe treated any finding as overturning the resolution, and
reported "the fix closed this case and not the class" — about a CRITICAL —
on the strength of a variant that produced a LOW over-caution. A different
and lesser failure is a case to file, not a defeat of this one. It now
compares failure classes and severity against the failure the resolution is
about.

**And a probe that raised is not a probe that held.** A generated variant
composed two mutators that contradicted each other and took the sweep down
mid-run. Whatever a broken probe does, it must not come back saying it
looked: turning a crash into evidence of a fix is the single worst thing
this module could do.

## What this changes about the corpus

A bucket says where a file lives. A standing says what the evidence
supports, and the two are allowed to disagree. An entry with no resolution
recorded reads `never interrogated` rather than inheriting a status from its
folder.

This is also the answer to "does SWIZZLE learn from its attacks". The useful
thing to carry forward is not *"writability is fixed"* — it is *"the
structure currently supports that conclusion, here is what would overturn
it, and here is which of those has actually been asked."* The unasked list
is the search's best seed: it names, per case, exactly which question has
never been put.
