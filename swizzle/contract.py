"""The compatibility contract other tools (Warden) can assert against SWIZZLE.

Warden runs SWIZZLE as a subprocess (``python -m swizzle.cli prove``,
``governor --json``, ``assay --json``) and reads what it prints. Nothing pinned
which SWIZZLE that was. ``swizzle --contract`` prints this document as JSON so a
caller can assert, before it relies on any output, that the SWIZZLE it found
speaks the dialect it expects.

``CONTRACT`` is an integer that changes only when something a caller parses
changes incompatibly: a command is removed or renamed, an exit code changes
meaning, a JSON field a caller reads is removed or changes type, or the line
``N of M proofs hold`` changes shape. Adding a command, a field or a new
optional flag does not change it. ``swizzle_version`` is informational (it moves
with every release); ``contract`` is what to compare. See docs/CONTRACT.md.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any, Dict

from ._version import __version__

#: Bump only for an incompatible change to what a caller parses. See docs/CONTRACT.md.
CONTRACT = 1

#: The name callers may assert on, so a different tool that also answers
#: ``--contract`` is not mistaken for SWIZZLE.
NAME = "swizzle"


def contract() -> Dict[str, Any]:
    """The contract as a plain dict (what ``swizzle --contract`` prints)."""
    from .governor.run import Finding
    from .governor.scenarios import SCENARIOS

    return {
        "name": NAME,
        "contract": CONTRACT,
        "swizzle_version": __version__,
        "invocation": ["python", "-m", "swizzle.cli"],
        "commands": {
            "prove": {
                "stdout_summary_line": r"^(\d+) of (\d+) proofs hold\.$",
                "exit_codes": {"0": "every selected proof holds",
                               "1": "a proof failed",
                               "2": "no proof ran, or --only named nothing"},
            },
            "governor": {
                "flags": ["--warden", "--json", "--only", "--list", "--assume-new-checks"],
                "json": "a list of finding objects on stdout; notes go to stderr",
                "finding_fields": [f.name for f in dataclasses.fields(Finding)],
                "status_values": ["held", "violated", "not_run"],
                "scenario_count": len(SCENARIOS),
                "exit_codes": {"0": "every selected scenario held",
                               "1": "a scenario was violated",
                               "2": "a scenario did not run, or a usage error",
                               "130": "interrupted"},
            },
            "assay": {
                "flags": ["--assay", "--ghost-tools", "--floor", "--json"],
                "json": "the ASSAY card on stdout",
                "exit_codes": {"0": "the key was scored (and met --floor, if given)",
                               "1": "Ghost caught fewer than --floor failure modes, or got worse",
                               "2": "the pairing could not run"},
            },
        },
    }


def render() -> str:
    return json.dumps(contract(), indent=2, sort_keys=True)
