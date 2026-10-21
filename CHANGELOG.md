# Changelog

All notable changes to SWIZZLE are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow the
`version` in `pyproject.toml`, which is the only place a version is declared:
`swizzle.__version__`, `swizzle --version` and the `swizzle.version` written into corpus records
all read it back through the installed package metadata (`swizzle/_version.py`).

Dates are taken from the git history. Where the history carries no release, the change is listed
under the first version that contains it.

## [Unreleased]

## [0.8.5] - 2026-10-21

### Changed
- CI tested set: Warden moved from `36e98433f4928b7d12905f02b56e55ee1943b56e` (0.13.4) to
  `1636e1a21f124eedbf6e158db95dc75344f4308d` (0.13.7, not tagged), and ghost_tools from
  `aa72c38294acac1da4c32a2752f0db58e2b07248` (1.10.3) to `c2ada82d2f6c0404074a668ba749c7872743aad9` (1.10.5). ASSAY stays
  `54248beb5a36600f69de7c816cb2271dda20a879` (0.11.2) and the CNS pin stays the `v1.9.0` tag. The workflow comments, the
  README CI paragraph, the `docs/IMPLEMENTATION_STATUS.md` header and `Tests/test_ci_config.py` name the new set
  (`test_the_tested_set_is_the_current_known_good_one` asserted the old versions and SHAs and now asserts the new ones; nothing else
  about it changed).
- `libcst==1.9.0` is added to the `dev` extra. `Tests/test_typing_regressions.py::test_the_pydantic_scan_reports_one_mapping_per_file`
  imports libcst with `pytest.importorskip` and had been skipped everywhere because nothing installed it. It now runs and
  passes (the test is unchanged). With the siblings at the pinned set the suite is 1360 passed, 0 skipped on Python 3.11, 3.12
  and 3.13. A new test in `Tests/test_ci_config.py` fails if libcst stops being pinned in the dev extra.
- `docs/IMPLEMENTATION_STATUS.md` "Current state" is re-measured on 2026-10-21 against ghost_tools 1.10.5 (it was
  2026-10-17, ghost_tools 1.9.1): 12 warps (12 of 12 proofs hold), 28 mutators, 25 seed cases, 28 governor scenarios, and the seed
  catalogue against Ghost (25 cases, 0 broken, 0 critical, 10 reproduce, 8 HIGH and 2 LOW, corroboration 0 of 10) are the
  same; the test count is 1360 (it was 1308). The file says which commands were run and that no ASSAY or governor pairing
  number is recorded.
- Version 0.8.5 (`pyproject.toml`, the `swizzle_version` example in `docs/CONTRACT.md`, the `docs/IMPLEMENTATION_STATUS.md` header).

## [0.8.4] - 2026-10-21

### Changed
- The CNS pin is spelled as the tag: the `cns` extra is now
  `cns @ git+https://github.com/wking53214/CNS.git@v1.9.0`, which peels to
  `da18e411743d4e3b0e783105394d845fb1c16746`. It was that full commit. Every repository in the circuit now spells the
  pin the same way, because pip treats a tag URL and a commit URL as two sources. The README and the workflow header
  say so. `Tests/test_cns_independence.py` and `Tests/test_ci_config.py` asserted the commit spelling and now assert the
  tag spelling (each test is renamed from `..._commit` to `..._tag`).
- CI tested set: ASSAY moved from `01c713a316dc0513d30e566fffe4d94536888e81` to `54248beb5a36600f69de7c816cb2271dda20a879`
  (still 0.11.2; ASSAY's `main`). The ASSAY ref in `.github/workflows/tests.yml`, `Tests/test_ci_config.py` and
  `docs/IMPLEMENTATION_STATUS.md` name it.

## [0.8.3] - 2026-10-21

Merges `origin/main` into the production-status branch: the other session's CNS v1.9.0 move and its numpy and
matplotlib install for ASSAY's answer key, reconciled with this branch's pin policy.

### Changed
- Merged `origin/main` (`b9b1186`: `cb5b2f9` "Move the CNS pin from v1.8.0 to v1.9.0" and `6567fb0` "CI: install numpy
  and matplotlib for ASSAY's answer key") with a real merge commit. The CNS pin stays a full commit, never the tag URL
  (pip treats the tag URL and the commit URL as two sources): the `cns` extra, `Tests/test_cns_independence.py`, the
  README and this log name `da18e411743d4e3b0e783105394d845fb1c16746` (CNS v1.9.0). The other session's bare
  `pip install numpy matplotlib` is not taken: CI keeps its per-interpreter exact pins (`numpy==2.4.6` below Python
  3.12, `numpy==2.5.4` from 3.12, `matplotlib==3.11.2`), because numpy 2.5.4 does not exist for Python 3.11. Its intent
  is kept and now recorded in the workflow comment: since ASSAY #21 an ASSAY claim that cannot run (the solvar cleanup
  specimen needs both libraries) is a failure, not a skip.
  `Tests/test_cns_independence.py::test_the_cns_extra_is_pinned_to_the_v1_9_0_commit` is renamed from `..._v1_8_0_...`.
- CI tested set: ASSAY moved from `7b781cf9cb2bbc3748aaff4343d778c64dc20d8c` (0.11.1, a commit that is now off ASSAY's
  `main`) through `b6b1ccf1feb39993e50d38b875cd52ff0bd38039` (0.11.2, the squash-merge commit of the ASSAY work, tree
  identical to that work's branch head `023589f`) to `01c713a316dc0513d30e566fffe4d94536888e81` (still 0.11.2; ASSAY's
  `main` with its own `cns` extra moved to the same CNS v1.9.0 commit). ghost_tools moved from
  `5d7a38638b12a75b25c84ab3652e4774acb9aa10` (1.10.1) to `aa72c38294acac1da4c32a2752f0db58e2b07248` (1.10.3); the full
  suite, the four CI report steps, ruff and mypy pass with it on Python 3.11, 3.12 and 3.13. Warden stays at
  `36e98433f4928b7d12905f02b56e55ee1943b56e` (0.13.4). The README, `docs/IMPLEMENTATION_STATUS.md` and
  `Tests/test_ci_config.py` name the new tested set.
- CI tested set: WARDEN moved from `580f659336818b4a5a2c0ca235d2344012536426` (Warden 0.13.3) to
  `36e98433f4928b7d12905f02b56e55ee1943b56e` (Warden 0.13.4). Warden 0.13.4 requires instrument roots to be git
  checkouts with a readable version and refuses site-packages roots; the CI checkout is a git checkout, so the governor
  attacks, `--contract` and the Warden-dependent tests run against it unchanged. ghost_tools
  `5d7a38638b12a75b25c84ab3652e4774acb9aa10` (1.10.1) and ASSAY `7b781cf9cb2bbc3748aaff4343d778c64dc20d8c` (0.11.1) stay.
  The README, `docs/IMPLEMENTATION_STATUS.md` and `Tests/test_ci_config.py` name the new tested set.

## [0.8.2] - 2026-10-21

### Changed
- CI tested set moved to the siblings that carry the `--contract` check: WARDEN `580f659336818b4a5a2c0ca235d2344012536426`
  (Warden 0.13.3, was 0.12.0 at `2cf0eec`), ghost_tools `5d7a38638b12a75b25c84ab3652e4774acb9aa10` (1.10.1, was 1.10.0)
  and ASSAY `7b781cf9cb2bbc3748aaff4343d778c64dc20d8c` (0.11.1, was 0.11.0). The comments next to each pin give the true
  version. The README sentence naming the tested set is updated.
- CI installs numpy and matplotlib before the ASSAY-dependent tests and steps, because ASSAY 0.11.1 exits 1 on a skipped
  claim and its verifier skips claims without them: `matplotlib==3.11.2` everywhere, `numpy==2.4.6` on Python 3.11 and
  `numpy==2.5.4` on 3.12 and 3.13, selected by environment markers.
- `Tests/test_ci_config.py` now also checks that the pins' version comments and the README's tested set agree, and that
  every job that runs the suite installs numpy and matplotlib at exact versions, with exactly one numpy pin applying on
  each Python the job uses and that numpy release supporting that Python.

### Fixed
- CI regression: an unmarked `pip install numpy==2.5.4` in every matrix job could not install on Python 3.11 (numpy 2.5
  requires Python 3.12 or newer), so the 3.11 job lacked numpy and `Tests/test_assay.py` failed (`swizzle assay` exit 2).
  numpy is now pinned per interpreter. The test that asserted the exact install string, and so locked the bug in, now
  asserts the policy instead.
- Every command that reads the corpus now exits 2 with the reason when the folder named with `--corpus-dir` does not
  exist, is not a directory or cannot be read, through one shared check. Only `corpus` did before; `history`,
  `knowledge`, `handoff list` and `handoff propose`, `report --bucket`, `diff` (without `--seeds`), `standing` (without a
  case) and `holdout` (without `--freeze`) exited 0 and printed an empty result. The default location may still be absent.
- `swizzle handoff list` no longer creates `./handoff/`: opening a `Handoff` touches nothing and the folders are made
  by the first write. It also no longer ignores `--corpus-dir`: unless `--handoff-path` is given, lessons live in
  `handoff/` inside the named corpus folder (with the default corpus the location is still `./handoff`).
  `Tests/test_no_surprise_writes.py` covers it.
- `docs/IMPLEMENTATION_STATUS.md` header: the stale SWIZZLE and Warden versions are refreshed, and the 2026-10-17
  measurements are labelled as dated.

## [0.8.1] - 2026-10-17

A cleanup pass on the 0.8.0 hardening, driven by an independent re-audit.

### Changed
- `swizzle` with no command now prints usage on standard error and exits 2 (it exited 0). `--help`,
  `--version` and `--contract` still exit 0.
- CI pins every GitHub Action by full commit SHA with its release tag in a comment (`actions/checkout`
  v4.2.2, `actions/setup-python` v5.6.0).
- CI sibling pins are the "tested set": ghost_tools `288cefa7608cace8be0f91cabcc305930466d84b`
  (ghost_tools 1.10.0) and ASSAY `5aafbf3b45c68d0948574ff4364cde614890839e` (ASSAY 0.11.0). Warden stays at
  `2cf0eeccf839f88d624deb133fe1cb4b16a99009`; it is re-pinned separately. The tested set may sit commits
  behind each repository's head, and the workflow header says how to bump it.
- `swizzle.integration.test_track` is renamed `swizzle.integration.experiment_track` (class `TestTrack` is now
  `ExperimentTrack`). It is a library module, but its name matched the `test_*.py` pattern that tools use to
  recognise a test file, and it shipped in the wheel under that name. There is no alias at the old path
  (an alias file would reintroduce the name). The wheel test no longer has an allowed exception for it.
- `swizzle.integration.ml_predictor` (the aliases kept from the `frequency_predictor` rename) now raises a
  `DeprecationWarning` when imported. The names keep working.
- Tests changed because the behaviour they asserted changed on purpose: `Tests/test_lab_cli.py`
  `test_corpus_on_an_empty_directory` and `test_corpus_json_is_json` named a corpus folder that did not exist
  and expected "empty"; they now create the empty folder first. `Tests/test_continuous_loop.py` imports the
  renamed `ExperimentTrack`. `Tests/test_packaging.py` drops its `test_track.py` exception.
  `Tests/test_lab_cli.py::test_no_command_prints_help` (now `..._and_is_a_usage_error`) expects exit 2 and usage on
  standard error. `Tests/test_no_surprise_writes.py::test_corpus_dir_is_accepted_...` creates the named empty
  folder first and asserts reading leaves it empty.

### Fixed
- `swizzle verify DIR --member ... ` exited 0 and printed a table of UNASKABLE oracle results for a `DIR` that
  does not exist. It now exits 2 with a message for a missing, non-directory, unreadable or empty `DIR`. An
  empty directory is refused because no oracle has anything to look at; a non-empty folder the oracles cannot
  judge is still a result (UNASKABLE, exit 0).
- `swizzle corpus --corpus-dir DIR` (or `--corpus-path`) exited 0 with "the corpus is empty" for a `DIR` that
  does not exist or is not a directory (for example `/dev/null/x`). A named corpus folder that cannot be read
  now exits 2. The default `./corpus` may be absent, since nothing has written it yet, and still reads empty.
- The CI pin comments for ghost_tools and ASSAY said `# v0.10.0`, but the pinned commits were 13 and 8 commits
  past that tag. The comments now give the sibling's version at the commit and say it is a tested set.
- The tag note below now says what is true: see "Notes for the owner".

## [0.8.0] - 2026-10-17

This release is a production-hardening pass. It is also the first version that is true to itself:
until now `swizzle --version` printed `0.4.0` while `pyproject.toml` said `0.7.1`, and every corpus
record carried the wrong version.

### Added
- `swizzle --contract`: a JSON document naming the contract number (`contract`), the SWIZZLE version,
  the commands Warden runs as subprocesses (`prove`, `governor --json`, `assay --json`), their exit
  codes and the fields of a governor finding. Documented in `docs/CONTRACT.md` and tested in
  `Tests/test_contract.py`. A caller can assert `contract == 1` before it trusts any output.
- `swizzle -v` / `-vv` and `$SWIZZLE_LOG_LEVEL`: diagnostics through the standard `logging` module,
  to stderr only. Library use stays silent unless the caller configures logging.
- `--corpus-dir` (alias of the older `--corpus-path`) on every command that reads or writes the attack memory.
- `ruff` (E, F, W, B) and `mypy` configuration in `pyproject.toml`, and both as gates in CI.
- Python 3.13 in the CI matrix.
- Tests: `Tests/test_version_identity.py`, `test_contract.py`, `test_wizzle_subprocess_safety.py`,
  `test_no_surprise_writes.py`, `test_typing_regressions.py`, `test_governor_cleanup.py`, `test_logging.py`
  and `test_ci_config.py` (the workflow pins every sibling to a full SHA and carries no `continue-on-error`
  on a blocking step), plus a wheel-contents check in `test_packaging.py`.
- `docs/CONTRACT.md` and `CHANGELOG.md`.

### Changed
- The version is resolved from `importlib.metadata` with a fallback to `pyproject.toml`, and to
  `0+unknown` rather than an invented number.
- Opening a corpus no longer creates `./corpus` and its five bucket folders. Folders are created by the
  first write, so read-only commands (`swizzle corpus`, `report`, `diff`) leave no trace in the working directory.
- The test files that lived in `swizzle/wizzle/` moved to `Tests/wizzle/`; they no longer ship in the wheel.
- `swizzle.wizzle.integration.VerificationArtifact.target_version` is a `default_factory` field.
- README claims about test counts and sibling checkouts now describe what CI actually runs.
- `swizzle.integration.ml_predictor` is renamed `frequency_predictor` (`FrequencyPredictor`, `FrequencyModel`):
  it counts how often similar past decisions succeeded, and says so. The old names remain as aliases in
  `ml_predictor.py`; the decision engine's evidence text now reads "History-adjusted confidence".
- `docs/IMPLEMENTATION_STATUS.md` is refreshed to SWIZZLE 0.8.0 and the pinned siblings (it was anchored to
  Ghost 1.7.0 as of 2026-09-12); the older measurements are kept and labelled as history.
- CNS is pinned by its full commit (`5252ceebe98185f7be81212d988055ccf9884568`, the v1.8.0 tag) in the `cns` extra.
  `Tests/test_cns_independence.py` now accepts only a full commit there, where it used to accept a tag too.
- CI: the sibling checkouts (ghost_tools, ASSAY, WARDEN) are pinned to full SHAs, are no longer
  `continue-on-error`, and `GHOST_TOOLS`, `ASSAY` and `WARDEN_ROOT` are set, so the live tests run instead of
  skipping. A non-blocking `siblings-latest` job tests against the default branches.
- `Tests/test_lab_corpus.py::test_every_bucket_exists` asserted that opening a corpus creates its folders. That
  is the behaviour removed above, so it is replaced by two tests: opening writes nothing and every bucket reads
  empty; each bucket is made by the write that needs it.

### Fixed
- Seven `shell=True` call sites in `swizzle/wizzle` and `tools/wizzle` interpolated paths into
  `cd {path} && ...`. They now use argument lists, `cwd=` and a timeout (`swizzle/wizzle/_proc.py`).
  A path containing spaces, quotes or `;` is inert.
- `HistoricalUsageOracle` ended its git command with `|| echo ''`, so a git failure looked like an empty
  history. A git failure is now reported as an unmeasured oracle (`error`, confidence 0.0), and so is it in `HistoryOracle`.
- The governor runner left `/tmp/swizzle-governor-*` behind when a straggler process wrote into the folder
  while it was removed; removal is retried and a probe that outlives its group no longer blocks the runner.
  The test that compared the global temp listing before and after failed whenever another SWIZZLE run shared the
  machine; it now runs against a private temp root.
- `FindingType.BOUNDARY_VIOLATED` does not exist: the false-positive, decision and oracle-training handlers
  raised `AttributeError` for a `boundary_violated` finding. They map to `WRITE_OUTSIDE_BOUNDARY`.
- `swizzle.integration.hooks.trigger_triage_event` indexed a dict with `[-1]`.
- `IntegrationOrchestrator.publish_swizzle_integration_bundle` raised `TypeError` when a triage ledger was set,
  because one bundle member was a dict instead of JSON text.
- The pydantic v2 adapter's scan returned `findings` as a dict, which the evidence layer cannot read.
- A timed-out sandbox command could return `bytes` for stdout and stderr.
- The scenario report crashed on an escaped warp with no proof or no true name.
- `swizzle attack --json` and every corpus record failed with `TypeError: Object of type Witness is not JSON
  serializable` for any case whose claim carries a witness (a claim's witness is now flattened in ground truth).
- 163 `mypy` findings across 41 files (wrong-type assignments, unchecked `Optional`, annotations that did not
  match the values returned). The remaining oracle-library typing is expressed with a `LibraryEvidence` type
  rather than a suppression.
- 282 `ruff` findings: 218 unused imports, 27 unused variables, and f-strings with no placeholders.
  A few tests assigned values they never asserted; they now assert them or drop them.

### Security
- No shell is involved in any subprocess WIZZLE starts (see Fixed). A test fails if `shell=True` returns.

## [0.7.1] and earlier, unreleased work (2026-09-12 to 2026-10-16)

`pyproject.toml` stayed at `0.7.1` while the following landed; it is recorded here for the first time.

### Added
- 2026-10-16: the optional CNS connection (`swizzle.cns_adapter`: `ProofGate`, `AttackGate`, `attack_rows`),
  its `cns` extra, independence tests with CNS blocked, and the packaging of `swizzle.governor`,
  `swizzle.integration` and `swizzle.production`.
- 2026-10-14: governor attacks on the tree watch; ASSAY failure modes 3.6 and 3.7 named.
- 2026-10-08 to 2026-10-13: `swizzle governor` (attack Warden's seams and report which invariants held),
  `swizzle assay` (score ghost_buster against ASSAY's answer key; first written as `touchstone`),
  the reporting oracle, lessons handed back to Ghost (`swizzle handoff`).
- 2026-10-05: the production upgrade (`swizzle.production`).
- 2026-09-18: the integration bridges with Ghost Tools (`swizzle.integration`), the oracle library and the
  pydantic v2 migrator adapter.
- 2026-09-13: WIZZLE independent verification (`swizzle.wizzle`).

### Changed
- 2026-10-12: README claims corrected to match code and test results.
- 2026-10-07: licensed under Apache-2.0.

### Fixed
- 2026-10-09: a crashed Warden is never "held"; exit codes tell the truth.
- 2026-09-24: a relative ghost_tools location is resolved before it is handed to a scan.

## [0.7.1] - 2026-09-12

### Fixed
- The harness knew a secret (a ground-truth detail) that it never told the target.

## [0.7.0] - 2026-09-12

### Added
- The adversarial laboratory covers every surface; identity and memory surfaces are attacked.

## [0.4.0] - 2026-09-12

### Added
- Frames, corpus seeding and bounded loops. False certification, and learning that records how it learned.

## [0.3.0] - 2026-09-12

### Added
- Epistemic standing: a fix is not a stamp of completion.

## Notes for the owner

- An older git tag `v0.10.0` (2026-10-12) exists in this repository. No version in `pyproject.toml` has ever
  been `0.10.0`, so the tag does not correspond to this version or to any release of this package. Releases of
  this version (0.8.0, 0.8.1) are not tagged yet. Tagging is the owner's decision; no tag was created, moved or
  deleted by the 0.8.0 or 0.8.1 work.
