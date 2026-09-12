# Architecture

## The pipeline

```
RepositoryGenome            a typed, serialisable description of an
      |                     adversarial world, plus a hypothesis
      v
   world.build()            genome + TargetDialect -> WorldDraft
      |                     (files as strings; ground truth accumulated
      |                      as each mutator records what it changed)
      v
 groundtruth.of()           the expectation, frozen, before anything runs
      |
      v
 world.materialise()        written into a Sandbox, made a git repository
      |
      v
  TargetAdapter.scan()      the target's read-only mode
  TargetAdapter.act()       the target's writing mode
  TargetAdapter.export_output()   where the target PUT its work
      |
      v
      Evidence              before, after, after-working, outside, both
      |                     observations, post-run checks
      v
   oracles.judge_all()      six independent readings
      |
      v
   fitness.score()          severity counts, compared by dominance
      |
      +---> reporting       human report and stable JSON
      +---> minimize        reduce the genome, rebuild, re-run
      +---> corpus          archive, and maybe promote
      +---> search          mutate the genome and go round again
```

## Modules

| Module | Responsibility |
|---|---|
| `lab/genome.py` | The case description. Typed dimensions, serialisation, digest |
| `lab/draft.py` | The world under construction; `TargetDialect`; ground-truth records |
| `lab/mutators.py` | Deterministic mutations, each recording its own ground truth |
| `lab/world.py` | Genome to draft to directory |
| `lab/groundtruth.py` | Freezing the expectation. Imports no adapter, by test |
| `lab/sandbox.py` | Disposable workspaces, path safety, timeouts |
| `lab/adapter.py` | `TargetAdapter`, `Observation` |
| `lab/adapters/ghost.py` | Everything specific to Ghost Tools |
| `lab/evidence.py` | One observation object; oracles are pure functions of it |
| `lab/oracles/*.py` | structural, expectation, scope, temporal, ledger, semantic |
| `lab/signals.py` | `Severity`, `Judgement`, `Signal`, failure classes |
| `lab/fitness.py` | Dominance scoring and corroboration |
| `lab/attack.py` | One case, end to end |
| `lab/minimize.py` | Greedy reduction to a locally minimal failing genome |
| `lab/corpus.py` | Attack memory, buckets, promotion |
| `lab/search.py` | Evolutionary search over genomes |
| `lab/differential.py` | Two target revisions compared per case |
| `lab/metrics.py` | The scorecard |
| `lab/coverage.py` | Surface × mutator × attacks-found matrix |
| `lab/reporting.py` | Human and machine reports |
| `lab/catalogue.py` | The seed genomes |
| `lab/cli.py` | The laboratory's commands |

The original project — `swizzle/warps/`, `schema.py`, `summon.py`,
`invoke.py`, `verdict.py`, `run.py`, `report.py`, `proving.py` — is
unchanged and still reachable through `swizzle list|prove|run|summon`.

## The three boundaries that matter

### Ground truth cannot reach the target

`groundtruth.py`, `draft.py`, `fitness.py`, `signals.py` and every oracle are
forbidden from importing an adapter, the sandbox, or `subprocess`. This is
enforced by `Tests/test_lab_oracle_independence.py`, which walks the import
graph, and by a second test that forbids naming a target in code (docstrings
are exempt, and several of them quote a target while explaining the rule).

Without this boundary the expectation could be shaped by the behaviour it is
supposed to judge, and the whole framework degrades into an expensive way of
asserting that the target did what the target did.

### The target lives behind an adapter

Nothing above `lab/adapter.py` names a target. A target's marker spellings,
its document conventions and its bookkeeping files reach the rest of the
laboratory through `TargetDialect`; its invocation, output location and
version metadata through `TargetAdapter`.

Two adapters exist: `GhostToolsAdapter`, and `Tests/fake_target.py`, a
configurable second target that the entire laboratory runs against
unmodified. The second one is not a mock — it is the evidence that the
abstraction is real, and it is what makes the oracle tests millisecond-fast
and deterministic.

### Oracles are pure functions of evidence

An oracle receives an `Evidence` and returns signals. It does not touch the
filesystem, so two oracles cannot disagree because they looked at different
moments, an archived case can be re-judged without rebuilding it, and every
oracle can be tested against hand-written evidence.

The one thing an oracle would need a subprocess for — "does the repository's
suite still pass" — is computed once by the orchestrator and handed in as
`Evidence.post_checks`.

## Where SWIZZLE sits among neighbouring ideas

**Fuzzing** generates inputs to find crashes, and its oracle is "did it fall
over". SWIZZLE's inputs are structured worlds and its failures are almost all
things that happen while the target is working perfectly.

**Mutation testing** mutates the code under test to find out whether the test
suite notices. SWIZZLE mutates the *world the tool operates on*, and asks
whether the tool's reasoning survives. Ghost Tools itself does mutation
testing; that is a different activity happening in the same repository.

**Property-based testing** generates inputs and checks invariants, and is the
nearest relative — `docs/REPRODUCIBILITY.md` lists the properties SWIZZLE
tests about itself in exactly that style. The difference is the subject: a
property test asserts things about a function's return value; SWIZZLE asserts
things about the *state of a repository after an autonomous agent has acted
on it*, which is not a return value and is not observable from inside the
process.

**Red teaming** is human-driven, creative, and unreproducible by nature.
SWIZZLE keeps the adversarial posture and gives up the improvisation in
exchange for genomes that can be archived, minimised and replayed.

**Automated program repair benchmarking** measures whether a system's patches
are correct. That is the mirror image: a repair benchmark asks "did it fix the
bug", SWIZZLE asks "what else did it touch, and was it entitled to". A system
can score perfectly on the first and catastrophically on the second.

**Adversarial evaluation** is the label that fits: a framework that searches
for inputs on which a system's own guarantees fail, with an independent
oracle deciding, and a reproducible artefact at the end.
