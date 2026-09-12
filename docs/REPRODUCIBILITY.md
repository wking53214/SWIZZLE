# Reproducibility

An attack that cannot be rebuilt is an anecdote. This is what makes one
rebuildable, and what is checked.

## What is recorded

Every corpus entry carries:

| Field | Why |
|---|---|
| `genome` | the complete world description |
| `genome_digest` | identity, stable across field order |
| `hypothesis` | what the case expected to go wrong |
| `target` | name, checkout, **commit SHA**, whether that checkout was dirty, package version, Python version, platform |
| `swizzle` | version and commit |
| `environment` | Python, platform, executable, working directory |
| `signals`, `ground_truth`, `changed` | the evidence |
| `recorded_at` | timestamp |
| `reproduce` | the exact command |

`commit_dirty` is there because a result attributed to a commit that had
uncommitted changes on top of it is attributed to nothing. `swizzle audit`
warns when the target checkout is dirty.

## Determinism

**Genome to world.** `world.build()` is pure. The same genome produces the
same files, the same symlinks and the same ground truth, byte for byte.

**Seeded mutations.** Each mutation's RNG is seeded from
`(genome seed, index, name)`, so adding a mutation at the end cannot change
what an earlier one did.

**Serialisation.** `to_dict`/`from_dict` round-trip exactly, through JSON, with
tuples normalised at the boundary. A field lost in serialisation would turn
every archived attack into a different experiment, silently.

**Relative symlinks.** Link bodies are relative, so a materialised case can be
archived, moved and replayed elsewhere. Absolute bodies baked the sandbox path
into the corpus and made every archived scope case unreproducible on a second
machine.

## Properties tested

In the style of property-based testing, over the whole seed catalogue and the
laboratory's own fixtures:

| Property | Test |
|---|---|
| every genome round-trips exactly | `test_lab_genome.py` |
| ... through JSON, preserving the digest | `test_lab_genome.py` |
| the digest is independent of field order | `test_lab_genome.py` |
| a foreign schema version is refused, not guessed at | `test_lab_genome.py` |
| building twice gives identical files and ground truth | `test_lab_determinism.py` |
| a rebuilt genome builds the same world | `test_lab_determinism.py` |
| adding a mutation does not change earlier ones | `test_lab_determinism.py` |
| materialising writes exactly the draft | `test_lab_determinism.py` |
| ground truth never depends on target output | `test_lab_self_adversarial.py` |
| ground truth is fixed before the target runs | `test_lab_self_adversarial.py` |
| unsafe mutation always outranks harmless abstention | `test_lab_fitness.py` |
| the scalar agrees with the dominance ordering | `test_lab_fitness.py` |
| a minimised attack is still the same attack | `test_lab_minimize.py` |
| every archived case still rebuilds | `test_lab_regression_replay.py` |
| every archived case carries what reproduction needs | `test_lab_regression_replay.py` |
| no judge module can reach a target | `test_lab_oracle_independence.py` |

## Reproducing one

```
swizzle reproduce prose_inside_the_maintained_block
```

Rebuilds the world from its genome, runs the target, prints the report.

```
swizzle reproduce prose_inside_the_maintained_block --build-only --keep ./w
```

Writes the repository and stops. Deliberately does **not** need the target
installed: somebody reading an archived attack should be able to look at the
world it describes without having the system under test to hand.

## What is not reproducible

**The target's own non-determinism.** If the target behaves differently on
identical input, SWIZZLE records what happened on the run it did and nothing
more. No attempt is made to detect flakiness by re-running: a verdict that
depends on how many times something was tried is not a verdict.

**Wall-clock timing.** No case depends on it. The temporal attacks are
deterministic by construction — the mutation is performed by the repository's
own suite, which the target runs itself — precisely so that nothing here is a
race.
