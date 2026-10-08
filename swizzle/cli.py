"""The command line."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Sequence

from . import __version__
from .invoke import InvocationFailed, git_available, locate_ghost_tools
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
        description="An adaptive adversarial evaluator for repository-level "
                    "autonomous modification systems. It builds repository "
                    "states in which the target is likely to make an "
                    "incorrect epistemic, diagnostic or mutational decision, "
                    "then proves independently whether it did.")
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

    verifying = sub.add_parser(
        "verify", help="independently evaluate a target claim with WIZZLE")
    verifying.add_argument("repository", type=Path)
    verifying.add_argument("--member", required=True)
    verifying.add_argument("--provenance", required=True)
    verifying.add_argument("--severity", required=True)
    verifying.add_argument("--evidence", action="append", default=[])

    summoning = sub.add_parser("summon", help="write one warp to disk")
    summoning.add_argument("warp")
    summoning.add_argument("--into", type=Path, default=Path.cwd(), metavar="DIR")

    touching = sub.add_parser(
        "assay", help="score ghost_buster against ASSAY's answer key")
    touching.add_argument("--assay", type=Path, default=None, metavar="PATH",
                          help="ASSAY checkout (default: $ASSAY, then a sibling)")
    touching.add_argument("--ghost-tools", type=Path, default=None, metavar="PATH")
    touching.add_argument("--ghost", action="append", default=[], metavar="PATH_OR_REV",
                          help="give twice, baseline first, to compare two revisions; "
                               "exits 1 if any specimen's outcome got worse")
    touching.add_argument("--json", action="store_true")

    # The laboratory's commands. The four above are the original SWIZZLE and
    # keep their behaviour exactly; everything the adversarial laboratory adds
    # registers itself here.
    from .lab import cli as lab_cli
    lab_cli.add_parsers(sub)

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    handlers = {
        "list": _list,
        "prove": _prove,
        "run": _run,
        "summon": _summon,
        "assay": _assay,
        "verify": _verify,
    }
    if args.command in handlers:
        handler = handlers[args.command]
    else:
        from .lab import cli as lab_cli
        handler = lambda a: lab_cli.handle(a.command, a)
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


def _assay(args) -> int:
    """ASSAY specimens against ghost_buster, scored by the MANIFEST.

    Exit 0: scored. Exit 1: compared two revisions and one got worse.
    Exit 2: could not score at all (no ASSAY, unproven answer key, an
    unmapped failure mode, or ghost_buster would not run) -- never a pass.
    """
    from . import assay as ts
    root = ts.locate_assay(args.assay)
    if root is None:
        print("swizzle: no ASSAY checkout with a published registry. Pass "
              "--assay PATH or set ASSAY.", file=sys.stderr)
        return 2
    if len(args.ghost) not in (0, 2):
        print("swizzle: give --ghost twice, baseline first", file=sys.stderr)
        return 2
    try:
        if args.ghost:
            import shutil
            from .lab.cli import _adapter_for
            scratch: List[Path] = []
            try:
                cards = [ts.run(root, _adapter_for(g, scratch).checkout) for g in args.ghost]
            finally:
                for path in scratch:
                    shutil.rmtree(path, ignore_errors=True)
            result = ts.Comparison(*cards)
        else:
            ghost_tools = args.ghost_tools or locate_ghost_tools()
            result = ts.run(root, ghost_tools)
            cards = [result]
    except (ts.AssayUnavailable, InvocationFailed, RuntimeError) as exc:
        print("swizzle: %s" % exc, file=sys.stderr)
        return 2
    if args.json:
        payload = (result.to_dict() if isinstance(result, ts.Scorecard)
                   else {"baseline": cards[0].to_dict(), "candidate": cards[1].to_dict(),
                         "changes": [list(c) for c in result.changes()]})
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(result.render())
    stuck = [s for card in cards for s in ts.blocked(card)]
    if stuck:
        print("\nswizzle: cannot score %d specimen(s): %s" % (len(stuck), ", ".join(stuck[:5])),
              file=sys.stderr)
        return 2
    if isinstance(result, ts.Comparison) and result.regressed():
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


def _verify(args) -> int:
    from .wizzle.integration import VerificationArtifact, verify_artifact

    result, oracle_results = verify_artifact(
        VerificationArtifact(repository=args.repository, target="ghost"),
        member_name=args.member,
        provenance_class=args.provenance,
        severity=args.severity,
        evidence_cited=args.evidence,
    )
    print(json.dumps({
        "semantic_correctness": result.semantic_correctness.name,
        "factual_correctness": result.factual_correctness.name,
        "overclaim": result.overclaim,
        "underclaim": result.underclaim,
        "oracle_results": oracle_results,
    }, indent=2, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":                          # pragma: no cover
    raise SystemExit(main())
