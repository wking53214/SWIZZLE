"""Warps with nothing wrong with them.

An adversary that only plants defects measures one half of a scanner. The
other half is what it says about code that is fine, and that half is the
one that decides whether anybody keeps reading the report. So two of the
warps in the catalogue carry no defect at all, declare which detectors are
forbidden to fire on them, and prove their own innocence the same way the
others prove guilt -- by running.

DISMISSED is the good outcome here. CONJURED is a false positive, and one
of these two is expected to produce one: ghost_buster states in its own
`dead_code` docstring that decorator-based registration is still untraced
and that it self-flags on its own `@register` pattern. Keeping a warp in
the catalogue for a false positive the author already documented is the
same decision as keeping the DISCLOSED escapes: the report is about
coverage, not about who knew what.
"""

from __future__ import annotations

from pathlib import Path

from ..proving import imported, seeded_users
from ..schema import Disclosure, Proof, Warp

# ------------------------------------------------- parameterised, and loud

_PARAMETERISED = r'''"""Reporting queries. Every one of them binds its values."""


def find_user(conn, uid):
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM users WHERE id = ?", (uid,))
    return cursor.fetchall()


def purge(conn, before):
    """Delete events older than `before`. Bounded, and bound."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id > ?", (before,))
    return cursor.rowcount


def describe(uid):
    """A log line that opens with the word SELECT and is never executed."""
    return f"SELECT for user {uid} served from cache"


def label(kind):
    """A .format() call on a string that opens with SELECT. Also not SQL."""
    return "SELECT {} rows".format(kind)
'''


def _binds_its_values(root: Path) -> Proof:
    """Try the injection that works on the other warps and watch it fail."""
    with imported(root, "app.reports") as module:
        conn = seeded_users()
        honest = module.find_user(conn, 1)
        attempted = module.find_user(conn, "1 OR 1=1")
    return Proof(
        holds=len(honest) == 1 and len(attempted) == 0,
        kind="executed",
        account=("id=1 returned %d row(s); id=\"1 OR 1=1\" returned %d. The "
                 "text was compared as a value, not run as SQL."
                 % (len(honest), len(attempted))),
    )


parameterised_but_alarming = Warp(
    name="parameterised_but_alarming",
    targets="sql_injection",
    intent=("Four functions that all look like the defect and none of which "
            "are it: two parameterised executes, an f-string opening with "
            "SELECT that is a log line, and a `.format()` on a SELECT string "
            "that is never handed to a driver."),
    disclosure=Disclosure.UNDISCLOSED,
    files={
        "app/__init__.py": "",
        "app/reports.py": _PARAMETERISED,
    },
    true_name=None,
    forbidden=("sql_injection", "destructive_sql"),
    tolerated=("dead_code",),
    prove=_binds_its_values,
)


# --------------------------------------------- live, through a decorator

_REGISTERED = r'''"""Commands, registered by decorator and dispatched by name."""

REGISTRY = {}


def command(fn):
    """Register `fn` under its own name and return it unchanged."""
    REGISTRY[fn.__name__] = fn
    return fn


@command
def export_ledger(entries):
    """Write the entry log out as CSV rows."""
    return ["%s,%s" % (account, amount) for account, amount in entries]


def run(name, entries):
    """Dispatch to a registered command."""
    return REGISTRY[name](entries)
'''


def _dispatches(root: Path) -> Proof:
    with imported(root, "app.commands") as module:
        rows = module.run("export_ledger", [("cash", 10), ("bank", 20)])
        registered = sorted(module.REGISTRY)
    return Proof(
        holds=rows == ["cash,10", "bank,20"] and registered == ["export_ledger"],
        kind="executed",
        account=("dispatch returned %r with %s registered. The function runs; "
                 "no `ast.Name` in the repository says so."
                 % (rows, registered)),
    )


dispatch_by_decorator = Warp(
    name="dispatch_by_decorator",
    targets="dead_code",
    intent=("A command that is registered by a decorator and reached through "
            "the registry. It is live -- the proof calls it -- and its name "
            "never appears as a name anywhere, which is the shape `dead_code` "
            "reports."),
    disclosure=Disclosure.DISCLOSED,
    disclosure_quote=("decorator-based registration (this tool's own @register "
                      "pattern is the concrete example -- it self-flags on "
                      "ghost_buster's own codebase, see README) are still "
                      "untraced"),
    files={
        "app/__init__.py": "",
        "app/commands.py": _REGISTERED,
    },
    true_name=None,
    forbidden=("dead_code",),
    prove=_dispatches,
)


WARPS = (parameterised_but_alarming, dispatch_by_decorator)
