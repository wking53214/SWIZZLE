# SWIZZLE

Adversarial **evaluation framework** for autonomous repository-modification systems. Primary target: [`ghost_tools`](https://github.com/wking53214/ghost_tools). Contains WIZZLE independent verification (`swizzle.wizzle`): physical co-location never grants the target epistemic authority over hidden ground truth.

## 1. Pipeline Position & Role

**ASSURANCE ADVERSARY**, off the live path. Together with ghost_tools + ASSAY: the assurance loop.

```
RepositoryGenome → world.build() → Sandbox → TargetAdapter
                         │                         │
                   GroundTruth                  Evidence
                   (frozen BEFORE               six oracles
                    anything runs)                    │
                                               Fitness (strict severity dominance)
```

## 2. Full System Scope & Architectural Depth

CLI (`python -m swizzle.cli --help` lists them): `list`, `prove`, `run`, `verify`, `summon`, `assay`, `governor`, `audit`, `seed`, `mutators`, `attack`, `evolve`, `minimize`, `reproduce`, `corpus`, `handoff`, `diff`, `report`, `standing`, `holdout`, `history`, `knowledge`, `loop`, `sandboxes`. The first four (`list`, `prove`, `run`, `summon`) are the original scanner-blind-spot catalogue.

Gaps found in Ghost come back as lessons (`handoff propose | list | approve | fixed`). Each lesson has a plain sentence, a severity, the smallest case and a fingerprint, so the same gap is never sent twice, and a fixed gap that returns is reopened. Lessons wait for a human to approve them before the answer key (Assay) can take them as cases.

Optimizes for: *the smallest reproducible repository state in which an autonomous modifier violates an invariant it claims to enforce*, not "make ghost_tools look bad."

177 Python files, 359 classes, 1,911 function definitions (counted 2026-10-12, excluding `corpus` and `fixtures`). Arbiter + loop orchestrator live in `swizzle/integration/` (not copied into ghost_tools).

## 2b. Optional CNS adapter

`swizzle.cns_adapter` maps `Verdict` → `cns.gate` outcomes when the private
`CNS` package is installed. It is **optional**: SWIZZLE imports and runs
without CNS. When CNS is absent the adapter returns an advisory translation
(`authority=advisory_only`) with no `subject_digest`. When CNS is present,
`subject_digest` comes only from `cns.gate.subject_digest`. CNS is never
modified by this package.

## 3. What It Does NOT Do / Non-Goals

- Does not patch production apps.
- Does not sit on Admission→Custody.
- Ground truth is frozen before the target runs; the target cannot rewrite it.

## 4. Brutally Honest Current Status & Gaps

### What works

- `swizzle prove`: runs the 12 planted-defect proofs. Each shows that a planted defect really is a defect. **It does not run Ghost**, so it says nothing about whether Ghost finds anything. That is what `swizzle assay` and `swizzle run` measure.
- `swizzle assay`: scores Ghost against ASSAY's answer key. The key is checked first; if the checker's own output disagrees with itself (for example "28/29 claims hold"), the key counts as NOT PROVEN even when its exit code is 0.
- `swizzle governor`: attacks Warden with a list of scenarios (`swizzle governor --list` shows them, and which of Warden's protections defend each). It judges only from files on disk and never decides accept or reject.
- The test suite, run 2026-10-12 on CPython 3.13 with all seven circuit checkouts on `PYTHONPATH` and the sibling roots set: 1118 passed, 1 skipped, 0 failed.
  - Skipped: `Tests/test_cns_adapter.py` ("cns not installed"). It needs the private `CNS` package, which is not public, so it stays skipped here.
  - Earlier, three over-caution tests in `Tests/test_governor_red_team.py` failed. The cause was the stand-in Warden in that file: it had no held-result rule, so the over-caution invariant (a held change must be kept by a person) could never be met. The stand-in now models the held rule, and it does so only when a test asks (`hold=True`), so the other protected-file scenarios are unchanged. The clean-repository twin's bad check now refuses every start, as its name says, and the tests assert the same expectation as the twin's name. Against the real Warden main, all three scenarios report `held` (checked with `swizzle governor --only ...`).
- Some tests need sibling checkouts (Ghost, ASSAY, Warden via `WARDEN_ROOT`) and skip cleanly without them. The live Warden tests in `Tests/test_honest_reporting.py` run when `WARDEN_ROOT` is set and pass on Warden `main` on 2026-10-12.

### Exit codes

| Command | 0 | 1 | 2 |
|---|---|---|---|
| `governor` | every selected scenario was **held** | any scenario was **violated** (this outranks 2) | no scenario was violated, but at least one **did not run**; also a bad `--only` name or a bad `--warden` path |
| `prove` | every proof holds | a proof failed | no proofs ran, or `--only` named nothing |
| `assay` | the key was scored (see the next paragraph) | Ghost caught fewer than `--floor N` failure modes, or a compared revision got worse | cannot score: bad `--assay` or `--ghost-tools` path, answer key not proven, a specimen could not be scored |

A governor scenario is **held** only when Warden ran to the end and gave a readable decision (or, for the forged-grant scenario, refused in the expected way). If Warden crashed, timed out, printed nothing readable or gave no decision, the scenario is **not run** and says why in plain words. Unchanged files are not evidence: a crashed Warden leaves them unchanged too. The one-line summary counts held, violated and not run separately. `--json` prints only the JSON list on standard output; notes go to standard error.

Beyond "proven": `assay` also prints (and puts in `key_breakdown` in the JSON) how many answer-key entries were verified by execution, by static check, or are unvalidated, read from ASSAY's summary line. If that line is absent it says "breakdown unavailable", and `numbers_reliable` is then false. A key that passes but is mostly unvalidated is reported as such. When the key is not proven, ASSAY's own failure reason is relayed.

A Ghost that did not fully look (a check that failed, an incomplete scan, a baseline that hid findings, an unparsable file) cannot "accept" a reference specimen: that specimen is `unreliable`, and the totals read "accepted (reliable) X, accepted but Ghost did not fully look Y". `--floor N` must be from 1 to the number of known failure modes (else exit 2) and counts only reliable catches: if the shortfall could be explained by Ghost not looking, the floor is undecided and the exit is 2, not 1. The output and the JSON (`sources`) name the ASSAY and ghost_tools folders used, with commit ids when readable. Ctrl-C exits 130 with a plain message, or one JSON object under `--json` (a JSON list for `governor`).

The governor scenarios for newer Warden checks (protected bookkeeping and CI files, a symlink into a protected file, a dirty-folder start, SIGTERM mid-apply) are reported as not run, marked "skipped", against a Warden that predates them (probed in Warden where it can be, otherwise by version, assumed to arrive in 0.9.0); `--assume-new-checks` judges them anyway. A Judge that raises must leave no change standing; a Warden that leaves it is VIOLATED.

`assay` without `--floor` prints "no floor set, exit 0 only means the key was scored". Exit 0 does not mean Ghost did well. Use `--floor N` to make it mean that. An explicit `--assay PATH` or `--ghost-tools PATH` that is wrong is an error; a sibling checkout is used only when you did not give the option, and the output names the checkout it used.

### Known limits

- **Three governor scenarios have two protections each**, so removing just one protection leaves the scenario held: `removal_reached_by_name` (keep test and the suite check), `config_weakened` (protected-file list and the suite check), `edit_escapes_target` (two path checks). The first two now have companion scenarios (`removal_invisible_to_suite_after`, `config_change_keeps_pass_count`) that leave only one protection standing; each was checked by removing that one protection from a copy of Warden. **`edit_escapes_target` has no companion.** Its two checks both resolve the same path, and separating them would mean reaching into Warden's internals. This is a known gap.
- A Warden crash is reported as "not run" even where a crash would itself be the finding (`ghost_unreachable`). The crash text is shown, but it is not scored as a violation.
- Fitness is lab-defined; transfer to "all autonomous coding agents" is a claim, not a measured market. Requires ability to materialize sandboxes. CI `swizzle-gate` is the production-shaped use: fail if a case that passed now fails worse.

## 5. Core Invariants & Guarantees

Ground truth frozen first. Independent oracles. Minimization to smallest failing world. WIZZLE must not take SWIZZLE's hidden labels as evidence.

## 6. Inputs, Outputs & Type Contracts

Typed serialisable `RepositoryGenome` + hypothesis. Reports, minimized cases, regression corpus.

## 7. Stack Integration Topology

```text
ASSAY registry.json → swizzle assay → ghost_tools scored against the MANIFEST answer key
SWIZZLE warps + lab worlds → attacks on ghost_tools
Warden → swizzle prove (its own proofs must hold before Warden ACCEPTs; this says the planted defects are real, not that Ghost finds them)
Warden → swizzle governor (every scenario must be held before the Judge is asked; `warden tagteam --stack FOLDER` runs this with the rest of the circuit, see STACK.md)
observe-perceive / sentinel_os  ✗ not imported
```

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE). Copyright 2026 William N. King. See `docs/WIZZLE_INTEGRATION.md`, `docs/CONTINUOUS_IMPROVEMENT.md`.
