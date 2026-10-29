# SWIZZLE

## What this is

SWIZZLE builds small repositories in which a tool that changes code is likely to get something wrong, and then checks, independently of the tool, whether it did. The main target is [`ghost_tools`](https://github.com/wking53214/ghost_tools) (a scanner); `swizzle governor` also attacks Warden, the program that decides whether a change is accepted. It is alpha software written and maintained by one person.

It contains WIZZLE independent verification (`swizzle.wizzle`): physical co-location never grants the target epistemic authority over hidden ground truth.

## How to install and run

You need Python 3.11 or newer and git. SWIZZLE has no runtime dependencies. These commands were run in a fresh virtual environment when this README was written, with the three sibling checkouts at the commits CI tests.

```bash
git clone https://github.com/wking53214/SWIZZLE.git
cd SWIZZLE
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev,cns]'
swizzle --version
swizzle prove
python -m pytest -q
```

- `.[dev,cns]` adds the test tools (`dev`) and the optional CNS contract (`cns`). `pip install -e .` alone is enough to run `swizzle`.
- Without a checkout: `pip install "git+https://github.com/wking53214/SWIZZLE.git"`.
- Do not install `swizzle` or `cns` from PyPI by bare name. Those names on PyPI belong to other projects. Use the checkout or the git URL.
- `swizzle list` and `swizzle prove` need nothing else. `swizzle run`, `swizzle assay` and `swizzle governor` need checkouts of the tools they test. `run` and `assay` find them from a flag, an environment variable or a sibling folder; `governor` needs `--warden PATH`. The `export` line is for the test suite, which reads all three variables:

```bash
git clone https://github.com/wking53214/ghost_tools.git ../ghost_tools
git clone https://github.com/wking53214/ASSAY.git ../ASSAY
git clone https://github.com/wking53214/WARDEN.git ../WARDEN
pip install numpy matplotlib   # ASSAY's verifier skips claims without them
export GHOST_TOOLS=$PWD/../ghost_tools ASSAY=$PWD/../ASSAY WARDEN_ROOT=$PWD/../WARDEN
swizzle run
swizzle assay
swizzle governor --warden ../WARDEN
```

The default branches of those repositories can be ahead of, or different from, the commits CI tests (see "What works"). Without the checkouts the tests that need them skip, and `pytest` still exits 0 (see "Known defects").

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
is constructed. Install the pinned contract (CNS v2.1.0) from a checkout of this repository with
`pip install -e '.[cns]'`, or just CNS with `pip install "cns @ git+https://github.com/wking53214/CNS.git@v2.1.0"`.
The PyPI projects named `swizzle` and `cns` are unrelated to this stack, so install from the checkout or the git
URL, never by bare name. Without CNS a gate raises `CnsNotInstalled`, which names those commands. CNS is never
modified by this package.

Migration note: 0.8.7 moved the pin from `v1.9.0` to `v2.0.0`. The suite, including `Tests/test_cns_adapter.py` and `Tests/test_cns_connector.py`, passed against the installed CNS 2.0.0 on Python 3.11, 3.12 and 3.13. SWIZZLE does not import `cns.stack`, which holds the one change CNS's changelog lists as breaking.

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

Each line names what shows it. "CI" means the `tests` job in `.github/workflows/tests.yml`; a test marked "needs a sibling" skips when the sibling checkout is missing and runs in CI.

- `swizzle prove` runs the 12 planted-defect proofs. Each shows that a planted defect really is a defect. **It does not run Ghost**, so it says nothing about whether Ghost finds anything. That is what `swizzle assay` and `swizzle run` measure. Shown by `Tests/test_proofs.py` (`test_the_defect_is_real`, `test_the_control_still_carries_the_defect`, one pair per warp), `Tests/test_honest_reporting.py::test_prove_footer_says_it_does_not_run_ghost` and `Tests/test_honest_reporting.py::test_prove_that_ran_nothing_exits_2`. The number 12 is held by `Tests/test_readme_claims.py`.
- `swizzle assay` scores Ghost against ASSAY's answer key. The key is checked first; if the checker's own output disagrees with itself (for example "28/29 claims hold"), the key counts as NOT PROVEN even when its exit code is 0. Shown by `Tests/test_honest_reporting.py::test_answer_key_that_disagrees_with_itself_is_not_proven`, `Tests/test_ecosystem_honesty.py` (the floor, the breakdown and the "Ghost did not fully look" cases) and, needing a sibling, the live parts of `Tests/test_assay.py`. CI also runs `python -m swizzle assay` as a report step.
- `swizzle governor` attacks Warden with a list of scenarios (`swizzle governor --list` shows them, and which of Warden's protections defend each). It judges only from files on disk and never decides accept or reject. A scenario counts as held only when Warden ran to the end and gave a readable decision. Shown by `Tests/test_honest_reporting.py::test_a_crashed_warden_is_never_held`, `Tests/test_honest_reporting.py::test_live_sabotaged_warden_is_never_held`, and, needing a sibling, `Tests/test_governor.py::test_live_warden_holds_every_invariant`.
- The optional CNS connection (section 2b). Shown by `Tests/test_cns_adapter.py` and `Tests/test_cns_connector.py` (they need the `cns` extra, which CI installs) and `Tests/test_cns_independence.py` (it blocks `cns` and runs everywhere, to show SWIZZLE works without it).
- The test suite: `python -m pytest -q` from a checkout (`pip install -e '.[dev,cns]'`). No pass count is written here, because a number in a README drifts (`Tests/test_ci_config.py::test_readme_does_not_hard_code_a_pass_count` fails if one is added); the suite prints its own.
  - **What CI runs** (`.github/workflows/tests.yml`): the full suite on CPython 3.11, 3.12 and 3.13, with ghost_tools, ASSAY and WARDEN checked out beside this repository at pinned full commit SHAs (the last set this repository's CI tested on its own: ghost_tools 1.10.6, ASSAY 0.11.2 and WARDEN 0.13.8, each version also in a comment next to its pin; a pin may sit behind that repository's branch head, and it is not moved when a sibling moves; the whole-stack check that the set the circuit lands on works together is the `stack` job in the CNS repository, not this workflow), every action pinned by commit SHA with its release tag in a comment, `GHOST_TOOLS`, `ASSAY` and `WARDEN_ROOT` set to them, the `cns` extra installed, which is pinned to the CNS tag `v2.1.0` (the tag spelling, shared by every repository in the circuit, which peels to `fde931ffa89aebec95647742256ad53033bd3d02`), and `numpy` and `matplotlib` installed at exact versions (`matplotlib==3.11.2` everywhere; `numpy==2.4.6` on Python 3.11 and `numpy==2.5.4` on 3.12 and 3.13, chosen by environment markers because numpy 2.5 requires Python 3.12 or newer), because ASSAY's verifier skips claims without them and exits 1. None of those steps is `continue-on-error`, so a sibling that cannot be fetched fails the job instead of silently skipping the live tests. A separate `static` job runs `ruff check .` and `mypy`. A separate, clearly named `siblings-latest` job runs the suite against each sibling's default branch; it never blocks. The workflow's shape is held by `Tests/test_ci_config.py`.
  - **Without siblings** the tests that need them skip cleanly (`GHOST_TOOLS` unset: `Tests/test_against_ghost_buster.py`, the live parts of `Tests/test_assay.py`; `WARDEN_ROOT` unset: the live attacks in `Tests/test_governor.py`, `Tests/test_honest_reporting.py`, `Tests/test_cns_connector.py`). `pytest -rs` lists what skipped and why. Without the `cns` extra, `Tests/test_cns_connector.py` and one test in `Tests/test_cns_adapter.py` skip; `Tests/test_cns_independence.py` blocks `cns` and runs everywhere.
  - **Governor temp folders.** `Tests/test_honest_reporting.py` checks that the governor leaves no `swizzle-governor-*` folder behind. It does that against a private temp root, because the system temp folder is shared with any other SWIZZLE run on the machine and comparing it before and after used to fail whenever one ran at the same time.
- Static gates: `ruff check .` (rules E, F, W, B; line length 120, with the one data file `swizzle/governor/scenarios.py` excepted) and `mypy` (the `swizzle` and `tools` packages, with `check_untyped_defs`; no `# type: ignore` in the source). Test modules are not type-checked (see the comment in `pyproject.toml`). Shown by the CI `static` job, `Tests/test_ci_config.py::test_static_gates_are_run` and `Tests/test_typing_regressions.py::test_mypy_gate_is_declared_in_pyproject`.

### Version, contract, logging, and where files are written

- **Version.** `pyproject.toml` is the only place a version is declared. `swizzle --version`, `swizzle.__version__` and the `swizzle.version` field of corpus records read it back through the installed package metadata (falling back to `pyproject.toml` in a plain checkout, and to `0+unknown` rather than a made-up number). `Tests/test_version_identity.py` fails if they differ. History is in `CHANGELOG.md`. Releases are tagged by the owner, so check the repository's tags and releases for what exists.
- **Contract for callers.** `swizzle --contract` prints JSON naming a `contract` number, the SWIZZLE version, and the exit codes and fields of the commands Warden runs as subprocesses (`prove`, `governor --json`, `assay --json`). A caller can assert on `name` and `contract` before trusting any output. See `docs/CONTRACT.md`. Held by `Tests/test_contract.py`.
- **Logging.** Diagnostics use the standard `logging` module and go to stderr only. `swizzle -v` shows progress, `-vv` shows every subprocess; `$SWIZZLE_LOG_LEVEL=DEBUG` does the same. Without it SWIZZLE prints no log lines, and as a library it stays silent unless you configure logging. Held by `Tests/test_logging.py`.
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

The governor scenarios for newer Warden checks (protected bookkeeping and CI files, a symlink into a protected file, a dirty-folder start, SIGTERM mid-apply) are reported as not run, marked "skipped", against a Warden that predates them (probed in Warden where it can be; where the probe does not show the check, by version: a Warden older than 0.9.0 is treated as lacking it, and 0.9.0 is only the label `NEW_CHECKS_SINCE` in `swizzle/governor/scenarios.py`, not a measured release boundary; the Warden CI tests, 0.13.8, is newer, and in the recorded self-hosting run the governor held all 28 scenarios); `--assume-new-checks` judges them anyway. A Judge that raises must leave no change standing; a Warden that leaves it is VIOLATED.

`assay` without `--floor` prints "no floor set, exit 0 only means the key was scored". Exit 0 does not mean Ghost did well. Use `--floor N` to make it mean that. An explicit `--assay PATH` or `--ghost-tools PATH` that is wrong is an error; a sibling checkout is used only when you did not give the option, and the output names the checkout it used.

### What does not work, and what is not proven

- **A green CI run does not mean Ghost or Warden is good.** The CI steps `python -m swizzle run` and `python -m swizzle assay` never gate on the score ("escapes are the finding, not the error"), and the governor step accepts exit 1 (a violated scenario) so that a finding in Warden is not a SWIZZLE failure (`|| [ $? -eq 1 ]` in the workflow). They fail only when the run itself cannot happen. What the numbers were on a given day is in `docs/IMPLEMENTATION_STATUS.md`.
- **The measurements in `docs/IMPLEMENTATION_STATUS.md` are dated and were taken by hand.** The inventory counts (warps, mutators, seed cases, governor scenarios) were re-counted for SWIZZLE 0.8.8 and `Tests/test_readme_claims.py::test_the_inventory_in_the_implementation_status_is_the_code_s` holds them. The attack results against Ghost are labelled in that file with the versions they were measured at (ghost_tools 1.10.5, with one spot check against 1.10.6) and are not re-measured; nothing holds them and CI does not re-measure them.
- **The only targets CI exercises are ghost_tools (through `swizzle run` and `swizzle assay`) and Warden (through `swizzle governor`).** Fitness is lab-defined; transfer to "all autonomous coding agents" is a claim, not a measured one. The pydantic v2 adapter has tests but no recorded run against a real migration tool. Requires ability to materialize sandboxes. CI `swizzle-gate` is the production-shaped use: fail if a case that passed now fails worse.
- **Three governor scenarios have two protections each**, so removing just one protection leaves the scenario held: `removal_reached_by_name` (keep test and the suite check), `config_weakened` (protected-file list and the suite check), `edit_escapes_target` (two path checks). The first two now have companion scenarios (`removal_invisible_to_suite_after`, `config_change_keeps_pass_count`) that leave only one protection standing; each was checked by removing that one protection from a copy of Warden. **`edit_escapes_target` has no companion.** Its two checks both resolve the same path, and separating them would mean reaching into Warden's internals. This is a known gap.
- **Warden's newer checks are decided by version where a probe cannot show them.** Governor scenarios for checks an older Warden lacks are reported as not run, marked "skipped" (see the exit-code section). The version floor, `NEW_CHECKS_SINCE = "0.9.0"`, is a fallback label chosen when the scenarios were written; nothing checks that Warden 0.9.0 really has those checks. `Tests/test_governor_red_team.py` holds the comparison, not the history.

### Known defects

These are open. Each is real as of this version; none has a fix scheduled in this README.

1. **A crashing Warden is reported "not run", even where the crash would itself be the finding** (`ghost_unreachable`). The crash text is printed, but it is not scored as a violation.
2. **The suite does not fail on a skip.** With no sibling checkouts, or without the `cns` extra, tests skip and `pytest` exits 0. A local green run without the siblings proves less than the CI run. CI prints skips (`-rs`), but nothing fails the build if a skip appears. (In 0.8.5 a test was skipped on every machine for a missing dev dependency and nothing flagged it; see the ledger.)
3. **`translate_verdict` stamps every result `ALPHA`, though a warp verdict judges a scan that has already run.** It is left as it is because changing it would change what existing callers receive.
4. **Governor attacks were reported as "not run" under heavy machine load in two audit runs, and the cause was not found.** I have not reproduced it and this repository has no test or log of it. The effect is safe: a scenario that did not run ends exit 2 and is never counted as held (`Tests/test_honest_reporting.py::test_a_crashed_warden_is_never_held`).
5. **Targets run with your permissions.** The lab sandbox (`swizzle/lab/sandbox.py`) refuses writes outside its own directory and kills what it started, but it is not an operating-system jail: a target that decides to write elsewhere is not stopped, only noticed. `Tests/test_lab_sandbox.py` tests what it does guarantee; `docs/SECURITY.md` says what it does not. The governor runs Warden's code in a subprocess inside a temporary folder and has the same limit.
6. **The CI tested set can fall behind.** Sibling commits are bumped by hand. `Tests/test_ci_config.py` checks that the pins are full commit SHAs and that the README names the versions in their comments, not that they are the siblings' newest. The `siblings-latest` job reports drift but never fails the build.
7. **The CNS package name `cns` on PyPI belongs to another project.** SWIZZLE pins CNS by git URL, so only installing `cns` by bare name goes wrong. Renaming the CNS distribution is deferred by the owner and is not done here.
8. **The no-shell check does not follow every way to reach a subprocess call.** It resolves `import subprocess`, `import subprocess as x`, `from subprocess import run` and a simple `name = subprocess.run` assignment. A call reached through `getattr`, `importlib` or `exec` is not followed. The source has none, and `Tests/test_wizzle_subprocess_safety.py` would not notice a new one.

### What broke and how it was fixed

Newest last. "Guard" is the test that fails if the defect comes back; "no test yet" means I found none. Entries marked with a date and no version are from before the version was bumped for them; the CHANGELOG lists them under "0.7.1 and earlier".

- **2026-09-12 (during the 0.2 to 0.7 work, no version recorded).** The evaluator blamed targets for things it did itself. Re-running the catalogue against a Ghost that had fixed its findings showed three bugs. SWIZZLE's own mid-run edit was diffed as if the target had made it. A case could demand a file both change and not change, so a target that did what it was authorised to do was reported. The differential called a fix that turned a HIGH finding into a LOW one a regression. Found by re-running against the fixed target. Guards: `Tests/test_lab_self_adversarial.py::test_swizzles_own_mid_run_edit_is_not_the_targets_fault`, `::test_a_case_cannot_demand_a_file_both_change_and_not_change`, `::test_no_seed_case_contradicts_itself`, `Tests/test_lab_differential.py::test_a_high_becoming_a_low_is_an_improvement_not_a_regression`.
- **0.7.1 (2026-09-12).** The harness knew a secret it never told the target. A changelog document rendered like an ordinary README, ground truth protected its claim anyway, and a search filed false CRITICAL findings, each backed by two oracles that read the same wrong premise. Found by building the world and reading the file. Guard: `Tests/test_lab_legible_ground_truth.py::test_a_kind_that_forbids_a_rewrite_is_visible_in_the_file`; a refusal must also name evidence in the rendered bytes (`Tests/test_lab_witness.py`).
- **2026-10-09 (no version).** A Warden that crashed could be judged "held", because the files it left unchanged looked like a protection that worked. The governor now calls a scenario held only when Warden ran to the end and gave a readable decision. In the same change `swizzle assay` stopped trusting an answer key whose own output said K of M with K not equal to M. Guards: `Tests/test_honest_reporting.py::test_a_crashed_warden_is_never_held`, `::test_answer_key_that_disagrees_with_itself_is_not_proven`.
- **2026-10-09 (no version).** SWIZZLE read only a bare JSON list from `ghost_buster --json`. When Ghost changed its output to an object, every scan against the current Ghost failed with "no JSON". Both shapes are read now, and exit 3 is a Ghost crash. Guard: `Tests/test_reading_ghost_output.py::test_an_object_reads_as_its_findings`.
- **2026-10-11 and 2026-10-12 (no version).** Warden began holding unverified changes instead of applying them, and the governor's over-caution checks, which expected the change to be applied, failed. After the probe was fixed, three over-caution tests still failed because the stand-in Warden in the test file had no held-result rule, so the governor reported a violation that was the stand-in's fault. The stand-in now models the held rule only when a test asks for it, and the clean-repository twin's bad check refuses every start, as its name says. Against the real Warden main all three scenarios reported held. Guards: `Tests/test_governor_red_team.py::test_clean_repository_twin_catches_a_dirty_check_that_refuses_everything` and `::test_the_hidden_prose_twin_catches_a_fix_that_protects_every_dotfile`.
- **2026-10-13 (no version).** The `ghost_unreachable` attack treated any decision outside a fixed list as "carried on as if nothing was wrong". A held result (Warden puts the tree back and stores the change) and a Judge rejection were reported as violations, and the Drafter's full-gate tests were rejected because of it. The attack now judges by the tree: a held result is clean only if the tree is unchanged. Guard: `Tests/test_governor.py::test_ghost_attack_accepts_a_held_result_only_when_the_tree_was_put_back`.
- **2026-10-08 (no version).** Some of this repository's own tests passed when the code under them was broken, or their assertions never ran (Ghost's mutation check found them). They were made able to fail. No single guard; the repaired tests are in `Tests/test_catalogue.py`, `Tests/test_lab_standing.py` and `Tests/test_oracle_library.py`, among others.
- **0.8.0 (2026-10-17).** `swizzle --version` printed 0.4.0 while `pyproject.toml` said 0.7.1, so every corpus record carried the wrong version. The version now has one source. Guard: `Tests/test_version_identity.py::test_cli_version_dunder_version_and_pyproject_agree`.
- **0.8.0.** Several call sites used `shell=True` with paths pasted into the command, so a path with spaces, quotes or `;` was not inert. They use argument lists now. Guards: `Tests/test_wizzle_subprocess_safety.py::test_no_shell_true_anywhere_in_the_source` and `::test_history_generator_builds_a_repository_at_a_hostile_path`. (The first guard was a text search for `shell=True` and was found to be passable in 0.8.8, see below.)
- **0.8.0.** `HistoricalUsageOracle` ended its git command with `|| echo ''`, so a git failure looked like an empty history. A git failure is now an unmeasured oracle. Guard: `Tests/test_wizzle_subprocess_safety.py::test_a_git_failure_is_an_unmeasured_oracle_not_an_empty_history`.
- **0.8.0.** The governor runner left `/tmp/swizzle-governor-*` folders behind when a straggler process wrote into the folder while it was removed, and the test that compared the shared temp folder before and after failed whenever another SWIZZLE run was on the machine. Removal is retried and the test uses a private temp root. Guards: `Tests/test_governor_cleanup.py::test_remove_tree_retries_while_a_straggler_keeps_writing`, `::test_a_straggler_that_left_the_probe_group_does_not_wedge_the_runner_or_leak_the_folder`.
- **0.8.0.** Several code paths crashed or returned the wrong type: a finding type that does not exist (`BOUNDARY_VIOLATED`) was handled in three places, `trigger_triage_event` indexed a dict with `[-1]`, the orchestrator bundle raised `TypeError` when a triage ledger was set, a timed-out sandbox command could return bytes, the scenario report crashed on an escaped warp with no proof, and `swizzle attack --json` and every corpus record failed for any case whose claim carries a witness. Ruff and mypy were first run as gates in this release and had many findings. Guards: `Tests/test_typing_regressions.py`, `Tests/test_typing_regressions.py::test_every_seed_cases_ground_truth_is_json_serialisable`, and the CI `static` job.
- **0.8.0.** CI sibling checkouts were `continue-on-error`, so a sibling that could not be fetched silently skipped the live tests, and README claims about test counts did not describe what CI ran. The checkouts are pinned and blocking. Guard: `Tests/test_ci_config.py::test_nothing_that_blocks_is_continue_on_error`.
- **0.8.1 (2026-10-17).** `swizzle verify DIR` exited 0 and printed a table for a `DIR` that does not exist, `swizzle corpus --corpus-dir DIR` exited 0 with "the corpus is empty" for a missing folder, and a bare `swizzle` exited 0. They exit 2 now. The module `swizzle.integration.test_track`, whose name matched the pattern tools use for test files, shipped in the wheel under that name and was renamed. The CI pin comments for ghost_tools and ASSAY named an old tag when the pinned commits were many commits past it (the comments now give the sibling's version; no test checks that wording). Guards: `Tests/test_cli_fail_closed.py::test_verify_refuses_a_directory_that_does_not_exist`, `::test_corpus_refuses_a_named_directory_that_does_not_exist`, `::test_bare_swizzle_is_a_usage_error`, `Tests/test_packaging.py::test_the_wheel_ships_no_test_files_and_every_declared_package`.
- **0.8.2 (2026-10-21).** The 0.8.1 fix was incomplete: only `corpus` refused a missing `--corpus-dir`. `history`, `knowledge`, `handoff list`, `handoff propose`, `report --bucket`, `diff`, `standing` and `holdout` still exited 0 with an empty result. `handoff list` also created `./handoff/` and ignored `--corpus-dir`. All now exit 2 and write nothing. Guards: `Tests/test_cli_fail_closed.py::test_every_corpus_reader_refuses_a_named_directory_that_does_not_exist`, `Tests/test_no_surprise_writes.py::test_handoff_list_reads_the_named_corpus_folder_and_writes_nothing`.
- **0.8.2.** CI went red on Python 3.11: an unmarked `numpy==2.5.4` cannot install there (numpy 2.5 needs 3.12 or newer), so ASSAY's verifier lacked numpy and `swizzle assay` exited 2. The test that checked the install line asserted the exact string, so it had locked the bug in. numpy is pinned per interpreter with environment markers, and the test now checks the policy instead. Guard: `Tests/test_ci_config.py::test_every_job_that_runs_the_suite_installs_the_assay_verifier_dependencies`.
- **0.8.4 (2026-10-21).** The CNS pin was a full commit while the other repositories spelled it as a tag, and pip treats the two as different sources. It is now the tag spelling, the same in every repository. (0.8.7 moves it to `v2.0.0`; 0.8.10 moves it to `v2.1.0`.) Guard: `Tests/test_cns_independence.py::test_the_cns_extra_is_pinned_to_the_v2_1_0_tag`.
- **0.8.5 (2026-10-21).** A test (`Tests/test_typing_regressions.py::test_the_pydantic_scan_reports_one_mapping_per_file`) was skipped on every machine because `libcst` was in no extra. `libcst` is pinned in the `dev` extra and a test fails if it stops being. The measurements in `docs/IMPLEMENTATION_STATUS.md` were also stale and were re-taken. Guard: `Tests/test_ci_config.py::test_libcst_is_pinned_in_the_dev_extra_so_the_pydantic_scan_test_runs`.
- **0.8.6 (2026-10-22).** `swizzle run --only NAME` with a name that matches nothing printed "0 of 0" and exited 0, also with `--fail-on-escape`, so a typo in a CI gate passed. It exits 2. `STACK.md` called CNS private; it is public. The install hints told the reader to install `swizzle[cns]` from PyPI, which installs an unrelated package. Guards: `Tests/test_cli_fail_closed.py::test_run_refuses_an_unknown_only_name`, `Tests/test_docs_install_hints.py::test_no_doc_calls_cns_private`, `::test_no_user_facing_install_hint_names_a_bare_pypi_distribution_of_this_stack`.
- **0.8.8 (2026-10-24).** The guard against `shell=True` (0.8.0, above) searched the source for those words, so `kw = {"shell": True}; subprocess.run(c, **kw)` passed it. Found by the round-6 independent audit, 2026-10-23 and 2026-10-24. The test now reads the parsed source and rejects a `shell` that is not the constant `False`, a `**` unpacking into a subprocess call that cannot be shown to omit it, and the calls that always use a shell. Guards: `Tests/test_wizzle_subprocess_safety.py::test_the_shell_check_rejects_every_spelling` and `::test_a_mutated_copy_of_the_source_fails_the_scan_in_both_spellings`.
- **0.8.8 (2026-10-24).** Several sentences were stale or false: the CI sibling pins were described as if they were each sibling's newest commit on `main`, the newer Warden checks were said to arrive at one fixed release, 0.9.0 (the constant is only a fallback label, and the Warden CI tests is 0.13.8), the self-hosting paragraph said no run was recorded after one was, and `docs/IMPLEMENTATION_STATUS.md` carried figures with no statement of what they were measured at. Found by the same audit. Guards: `Tests/test_readme_claims.py::test_no_sentence_that_has_gone_stale_is_left_in_the_documents_or_the_workflow`, `::test_the_tested_set_is_described_as_what_this_repository_tested_not_as_the_siblings_heads`, `::test_the_version_floor_is_described_as_a_label_not_a_measured_release`, `::test_the_self_hosting_paragraph_states_the_recorded_run_and_what_it_does_not_mean` and `::test_the_inventory_in_the_implementation_status_is_the_code_s`.
- **0.8.9 (2026-10-28).** The self-hosting paragraph quoted the test counts of run 2, which drift as the suite grows, so the circuit's drift check flagged this README as stating a count the tree contradicts and the finisher could not finish the repository. Found by self-hosting run 3 (2026-10-24). The paragraph now names the record file that holds the counts and quotes none. Guard: `Tests/test_readme_claims.py::test_the_self_hosting_paragraph_states_the_recorded_run_and_what_it_does_not_mean`, updated to assert that the sentence names the record and holds no bare count.
- **0.8.9 (2026-10-28).** CI went red on the first push of 0.8.9 (run 40785126388): the `dev` extra allowed any pytest from 8 up, so CI installed pytest 9.2.0, and pytest-benchmark 5.3.0, the newest release, fails on it (`'Function' object has no attribute '_nodeid'`), so the three benchmark tests errored at setup in every job that runs the suite. Nothing in this repository's code changed. Guard: the `dev` extra in `pyproject.toml` is `pytest>=8,<9.2`, which pip resolves to a pytest this repository's benchmark tests were run green on (9.1.1); no test holds the constraint, so a newer pytest or pytest-benchmark release is not tried until the bound is raised by hand.

### Self-hosting

The whole circuit has been run on a clone of this repository. The record is the CNS repository's `docs/evidence/SELFHOSTING_2026-10-23.md` (on the CNS branch `claude/horsemen-production-status-5wsndb` until that branch is merged), with the run records beside it in that repository. It covers SWIZZLE 0.8.7 at commit `3f35dad5568b590c2ee36e60533d50a35db94aa2`, run on 2026-10-22 and 2026-10-23 with scope `documentation`. Run 1 ended FINISH_REJECTED: the finisher (Burnish 0.3.11) wrote the suite's test count into this README, the suite then had 1 failure, and Warden put the change back. The record gives counts only; the failing test was identified afterwards by reproducing the finisher's text outside Warden, and it is `Tests/test_ci_config.py::test_readme_does_not_hard_code_a_pass_count`. That was a defect in Burnish, fixed in Burnish 0.3.12, not a defect found in this repository's code. Run 2 ended ACCEPT (exit 0) with a green suite. The pass and skip counts are in `SWIZZLE.run2.json` in that repository's `docs/evidence/selfhosting-records-2026-10-23/` and are not quoted here, because a count written into this README drifts as the suite grows (the skip reasons are inferred, not recorded: tests that need the sibling checkouts or their environment variables, which were not set in that run). The record also shows 7 Ghost checks declined and recorded as gaps (mutate, kernel, structure, tests, project, secrets, correlate), and 215 Ghost findings still standing, none new.

What the record does not mean. ACCEPT here carries those 7 gaps: it does not mean the repository has no secrets or no weak tests, and it does not mean the 215 standing findings are resolved. It covers commit 3f35dad only, not the commits after it. The run 2 record also names the finisher as Burnish 0.3.11 although 0.3.12 ran, because Warden took the seat's version from the pip install record, not from the checkout that ran; the audit found this, and Warden's README says where that stands. The numbers above are copied into `Tests/test_readme_claims.py` from that evidence file, so the README cannot drift from them without a test failing. The earlier runs of 2026-10-14 and 2026-10-15 (Warden's `docs/REGISTRY.json`, rows 5 and 6, SWIZZLE 0.7.1) predate the current rules and are superseded by this record.

### Ceilings code cannot fix

- The repository is young. Its first commit is dated 2026-09-12.
- It has one human maintainer.
- It has no outside users that I can point to, so nobody but its author has tried it on a repository of their own.
- Releases are tagged by the owner, so check the repository's tags and releases for what exists. This README does not list them, because a list goes stale.

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
