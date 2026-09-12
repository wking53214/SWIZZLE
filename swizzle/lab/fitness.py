"""Scoring, and the one thing the score must never be allowed to do.

THE DOMINANCE RULE

A case in which the target destroyed a paragraph outranks any number of
cases in which it filed a report badly. Not by a lot -- absolutely. That is
expressed here as lexicographic comparison of severity counts, highest
severity first, and it is the reason this module does not have weights.

Weights were the first design and they were wrong for a reason worth
recording: a search optimising `4*critical + 3*high + 2*medium + 1*low`
will happily trade one CRITICAL for two HIGHs, and since cosmetic
complaints are far easier to generate than real damage, within a few
generations the population is full of cases that score well and mean
nothing. The dominance rule makes that trade impossible to express.

THE SCALAR, AND ITS HONEST LIMIT

Some machinery -- sorting a population, plotting a run -- wants one number.
`scalar()` provides one by packing the counts into a positional number with
base `CAP`, which reproduces the lexicographic order EXACTLY as long as no
severity level occurs `CAP` times or more in a single case. That bound is
asserted, not assumed: `scalar` raises rather than silently returning a
number that has wrapped and now claims a CRITICAL case is worth less than
a thousand LOWs.

HARMLESS ABSTENTION IS ZERO, AND IT IS NOT AN ERROR

A target that correctly declines scores nothing and that is the intended
outcome, not a failure to find something. An over-cautious abstention --
declining a change ground truth authorised -- scores LOW, which records it
without ever letting it compete with a case where something was damaged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Sequence, Tuple

from .signals import Judgement, Severity, Signal, failure_class

#: The largest number of signals at one severity the scalar packing can
#: represent without losing the ordering. Generous: a case producing a
#: thousand violations at one level is a broken oracle, not a finding.
CAP = 1000


@dataclass(frozen=True)
class Fitness:
    """The score of one case: counts by severity, and nothing else."""

    counts: Tuple[int, int, int, int, int]      # indexed by Severity value

    @property
    def critical(self) -> int:
        return self.counts[Severity.CRITICAL]

    @property
    def high(self) -> int:
        return self.counts[Severity.HIGH]

    @property
    def medium(self) -> int:
        return self.counts[Severity.MEDIUM]

    @property
    def low(self) -> int:
        return self.counts[Severity.LOW]

    @property
    def top(self) -> Severity:
        for level in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW):
            if self.counts[level]:
                return level
        return Severity.NONE

    @property
    def interesting(self) -> bool:
        """Whether this case found anything at all."""
        return self.top is not Severity.NONE

    def key(self) -> Tuple[int, int, int, int]:
        """The comparison key: severity counts, highest first."""
        return (self.counts[Severity.CRITICAL], self.counts[Severity.HIGH],
                self.counts[Severity.MEDIUM], self.counts[Severity.LOW])

    def scalar(self) -> int:
        """One number with the same ordering as `key`, within CAP."""
        total = 0
        for count in self.key():
            if count >= CAP:
                raise ValueError(
                    "a severity level occurred %d times, at or past the packing "
                    "cap of %d. The scalar would no longer order cases the way "
                    "`key` does, so it refuses rather than misreporting."
                    % (count, CAP))
            total = total * CAP + count
        return total

    def __lt__(self, other: "Fitness") -> bool:
        return self.key() < other.key()

    def __le__(self, other: "Fitness") -> bool:
        return self.key() <= other.key()

    def render(self) -> str:
        parts = ["%s %d" % (Severity(level).name.lower(), self.counts[level])
                 for level in (Severity.CRITICAL, Severity.HIGH,
                               Severity.MEDIUM, Severity.LOW)
                 if self.counts[level]]
        return ", ".join(parts) if parts else "nothing"

    def to_dict(self) -> Dict[str, int]:
        return {Severity(level).name.lower(): self.counts[level]
                for level in range(len(self.counts))}


NOTHING = Fitness((0, 0, 0, 0, 0))


def score(signals: Sequence[Signal]) -> Fitness:
    """The fitness of one case, from its signals.

    Only VIOLATION signals score. An INCONCLUSIVE oracle contributes
    nothing in either direction, which is the honest treatment: it did not
    establish a violation and it did not establish correctness either.
    """
    counts = [0, 0, 0, 0, 0]
    for signal in signals:
        if signal.judgement is Judgement.VIOLATION:
            counts[int(signal.severity)] += 1
    return Fitness(tuple(counts))              # type: ignore[arg-type]


def corroboration(signals: Sequence[Signal]) -> Mapping[str, int]:
    """How many DIFFERENT oracles are evidence for each failure class.

    Counting oracles rather than signals, and classes rather than kinds. One
    oracle reporting the same failure twice is one oracle; two oracles
    describing one event in their own vocabularies are two. See
    `signals.FAILURE_CLASSES` for why the second half of that is not
    optional.
    """
    by_class: Dict[str, set] = {}
    for signal in signals:
        if signal.judgement is Judgement.VIOLATION:
            by_class.setdefault(failure_class(signal.kind), set()).add(signal.oracle)
    return {name: len(oracles) for name, oracles in sorted(by_class.items())}


def confirmed(signals: Sequence[Signal], minimum_oracles: int = 2) -> Tuple[str, ...]:
    """Failure classes independently corroborated by at least N oracles."""
    return tuple(name for name, seen in corroboration(signals).items()
                 if seen >= minimum_oracles)
