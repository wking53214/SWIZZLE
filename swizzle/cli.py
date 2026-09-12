"""The command line."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Sequence

from . import __version__
from .invoke import git_available, locate_ghost_tools
from .report import as_dicts, render
from .run import prove, run_all
from .schema import Verdict, Warp
from .summon import summon
from .warps import by_name, catalogue


def _detach_stdout() -> None:
    """Point stdout at the void, because the reader has gone.

    Closing it is not enough: Python flushes stdout during interpreter
    shutdown, and that flush raises `BrokenPipeError` again somewhere no
    handler can reach. Replacing the file descriptor gives the final flush
    somewhere harmless to go, which is the documented fix and the reason
    this is not one line of `except BrokenPipeError: pass`.
    """
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, sys.stdout.fileno())


def _selected(pattern: str | None) -> List[Warp]:
    warps = list(catalogue())
    if not pattern:
        return warps
    return [w for w in warps if pattern in w.name or pattern in w.targets]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="swizzle",
        description="A reality warper with a defeat condition: it builds "
                    "repositories with proven defects in them, declares the "
                    "finding that would banish each one, and reports which "
                    "ones ghost_buster named.")
    parser.add_argument("--version", action="version",
                        version="swizzle %s" % __version__)
    sub = parser.add_subparsers(dest="command")

    listing = sub.add_parser("list", help="the catalogue")
    listing.add_argument("--only", default=None, metavar="SUBSTRING",
                         help="warps whose name or target contains this")

    proving = sub.add_parser(
        "prove", help="run every warp's proof and nothing else -- the check "
                      "that SWIZZLE is not claiming defects it does not have")
    proving.add_argument("--only", default=None, metavar="SUBSTRING")

    running = sub.add_parser("run", help="build, scan, score")
    running.add_argument("--only", default=None, metavar="SUBSTRING")
    running.add_argument("--ghost-tools", type=Path, default=None, metavar="PATH",
                         help="the ghost_tools checkout (default: importable, "
                              "then $GHOST_TOOLS, then a sibling directory)")
    running.add_argument("--json", action="store_true",
                         help="emit the result as JSON instead of the report")
    running.add_argument("--keep", type=Path, default=None, metavar="DIR",
                         help="build the warps here and leave them behind")
    running.add_argument("--fail-on-escape", action="store_true",
                         help="exit non-zero if any warp escaped or any decoy "
                              "was flagged (for CI; the default exit code "
                              "reports only SWIZZLE's own failures)")

    summoning = sub.add_parser("summon", help="write one warp to disk")
    summoning.add_argument("warp")
    summoning.add_argument("--into", type=Path, default=Path.cwd(), metavar="DIR")

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    handler = {"list": _list, "prove": _prove, "run": _run,
               "summon": _summon}[args.command]
    try:
        return handler(args)
    except BrokenPipeError:
        # `swizzle list | head` is a reasonable thing to type, and a
        # traceback is not a reasonable thing to get back for it.
        _detach_stdout()
        return 0


def _list(args) -> int:
    warps = _selected(args.only)
    for warp in warps:
        kind = "decoy " if warp.is_decoy else "defect"
        print("%-34s %-20s %s %s" % (warp.name, warp.targets, kind,
                                     warp.disclosure.value))
        if warp.true_name is not None:
            print("    banished by  %s at %s:%s"
                  % (warp.true_name.detector, warp.true_name.file,
                     warp.true_name.line_start or "-"))
        else:
            print("    must not say %s" % ", ".join(warp.forbidden))
    print()
    print("%d warp(s)." % len(warps))
    return 0


def _prove(args) -> int:
    import tempfile
    warps = _selected(args.only)
    failed = 0
    with tempfile.TemporaryDirectory(prefix="swizzle-prove-") as scratch:
        workspace = Path(scratch)
        for warp in warps:
            root = summon(warp, workspace)
            proof = prove(warp, root)
            status = "holds " if proof.holds else "FAILED"
            if not proof.holds:
                failed += 1
            print("%s %-34s %s" % (status, warp.name, proof.kind))
            print("       %s" % proof.account)
    print()
    print("%d of %d proofs hold." % (len(warps) - failed, len(warps)))
    return 1 if failed else 0


def _run(args) -> int:
    if not git_available():
        print("swizzle: git is not on PATH, and a warp is a repository.",
              file=sys.stderr)
        return 2
    ghost_tools = args.ghost_tools
    if ghost_tools is None:
        try:
            import ghost_buster                      # noqa: F401
        except ImportError:
            ghost_tools = locate_ghost_tools()
            if ghost_tools is None:
                print("swizzle: ghost_buster is not importable and no "
                      "checkout was found. Pass --ghost-tools PATH or set "
                      "GHOST_TOOLS.", file=sys.stderr)
                return 2

    warps = _selected(args.only)
    outcomes = run_all(warps, ghost_tools, keep=args.keep)

    if args.json:
        print(json.dumps(as_dicts(outcomes, warps), indent=2, sort_keys=True))
    else:
        print(render(outcomes, warps))

    if any(o.verdict is Verdict.UNSUMMONED for o in outcomes):
        return 2
    if args.fail_on_escape and any(
            o.verdict in (Verdict.ESCAPED, Verdict.CONJURED) for o in outcomes):
        return 1
    return 0


def _summon(args) -> int:
    try:
        warp = by_name(args.warp)
    except KeyError:
        print("swizzle: no warp called %r. `swizzle list` has the catalogue."
              % args.warp, file=sys.stderr)
        return 2
    root = summon(warp, args.into)
    print(root)
    return 0


if __name__ == "__main__":                          # pragma: no cover
    raise SystemExit(main())
