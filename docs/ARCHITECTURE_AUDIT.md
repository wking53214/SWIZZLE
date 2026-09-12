# Architecture audit

An audit of SWIZZLE v0.1.0 as it stood before the adversarial laboratory was
built, and the reasoning behind what was kept, what was extended, and what
was left alone.

## What v0.1.0 was

A catalogue of twelve hand-written **warps**: small synthetic repositories,
each with a defect placed in it by hand, each declaring the finding a scanner
ought to report about it (its **true name**), each carrying a **proof** that
the defect was real, and three of them carrying a **control** — the same
defect with the evasion removed — to establish that the escape was caused by
what the case said it was.

Execution flow, end to end:

```
catalogue()  ->  summon()  ->  ghost_buster --json  ->  judge()  ->  render()
 (12 Warps)     (tmpdir +      (subprocess)           (verdict)     (report)
                 git init)
```

Verdicts were `BANISHED` / `MISNAMED` / `ESCAPED` / `CONJURED` / `DISMISSED` /
`UNSUMMONED`, and the report graded each escape by whether ghost_tools
disclosed the gap itself.

## What it already did well

These are the things the laboratory was built **on top of** rather than
replacing, because they were right the first time.

**Ground truth declared in advance.** Every warp said what a correct scanner
would report before the scanner ran. That single decision is what separated
the project from a fuzzer, and it is the ancestor of `GroundTruth`.

**Proof independent of the target.** Each warp demonstrated its own defect by
running it — the injected query really returned the extra row. A framework
that cannot show its planted defects are real is measuring its own fixtures.

**Controls for causal claims.** Three warps carried the same defect with the
costume removed, so "this escaped because of the exclusion" was evidence
rather than a story. This is the direct ancestor of the control mechanism and
of the whole attitude the laboratory took to attribution.

**Disclosure grading.** An escape through a documented scope limit was scored
differently from one nobody knew about. Correct, and carried forward.

**Honest negative results.** One warp was kept in the catalogue specifically
because it did *not* find anything.

## What was weak

**Fixtures, not descriptions.** A warp was Python source in a string. It could
not be mutated by a search, could not be minimised except by editing code, and
two readers could not agree on which detail was load-bearing. Everything the
brief asks for — evolution, minimisation, reproduction from a seed — is
blocked by this one representation choice. **This is the defect that motivated
the genome.**

**One oracle.** `verdict.judge()` compared the target's reported findings
against the declared true name. Nothing else. It could not see an unauthorised
write, could not see a change outside the repository, could not see a stale
diagnosis, and could not see the target contradicting its own report. It also
had a structural blind spot: it only ever asked *what the target said*, never
*what the target did*.

**Scanning only, never acting.** Every invocation was `--json`. The write path
— the part of an autonomous modification system that can actually damage a
repository — was never exercised at all. The most serious finding in this
repository (a write outside the target tree) was unreachable by v0.1.0 by
construction.

**No memory.** No corpus, no regression promotion, no reproduction command, no
record of which target revision a result belonged to.

**No search.** Twelve cases, forever, until a human wrote a thirteenth.

**No minimisation.** Each warp was already small because a human made it small.

**Scoring by counting.** The report counted escapes. Nothing expressed that an
unauthorised write outranks a reporting nit.

## Technical debt found

- `verdict.py` had accumulated two different notions of "near miss" and the
  `tolerated` mechanism was doing work that belonged in a ground-truth model.
- `invoke.QUIET` hard-coded Ghost's flags in a module named as though it were
  general.
- The catalogue named `ghost_buster` throughout, in code as well as prose, so
  a second target could not have been plugged in without editing it.

## What was built

| Added | Why |
|---|---|
| `lab/genome.py` | Cases as typed, serialisable descriptions instead of source |
| `lab/mutators.py` | Deterministic, seeded, ground-truth-recording mutations |
| `lab/world.py`, `lab/draft.py` | Genome to repository, ground truth accumulated en route |
| `lab/groundtruth.py` | The expectation, provably independent of the target |
| `lab/oracles/` | Six independent readings instead of one |
| `lab/fitness.py` | Strict severity dominance |
| `lab/adapter.py`, `lab/adapters/` | The target boundary, with a second implementation |
| `lab/sandbox.py` | Disposable workspaces and path safety |
| `lab/minimize.py` | Reduction to a locally minimal failing world |
| `lab/corpus.py` | Attack memory and a promotion rule that can refuse |
| `lab/search.py` | Adaptive evolutionary search |
| `lab/differential.py` | Two target revisions, compared per case |
| `lab/metrics.py`, `lab/coverage.py` | A scorecard, and an honest empty-row table |

## What was deliberately NOT rewritten

**The original four commands.** `swizzle list`, `prove`, `run` and `summon`
behave exactly as they did. They are tested in `Tests/test_lab_cli.py`
alongside the new surface so that a change to the laboratory cannot quietly
break them.

**The warp catalogue.** All twelve warps, their proofs and their controls are
untouched and still run. They answer a different question from the laboratory
— "is this scanner's *reading* of a defect correct" rather than "is this
modification system's *writing* safe" — and that question did not stop being
worth asking.

**`swizzle/schema.py`, `warps/`, `proving.py`, `summon.py`, `invoke.py`,
`verdict.py`, `run.py`, `report.py`.** Left alone. The laboratory lives in
`swizzle/lab/` and imports exactly one thing from the original code
(`invoke.locate_ghost_tools`, from the Ghost adapter, where target knowledge
belongs).

**`verdict.py`'s notion of MISNAMED.** It was refined inside the laboratory's
own oracles rather than back-ported, because the two layers are answering
different questions and merging them would have made both vaguer.

## Proposed further evolution

In the order the evidence says they are worth doing; see
`docs/IMPLEMENTATION_STATUS.md` for what is already done.

1. **Identity and baseline attacks.** The coverage matrix reports these rows as
   never exercised, which is true. They need multi-run sequences and a
   baseline-priming step in the adapter.
2. **Mid-write interruption.** The crash experiment currently interrupts during
   diagnosis, because that is the only point a target-independent mechanism can
   reach. Interrupting between a write and its verification needs
   `TargetAdapter.interrupt_points()` to be implemented for Ghost.
3. **Mid-run filesystem observation.** Two documented blind spots (a change that
   is reverted, an escape that is restored) are both invisible to before/after
   comparison and both closable by watching the filesystem during the run.
