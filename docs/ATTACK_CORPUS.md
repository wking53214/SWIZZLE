# The attack corpus

## Four buckets

| Bucket | Contains |
|---|---|
| `discovered/` | a case that produced a violation. Nothing is claimed beyond that it happened |
| `minimized/` | reduced to a locally minimal world that still fails |
| `regression/` | reviewed, corroborated, promoted. Run on every evaluation; a change in outcome is news |
| `rejected/` | a case that did **not** fail, kept on purpose |

## Why rejected cases are kept

A negative result that reproduces is evidence. `two_maintained_blocks` is in
there because two maintained count blocks in one README sounded like an attack
— a non-greedy match reaches only the first — and it is not: a second remedy
covers the other block independently, and the document ends up consistent.

Deleting that means rediscovering the same dead end in six months. It also
means losing a regression: if the second remedy is ever changed, the case
starts failing and moves buckets.

## Promotion

```
discovered -> confirmed -> minimized -> reviewed -> regression
```

`swizzle corpus --promote NAME` refuses a case that no two independent oracles
agreed on, unless it is `CRITICAL` or a human passes `--force` with a
`--reason` that goes into the record.

The refusal exists because the cheapest way to make an adversarial framework
look productive is to promote everything it flags, and a regression suite full
of single-oracle curiosities is worse than none: it fails for reasons nobody
can defend and gets switched off.

**The CRITICAL exception, stated narrowly.** A CRITICAL here is a byte-level
fact — a hash recorded when the world was built no longer matches the file —
rather than a judgement, and for one of them (a write outside the repository)
only one oracle can see outside at all. Requiring corroboration there would
mean the most serious result the framework can produce is the one it refuses
to keep.

## Current contents

Against Ghost Tools 1.7.0 (`d14dc1a`):

| Bucket | Case | Severity | Corroborated |
|---|---|---|---|
| regression | `prose_inside_the_maintained_block` | CRITICAL | yes |
| regression | `link_out_of_the_repository` | CRITICAL | CRITICAL exception |
| minimized | `prose_inside_the_maintained_block` | CRITICAL | yes |
| discovered | `alias_and_prose_together` | CRITICAL | yes |
| discovered | `claim_rewritten_while_the_suite_runs` | HIGH | yes |
| discovered | `block_in_a_document_about_a_moment` | HIGH | single oracle |
| discovered | `document_reached_through_an_alias` | HIGH | single oracle |
| discovered | `uninvited_section_in_a_readme` | HIGH | single oracle |
| rejected | `dated_claim_in_a_current_document` | — | target correct |
| rejected | `live_claim_in_a_historical_document` | — | target correct |
| rejected | `marker_that_never_closes` | — | target correct |
| rejected | `two_maintained_blocks` | — | target correct |
| rejected | `killed_while_operating` | — | target correct |

Five of thirteen are the target behaving correctly. That ratio is the point:
a corpus with no passes in it is a corpus whose oracles nobody should trust.

## Using it

```
swizzle corpus                          everything
swizzle corpus --bucket regression      just the promoted cases
swizzle attack --from-corpus regression run them
swizzle diff --ghost OLD --ghost NEW    both revisions, compared per case
```

## Integrity

`Tests/test_lab_regression_replay.py` runs over every entry on every test run
and checks that it still round-trips, still rebuilds, still carries the target
revision it was recorded against, and is filed in a bucket consistent with its
severity. An entry that no longer round-trips is an entry whose experiment has
silently changed — and the first anyone would otherwise know is a regression
run failing for a reason nobody can reconstruct.
