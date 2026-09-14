# WIZZLE integration

SWIZZLE is the parent system: it constructs adversarial repositories, runs a
target such as Ghost Tools, and records raw experiment artifacts. WIZZLE is
the independent verification subsystem at `swizzle.wizzle`.

The dependency direction is:

```text
SWIZZLE experiment
    -> target execution
    -> immutable VerificationArtifact
    -> WIZZLE observation oracles
    -> evidence entitlement and action entitlement
    -> independent verdict
```

Physical integration does not imply epistemic dependence. WIZZLE may consume
the repository state and the target's raw claim, but its warrant is computed
from its own observations. It does not consume SWIZZLE `GroundTruth`, a
hidden world model, or a target-provided conclusion as evidence.

`WorldModel`-style values remain construction and post-hoc comparison data.
They are not accepted by `Evaluator.evaluate_observation`. The target claim
is an observation to compare against the independent warrant, not an input
that establishes the warrant.

The integrated entry point is:

```bash
python -m swizzle verify REPOSITORY \
  --member PHANTOM \
  --provenance REMOVED_FROM_LIBRARY \
  --severity MAJOR
```

The original WIZZLE API remains available for isolated tests under
`swizzle.wizzle`; the historical scenario builders and forensics fixture are
kept under `tools/wizzle` and `fixtures/wizzle-forensics`.
