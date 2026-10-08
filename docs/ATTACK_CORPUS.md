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

Five of thirteen are the target behaving correctly. That ratio is the point:
a corpus with no passes in it is a corpus whose oracles nobody should trust.

## After Ghost stopped writing READMEs

The table above describes defects in README writers that existed at `d14dc1a`.
Ghost has since lost those writers: it no longer rewrites a stale test count,
no longer maintains a marked count block, and no longer writes a
name-disagreement table into a README. Only Streamline writes READMEs.

The cases are kept, because they are the record of why those writers were
dangerous and they still run. What changed is the expectation. The Ghost
adapter declares `rewrites_documents=False`, so a world built for Ghost
authorises no document edit, and any change to a README or other document is
reported as acting where abstention was correct. Run against the old Ghost,
`prose_inside_the_maintained_block` is a violation; run against the new one it
is clean. A regression back to rewriting READMEs would fail the gate.

## After the fixes

The table above is the state at `d14dc1a`, and the entries are kept as
recorded: an archived case is attributed to the revision it was found
against, and rewriting it to match a later one would destroy the only thing
that makes it evidence.

Against `40b8dae` (1.7.1) every discovered case comes back clean except
`document_reached_through_an_alias`, which drops from HIGH to LOW. Re-run it
yourself with `swizzle diff --ghost d14dc1a --ghost 40b8dae --seeds`.

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
