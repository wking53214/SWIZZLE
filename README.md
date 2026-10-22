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

CLI (`python -m swizzle.cli --help` lists them; `swizzle --version` and `swizzle --contract` are flags, not commands): `list`, `prove`, `run`, `verify`, `summon`, `assay`, `governor`, `audit`, `seed`, `mutators`, `attack`, `evolve`, `minimize`, `reproduce`, `corpus`, `handoff`, `diff`, `report`, `standing`, `holdout`, `history`, `knowledge`, `loop`, `sandboxes`. The first four (`list`, `prove`, `run`, `summon`) are the original scanner-blind-spot catalogue.

Gaps found in Ghost come back as lessons (`handoff propose | list | approve | fixed`). Each lesson has a plain sentence, a severity, the smallest case and a fingerprint, so the same gap is never sent twice, and a fixed gap that returns is reopened. Lessons wait for a human to approve them before the answer key (Assay) can take them as cases.

Optimizes for: *the smallest reproducible repository state in which an autonomous modifier violates an invariant it claims to enforce*, not "make ghost_tools look bad."

The arbiter and the loop orchestrator live in `swizzle/integration/` (not copied into ghost_tools). `docs/CODEBASE_AST.md` is a dated map of the code, not a live count.

## 2b. Optional CNS connection

`swizzle.cns_adapter` connects SWIZZLE to CNS in both directions. It is **optional**: SWIZZLE
imports and runs without CNS, declares no runtime dependency, and imports `cns` only when a gate
is constructed. Install the pinned contract with `pip install 'swizzle[cns]'` (CNS v1.9.0); without it a
gate raises `CnsNotInstalled`, which names that command. CNS is never modified by this package.

- `translate_verdict` (unchanged) maps one warp `Verdict` to a `cns.gate` outcome, or to an advisory
  record when CNS is absent. It is not a `Gate`, and it stamps every result `ALPHA`, though a warp
  verdict judges a scan that has already run. That is left as it is, because changing it would
  change what existing callers receive.
- `ProofGate` (ALPHA) asks whether the instrument is sound. Its candidate is what `swizzle prove`
  computes, `[(warp name, Proof)]`, returned by `run_proofs()`. Every warp's proof held: `PASS`. A
  proof that did not hold (or crashed): `TERMINAL_BREACH`, because nothing a broken instrument says
  counts. No proofs, or a warp without one: `RETRY`. An unreadable candidate, or an answer it does not
  recognise: `TERMINAL_BREACH`.
- `AttackGate` (OMEGA) asks whether each attack on the governor held. Its candidate is the list
  `swizzle governor --json` prints. `held`: `PASS`. `violated`: `TERMINAL_BREACH`. `not_run` (no clean
  answer) or an empty report: `RETRY`. Any other status: `TERMINAL_BREACH`. Severity is validated as
  text and never used; what a violated invariant means for a run is the Judge's to decide.
- `attack_rows(report)` checks SWIZZLE's own attack output against `cns.attack.AttackResult` and
  returns `(rows, problems)`, so a drifted field fails SWIZZLE's tests rather than a reader.
- Every verdict is bound to what it judged with `cns.gate.subject_digest`. A candidate that cannot be
  read or bound is `TERMINAL_BREACH` with no digest, never a pass. An exception from SWIZZLE's own
  code propagates.

Warden runs `swizzle prove` and `swizzle governor --json` as subprocesses and reads their text and
JSON; the gates are for a caller that holds those results in Python.

## 3. What It Does NOT Do / Non-Goals

- Does not patch production apps.
- Does not sit on Admission→Custody.
- Ground truth is frozen before the target runs; the target cannot rewrite it.

## 4. Brutally Honest Current Status & Gaps

### What works

- `swizzle prove`: runs the 12 planted-defect proofs. Each shows that a planted defect really is a defect. **It does not run Ghost**, so it says nothing about whether Ghost finds anything. That is what `swizzle assay` and `swizzle run` measure.
- `swizzle assay`: scores Ghost against ASSAY's answer key. The key is checked first; if the checker's own output disagrees with itself (for example "28/29 claims hold"), the key counts as NOT PROVEN even when its exit code is 0.
- `swizzle governor`: attacks Warden with a list of scenarios (`swizzle governor --list` shows them, and which of Warden's protections defend each). It judges only from files on disk and never decides accept or reject.
- The test suite: `python -m pytest -q` from a checkout (`pip install -e '.[dev,cns]'`). No pass count is written here, because a number in a README drifts (`Tests/test_ci_config.py` fails if one is added); the suite prints its own.
  - **What CI runs** (`.github/workflows/tests.yml`): the full suite on CPython 3.11, 3.12 and 3.13, with ghost_tools, ASSAY and WARDEN checked out beside this repository at pinned full commit SHAs (a tested set: ghost_tools 1.10.5, ASSAY 0.11.2 and WARDEN 0.13.7, each version also in a comment next to its pin; the commit may sit behind that repository's head, so bump it as the workflow header describes), every action pinned by commit SHA with its release tag in a comment, `GHOST_TOOLS`, `ASSAY` and `WARDEN_ROOT` set to them, the `cns` extra installed, which is pinned to the CNS tag `v1.9.0` (the tag spelling, shared by every repository in the circuit, which peels to `da18e411743d4e3b0e783105394d845fb1c16746`), and `numpy` and `matplotlib` installed at exact versions (`matplotlib==3.11.2` everywhere; `numpy==2.4.6` on Python 3.11 and `numpy==2.5.4` on 3.12 and 3.13, chosen by environment markers because numpy 2.5 requires Python 3.12 or newer), because ASSAY's verifier skips claims without them and exits 1. None of those steps is `continue-on-error`, so a sibling that cannot be fetched fails the job instead of silently skipping the live tests. A separate `static` job runs `ruff check .` and `mypy`. A separate, clearly named `siblings-latest` job runs the suite against each sibling's default branch; it never blocks.
  - **Without siblings** the tests that need them skip cleanly (`GHOST_TOOLS` unset: `Tests/test_against_ghost_buster.py`, the live parts of `Tests/test_assay.py`; `WARDEN_ROOT` unset: the live attacks in `Tests/test_governor.py`, `Tests/test_honest_reporting.py`, `Tests/test_cns_connector.py`). `pytest -rs` lists what skipped and why. Without the `cns` extra, `Tests/test_cns_connector.py` and one test in `Tests/test_cns_adapter.py` skip; `Tests/test_cns_independence.py` blocks `cns` and runs everywhere.
  - **Governor temp folders.** `Tests/test_honest_reporting.py` checks that the governor leaves no `swizzle-governor-*` folder behind. It does that against a private temp root, because the system temp folder is shared with any other SWIZZLE run on the machine and comparing it before and after used to fail whenever one ran at the same time.
  - Earlier, three over-caution tests in `Tests/test_governor_red_team.py` failed. The cause was the stand-in Warden in that file: it had no held-result rule, so the over-caution invariant (a held change must be kept by a person) could never be met. The stand-in now models the held rule, and it does so only when a test asks (`hold=True`), so the other protected-file scenarios are unchanged. The clean-repository twin's bad check now refuses every start, as its name says, and the tests assert the same expectation as the twin's name. Against the real Warden main, all three scenarios report `held` (checked with `swizzle governor --only ...`).
- Static gates: `ruff check .` (rules E, F, W, B; line length 120) and `mypy` (the `swizzle` and `tools` packages, with `check_untyped_defs`; no `# type: ignore` in the source). Test modules are not type-checked (see the comment in `pyproject.toml`).

### Version, contract, logging, and where files are written

- **Version.** `pyproject.toml` is the only place a version is declared. `swizzle --version`, `swizzle.__version__` and the `swizzle.version` field of corpus records read it back through the installed package metadata (falling back to `pyproject.toml` in a plain checkout, and to `0+unknown` rather than a made-up number). `Tests/test_version_identity.py` fails if they differ. History is in `CHANGELOG.md`. An older `v0.10.0` git tag exists in this repository that does not correspond to this version (no `pyproject.toml` has ever said 0.10.0); releases of this version are not tagged yet, and tagging is the owner's decision.
- **Contract for callers.** `swizzle --contract` prints JSON naming a `contract` number, the SWIZZLE version, and the exit codes and fields of the commands Warden runs as subprocesses (`prove`, `governor --json`, `assay --json`). A caller can assert on `name` and `contract` before trusting any output. See `docs/CONTRACT.md`.
- **Logging.** Diagnostics use the standard `logging` module and go to stderr only. `swizzle -v` shows progress, `-vv` shows every subprocess; `$SWIZZLE_LOG_LEVEL=DEBUG` does the same. Without it SWIZZLE prints no log lines, and as a library it stays silent unless you configure logging.
- **Where SWIZZLE writes.** `swizzle list`, `prove`, `run`, `assay`, `governor` and the read-only lab commands (`corpus`, `report`, `diff`, `seed`, `mutators`, ...) write nothing into the working directory; they work in temporary folders they remove. The attack memory is a folder you name with `--corpus-dir DIR` (older spelling `--corpus-path`); it defaults to `./corpus` in the current directory, and nothing is created there until a command records something (`attack --corpus`, `evolve --corpus`, `minimize --corpus`, `corpus --promote`, `standing --record`, ...). `Tests/test_no_surprise_writes.py` holds this.

### Exit codes

A bare `swizzle` (no command) prints usage on standard error and exits 2, like any CLI given no command; `--help`, `--version` and `--contract` exit 0. `swizzle verify DIR` exits 2 when `DIR` does not exist, is not a directory, cannot be read or is empty (there is nothing to verify against; an existing folder whose claim the oracles cannot judge is still a result, reported as UNASKABLE, exit 0). `swizzle corpus --corpus-dir DIR` exits 2 when a `DIR` you named does not exist or is not a readable directory; only the default `./corpus`, which has not been written yet, reads as "the corpus is empty".

| Command | 0 | 1 | 2 |
|---|---|---|---|
| `governor` | every selected scenario was **held** | any scenario was **violated** (this outranks 2) | no scenario was violated, but at least one **did not run**; also a bad `--only` name or a bad `--warden` path |
| `prove` | every proof holds | a proof failed | no proofs ran, or `--only` named nothing |
| `run` | the report was produced (without `--fail-on-escape`, an escape is the finding, not an error) | only with `--fail-on-escape`: a warp escaped or a decoy was flagged | a warp could not be built, a bad `--ghost-tools` path, or a `--only` name that matches nothing (with or without `--fail-on-escape`; a typo in a gate never passes) |
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
