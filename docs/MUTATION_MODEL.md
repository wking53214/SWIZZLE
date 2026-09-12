# The mutation model

## What a mutator is

A named, versioned, seeded function that does two things:

1. edits the `WorldDraft`
2. records what that edit means for what a correct tool may do afterwards

Both halves are mandatory. A mutator that only edits is a fuzzer, and the
ground truth it fails to record is exactly what turns a diff into a finding.
`Tests/test_lab_mutators.py` asserts that every attack mutator leaves the
draft's expectation different from the unmutated one.

## Why not random text

Because a tool failing on garbage is not news. Every mutator produces
something a real repository could plausibly contain: a status document that
kept its markers, a README that is a symlink into `docs/`, a test that writes
a snapshot file while it runs.

The question is never "does the target survive nonsense". It is "does the
target's reasoning hold on a world it did not anticipate but could meet".

## Determinism

Each mutation gets an RNG seeded from `(genome seed, its index, its name)`.

Not a shared RNG, and this is load-bearing. With a shared stream, removing any
mutation reshuffles every later one, so a minimiser's reduction destroys the
attack for a reason that has nothing to do with the mutation it removed —
which made the minimiser useless in the first version. There is a test for it.

## Reversibility

None of them mutate anything on disk. They edit a draft, and the world is
built from the draft afterwards, so *undoing* a mutation means removing it
from the genome's sequence and rebuilding. That is what makes delta debugging
possible at all, and it is why the minimiser works on genomes rather than on
directories.

## Phases

| Phase | When | Notes |
|---|---|---|
| `build` | while constructing the world | most mutators |
| `during_tests` | by the repository's own suite, which the target runs mid-scan | the only injection point genuinely *inside* a target run |
| `between_runs` | between two target invocations | needs an adapter exposing scan and act separately; Ghost's does not |

A case containing a `during_tests` mutation is run **once**: a preliminary
read-only scan would fire the mutation early and there would be no stale
window left to test. The scope oracle is told so and reports
`attribution_unanswerable` rather than guessing.

## The registry

`swizzle mutators` prints it. Currently 22, across:

| Category | Mutators |
|---|---|
| `claim_shape` | `make_dated_claim`, `make_historical_claim`, `make_scoped_claim`, `make_attributed_claim`, `make_hedged_claim`, `make_comparison_table`, `push_the_trigger_out_of_the_window` |
| `writability` | `put_prose_in_count_block`, `duplicate_count_block`, `nest_count_block_marker`, `corrupt_count_block_marker`, `move_count_block_to_document` |
| `scope` | `alias_document_with_symlink`, `symlink_escapes_repository` |
| `temporal` | `rewrite_claim_during_tests` |
| `verification` | `break_the_subject_import`, `break_the_subject_syntax`, `skip_the_subject_at_module_level`, `argue_the_failure_is_correct` |
| `composition` | `count_that_depends_on_the_document` |
| `crash` | `kill_target_during_tests` |
| `control` | `add_filler_modules` |

Three of these do something the rest do not, and each is worth naming.

**`push_the_trigger_out_of_the_window`** does not hide the trigger — it moves
the *rest of the sentence* so far from it that the analyser's fixed lookback
never reaches it. The claim is unchanged in meaning and longer in bytes. What
comes out is not a wrong answer but an **unfalsifiable** one: a verdict about
the fragment that fit in the window, indistinguishable in the report from a
verdict about the whole.

**The `verification` family** attacks the evidence rather than the subject. If
the thing a test asserts about cannot be imported, cannot be parsed, or skips
itself at module level, then a test that "passes" has asserted nothing — and a
suite certified green on that basis has certified the absence of evidence.

**`count_that_depends_on_the_document`** builds a world where acting creates
the reason to act again: a suite parametrised over a number in the document
the tool writes that number into. It is only legible across rounds, so it is
asked with `swizzle loop` rather than `swizzle attack`. See
`docs/CONVERGENCE.md`, including the two rules of Ghost's that turned out to
be brakes on the loop.

## Permitted mutation kinds

Ground truth authorises not just a file and a line span but a *kind* of
change. A tool that edits an authorised line in an unauthorised way has still
done something nobody permitted.

| Kind | Means |
|---|---|
| `rewrite_count_digits` | change the digits of a count, nothing else |
| `maintain_count_block` | set the body of a block the repository opted into |
| `append_own_section` | add a marked section of the tool's own |
| `annotate_source_comment` | add a comment to a source line |

## Composition

The genome's `mutations` is a sequence, so composition is the ordinary case
rather than a special mechanism. `alias_and_prose_together` composes a scope
mutator with a writability mutator; the result is worse than either, because
neither the writability decision nor the block verification is looking at the
file that loses the paragraph.

The search composes automatically: `offspring` adds a mutation to a parent's
sequence, with prerequisites checked so the result is still buildable.

## Adding one

1. Decide what world it constructs, and convince yourself a real repository
   could contain it.
2. Write the edit.
3. Record the ground truth: `draft.protect(...)` with a stated reason,
   `draft.permit(...)`, `draft.expect_abstention = True`, or a `draft.facts`
   entry an oracle will need.
4. Give it a summary long enough to be useful in `swizzle mutators`.
5. `python -m pytest Tests/test_lab_mutators.py` — it applies every mutator to
   a real draft and checks determinism, ground-truth recording, and that every
   protected region states a reason.
