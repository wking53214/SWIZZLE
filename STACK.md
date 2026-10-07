# Stack role — SWIZZLE

**ASSURANCE (not the live decision path).**

Adversarial evaluation framework for autonomous repository-modification systems (primary target: [ghost_tools](https://github.com/wking53214/ghost_tools)). Builds adversarial worlds, runs the target, judges invariant violations independently.

| Related | Role |
|---------|------|
| [ghost_tools](https://github.com/wking53214/ghost_tools) | Primary target under test |
| [TOUCHSTONE](https://github.com/wking53214/TOUCHSTONE) | Specimen corpus / ground truth; read by `swizzle touchstone` |
| [Elegant](https://github.com/wking53214/Elegant) | Runs `swizzle prove` before it will ACCEPT a change |
| [observe-perceive](https://github.com/wking53214/observe-perceive) | Live governed-action hub |

```text
Live path: Admission → OBSERVE/Keys → Locks → PERCEIVE → Decision → Conservation → Execution → Custody
Assurance: ghost_tools · Elegant · SWIZZLE · TOUCHSTONE
```

See [README.md](README.md) for full framework documentation.
