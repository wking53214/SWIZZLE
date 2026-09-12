"""Six independent readings of the same run.

WHY SIX AND NOT ONE

Because one oracle is a single point of being wrong, and the failure mode
is silent. An oracle that has been quietly broken by a refactor reports
clean runs forever, and a clean run is exactly what a healthy target also
produces, so nothing ever looks wrong.

Independence here means something specific: each oracle answers a question
the others do not ask, from the same evidence, without consulting each
other's conclusions. The structural oracle asks what bytes moved. The
expectation oracle asks what ground truth authorised. The scope oracle asks
where the change landed and whether anything the target said accounts for
it. The temporal oracle asks whether the world the target reasoned about
still existed when it acted. The ledger oracle asks whether the target's
own account matches the tree. The semantic oracle asks whether the result
still works.

A finding corroborated by two of them is worth reporting. A finding seen by
exactly one is worth investigating, and `corpus promote` will not turn it
into a regression test without a second signal or an explicit override.

NONE OF THEM MAY IMPORT AN ADAPTER. Tests/test_oracle_independence.py walks
the import graph and fails if any of them can reach one.
"""

from __future__ import annotations

from typing import Callable, Dict, Mapping, Sequence, Tuple

from ..evidence import Evidence
from ..signals import Signal

Oracle = Callable[[Evidence], Sequence[Signal]]

from . import expectation, ledger, scope, semantic, structural, temporal  # noqa: E402

#: Order is presentation only; no oracle depends on another's output.
ORACLES: Dict[str, Oracle] = {
    "structural": structural.judge,
    "expectation": expectation.judge,
    "scope": scope.judge,
    "temporal": temporal.judge,
    "ledger": ledger.judge,
    "semantic": semantic.judge,
}


def judge_all(evidence: Evidence,
              only: Sequence[str] = ()) -> Tuple[Signal, ...]:
    """Every oracle's reading of one case.

    An oracle that raises is reported as INCONCLUSIVE rather than crashing
    the run: a broken oracle must not be able to hide the other five, and it
    must not be able to masquerade as a clean result either.
    """
    from ..signals import unsure
    out = []
    for name, oracle in ORACLES.items():
        if only and name not in only:
            continue
        try:
            out.extend(oracle(evidence))
        except Exception as exc:                    # the oracle is the subject
            out.append(unsure(name, "oracle_failed",
                              "the %s oracle raised %s" % (name, type(exc).__name__),
                              detail=str(exc)))
    return tuple(out)
