# SWIZZLE

Adversarial **evaluation framework** for autonomous repository-modification systems. Primary target: [`ghost_tools`](https://github.com/wking53214/ghost_tools). Contains WIZZLE independent verification (`swizzle.wizzle`): physical co-location never grants the target epistemic authority over hidden ground truth.

## 1. Pipeline Position & Role

**ASSURANCE ADVERSARY**, off the live path. Together with ghost_tools + TOUCHSTONE: the assurance loop.

```
RepositoryGenome → world.build() → Sandbox → TargetAdapter
                         │                         │
                   GroundTruth                  Evidence
                   (frozen BEFORE               six oracles
                    anything runs)                    │
                                               Fitness (strict severity dominance)
```

## 2. Full System Scope & Architectural Depth

CLI: `audit | seed | attack | evolve | minimize | reproduce | corpus | diff | report` plus original scanner-blind-spot catalogue (`list|prove|run|summon`).

Optimizes for: *the smallest reproducible repository state in which an autonomous modifier violates an invariant it claims to enforce* — not "make ghost_tools look bad."

~155 py files, 338 classes, 790 funcs. Arbiter + loop orchestrator live in `swizzle/integration/` (not copied into ghost_tools).

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

2 TODOs in tree. Fitness is lab-defined; transfer to "all autonomous coding agents" is a claim, not a measured market. Requires ability to materialize sandboxes. CI `swizzle-gate` is the production-shaped use: fail if a case that passed now fails worse.

## 5. Core Invariants & Guarantees

Ground truth frozen first. Independent oracles. Minimization to smallest failing world. WIZZLE must not take SWIZZLE's hidden labels as evidence.

## 6. Inputs, Outputs & Type Contracts

Typed serialisable `RepositoryGenome` + hypothesis. Reports, minimized cases, regression corpus.

## 7. Stack Integration Topology

```text
TOUCHSTONE specimens ⊂ SWIZZLE worlds ⊂ attacks on ghost_tools
observe-perceive / sentinel_os  ✗ not imported
```

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE). Copyright 2026 William N. King. See `docs/WIZZLE_INTEGRATION.md`, `docs/CONTINUOUS_IMPROVEMENT.md`.
