"""Does the target settle, or does it generate work forever.

THE QUESTION NO SINGLE RUN CAN ANSWER

Every case in this laboratory so far asks whether one run of a target did
something it should not have. This one asks something a single run cannot
see: if you ACCEPT the output and run again, does it stop?

A tool that never reaches a fixpoint is not wrong on any particular run.
Each one is individually defensible, each writes a number it just measured,
and together they are a pull request every time anyone looks -- each
correcting the last, none of them ever right for longer than it takes to
commit. In a self-hosted loop it is commits forever; through a maintainer
it is their attention forever.

BOUNDED BY CONSTRUCTION

Nothing here runs until it stops. `rounds` is the bound, the iteration stops
at it whatever happens, and not-settling-within-the-bound is the FINDING
rather than a reason to keep going. An adversarial harness that can hang is
an adversarial harness nobody will run.

WHAT THE CLASSIFICATIONS MEAN

    FIXPOINT       the state stopped changing. The tool is idempotent here,
                   which is what an autonomous modification system owes its
                   users and the only outcome that ends the loop.
    CYCLE          a state came back. A -> B -> A forever: two remedies, or
                   one remedy and one detector, each undoing the other.
    DIVERGENT      still changing at the bound, with no state repeated. A
                   runaway rather than a cycle, and just as unending.
    INERT          nothing ever changed. No loop, and no work either.
    UNSUPPORTED    the target has no way to adopt its own output, so the
                   question cannot be asked of it here.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import world
from .adapter import Observation, TargetAdapter
from .evidence import read_tree
from .genome import RepositoryGenome
from .groundtruth import of as ground_truth_of
from .sandbox import Sandbox

#: How many times the target is run before the experiment stops regardless.
#: Six is enough to see a 2-cycle three times over and a runaway clearly,
#: and small enough that a full sweep is minutes rather than hours.
DEFAULT_ROUNDS = 6


class Settling(str, Enum):
    FIXPOINT = "fixpoint"
    CYCLE = "cycle"
    DIVERGENT = "divergent"
    INERT = "inert"
    UNSUPPORTED = "unsupported"
    BROKEN = "broken"

    @property
    def is_a_loop(self) -> bool:
        return self in (Settling.CYCLE, Settling.DIVERGENT)


@dataclass(frozen=True)
class Round:
    index: int
    digest: str
    changed: Tuple[str, ...]
    claimed: Tuple[str, ...]
    adopted: bool
    #: Did the target actually run this round? A round it refused to begin
    #: leaves the tree untouched, and an unchanged tree is exactly what a
    #: fixpoint looks like. Measured: the target names its working branch to
    #: the second, two rounds inside one second collided, and this harness
    #: read the refusal as "it has settled" -- a false negative on the only
    #: question the experiment asks. See `_settles`.
    ran: bool = True
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"round": self.index, "digest": self.digest,
                "changed": list(self.changed), "claimed": list(self.claimed),
                "adopted": self.adopted, "ran": self.ran, "note": self.note}


@dataclass(frozen=True)
class Iteration:
    genome: RepositoryGenome
    settling: Settling
    rounds: Tuple[Round, ...]
    #: For CYCLE: the round the repeated state first appeared at, and the period.
    repeated_at: Optional[int] = None
    period: int = 0
    seconds: float = 0.0
    note: str = ""

    @property
    def settled_after(self) -> Optional[int]:
        if self.settling is not Settling.FIXPOINT:
            return None
        for index in range(1, len(self.rounds)):
            if self.rounds[index].digest == self.rounds[index - 1].digest:
                return index
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {"case": self.genome.name, "settling": self.settling.value,
                "rounds": [r.to_dict() for r in self.rounds],
                "repeated_at": self.repeated_at, "period": self.period,
                "settled_after": self.settled_after,
                "seconds": round(self.seconds, 1), "note": self.note}

    def render(self) -> str:
        lines = ["%s" % self.genome.name, "-" * 66,
                 "  settling        %s" % self.settling.value, ""]
        for entry in self.rounds:
            mark = "adopted" if entry.adopted else "not adopted"
            if not entry.ran:
                mark = "NEVER RAN"
            lines.append("  round %d  %s  %-11s %s"
                         % (entry.index, entry.digest[:10], mark,
                            ", ".join(entry.claimed[:2]) or "no change claimed"))
            if entry.changed:
                lines.append("           changed: %s"
                             % ", ".join(sorted(entry.changed)[:4]))
            if entry.note:
                lines.append("           %s" % entry.note[:90])
        lines.append("")
        if self.settling is Settling.CYCLE:
            lines.append("  The state at round %d came back at round %d: a "
                         "period-%d cycle."
                         % (self.repeated_at, self.repeated_at + self.period,
                            self.period))
            lines.append("  Accepting this tool's output and running it again "
                         "returns the repository")
            lines.append("  to where it was. Nothing here ever finishes.")
        elif self.settling is Settling.DIVERGENT:
            lines.append("  Still changing after %d round(s), with no state "
                         "repeated." % len(self.rounds))
            lines.append("  Every value written was false by the time the next "
                         "run measured it.")
        elif self.settling is Settling.FIXPOINT:
            lines.append("  Settled after %s round(s). Running it again changes "
                         "nothing, which" % self.settled_after)
            lines.append("  is what an autonomous modification system owes the "
                         "people who run it.")
        elif self.settling is Settling.INERT:
            lines.append("  Nothing changed in any round.")
        else:
            lines.append("  %s" % (self.note or "the question could not be asked"))
        return "\n".join(lines) + "\n"


def iterate(genome: RepositoryGenome, adapter: TargetAdapter, *,
            rounds: int = DEFAULT_ROUNDS, timeout: float = 900.0,
            keep: bool = False,
            on_round=None) -> Iteration:
    """Run the target, adopt its output, run again. Up to `rounds` times."""
    started = time.perf_counter()
    dialect = adapter.dialect()
    draft = world.build(genome, dialect)
    truth = ground_truth_of(draft)
    sandbox = Sandbox(keep=keep)
    entries: List[Round] = []
    settling, repeated_at, period, note = Settling.INERT, None, 0, ""

    try:
        root = world.materialise(draft, sandbox)
        seen: Dict[str, int] = {_digest(read_tree(root), dialect): 0}

        if not dialect.acts:
            note = "the target only reports; there is no output to adopt, so it cannot fail to settle"
        for index in range(1, (rounds if dialect.acts else 0) + 1):
            try:
                observed = adapter.act(root, sandbox, timeout=timeout)
            except Exception as exc:
                settling, note = Settling.BROKEN, "%s: %s" % (type(exc).__name__, exc)
                break
            if observed.failed:
                # Record the round before leaving, so a reader can see WHICH
                # round refused rather than only that some round did.
                entries.append(Round(index=index, digest=_digest(read_tree(root), dialect),
                                     changed=(), claimed=(), adopted=False,
                                     ran=False, note=observed.failure))
                if on_round:
                    on_round(entries[-1])
                settling, note = Settling.BROKEN, observed.failure
                break

            adopted = adapter.adopt_output(root, sandbox, observed)
            if not adopted and observed.output_ref:
                settling = Settling.UNSUPPORTED
                note = ("the target produced output on %s and this adapter "
                        "cannot adopt it, so 'run it again on its own result' "
                        "is not askable here" % observed.output_ref)
                break

            after = read_tree(root)
            digest = _digest(after, dialect)
            changed = tuple(sorted(_changed(draft.files, after, dialect)))
            entries.append(Round(index=index, digest=digest, changed=changed,
                                 claimed=tuple(observed.claimed_changes),
                                 adopted=adopted, ran=True,
                                 note=observed.notes))
            if on_round:
                on_round(entries[-1])

            if digest in seen:
                first = seen[digest]
                if first == index - 1:
                    settling = Settling.FIXPOINT
                elif not _settles(entries, first, index):
                    # The repeat is real but the rounds between it are not a
                    # cycle either -- some round in the window never ran. Say
                    # so instead of naming a period that describes nothing.
                    settling = Settling.BROKEN
                    note = ("a round in the repeat window never ran, so "
                            "neither settling nor cycling can be concluded")
                    break
                else:
                    settling, repeated_at, period = (Settling.CYCLE, first,
                                                     index - first)
                break
            seen[digest] = index
        else:
            settling = Settling.DIVERGENT

        if entries and settling is Settling.INERT:
            settling = Settling.DIVERGENT if len(seen) > 1 else Settling.INERT
        if entries and not any(e.changed for e in entries):
            settling = Settling.INERT
    finally:
        sandbox.dispose()

    return Iteration(genome=genome, settling=settling, rounds=tuple(entries),
                     repeated_at=repeated_at, period=period,
                     seconds=time.perf_counter() - started, note=note)


def _settles(entries: Sequence[Round], first: int, index: int) -> bool:
    """Did every round between a state and its repeat actually run?

    `seen` keys states by the round index that produced them, where 0 is the
    state before any round. Rounds `first + 1 .. index` are the ones that
    carried the repository away from that state and back to it, and they are
    `entries[first .. index - 1]`. A cycle is a claim about what the target
    DOES, so it is only a cycle if the target ran every one of them.
    """
    window = entries[first:index]
    return bool(window) and all(entry.ran for entry in window)


def _digest(tree, dialect) -> str:
    """The repository's state, with the target's own bookkeeping excluded.

    A tool that writes a timestamped ledger into the tree it examines would
    otherwise never reach a fixpoint by construction, and reporting that as
    a loop would be reporting the ledger.
    """
    payload = "".join(
        "%s\0%s\0" % (path, text) for path, text in sorted(tree.items())
        if path not in dialect.memory_files and not path.startswith(".git"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _changed(before, after, dialect) -> List[str]:
    out = []
    for path in sorted(set(before) | set(after)):
        if path in dialect.memory_files or path.startswith(".git"):
            continue
        if before.get(path) != after.get(path):
            out.append(path)
    return out
