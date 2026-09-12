"""A function nothing calls, kept alive by a help string.

`dead_code` is deliberately conservative and says so at length: it would
rather miss a dead definition than call a live one dead. One of its
exclusions, added after a real false positive on a live repository, is
that a NAME-SHAPED STRING USED AS A SUBSCRIPT KEY counts as a reference,
because `registry["SomeName"]` is how a great deal of real dispatch works
and flagging all of it would produce noise instead of findings.

The cost of that generosity is that any string literal anywhere in the
repository, in any subscript, can hold any definition up. It does not have
to be a dispatch table and it does not have to reach the definition at
all. A help text keyed by command name will do, which is what this warp
is: a command unwired from the CLI, left in the tree, with its help entry
still listed under `--help`.

The control isolates the subscript and nothing else. It keeps the same
help dictionary, with the same key spelled the same way in the same file,
and removes only the one place that READS that key by literal. If the
control is reported and the warp is not, the subscript is the entire
difference.
"""

from __future__ import annotations

import ast
from pathlib import Path

from ..schema import Control, Disclosure, Proof, TrueName, Warp, locate

_DEAD = r'''"""Ledger commands."""


def reconcile_ledger(entries):  # swizzle:true-name
    """Recompute every balance from the entry log and return the totals."""
    totals = {}
    for account, amount in entries:
        totals[account] = totals.get(account, 0) + amount
    return totals
'''

_HELP = r'''"""Help text, keyed by command name."""

HELP = {
    "reconcile_ledger": "recompute every balance from the entry log",
    "export_ledger": "write the entry log to CSV",
}


def help_for(topic):
    """The one-line description of `topic`."""
    return HELP[topic]


def ledger_help():
    """The paragraph printed under `ledger --help`."""
    return "%s\n%s" % (HELP["reconcile_ledger"], help_for("export_ledger"))
'''

#: The control. Same dictionary, same key, same spelling; the function that
#: reads the key by literal is gone.
_HELP_CONTROL = r'''"""Help text, keyed by command name."""

HELP = {
    "reconcile_ledger": "recompute every balance from the entry log",
    "export_ledger": "write the entry log to CSV",
}


def help_for(topic):
    """The one-line description of `topic`."""
    return HELP[topic]


def ledger_help():
    """The paragraph printed under `ledger --help`."""
    return help_for("export_ledger")
'''

_CLI = r'''"""The command line, and what it actually dispatches to."""

from app.help import help_for, ledger_help

COMMANDS = ("export_ledger",)


def main(argv):
    """Run one command, or print help."""
    if not argv:
        return ledger_help()
    if argv[0] in COMMANDS:
        return help_for(argv[0])
    return "unknown command"
'''

_INIT = r'''"""The ledger application."""

from app.cli import main

__all__ = ["main"]
'''


def _nothing_calls_it(root: Path) -> Proof:
    """Assert over the syntax trees that the name is never used as a name.

    There is nothing to execute: the defect IS the absence of a call. So
    the proof walks every file in the warp and counts the occurrences that
    are references -- an `ast.Name`, an `ast.Attribute`, an import -- and
    requires that what is left is the definition and string literals.
    """
    target = "reconcile_ledger"
    referenced, strings = [], []
    for path in sorted(Path(root).rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == target:
                referenced.append("%s:%d" % (path.name, node.lineno))
            elif isinstance(node, ast.Attribute) and node.attr == target:
                referenced.append("%s:%d" % (path.name, node.lineno))
            elif isinstance(node, ast.alias) and target in (node.name, node.asname):
                referenced.append("%s import" % path.name)
            elif isinstance(node, ast.Constant) and node.value == target:
                strings.append("%s:%d" % (path.name, node.lineno))
    return Proof(
        holds=not referenced and bool(strings),
        kind="structural",
        account=("`%s` is defined once and referenced as a name %d time(s); it "
                 "survives only as a string literal, at %s."
                 % (target, len(referenced), ", ".join(strings) or "nowhere")),
    )


kept_alive_by_a_string = Warp(
    name="dead_code_kept_alive_by_a_string",
    targets="dead_code",
    intent=("The command is gone from the dispatch table and nothing imports "
            "it. Its name still appears in a help dictionary, and one of "
            "those appearances is a subscript key, which counts as a "
            "reference on the grounds that string-keyed dispatch is real. "
            "Here it is documentation."),
    disclosure=Disclosure.EXCLUSION_ABUSE,
    disclosure_quote=("A STRING CONSTANT USED AS A SUBSCRIPT KEY counts as a "
                      "reference too"),
    files={
        "app/__init__.py": _INIT,
        "app/ledger.py": _DEAD,
        "app/help.py": _HELP,
        "app/cli.py": _CLI,
    },
    true_name=TrueName(
        detector="dead_code",
        file="app/ledger.py",
        line_start=locate(_DEAD),
        line_end=locate(_DEAD),
        why=("Defined, never imported, never called, absent from the command "
             "table. The only thing holding it up is a help string."),
    ),
    tolerated=("dead_code",),
    control=Control(
        files={
            "app/__init__.py": _INIT,
            "app/ledger.py": _DEAD,
            "app/help.py": _HELP_CONTROL,
            "app/cli.py": _CLI,
        },
        true_name=TrueName(
            detector="dead_code",
            file="app/ledger.py",
            line_start=locate(_DEAD),
            line_end=locate(_DEAD),
            why="The same dead command, with nothing reading its key.",
        ),
        removed="the one subscript that reads HELP by literal key",
    ),
    prove=_nothing_calls_it,
)


WARPS = (kept_alive_by_a_string,)
