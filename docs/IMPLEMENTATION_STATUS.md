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

234 new tests, 343 total, all passing.

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
