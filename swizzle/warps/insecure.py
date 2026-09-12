"""Two insecure defaults that are not assignments and not `run(debug=True)`.

`insecure_default` is a list of exact shapes: an assignment to a name
called DEBUG whose value is True, an ALLOWED_HOSTS of `["*"]`, a call
named `run` with `debug=True`, CORS with both a star origin and
credentials, and a call with `verify=False`. Every one of them is a real
pattern and the list is the right way to build this check -- shapes, not
guesses about intent.

A list of shapes has an outside. The value can be true without the
literal `True` appearing at the shape: it can sit in a function's default
argument and arrive at the call as a name, or go into the configuration
through a method that is not spelled `run`. Both warps below are
ordinary-looking code with the insecure value genuinely in effect at
runtime, which each one proves by looking at what the call actually
received.
"""

from __future__ import annotations

from pathlib import Path

from ..proving import imported
from ..schema import Disclosure, Proof, TrueName, Warp, locate

# ------------------------------------------------- verify=False, one hop away

_TLS_DEFAULT = r'''"""The HTTP client every service grows, wrapping one library call."""

CALLS = []


class _Session:
    """Stands in for `requests`, so the warp needs nothing installed.

    It records what it was asked to do, which is all the proof needs: the
    question is what value of `verify` reaches the transport.
    """

    @staticmethod
    def get(url, verify=True, timeout=None):
        CALLS.append({"url": url, "verify": verify})
        return {"url": url, "verify": verify, "status": 200}


session = _Session()


def fetch(url, verify=False):  # swizzle:true-name
    """GET `url` and return the decoded response."""
    return session.get(url, verify=verify, timeout=10)


def fetch_profile(user_id):
    return fetch("https://accounts.internal/profile/%s" % user_id)
'''


def _tls_is_off(root: Path) -> Proof:
    with imported(root, "app.http") as module:
        module.fetch_profile(7)
        call = module.CALLS[-1]
    return Proof(
        holds=call["verify"] is False,
        kind="executed",
        account=("the transport received verify=%r for %s. No caller wrote "
                 "False; the signature did." % (call["verify"], call["url"])),
    )


tls_off_by_default = Warp(
    name="tls_off_by_default_argument",
    targets="insecure_default",
    intent=("`verify=False` is checked as a keyword at a call site. Here it "
            "is a default in a function signature, so every call site says "
            "`verify=verify` and passes a name. The certificate is fetched "
            "and ignored on every request that does not opt back in."),
    disclosure=Disclosure.UNDISCLOSED,
    files={
        "app/__init__.py": "",
        "app/http.py": _TLS_DEFAULT,
    },
    true_name=TrueName(
        detector="insecure_default",
        file="app/http.py",
        line_start=locate(_TLS_DEFAULT),
        line_end=locate(_TLS_DEFAULT) + 2,
        why=("TLS verification is disabled for every caller that does not "
             "name it, which is all of them."),
    ),
    tolerated=("dead_code",),
    prove=_tls_is_off,
)


# ------------------------------------------------ DEBUG=True, through a dict

_DEBUG_CONFIG = r'''"""Application configuration."""


class Application:
    """Stands in for the web framework: a config dict and nothing else."""

    def __init__(self):
        self.config = {"DEBUG": False, "SECRET_KEY": "change-me"}


def configure(app):
    """Apply the deployment configuration to `app`."""
    app.config.update(DEBUG=True)  # swizzle:true-name
    return app


def build():
    return configure(Application())
'''


def _debug_is_on(root: Path) -> Proof:
    with imported(root, "app.settings") as module:
        app = module.build()
        value = app.config["DEBUG"]
    return Proof(
        holds=value is True,
        kind="executed",
        account="the built application reports config['DEBUG'] = %r." % (value,),
    )


debug_through_config_update = Warp(
    name="debug_true_through_config_update",
    targets="insecure_default",
    intent=("DEBUG is caught when it is a module-level assignment. This one "
            "goes in through `config.update(DEBUG=True)`, which is how Flask "
            "configuration is usually written, and is a call named `update` "
            "rather than a call named `run` or an assignment to a name."),
    disclosure=Disclosure.UNDISCLOSED,
    files={
        "app/__init__.py": "",
        "app/settings.py": _DEBUG_CONFIG,
    },
    true_name=TrueName(
        detector="insecure_default",
        file="app/settings.py",
        line_start=locate(_DEBUG_CONFIG),
        line_end=locate(_DEBUG_CONFIG),
        why=("Debug is on in the built application. The interactive console "
             "does not care which syntax switched it on."),
    ),
    tolerated=("dead_code",),
    prove=_debug_is_on,
)


WARPS = (tls_off_by_default, debug_through_config_update)
