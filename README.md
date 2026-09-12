# SWIZZLE -- v0.4.0

An adaptive adversarial evaluator for repository-level autonomous
modification systems.

    swizzle audit      can the laboratory run, and what does it currently attack
    swizzle seed       the catalogue of adversarial worlds, with hypotheses
    swizzle attack     build cases, run the target, judge what happened
    swizzle evolve     search for cases nobody wrote down
    swizzle minimize   reduce a failure to the smallest world that still shows it
    swizzle reproduce  rebuild one case from its genome
    swizzle corpus     attack memory, and promotion to a regression case
    swizzle diff       two revisions of the target, compared per case
    swizzle report     scorecard and coverage

    swizzle list|prove|run|summon    the original scanner-blind-spot catalogue,
                                     unchanged (see "The first SWIZZLE" below)

## What it optimises for

Not "finding bugs in Ghost Tools". This:

> finding the smallest reproducible repository state in which an autonomous
> software-modification system violates an invariant it claims to enforce

The distinction decides everything else. A framework aimed at the first goal
keeps whatever makes the target look bad. A framework aimed at the second has
to produce a scientific artefact each time: a hypothesis, a constructed world,
an independent observation, a classification, a minimisation, and a command
that reproduces it.

## The shape of it

```
RepositoryGenome  ->  world.build()  ->  Sandbox  ->  TargetAdapter
   (typed, seeded,         |                              |
    serialisable,    GroundTruth                      Evidence
    with a stated     (frozen BEFORE                      |
    hypothesis)        anything runs)              six independent oracles
                                                          |
                                          Fitness (strict severity dominance)
                                                          |
                                     report / minimise / archive / evolve
```

Three boundaries hold it up, and each is enforced by a test rather than by
intention:

**Ground truth cannot reach the target.** `Tests/test_lab_oracle_independence.py`
walks the import graph and fails if any module that decides what *should* have
happened can reach anything that can ask the target a question. Without it, the
expectation could be shaped by the behaviour it exists to judge.

**The target lives behind an adapter.** Nothing above `lab/adapter.py` names a
target. A second adapter — a configurable fake with ten behaviours — runs the
entire laboratory unmodified, which is the evidence that the abstraction is
real rather than decorative.

**Oracles are pure functions of evidence.** They never touch the filesystem, so
two of them cannot disagree by looking at different moments, and an archived
case can be re-judged without rebuilding it.

## Results against Ghost Tools 1.7.0

Seven attacks, five clean passes. Two of the attacks are CRITICAL:

**A write landed outside the repository.** One remedy composes `root/"README.md"`
and writes to it with no containment check. A symlink carries the write out of
the tree — where the branch the tool opened cannot revert it, and where the
tool's own commit then fails because there is nothing in the repository to
commit. Its error path sees a symptom after the damage.

**Author prose inside an opt-in block was deleted.** A repository hands over a
*count* by writing a marker pair. The tool replaces the *region*, so a sentence
somebody wrote inside it is gone — and the verification that follows the write
checks that bytes *outside* the block are unchanged, so it cannot see the loss.
The verification was not weak; it answered a different question from the one
the invariant needed.

The differential pins the second one to a release:

```
baseline   1.6.1 at e5ad44b57a
candidate  1.7.0 at d14dc1acf0
worsened   prose_inside_the_maintained_block  LOW -> CRITICAL
```

And the five passes matter as much. Ghost correctly declined to rewrite a
dated claim, a live-looking claim inside a historical document, and a document
whose marker pair never closes; it handled two maintained blocks
consistently; and when it was sent SIGKILL in the middle of an operation it
left the repository on its original branch, clean, with nothing changed. A
corpus with no passes in it is a corpus whose oracles nobody should trust.

## What happened when the findings were fixed

Ghost Tools 1.7.1 fixed all seven. Re-running the same genomes across the
two revisions:

```
baseline   1.7.0 at d14dc1acf0
candidate  1.7.1 at 40b8daea6a

  fixed        6
  improved     1
  unchanged    5
  regressed    0
```

The one `improved` is the honest part. `document_reached_through_an_alias`
went from HIGH (a writability verdict reached about a symlink and applied to
its target) to LOW (declining to rewrite a live claim in a document whose
resolved name is not on the tool's allow-list). The tool stopped damaging the
tree and started being slightly too careful, which is the trade the fix was
for, and the severity ladder says so without being asked.

Two harness bugs surfaced in the same run, both of them SWIZZLE reporting a
target for something SWIZZLE had done:

- a during-tests mutation lands after the baseline snapshot, so the edit the
  harness made mid-run was attributed to the target. `Evidence.baseline` now
  replays SWIZZLE's own edits before anything is diffed.
- a composed case protected a file byte-for-byte while also permitting an
  edit in it, so a target doing exactly what it was authorised to do was
  reported for it. `groundtruth.of` now refuses to build a case that
  contradicts itself.

And one classifier bug: the differential called HIGH-to-LOW a regression,
because it keyed on the failure class before the severity. A maintainer
reading that column would have backed the fix out.

All three have guarantees in `Tests/test_lab_self_adversarial.py` and
`Tests/test_lab_differential.py` now. Finding them is what re-running after a
fix is for.

## A fix is not a stamp of completion

When an attack stops reproducing, the most this laboratory will say is:

> the current structure supports the conclusion that this has been resolved

Never `fixed`. The word appears in exactly one place in the output, in the
sentence refusing it, and a test asserts that every occurrence is negated.

The reason is the sentence *"I didn't say she stole my money"* — seven words,
seven meanings, one text, depending only on which word takes the stress. The
same thing happens to "it no longer reproduces": stress any word and it names
something that was not established. **THIS** case, not the class. This
**CASE** — the observable, not the defect. **THESE** oracles, one of which
declined to say rather than agreeing. **THIS** world, the one minimisation
left behind.

Each of the seven readings is a question the tool can actually ask
(`swizzle standing CASE`), and each answer is *defeated*, *held*, or **not
asked** — three states, because "not asked" and "asked, nothing found" are
different and collapsing them is how a corpus fills with conclusions nobody
reached.

The failure being refused is **epistemic promotion**: an observation
acquiring authority, provenance, certainty and historical status it never
earned. `docs/EPISTEMIC_STANDING.md` has the full decomposition, including
the two occasions the module committed that failure itself on its first real
run.

## Does the target ever finish?

Every other experiment here asks whether **one run** did something wrong. One
asks what a single run structurally cannot answer: accept the output, run
again — does it stop?

A tool that never reaches a fixpoint is not wrong on any particular run. Each
one writes a number it just measured; each would pass review. Together they
are a pull request every time anybody looks. `swizzle loop CASE` runs the
target, merges its branch, and runs it again, bounded — **not settling within
the bound is the finding, never a reason to keep going.**

Measured against Ghost Tools: a suite parametrised over a number in its own
README, beside a tool that writes the suite's size into that README, cycles
31 → 32 → 33 → 31 forever.

Two of Ghost's rules turned out to be brakes on the loop, and they are the
more interesting half of the result: its drift rule is one-directional, and
its green gate declines to write into a suite that is not passing. The first
version of the case tripped the second one and settled — **correctly**.
Getting a cycle meant building a world where the tool has no defensible
reason to stop.

The harness had the same bug it hunts. A round the target *refused to begin*
leaves exactly the same unchanged repository as a round where it ran and
settled, and reading the first as the second reported a fixpoint for an
experiment that never happened. `docs/CONVERGENCE.md` has the three
corrections, at three layers.

## Learning: three ways, and one of them has no prior

`swizzle knowledge` reports what has been learned about a target **and how
it came to be known** — because those license different things.

| acquired | means | weight |
|---|---|---|
| `observed` | measured against this revision | a real posterior |
| `connected` | a pairing that beat every one of its members' best | posterior + lift |
| `carried` | measured against a *different* revision: inference | ranked below anything observed |
| `zero base` | never offered here | **none** |

`none` is not a small number. It is the absence of a measurement, and the
earlier design's `0.15` floor was a number invented and then consumed as
evidence — the same unearned promotion, one layer down from `fixed`. A
zero-base key is reached through a reserved share of the search budget
instead: an experiment, because it is unknown, rather than a bet dressed up
as one.

Carried evidence is subordinate structurally, not by a discount. A phase 3
result is not a post-market observation.

## Recording that a case was fixed, without saying it was fixed

`swizzle standing --record` appends an **episode** — one per case per revision
of the target, append-only, never merged across revisions. `swizzle history`
reads the arc:

| arc | means |
|---|---|
| `never established` | it has never produced its failure anywhere |
| `open` | reproduces at the newest revision, never been quiet |
| `held` | reproduced, stopped, and every episode since agrees |
| `returned` | reproduced, stopped, and reproduced again. **The finding** |
| `contested` | went quiet, and a probe against that quiet defeated it |
| `unknown` | one episode. An arc needs a sequence |

None of the six contains the string `fix`, and a test asserts it. `held` is a
statement about the *record*, not about the defect — the whole point of writing
down that a case stopped reproducing is to make it possible to find out later
that it did not stay stopped.

The first version of the file listed the stored standing spellings by hand
beside the enum that produces them and got two wrong. Nothing raised: every arc
came back `unknown`, and a ledger whose purpose is to notice a case coming back
would have said `unknown` forever without failing a test. Silence is the
failure mode of a lookup table. `docs/CASE_HISTORY.md`.

## Aiming at what has never been tested

Weighting mutators by what has paid is rich-get-richer: it concentrates the
search where it has already succeeded, which is where new information is least
likely to be. A quarter of mutator choices are reserved for reaching a
**surface of the target no case has landed on** — reserved, not weighted, for
the same reason a zero-base key gets no prior.

Three grounds, in order, and the order is a claim: ignorance about the
*subject* outranks ignorance about the *instrument*, which outranks the
evidence about what pays. The search reports which surfaces **opened**, and
which are still empty — not how often it chose on uncovered grounds, because
that would be a report about its own policy rather than a result.
`docs/UNCOVERED_SURFACES.md`.

## Severity, and the one rule that cannot be tuned

A case where the target destroyed a paragraph outranks any number of cases
where it filed a report badly. Not by a lot -- absolutely. Severity counts are
compared lexicographically, so the trade cannot be expressed.

Weights were the first design and they were wrong: a search optimising
`4*critical + 3*high + ...` trades one CRITICAL for two HIGHs, and cosmetic
complaints are far easier to generate than real damage, so within a few
generations the population scores well and means nothing.

Harmless abstention scores zero. Over-cautious abstention scores LOW, because
an evaluator that cannot see over-caution cannot tell a safe target from a
broken one -- and LOW so that no quantity of it competes with damage.

## Who watches the adversary

`Tests/test_lab_self_adversarial.py` attacks SWIZZLE's own oracles with targets
built to satisfy them while doing the wrong thing. It contains two kinds of
test, and the difference is the point:

- tests asserting an attack on the oracles **fails**. Guarantees.
- tests asserting an attack on the oracles **succeeds**. Each names a blind
  spot that is real today and will fail the day somebody closes it.

Three blind spots are recorded that way: a change that is reverted is
invisible, an escape that is restored is invisible, and a wrong ground truth
cannot be detected by anything here. They are in `docs/ORACLES.md` under "What
the oracles cannot see".

## Documentation

| | |
|---|---|
| `docs/ARCHITECTURE.md` | modules, pipeline, and where this sits among fuzzing, mutation testing, property testing, red teaming and repair benchmarking |
| `docs/ARCHITECTURE_AUDIT.md` | the audit of v0.1.0, and what was deliberately not rewritten |
| `docs/ADVERSARIAL_CONTRACT.md` | what counts as an attack; the eight invariants |
| `docs/THREAT_MODEL.md` | nine threats, why each is reachable, which are constructed |
| `docs/MUTATION_MODEL.md` | the mutator contract |
| `docs/ORACLES.md` | the six, and what none of them can see |
| `docs/FITNESS.md` | the dominance rule |
| `docs/MINIMIZATION.md` | reduction, and a worked example |
| `docs/ADAPTIVE_SEARCH.md` | the search, and why it is not machine learning |
| `docs/REPRODUCIBILITY.md` | what is recorded, and the properties tested |
| `docs/ATTACK_CORPUS.md` | the four buckets and the promotion rule |
| `docs/SECURITY.md` | what the sandbox guarantees, and what it does not |
| `docs/IMPLEMENTATION_STATUS.md` | what exists, what does not, what is next |

## Install

    pip install -e ".[dev]"
    swizzle audit --ghost-tools ../ghost_tools

Python 3.11, `git`, and nothing else. The generated worlds are stdlib-only,
because a fixture that needs a package installed is a fixture that can fail
for a reason the report cannot explain.

## Tests

    python -m pytest

343 tests. The ones that matter most are not the ones that check the
laboratory works: they are `test_lab_oracle_independence.py`, which proves the
expectation cannot be influenced by the target, and
`test_lab_self_adversarial.py`, which tries to fool the evaluation layer.

---

# The first SWIZZLE

Everything below is the original project, unchanged and still running. It asks
a different question -- whether a scanner's *reading* of a defect is correct,
rather than whether a modification system's *writing* is safe -- and that
question did not stop being worth asking. `swizzle list`, `prove`, `run` and
`summon` behave exactly as they always did.

## The defeat condition

A reality warper whose entire intent is to trick `ghost_tools`, and whose
entire design is to be caught doing it.

    swizzle list     the catalogue: every trick and the name that banishes it
    swizzle prove    run the proofs alone -- is every planted defect real?
    swizzle run      build them all, scan them, score it
    swizzle summon   write one warp to disk and leave it there to read

## The defeat condition

The imp this is named after cannot be beaten by force. Mister Mxyzptlk
bends the rules of the world he visits, and the only thing that sends him
home is being made to say his own name backwards. That is the whole design
here, borrowed intact.

Every trick SWIZZLE builds -- a **warp**: a small repository with a real
defect in it -- declares in advance, in machine-readable form, the finding
a scanner ought to report about it. The detector, the file, the line, and
one sentence of why. That declaration is the warp's **true name**. Name it
and the imp goes home.

An adversary without a defeat condition is not a measuring instrument. It
can only say "you missed something", which cannot be checked, cannot be
regression-tested, and cannot tell a genuine blind spot from a fixture
that was never defective to begin with. So the true name is mandatory, and
the test suite refuses a warp that does not carry one.

## The second rule: a claim is not a defect

A declared true name is still only a claim. Each warp therefore carries a
**proof**: a demonstration, independent of any scanner, that the defect is
real.

Where the defect is a runtime one, the proof runs it. The injected query
really does return the row the caller was never entitled to. The failed
publish really does return the same value as the successful one. The
audited event really is absent from the audit log afterwards. Where the
defect is structural -- a definition nothing references -- there is nothing
to run, and the proof is an assertion over the syntax tree instead.

A warp whose proof does not hold is SWIZZLE's bug. It is reported as
`UNSUMMONED` and never counted as an escape, because claiming a blind spot
that is not there would corrupt the only number this tool produces.
`swizzle prove` runs that gate on its own, and the test suite runs it on
every warp on every commit.

## The third rule: an exclusion needs a control

Three of the warps do not go around a detector. They put on a costume it
was told to respect.

`sql_injection` skips any path with `test`, `tests`, `testing` or
`fixtures` in it, because a permissive setting inside a test is usually the
subject of the test. `dead_end_call` skips a hollow method whose class
declares `ABC`, `ABCMeta` or `Protocol`, because a declared seam is empty
on purpose. `dead_code` counts a name-shaped string in a subscript as a
reference, because string-keyed dispatch is real and flagging all of it
produced noise on a live repository.

Every one of those exclusions is defensible and every one was added after
a measured false positive. The finding is not that they exist. It is that
production code can wear them: a live request handler in a directory
called `testing`, a concrete instantiated class with `ABC` in its base list
and no abstract methods on it, a dead command held up by its own help text.

"This escaped because of the exclusion" is a causal claim, and a causal
claim without a control is a story. So each of those warps also carries the
same defect with the costume removed, and SWIZZLE scans both. The report
then says which it was:

    control caught: removing the `ABC` base and its import brings back
    `dead_end_call` at app/audit.py:11, so that is what the warp is
    hiding behind

If the control is missed too, the escape is not explained by the exclusion
and SWIZZLE says so rather than taking the credit.

## Verdicts

| Verdict | What happened |
|---|---|
| `BANISHED` | The scanner named the true name: right detector, right place. |
| `MISNAMED` | It spoke, but said the wrong thing, or pointed at the wrong place. |
| `ESCAPED` | Silence over a proven defect. A blind spot. |
| `CONJURED` | A decoy with nothing wrong with it, and the scanner fired. A false positive. |
| `DISMISSED` | A decoy, and the scanner stayed quiet. Correct. |
| `UNSUMMONED` | SWIZZLE could not build it, run the scan, or prove the defect. Its own failure. |

Two of the twelve warps carry no defect at all. An adversary that only
plants defects measures one half of a scanner; the other half is what it
says about code that is fine, and that half decides whether anyone keeps
reading the report. The decoys declare which detectors are forbidden to
fire on them and prove their own innocence by running -- the injection that
works on the other warps returns zero rows against the parameterised one.

## What a run looks like

Measured 2026-09-12 against ghost_tools 1.7.0, every detector on, the
checks that reach outside the file set off:

    proven defects named      0 of 10
    clean fixtures left alone 1 of 2

The single false positive is one ghost_buster documents about itself:
decorator-based registration is untraced, and it self-flags on its own
`@register` pattern. It is in the catalogue anyway, for the same reason the
disclosed escapes are: the report is about coverage, not about who knew
what.

### The catalogue

| Warp | Target | Gap |
|---|---|---|
| `sql_through_a_name` | `sql_injection` | undisclosed |
| `sql_behind_a_wrapper` | `sql_injection` | undisclosed |
| `sql_in_a_place_called_testing` | `sql_injection` | exclusion worn as a costume |
| `sql_behind_a_comment` | `sql_injection` | undisclosed |
| `handler_that_logs_and_carries_on` | `swallowed_exception` | disclosed |
| `suppress_around_everything` | `swallowed_exception` | disclosed |
| `hollow_behind_an_abstract_base` | `dead_end_call` | exclusion worn as a costume |
| `dead_code_kept_alive_by_a_string` | `dead_code` | exclusion worn as a costume |
| `tls_off_by_default_argument` | `insecure_default` | undisclosed |
| `debug_true_through_config_update` | `insecure_default` | undisclosed |
| `parameterised_but_alarming` | `sql_injection` | decoy: must stay silent |
| `dispatch_by_decorator` | `dead_code` | decoy: disclosed false positive |

### Four of them, in one line each

**`sql_through_a_name`.** The detector inspects the argument node of the
`execute` call. Put the f-string in a variable on the line above and the
argument node is a `Name` with nothing in it to interpolate. The query is
identical and the injection works.

**`sql_behind_a_comment`.** A string is treated as SQL only if it opens
with a statement keyword, anchored at `^\s*`. This one opens with
`-- audit: user lookup`. The database strips the comment; the regex does
not, because a comment is not whitespace.

**`tls_off_by_default_argument`.** `verify=False` is checked as a keyword
at a call site. Here it is a default in a function signature, so every call
site passes `verify=verify` -- a name -- and every request that does not opt
back in fetches the certificate and ignores it.

**`hollow_behind_an_abstract_base`.** A concrete, instantiated, called
class whose one method is a docstring and nothing else. It declares `ABC`
as a base and no abstract methods, which Python does not treat as abstract
in any enforceable sense, but is the exact spelling the seam test looks
for. `audit()` returns True; the log is empty.

## Disclosure, and why escapes are graded

An escape through a limit the tool documents about itself is worth less
than an escape through a limit nobody knew about, and the report separates
them:

- **UNDISCLOSED** -- no part of ghost_tools mentions this gap. A bug report.
- **EXCLUSION WORN AS A COSTUME** -- a real exclusion, put on by code not
  entitled to it, with a control proving the attribution.
- **DISCLOSED** -- ghost_tools states the scope limit in its own words,
  which the warp quotes. A roadmap item.

Grading them the same would teach the reader of the report to skim it,
which is ghost_buster's own argument about severity, borrowed.

## What SWIZZLE does not do

**It does not modify the tool it measures.** Every warp is written into a
fresh directory, committed, scanned, and thrown away. A measurement taken
by modifying the thing being measured is not a measurement. `ghost_tools`
is read-only to this repository and is not even imported into its process
-- the scan runs in a subprocess.

**It does not help anything evade a scanner in the field.** Every warp is a
self-contained synthetic fixture with its defect declared, proven, located
by line, and printed in the report. The output is a list of things a
scanner should have said and did not. Removing the declaration is what it
would take to make this into something else, and the test suite fails
without it.

**It does not judge the score.** `swizzle run` exits non-zero only when
SWIZZLE itself failed. Escapes are the finding, not the error. Use
`--fail-on-escape` in CI once a scanner has closed the ones it intends to.

## Install

    pip install -e ".[dev]"

SWIZZLE needs Python 3.11 and `git`, and nothing else -- the warps are
stdlib-only, because a fixture that needs a package installed is a fixture
that can fail for a reason the report cannot explain.

To run it against a checkout of the tool, point it at one:

    swizzle run --ghost-tools ../ghost_tools
    GHOST_TOOLS=../ghost_tools swizzle run

Failing both, it looks for `ghost_buster` on the import path and then for a
sibling `ghost_tools` directory.

Useful flags:

    swizzle run --only sql          just the SQL family
    swizzle run --json              the same result, for a machine
    swizzle run --keep ./warps      build them here and leave them to read
    swizzle summon sql_behind_a_comment --into /tmp

## Tests

    python -m pytest

109 tests. The one that matters is `Tests/test_proofs.py`: every warp in
the catalogue summons itself and proves its own defect, with no scanner
involved. If that suite is green, every escape in the report is an escape
from something real.

`Tests/test_against_ghost_buster.py` skips when no checkout is available,
so the honesty gate can run in CI without dragging the subject of the
measurement in with it. It asserts the plumbing and one calibration shot --
that an undisguised injection is still reported -- and never asserts the
score, because a suite that fails the day the scanner improves is a suite
pointed the wrong way.

## SWIZZLE under ghost_buster

The adversary is scanned by its target. As of 2026-09-12, v0.2.0 comes back
with 42 findings, every one of them MINOR, and the breakdown is worth stating
rather than rounding to a claim:

    29  dead_code        every one a false positive, and a disclosed one:
                         they are the CLI's command handlers and the
                         mutator registry, all reached through decorators
                         and a dispatch table. ghost_buster documents that
                         it cannot trace decorator registration and that it
                         self-flags on its own `@register` pattern -- which
                         is exactly what `dispatch_by_decorator`, a decoy in
                         the warp catalogue below, exists to demonstrate
     7  duplicate block  repeated `lines.append("")` in report renderers
     3  long_function    argparse setup, one report renderer, the search loop
     3  name_disagreement
    ...

v0.1.0 scanned clean at zero findings; the laboratory added enough code to
change that, and the honest version of this section is the table above rather
than a smaller number obtained by writing less. Everything actionable the
scan found on the first pass was fixed: an `except KeyError: pass` in the
case lookup (the exact defect this project reports in other people's code),
three loop-invariant calls, and a name disagreement. What is left is the
disclosed false-positive class and formatting churn in code that renders
reports.

## Adding a warp

1. Write the smallest repository that carries the defect.
2. Mark the defect line with `# swizzle:true-name` -- exactly once. Line
   numbers are read off the fixture, never written down beside it.
3. Declare the `TrueName`: detector, file, line span, one sentence of why.
4. Write the proof. Run the defect if it can be run.
5. If the warp wears an exclusion, add the `Control`: the same defect with
   the costume off, and what was removed.
6. `swizzle prove --only <name>`, then `python -m pytest`.

The test suite will refuse a warp with a drifted marker, a true name
pointing outside its own files, a disclosed gap with nothing quoted, or a
costume with no control.
