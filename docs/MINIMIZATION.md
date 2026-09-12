# Minimisation

## The question it answers

> What is the smallest world in which the target breaks its own invariant?

"A forty-file generated repository made the tool misbehave" is not a bug
report. The reader cannot tell which file matters, cannot tell whether it is
one defect or three interacting, and cannot tell whether a fix worked.

"A README with one sentence inside a marked block makes the tool delete the
sentence" is a bug report.

## On genomes, not directories

Every reduction changes the genome, then rebuilds and re-runs. Slower per step
than editing files in place, and the only version that stays correct: reducing
a materialised directory can produce a world no genome describes, which is
then unreproducible — and an unreproducible minimal case is worse than the
large one it replaced.

## Greedy to a fixpoint, not ddmin

ddmin's power is finding a minimal subset of *independent* deltas. These
deltas are not independent: removing a document invalidates the claims inside
it. Greedy-to-fixpoint over moves that each keep the genome valid is the
version that needs no repair step.

The cost is that the result is **locally** minimal rather than provably
minimal — every single reduction the minimiser knows how to make was tried,
and each one destroyed the failure. That is stated in the report rather than
implied away.

## The moves

Offered largest-effect-first, because dropping a mutation can make three other
reductions possible:

drop a mutation · drop filler modules · drop a document (and the claims and
blocks inside it) · strip a document's prose · drop a claim · drop a count
block · drop a module · one function per module · drop CI · halve the suite

The test count is halved rather than dropped: the target's drift thresholds
need the real suite some distance past the documented number, so zero is never
reachable and a binary walk finds the floor in a handful of steps.

## Preserving the attack

A reduction is kept only if the case still produces the same **failure classes
at the same top severity**.

Not the same signal count — a smaller world legitimately produces fewer
signals of the same kind, and requiring the count to match would reject every
real reduction. Not the same kinds either — dropping a document can move a
failure from `unauthorised_file_mutation` to `edit_outside_permitted_lines`
without changing what went wrong.

`Tests/test_lab_minimize.py` asserts that the minimal genome still produces
the original signature, that the load-bearing mutation is never removed, that
the scenery is, and that a case which never failed is refused rather than
"successfully" reduced to nothing.

## Budget

Each step runs the target over a repository: seconds, not microseconds.
`--budget` (default 60) caps the steps, and exhausting it is reported rather
than hidden — the result is then reduced, not locally minimal.

## A worked example

`prose_inside_the_maintained_block` against Ghost Tools 1.7.0:

```
  1   dropped   drop mutation put_prose_in_count_block
  2   kept      drop prose from README.md
  3   dropped   drop mutation put_prose_in_count_block
  4   kept      drop claim in README.md
  5   dropped   drop mutation put_prose_in_count_block
  6   dropped   drop count block in README.md
  7   dropped   halve the suite (30 -> 15)

minimised: 2 of 7 reductions held (size 15 -> 13, ratio 0.87)
```

Read it as a set of claims about the attack, each one now tested:

- the mutation is load-bearing (tried three times, destroyed the failure each
  time)
- the count block is load-bearing
- the README's introductory prose is **not** part of the attack
- neither is the live claim outside the block
- the suite size **is** load-bearing, because at 15 tests against 12
  documented the target's growth thresholds are not met and there is no
  finding to act on

The last line is the kind of thing minimisation is for. It says the attack
needs the documented count to be *substantially* stale, which is a fact about
the attack nobody wrote down in advance.
