# A refusal must point at the world

## The circle

    mutator says     "this claim must not be rewritten, it is a changelog"
    ground truth     records the declaration
    oracle           checks the target against ground truth
    verdict          CRITICAL

Every link holds. And the chain can consistently validate a wrong
interpretation, because the mutator was the only authority on its own
semantics and nothing downstream was in a position to disagree.

This is not theoretical. Measured in one search: **eight CRITICALs**, each
corroborated by two independent oracles, on worlds where
`DocumentKind.CHANGELOG` rendered a file indistinguishable from an ordinary
README. Ground truth refused the rewrite because "a changelog entry is about
the past by definition." Nothing in the file said it was a changelog. The
target rewrote a live claim in a file named `README.md`, which is correct,
and was reported for destroying protected text.

**Corroboration does not help when both oracles read the same wrong premise.**
Independence of oracles is not independence of assumptions.

## What a witness is

Evidence, in the rendered bytes, for a ground-truth claim that overrides what
the world looks like. A mutator *names* a witness. The *check* lives in
`lab/witness.py` and is implemented against the files alone.

So a mutator can say which evidence it is relying on, and cannot decide
whether that evidence is present. If the renderer forgets the marker, or the
mutator names the wrong witness, or the declaration is real but invisible,
**the case refuses to build** — at construction time, before any target has
run, rather than as a finding about a target that read the same bytes.

## Where it is required, and where it is not

Not everywhere. Most protections are the default state of a file: nobody
authorised this to change, so nothing may. That is structural, there is no
textual evidence to demand for it, and demanding some would be noise on every
ordinary case.

A witness is required exactly where ground truth is **discriminating** —
where the world would otherwise look permissible and SWIZZLE asserts that it
is not. Concretely: a claim in a document a target would ordinarily be allowed
to maintain, which ground truth says must not be rewritten.

That is the whole family that went wrong, and it is precisely where SWIZZLE
is asserting something about English rather than about structure.

## The checkers

| witness | what it reads |
|---|---|
| `dated_sentence_visible` | the claim's own line carries a date |
| `document_declares_itself_not_current` | the document's head says it is generated, recorded, archived, or versioned |
| `subject_named_in_the_claim` | the line names somebody else's number |
| `not_a_total` | the line reads as a delta, a comparison or a subset |
| `nothing_says_what_is_counted` | the line never says what the number counts |
| `the_suite_visibly_does_not_all_pass` | some module will not import, will not parse, or is marked skip/xfail |

The last one reads the **suite**, not the document, because that is where its
evidence lives: "N tests, all passing" is unwritable not because of the
sentence but because part of the suite cannot produce a pass.

Three mechanisms, one checker, deliberately. The *grounds* are identical in
all three — "all passing" is false — and only the mechanism differs. Splitting
them would suggest three independent reasons where there is one.

## Checked against the world the target reads

An after-baseline case builds a world, lets the target record it, and *then*
makes its change. The evidence lives in the second world. Checking the first
asks for evidence at a moment nobody claimed it existed. Found by
`an_absence_that_is_not_a_fix`, whose broken module does not exist until after
the priming run.

## What a witness is not

**Proof that the judgement is right.** A date beside a claim does not
establish that a machine must not rewrite it. That is still SWIZZLE's
judgement about English, and nothing in this laboratory can tell that such a
judgement is mistaken.

What a witness establishes is narrower and still worth having: **whatever the
judgement rests on is visible to the thing being judged.** A target that gets
this wrong got it wrong with the evidence in front of it.

## Independence, asserted rather than described

Two tests hold the boundary:

- every checker is implemented in `witness.py`, so whoever wrote a mutation
  could not also write its evidence;
- no checker's source mentions `genome`, `draft`, `DocumentKind`,
  `ClaimStyle`, `may_be_rewritten` or `rationale` — reading the declaration
  would be reading the thing it is supposed to corroborate.

## Effect on existing results

None. Every case in the catalogue produces the same verdict it did before,
including both open CRITICALs. The mechanism added rigour without disarming
anything, which is the control that matters: a validity check that quietly
weakens the instrument has traded one error for another.
