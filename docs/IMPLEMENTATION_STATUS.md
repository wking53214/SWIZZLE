# Implementation status

Against Ghost Tools `d14dc1a` (v1.7.0), measured 2026-09-12.

## What was already present

SWIZZLE v0.1.0: twelve hand-written warps, each with a declared true name, an
executable proof that its defect was real, and — for three of them — a control
establishing that the escape was caused by what the case claimed. One oracle,
scan-only, no memory, no search, no minimisation. Audited in full in
`docs/ARCHITECTURE_AUDIT.md`.

## What was changed

Nothing in the original code path. `swizzle list|prove|run|summon`, the warp
catalogue, its proofs and its controls are untouched and still pass, and are
now covered by `Tests/test_lab_cli.py` as well as their own tests.

Two things were extended rather than replaced:

- `swizzle/cli.py` grew a call to `lab.cli.add_parsers()` and a fallback
  handler lookup. The four original commands dispatch exactly as before.
- The package description changed to say what the project is now.

## What was added

**Phase 1 — case model and infrastructure.** `lab/genome.py` (typed,
serialisable, digested repository genome with twelve dimensions and a stated
hypothesis), `lab/draft.py`, `lab/world.py`, `lab/mutators.py` (16
deterministic seeded mutators), `lab/sandbox.py`, `lab/groundtruth.py`,
`lab/adapter.py` + `lab/adapters/ghost.py`.

**Phase 2 — attack taxonomy.** Six independent oracles (`lab/oracles/`),
`lab/signals.py` (severity ladder, failure classes), `lab/fitness.py` (strict
dominance), `lab/attack.py`, `lab/catalogue.py` (12 seed cases across
writability, scope, temporal, claim-shape, composition, crash and control).

**Phase 3 — minimisation, corpus, reproduction.** `lab/minimize.py`,
`lab/corpus.py` (four buckets, promotion with refusal), `swizzle reproduce`
including `--build-only`, which needs no target.

**Phase 4 — search and differential.** `lab/search.py` (evolutionary, adaptive
mutator weighting, novelty cache), `lab/differential.py` (five outcomes
including `improved`/`worsened`).

**Phase 5 — crash experiments and self-adversarial testing.**
`kill_target_during_tests`, the recovery checks in the ledger oracle,
`Tests/test_lab_self_adversarial.py`.

**Reporting.** `lab/reporting.py`, `lab/metrics.py` (scorecard of thirteen
rates, each with its denominator), `lab/coverage.py` (surface matrix that
shows empty rows).

**Phase 6 — LLM mutation generator.** Not implemented, deliberately. Phases
1–5 are useful without it and the brief is explicit that it comes last.

## Tests added

234 new tests, 343 total, all passing. (509 total at v0.5.0.)

| File | Covers |
|---|---|
| `test_lab_genome.py` | serialisation, digest stability, schema refusal |
| `test_lab_determinism.py` | same genome, same world, byte for byte |
| `test_lab_mutators.py` | every mutator: metadata, determinism, ground-truth recording, stated reasons |
| `test_lab_oracles.py` | each oracle against a configurable second target |
| `test_lab_oracle_independence.py` | import-graph walk: no judge can reach a target |
| `test_lab_fitness.py` | dominance, scalar cap, corroboration by class |
| `test_lab_minimize.py` | reduction preserves the attack; refuses a case that never failed |
| `test_lab_sandbox.py` | path safety, escape refusal, disposal guards |
| `test_lab_corpus.py` | record, promote, refuse, override with reason |
| `test_lab_differential.py` | the five outcomes |
| `test_lab_cli.py` | new commands **and** the original four |
| `test_lab_regression_replay.py` | every archived case still rebuilds |
| `test_lab_self_adversarial.py` | attacks on SWIZZLE's own oracles |
| `fake_target.py` | a second `TargetAdapter` with 10 behaviours |

## Attacks discovered

Seven, against Ghost Tools 1.7.0. Each was verified by hand before the
laboratory existed or is corroborated by two independent oracles.

| Case | Severity | What happens |
|---|---|---|
| `link_out_of_the_repository` | CRITICAL | A write lands on a file **outside** the repository. One remedy composes `root/"README.md"` and writes to it with no containment check; a symlink carries the write out of the tree, where the branch the tool opened cannot revert it. The tool's own commit then fails, having nothing to commit — its error path sees a symptom after the damage |
| `prose_inside_the_maintained_block` | CRITICAL | Three lines of author prose inside an opt-in marked block are deleted. The post-write verification checks that bytes **outside** the block are unchanged, so it cannot see the loss |
| `alias_and_prose_together` | CRITICAL | Both of the above composed; the paragraph is lost in a file no finding names |
| `claim_rewritten_while_the_suite_runs` | HIGH | The repository's own suite rewrites a live claim into a dated one mid-run; the tool then writes its measured number into the dated sentence. Its pre-write re-check runs a weaker predicate than the one that authorised the write |
| `document_reached_through_an_alias` | HIGH | The writability decision is made about `README.md` and the bytes land on `docs/project_notes.md`, whose name the same rule would have refused |
| `block_in_a_document_about_a_moment` | HIGH | The prose remedy refuses dated documents by name; the block remedy performs no document check at all, so the same repository gets two answers depending on which mechanism reaches it |
| `uninvited_section_in_a_readme` | HIGH | The tool argues in its own source that inserting markup into somebody's README uninvited "has decided something that was not its to decide", and declines to add its own markers for that reason — while a different remedy appends a section on every operation, including when it has nothing to report |

**Five cases came back clean** and are archived as such: a dated claim in a
README, a live-looking claim in a historical document, a malformed marker
pair, two maintained blocks, and — notably — a SIGKILL mid-operation, after
which the repository was on its original branch and clean.

The differential pins one of them to a release:

```
baseline   1.6.1 at e5ad44b57a
candidate  1.7.0 at d14dc1acf0
worsened   prose_inside_the_maintained_block  LOW -> CRITICAL
```

## Attacks minimised

`prose_inside_the_maintained_block`, from size 15 to 13 (2 of 7 reductions
held). The reduction establishes that the README's introductory prose and the
live claim outside the block are scenery, and that the suite size **is**
load-bearing — at 15 tests against 12 documented, the drift thresholds are not
met and there is nothing to act on. That last fact was not known in advance.

## Outcome against 1.7.1

All seven were fixed in Ghost Tools 1.7.1 (`40b8dae`). `swizzle diff --ghost
d14dc1a --ghost 40b8dae --seeds` reports 6 fixed, 1 improved (HIGH to LOW:
an unauthorised write became an over-cautious refusal), 5 unchanged, 0
regressed.

The re-run also found three bugs in SWIZZLE itself, each of which had it
reporting a target for something SWIZZLE had done or demanding something
impossible:

- a during-tests mutation was attributed to the target, because it lands
  after the baseline snapshot. Fixed by `Evidence.baseline`, which replays
  the harness's own edits before anything is diffed.
- a composed case froze a file byte-for-byte while also permitting an edit in
  it. `groundtruth.of` now refuses to build a self-contradictory case.
- the differential classified HIGH-to-LOW as a regression, keying on failure
  class before severity.

Each has a test asserting the guarantee.

## Standing, after interrogation (v0.3.0)

`swizzle standing` was run across the corpus against ghost_tools 1.7.2.
Nothing reads `fixed`:

| case | standing |
|---|---|
| `link_out_of_the_repository` | current structure supports resolved |
| `prose_inside_the_maintained_block` | current structure supports resolved |
| `uninvited_section_in_a_readme` | current structure supports resolved |
| `alias_and_prose_together` | unreproduced, unprobed (no siblings to ask) |
| `block_in_a_document_about_a_moment` | **unreproduced, but a probe defeated it** |
| `claim_rewritten_while_the_suite_runs` | **unreproduced, but a probe defeated it** |
| `document_reached_through_an_alias` | reproduces (LOW over-caution) |
| five controls | never reproduced |

Two things came out of that run that would not have come out of re-running
the cases.

**A CRITICAL that 1.7.1 reported fixed was still open.** The variant probe
built the same world with a count block in it and walked back out of the
repository: 1.7.1 had guarded two writers and left the third, and the case
that found the original hole had no block in it, so the fix was verified
against a world that could not exercise the writer it left open. Fixed in
1.7.2, where the test now runs every writer over one world.

**Two classes are still open**, each found by a variant one dimension from a
case that had been declared fixed:

- a README whose kind is `generated` -- carrying `<!-- generated: do not edit
  by hand -->` -- has its claim rewritten anyway. The writability gate is by
  filename and has no notion of a document declaring itself not
  hand-editable. Verified by hand: CRITICAL, `protected_text_destroyed`.
- a variant of the during-tests case reproduces `unauthorised_mutation` at
  HIGH.

Both genomes are archived inside the resolutions and are reproducible.

## Frames, seeding, and loops (v0.5.0)

Three things, in the order they were asked for.

**Seeding the population from the corpus.** `swizzle evolve --from-corpus
BUCKET` starts the search from cases that have already earned their place
rather than only from the hand-written catalogue. The catalogue is a set of
hypotheses; the corpus is a set of measurements, and starting from
measurements is strictly better information.

**Starting in the middle of a trigger.** `push_the_trigger_out_of_the_window`
makes a claim dated and then pads between the date and the number, so the date
falls outside the fixed lookback the analyser reads. The sentence asserts
exactly what the short one asserts — what was true on a named day — and the
only difference is its length.

The consequence is the interesting part, and it is the one the brief named:
a verdict reached on the fragment that fits in the window is a verdict about
*the fragment*, and nothing in the output says so. A passing check is not
wrong, exactly; it is **unfalsifiable** — correct with respect to a partial
view, and there is no report that distinguishes it from correct with respect
to the whole. Confirmed at the predicate level (`_CLAIM_LOOKBACK = 80`,
`_WRITABILITY_LOOKBACK = 240`) and end to end.

**Loops.** `swizzle loop CASE` runs the target, adopts its output, and runs it
again — bounded, because a harness that can hang is a harness nobody runs, and
not settling within the bound is the finding. Six classifications; full
reasoning in `docs/CONVERGENCE.md`.

Measured: `a_count_that_changes_when_you_write_it` cycles 31 → 32 → 33 → 31
against ghost_tools 1.7.2, period 3, confirmed across four rounds.

Two results matter more than the cycle itself.

*Two of Ghost's rules are brakes on the loop.* Its drift rule is
one-directional, so it settles the moment it writes a value at or above the
static bound; and its green gate declines to write into a suite that is not
passing. The first version of the case tripped the second and settled, and
**Ghost was right to settle there**. Building a genuine cycle meant
constructing a world where the tool has no defensible reason to stop.

*The harness had the defect it hunts.* A round the target refused to begin
leaves the same unchanged repository as a round where it ran and settled.
Ghost names its working branch to the second, two rounds inside one second
collided, the refusal went to stderr where nothing was looking, and a real
period-3 cycle was reported as a fixpoint. Three corrections at three layers,
each where the knowledge belongs, all three regression-tested against the fake
target.

## Known limitations

**Identity and baseline attacks are not implemented.** The coverage matrix
reports both rows as never exercised, which is true. They need multi-run
sequences and a baseline-priming step in the adapter.

**Crash experiments interrupt during diagnosis, not mid-write.** The
interruption is delivered by the repository's own suite, which is the only
point a target-independent mechanism can reach. Interrupting between a write
and its verification needs `TargetAdapter.interrupt_points()` implemented for
the target.

**A change that is reverted is invisible.** Every oracle compares before with
after. Closing it needs filesystem observation during the run. Documented in
`docs/ORACLES.md` and asserted as an open blind spot in
`test_lab_self_adversarial.py`, so closing it will make a test fail.

**An escape that is restored is invisible.** Same hole, other side.

**No semantic judgement of rewritten prose.** Whether edited English still
says something true is not assessed. It needs a human or a model, and a
model's opinion is the kind of oracle this framework refuses to depend on.

**Ground truth can be wrong.** It is SWIZZLE's own judgement about English and
about what a machine may do to somebody's writing, and nothing here can detect
that it is mistaken. The defences are stated reasons on every judgement, and
controls that are expected to pass.

**Minimisation is locally minimal, not minimal.** Greedy to a fixpoint over a
fixed move set. Stated in every report that includes one.

**`between_runs` mutations are unavailable for Ghost**, which scans and
operates in one process. Temporal attacks use the during-tests window instead.

## Next highest-value work

1. **Identity and baseline attacks.** The largest genuinely empty row, and the
   one the brief asks for most explicitly. Needs `TargetAdapter.prime_baseline`
   and a `Phase.AFTER_BASELINE`.
2. **Mid-write interruption.** Implement `interrupt_points()` for Ghost so the
   window between a write and its verification can be tested. Ghost's recovery
   passed the experiment that was available; the harder one has not been run.
3. **Filesystem observation during the run.** Closes two documented blind
   spots at once and would make "the target touched a file it should not have"
   answerable even when it tidied up afterwards.
4. **More targets.** The adapter boundary is real and tested by a second
   implementation, but the second implementation is a fake. A third real target
   would find out how much Ghost-shaped thinking is still baked into the
   genome dimensions.
