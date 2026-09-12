"""Two failures that are lost without a `pass` anywhere in sight.

`swallowed_exception` reports a handler whose entire body is `pass`, and
it says in its own docstring why it stops there: a `continue` in a retry
loop is often exactly right, and rating it alongside `except Exception:
pass` teaches the reader of the report to skim. That is a defensible
place to stop and it is documented, so both warps here are DISCLOSED.
They are in the catalogue anyway, because a disclosed gap is still a gap
and the number that matters is how much of the real failure surface the
report covers, not how much of it the author knew about.

What both warps share is the shape that makes the defect dangerous: the
function returns success. Not `None`, not an error, not a raised
exception the caller could notice -- True, on the path where nothing was
delivered.
"""

from __future__ import annotations

from pathlib import Path

from ..proving import imported
from ..schema import Disclosure, Proof, TrueName, Warp, locate

_QUOTE = ("Only `pass`. A handler whose body is `continue`, `return None` or "
          "a lone `logger.debug(...)` swallows just as thoroughly, and each "
          "would need its own measurement before it earned a place here")

_SUPPRESS_QUOTE = ("`contextlib.suppress` is deliberately not flagged at all: "
                   "it says in its own name what it does, which is the "
                   "opposite of the defect.")


def _loses_the_failure(root: Path, dotted: str) -> Proof:
    """Publish through a transport that always fails, and see what comes back.

    The defect is not that sending failed. It is that `publish` returned
    the same value it returns on success, so no caller can tell the two
    apart, and the delivery list is empty.
    """
    with imported(root, dotted) as module:
        transport = module.Transport(fail=True)
        returned = module.publish(transport, {"id": 1})
        delivered = list(transport.delivered)
        healthy = module.Transport(fail=False)
        happy = module.publish(healthy, {"id": 2})
    holds = returned == happy and not delivered
    return Proof(
        holds=holds,
        kind="executed",
        account=("failing transport returned %r, working transport returned "
                 "%r, delivered %d event(s). Success and failure are the same "
                 "value to the caller." % (returned, happy, len(delivered))),
    )


# ------------------------------------------------------- a handler that logs

_LOGGING_HANDLER = r'''"""Event publishing."""

import logging

logger = logging.getLogger(__name__)


class Transport:
    """Delivers events, or does not."""

    def __init__(self, fail=False):
        self.fail = fail
        self.delivered = []

    def send(self, event):
        if self.fail:
            raise RuntimeError("transport unavailable")
        self.delivered.append(event)


def publish(transport, event):
    """Publish `event`. Returns True when the event has been published."""
    try:
        transport.send(event)
    except Exception:  # swizzle:true-name
        logger.debug("publish failed")
    return True
'''

logs_and_carries_on = Warp(
    name="handler_that_logs_and_carries_on",
    targets="swallowed_exception",
    intent=("The handler body is one `logger.debug` call instead of one "
            "`pass`, so it is not an empty body. Everything the empty body "
            "would have hidden is hidden, at a level nobody has switched on, "
            "and the function returns True either way."),
    disclosure=Disclosure.DISCLOSED,
    disclosure_quote=_QUOTE,
    files={
        "app/__init__.py": "",
        "app/publishing.py": _LOGGING_HANDLER,
    },
    true_name=TrueName(
        detector="swallowed_exception",
        file="app/publishing.py",
        line_start=locate(_LOGGING_HANDLER),
        line_end=locate(_LOGGING_HANDLER) + 1,
        why=("`except Exception` around the only line that does the work, a "
             "body that cannot fail, and an unconditional success return."),
    ),
    tolerated=("dead_code",),
    prove=lambda root: _loses_the_failure(root, "app.publishing"),
)


# ------------------------------------------------- suppress around the lot

_SUPPRESSED = r'''"""Event publishing, with the handler moved into a context manager."""

from contextlib import suppress


class Transport:
    """Delivers events, or does not."""

    def __init__(self, fail=False):
        self.fail = fail
        self.delivered = []

    def send(self, event):
        if self.fail:
            raise RuntimeError("transport unavailable")
        self.delivered.append(event)


def publish(transport, event):
    """Publish `event`. Returns True when the event has been published."""
    with suppress(Exception):  # swizzle:true-name
        transport.send(event)
        record(event)
    return True


def record(event):
    """Write the event to the outbox."""
    OUTBOX.append(event)


OUTBOX = []
'''

suppress_around_everything = Warp(
    name="suppress_around_everything",
    targets="swallowed_exception",
    intent=("`contextlib.suppress` is exempt because it names what it does. "
            "The name is honest about suppression and silent about scope: "
            "this one wraps two statements, so a failure in the first also "
            "skips the second, and the exemption covers `Exception` as "
            "readily as it covers one narrow class."),
    disclosure=Disclosure.DISCLOSED,
    disclosure_quote=_SUPPRESS_QUOTE,
    files={
        "app/__init__.py": "",
        "app/outbox.py": _SUPPRESSED,
    },
    true_name=TrueName(
        detector="swallowed_exception",
        file="app/outbox.py",
        line_start=locate(_SUPPRESSED),
        line_end=locate(_SUPPRESSED) + 2,
        why=("Suppressing `Exception` across two statements, one of which is "
             "the record-keeping the other depends on, under a success "
             "return."),
    ),
    tolerated=("dead_code",),
    prove=lambda root: _loses_the_failure(root, "app.outbox"),
)


WARPS = (logs_and_carries_on, suppress_around_everything)
