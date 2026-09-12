"""The boundary between this laboratory and whatever it is pointed at.

SWIZZLE is not a Ghost Tools test suite. It is an adversarial evaluator for
repository-level autonomous modification systems, and Ghost is the first
one plugged into it. Everything above this line -- genomes, mutators,
ground truth, oracles, fitness, minimisation, corpus -- names no target.
Everything target-specific lives behind `TargetAdapter`.

WHAT AN ADAPTER OWES THE LABORATORY

    dialect()    the target's spellings: what its opt-in markers look like,
                 which documents it considers current-state, which files it
                 writes as its own bookkeeping
    version()    enough to reproduce: commit, package version, interpreter,
                 platform
    scan()       run the target in its read-only mode
    act()        run the target in the mode that writes
    output_ref() where the target PUT its work, which is not necessarily the
                 working tree. A target that commits to a branch and returns
                 the tree to where it found it has still modified the
                 repository, and an evaluator that only diffs the working
                 tree would score every one of those runs as an abstention.

That last one is the reason this boundary is an interface and not a
function. It was learned by getting it wrong: the first version diffed the
working directory, saw nothing, and reported that Ghost had abstained on a
case where Ghost had in fact rewritten a README and committed it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from .draft import TargetDialect
from .sandbox import Completed, Sandbox


@dataclass(frozen=True)
class Observation:
    """Everything the target did and said, as data.

    `findings`, `claimed_changes` and `abstained` are the TARGET'S account
    of itself. They are evidence -- an oracle may compare them against what
    actually happened and report a disagreement -- and they are never
    treated as authority about whether the target was right.
    """

    target: str
    mode: str                              # "scan" or "act"
    version: Mapping[str, str]
    invocations: Tuple[Completed, ...]
    findings: Tuple[Mapping[str, Any], ...] = ()
    claimed_changes: Tuple[str, ...] = ()
    abstained: bool = True
    output_ref: Optional[str] = None
    memory: Mapping[str, str] = field(default_factory=dict)
    notes: str = ""
    failed: bool = False
    failure: str = ""

    @property
    def stdout(self) -> str:
        return "\n".join(c.stdout for c in self.invocations)

    @property
    def stderr(self) -> str:
        return "\n".join(c.stderr for c in self.invocations)

    @property
    def timed_out(self) -> bool:
        return any(c.timed_out for c in self.invocations)


class TargetUnavailable(RuntimeError):
    """The target could not be found or run. Never an attack."""


class TargetAdapter(ABC):
    """One autonomous modification system, as the laboratory sees it."""

    name: str = "target"

    @abstractmethod
    def dialect(self) -> TargetDialect:
        """The spellings a world needs to be concrete for this target."""

    @abstractmethod
    def version(self) -> Mapping[str, str]:
        """Enough metadata to reproduce a run against this exact target."""

    @abstractmethod
    def scan(self, root: Path, sandbox: Sandbox, timeout: float = 900.0) -> Observation:
        """Run the target's read-only mode over `root`."""

    @abstractmethod
    def act(self, root: Path, sandbox: Sandbox, timeout: float = 900.0) -> Observation:
        """Run the mode that is allowed to modify `root`."""

    @abstractmethod
    def export_output(self, root: Path, sandbox: Sandbox,
                      observation: Observation, into: str) -> Optional[Path]:
        """Materialise the state the target considers its result.

        Returns the directory, or None when the target produced no separate
        output state (in which case the working tree is the result).
        """

    def interrupt_points(self) -> Sequence[str]:
        """Named places a crash-consistency experiment can cut the target off.

        The default is none: interrupting a target safely needs target
        knowledge, and a laboratory that guesses would be reporting its own
        SIGKILL as a finding.
        """
        return ()
