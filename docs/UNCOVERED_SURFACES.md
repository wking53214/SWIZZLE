# Aiming at what has never been tested

## The problem with learning only from what paid

The search weights mutators by how often they have produced a case that beat
its parent. That is correct as far as it goes, and on its own it is
rich-get-richer.

It concentrates the search exactly where it has already succeeded — which is
where new information is least likely to be. A search that has found four
writability bugs will keep finding writability bugs, and the `identity` and
`baseline` rows of the coverage matrix will sit at zero forever. The empty row
is the one thing that table can tell you which a pass rate cannot, and a search
that never aims at it guarantees the row stays empty.

## A reserved share, not a weight

`UNCOVERED_SHARE = 0.25` of mutator choices go to a mutator that can reach a
**surface of the target** no case in this run has landed on.

Reserved, not weighted, and the difference is the same one `knowledge.py`
makes for a zero base. A floor on a weight invents a number and then consumes
the result as evidence. A reserved share says plainly that part of the budget
is being spent on the unknown *because* it is unknown — an experiment, not a
bet — and leaves the weights describing only what was measured.

A surface with no cases has no measurement. It is not a surface that scored
badly.

## The order is a claim

Three grounds, taken in order:

1. the target has a mechanism nothing has ever attacked
2. this mutator has never been offered against this revision
3. the evidence says it pays

Ignorance about the **subject** is taken ahead of ignorance about the
**instrument**. Never having tested a mechanism of the target is the more
expensive thing to keep, because it is a gap in what is known about the thing
under test rather than about the tool being used on it.

That ordering is asserted in `Tests/test_lab_uncovered_bias.py` rather than
left as a comment.

## Recomputed every generation

A surface stops being uncovered the moment a case lands on it, and continuing
to aim there would be spending the reserved share on something no longer
unknown.

## What gets reported

`surfaces_opened` — surfaces that had zero cases when the search started and
had at least one when it finished. `surfaces_still_empty` — the honest other
half.

Deliberately *not* a counter of how often the search chose on uncovered
grounds. That would be a report about this module's own policy, which is not a
result. What surfaces actually opened is.
