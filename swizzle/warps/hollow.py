"""A method that does nothing, called by code that believes it did.

`dead_end_call` is the detector this repository's author is proudest of,
and rightly: it reports a callable whose body does nothing while live code
calls it, and it suppresses that report when the emptiness is DECLARED --
an abstract method, a Protocol, a plugin seam. Declaring the seam is how
you say "empty on purpose", and the declaration is read off the class's
bases by name.

Which means the declaration can be worn rather than earned. `ABC` with no
abstract methods on it is an ordinary, instantiable class. Python does not
object, no reader flinches at `from abc import ABC`, and the detector
reads the base name and stops.
"""

from __future__ import annotations

from pathlib import Path

from ..proving import imported
from ..schema import Control, Disclosure, Proof, TrueName, Warp, locate

_HOLLOW_UNDER_ABC = r'''"""Audit sinks."""

from abc import ABC


class FileAuditSink(ABC):
    """Appends audit entries to the audit log."""

    def __init__(self, path):
        self.path = path
        self.written = []

    def record(self, entry):  # swizzle:true-name
        """Append `entry` to the audit log, one line per entry."""


def audit(sink, entry):
    """Record `entry`. Returns True once the entry is durable."""
    sink.record(entry)
    return True
'''


_CONTROL_UNDER_NOTHING = r'''"""Audit sinks."""


class FileAuditSink:
    """Appends audit entries to the audit log."""

    def __init__(self, path):
        self.path = path
        self.written = []

    def record(self, entry):  # swizzle:true-name
        """Append `entry` to the audit log, one line per entry."""


def audit(sink, entry):
    """Record `entry`. Returns True once the entry is durable."""
    sink.record(entry)
    return True
'''


def _records_nothing(root: Path) -> Proof:
    """Audit an entry, then look in the log for it."""
    with imported(root, "app.audit") as module:
        sink = module.FileAuditSink("/tmp/audit.log")
        returned = module.audit(sink, "user 1 deleted account 2")
        written = list(sink.written)
    holds = bool(returned) and not written
    return Proof(
        holds=holds,
        kind="executed",
        account=("audit() returned %r and the sink holds %d entr(ies). The "
                 "caller has been told the record is durable."
                 % (returned, len(written))),
    )


behind_an_abstract_base = Warp(
    name="hollow_behind_an_abstract_base",
    targets="dead_end_call",
    intent=("A concrete, instantiated, called class whose one method has a "
            "docstring and no body. It declares `ABC` as a base and no "
            "abstract methods, which is not an abstract class in any sense "
            "Python enforces, but is the exact spelling the seam test looks "
            "for."),
    disclosure=Disclosure.EXCLUSION_ABUSE,
    disclosure_quote=("declared by inheritance    ABC, ABCMeta or Protocol "
                      "base"),
    files={
        "app/__init__.py": "",
        "app/audit.py": _HOLLOW_UNDER_ABC,
    },
    true_name=TrueName(
        detector="dead_end_call",
        file="app/audit.py",
        line_start=locate(_HOLLOW_UNDER_ABC),
        line_end=locate(_HOLLOW_UNDER_ABC) + 1,
        why=("`record` is documented, called, and empty, on a class that is "
             "instantiated. Nothing about the class is abstract except the "
             "word in its base list."),
    ),
    tolerated=("dead_code",),
    control=Control(
        files={
            "app/__init__.py": "",
            "app/audit.py": _CONTROL_UNDER_NOTHING,
        },
        true_name=TrueName(
            detector="dead_end_call",
            file="app/audit.py",
            line_start=locate(_CONTROL_UNDER_NOTHING),
            line_end=locate(_CONTROL_UNDER_NOTHING) + 1,
            why="The same hollow method on a class that claims nothing.",
        ),
        removed="the `ABC` base and its import",
    ),
    prove=_records_nothing,
)


WARPS = (behind_an_abstract_base,)
