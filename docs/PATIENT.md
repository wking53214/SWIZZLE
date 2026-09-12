# When SWIZZLE is the patient

The alignment reversed: ghost_tools was pointed at this repository. What
follows is the first complete round, including the parts that went wrong.

## The audit came back mostly noise

First scan: **85 findings across 105 files**, 661 tests green.

**51 of the 85 were one false-positive class.** Every CLI command here is
registered with `@_register("name")`, so its function name is reached through
a registry and never appears as an identifier again. Ghost's `dead_code`
detector called all of them dead.

This was *disclosed*, not hidden — Ghost's own docstring has named decorator
registration as an untraced case since 0.1.1, with its own `@register` as the
example. Which is the actual lesson: **a disclosed limitation is fine for a
report a human reads and becomes dangerous the moment autonomy is
contemplated.** A remedy authorised to delete dead code would have removed
every command this tool has.

Fixed in ghost_tools 1.7.5. Findings fell 85 → 37, and the two `dead_code`
findings that remained were both true positives — one of them a dead exception
class introduced in this repository hours earlier.

## And zero findings about what makes this repository correct

Not one finding concerned ground-truth independence, oracle coupling, witness
validity, phase semantics, or whether an experiment still asks its question.
Ghost saw a Python application, because that is what it is built to see.

That gap is the whole point of the reversal.

## The defect that mattered

Ghost 1.7.5 gained `unreachable_declared_state`: an enum member no code ever
produces, in an enum whose other members it does. It found one here on the
first run.

`Phase.BETWEEN_RUNS` was declared among four phases of which `world.build`
carried out three. A genome asking for the fourth:

- built a world **without its mutation**
- recorded an **empty construction history**
- was still judged by the temporal oracle, which reads the phase off the
  genome and adjusts its verdict because the phase was *declared*, not
  because anything happened

The experiment stopped asking its question and produced an answer anyway.
**Nothing downstream could tell that answer apart from a real one.** That is
the worst shape a defect in an instrument can take, and it is exactly the
class an ordinary test suite cannot see: all 661 tests were green throughout.

## Three repairs were available and two were wrong

**Carry the mutation out at build time.** Silently redefines what the phase
means — "between two separate target invocations" is not "during
construction". A different experiment wearing the same name.

**Delete the member.** Removes a genome's ability to say what it wanted, and
takes the temporal oracle's reference with it.

**Refuse the case.** The phase stays, nothing pretends to carry it out, and a
genome asking for it is refused at construction — before a verdict exists to
be mistaken for a real one.

The third. An unaskable experiment is not a failed experiment and must never
be reported as a passed one.

`UnaskableExperiment` is deliberately distinct from `ContradictoryGroundTruth`
and `UnwitnessedGroundTruth`. Three different things went wrong: ground truth
disagreeing with itself, ground truth the world does not carry, and machinery
that cannot perform the case at all. Collapsing them would lose which.

## Ghost diagnosed it and did not repair it

Correctly. Producing the state, handling its arrival, and removing it are all
defensible, and an AST cannot choose between them. The finding is MINOR and
says what a human must decide.

**Reportable and not writable** — the same distinction Ghost already draws for
documents, applied to its new patient.

## Post-surgical validation

"pytest passes" is not the standard. The repair was validated as:

| check | result |
|---|---|
| regression suite | 674 passed |
| motivating defect closed | Ghost reports 0 |
| frozen holdout | 0 of 12, unchanged |
| full attack replay, 26 cases | every verdict identical |
| both open CRITICALs | still reproduce |

The last two rows are the ones that matter. A repair to an instrument that
changes what the instrument measures has traded a defect for a worse one, and
the only way to know is to replay the experiments and compare.

## What the drift guard is

The defect was a list and a behaviour drifting apart. So the repair asserts
they cannot:

    test_the_carried_phases_are_the_ones_build_actually_runs

reads the source of `build` and requires that every phase declared as carried
out is run there, and that no phase not so declared is. The defect's own shape,
turned into a check.
