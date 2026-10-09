r"""Four ways an injectable query stays quiet.

ghost_buster's `sql_injection` is unusually well built for an AST-only
check. It reports interpolation INTO a statement THAT IS EXECUTED, it
walks to the leftmost operand of a concatenation because that is how the
bug is actually written, and it refuses to report a runtime-built string
it cannot see executed. Everything below respects that design and goes
around it, because going around a good check is the only way to learn
where its edge is.

The four edges, in the order they are defined here:

  1. The interpolation is an argument to `execute`, so the check looks at
     the argument node. Put the same f-string in a variable on the line
     above and the argument node is a Name.
  2. The call must be one of six executor names. A repository with its own
     thin database wrapper has none of them at its call sites.
  3. Any path with `test`, `tests`, `testing` or `fixtures` in it is
     skipped, because a permissive setting inside a test is usually the
     subject of the test. Production code living under `testing/` inherits
     the exemption.
  4. A string is SQL only if it OPENS with a statement keyword, anchored
     at `^\s*`. A leading SQL comment is not whitespace.

Each warp is the smallest repository that carries the defect and can be
made to demonstrate it, and each proves itself by returning a row the
caller was never entitled to.
"""

from __future__ import annotations

from pathlib import Path

from ..proving import imported, seeded_users
from ..schema import Control, Disclosure, Proof, TrueName, Warp, locate

_TOLERATED = ("dead_code",)


def _injects(root: Path, dotted: str, call: str) -> Proof:
    """Run the warp's lookup honestly, then dishonestly.

    `id=1` must return exactly the one row it asks for, and `1 OR 1=1`
    must return both -- the second row is the proof, because no amount of
    quoting or validation upstream could have produced it from a value.
    """
    with imported(root, dotted) as module:
        conn = seeded_users()
        finder = getattr(module, call)
        honest = finder(conn, 1)
        injected = finder(conn, "1 OR 1=1")
    holds = len(honest) == 1 and len(injected) == 2
    return Proof(
        holds=holds,
        kind="executed",
        account=("id=1 returned %d row(s); id=\"1 OR 1=1\" returned %d. %s"
                 % (len(honest), len(injected),
                    "The interpolated text became part of the statement."
                    if holds else
                    "Expected 1 and 2, so the injection was NOT shown.")),
    )


# ---------------------------------------------------------------- 1. a name

_THROUGH_A_NAME = r'''"""User lookup."""


def find_user(conn, uid):
    """Every row this caller is entitled to, for `uid`."""
    statement = f"SELECT id, name FROM users WHERE id = {uid}"
    cursor = conn.cursor()
    cursor.execute(statement)  # swizzle:true-name
    return cursor.fetchall()
'''

_MAIN = r'''"""Entry point, so the lookup is live code rather than an orphan."""

from app.queries import find_user


def main(conn, uid):
    return find_user(conn, uid)
'''

through_a_name = Warp(
    name="sql_through_a_name",
    targets="sql_injection",
    intent=("The f-string is assigned to a variable on the line above the "
            "execute call, so the argument node the detector inspects is a "
            "Name and there is nothing in it to interpolate."),
    disclosure=Disclosure.UNDISCLOSED,
    files={
        "app/__init__.py": "",
        "app/queries.py": _THROUGH_A_NAME,
        "main.py": _MAIN,
    },
    true_name=TrueName(
        detector="sql_injection",
        file="app/queries.py",
        line_start=locate(_THROUGH_A_NAME) - 1,
        line_end=locate(_THROUGH_A_NAME),
        why=("A statement built by f-string from a caller-supplied value is "
             "executed two lines later. The variable is not a boundary."),
    ),
    tolerated=_TOLERATED,
    prove=lambda root: _injects(root, "app.queries", "find_user"),
)


# ------------------------------------------------------------- 2. a wrapper

_WRAPPER_DB = r'''"""The thin database wrapper every repository eventually grows."""


class Database:
    """One connection, one method, no driver details at the call sites."""

    def __init__(self, conn):
        self._conn = conn

    def run(self, statement):
        cursor = self._conn.cursor()
        cursor.execute(statement)
        return cursor.fetchall()
'''

_WRAPPER_ACCOUNTS = r'''"""Account lookups, written against the wrapper."""

from app.db import Database


def find_account(db, uid):
    return db.run(f"SELECT id, name FROM users WHERE id = {uid}")  # swizzle:true-name


def open_database(conn):
    return Database(conn)


def find_user(conn, uid):
    """The shape the proof calls: connection in, rows out."""
    return find_account(open_database(conn), uid)
'''

behind_a_wrapper = Warp(
    name="sql_behind_a_wrapper",
    targets="sql_injection",
    intent=("The interpolation is a direct argument to a call, exactly as the "
            "detector expects -- but the call is `db.run`, and the executor "
            "allow-list holds six names that are not it. Inside the wrapper "
            "the real `execute` receives a Name, which warp 1 already showed "
            "is quiet."),
    disclosure=Disclosure.UNDISCLOSED,
    files={
        "app/__init__.py": "",
        "app/db.py": _WRAPPER_DB,
        "app/accounts.py": _WRAPPER_ACCOUNTS,
    },
    true_name=TrueName(
        detector="sql_injection",
        file="app/accounts.py",
        line_start=locate(_WRAPPER_ACCOUNTS),
        line_end=locate(_WRAPPER_ACCOUNTS),
        why=("Interpolated SQL handed to a method that executes it. The name "
             "of the method is not a property of the vulnerability."),
    ),
    tolerated=_TOLERATED,
    prove=lambda root: _injects(root, "app.accounts", "find_user"),
)


# --------------------------------------------------- 3. a costume named test

_IN_TESTING = r'''"""Fixture data endpoints. Imported by the service at runtime."""


def find_user(conn, uid):
    cursor = conn.cursor()
    cursor.execute(f"SELECT id, name FROM users WHERE id = {uid}")  # swizzle:true-name
    return cursor.fetchall()
'''

_TESTING_CALLER = r'''"""The production path that reaches into the fixtures package."""

from service.testing.lookup import find_user


def handle(conn, request_uid):
    return find_user(conn, request_uid)
'''

in_a_place_called_testing = Warp(
    name="sql_in_a_place_called_testing",
    targets="sql_injection",
    intent=("Byte for byte the injection the detector was written to catch, "
            "and it is caught when the file sits in `app/`. This copy sits in "
            "`service/testing/`, and any path component called test, tests, "
            "testing or fixtures is skipped before the file is parsed."),
    disclosure=Disclosure.EXCLUSION_ABUSE,
    disclosure_quote=("A permissive setting inside a test is usually the "
                      "subject of the test. Matched on the path, not the "
                      "content"),
    files={
        "service/__init__.py": "",
        "service/testing/__init__.py": "",
        "service/testing/lookup.py": _IN_TESTING,
        "service/api.py": _TESTING_CALLER,
    },
    true_name=TrueName(
        detector="sql_injection",
        file="service/testing/lookup.py",
        line_start=locate(_IN_TESTING),
        line_end=locate(_IN_TESTING),
        why=("The exemption is for code that is the subject of a test. This "
             "is live code that a request reaches, in a directory that "
             "happens to be spelled `testing`."),
    ),
    tolerated=_TOLERATED,
    control=Control(
        files={
            "app/__init__.py": "",
            "app/lookup.py": _IN_TESTING,
        },
        true_name=TrueName(
            detector="sql_injection",
            file="app/lookup.py",
            line_start=locate(_IN_TESTING),
            line_end=locate(_IN_TESTING),
            why="The same bytes, in a directory with an ordinary name.",
        ),
        removed="the `testing/` directory in the path",
        prove=lambda root: _injects(root, "app.lookup", "find_user"),
    ),
    prove=lambda root: _injects(root, "service.testing.lookup", "find_user"),
)


# ------------------------------------------------------- 4. a leading comment

_LEADING_COMMENT = r'''"""Audited lookups. Every statement carries its reason."""


def find_user(conn, uid):
    cursor = conn.cursor()
    cursor.execute(  # swizzle:true-name
        f"-- audit: user lookup\nSELECT id, name FROM users WHERE id = {uid}"
    )
    return cursor.fetchall()
'''

behind_a_comment = Warp(
    name="sql_behind_a_comment",
    targets="sql_injection",
    intent=("The statement is recognised as SQL only if it opens with a "
            "statement keyword, anchored at the start of the string. This one "
            "opens with a SQL comment -- which the database strips and the "
            "regex does not, because a comment is not whitespace."),
    disclosure=Disclosure.UNDISCLOSED,
    files={
        "app/__init__.py": "",
        "app/audit.py": _LEADING_COMMENT,
    },
    true_name=TrueName(
        detector="sql_injection",
        file="app/audit.py",
        line_start=locate(_LEADING_COMMENT),
        line_end=locate(_LEADING_COMMENT) + 2,
        why=("An executed, interpolated statement. The leading comment "
             "changes what the regex sees and nothing about what the driver "
             "runs."),
    ),
    tolerated=_TOLERATED,
    prove=lambda root: _injects(root, "app.audit", "find_user"),
)


WARPS = (through_a_name, behind_a_wrapper, in_a_place_called_testing,
         behind_a_comment)
