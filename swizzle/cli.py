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
    proving.add_argument("--only", default=None, metavar="SUBSTRING",
                         help="warps whose name or target contains this "
                              "(comma-separated); a name that matches nothing "
                              "is an error (exit 2)")

    running = sub.add_parser("run", help="build, scan, score")
    running.add_argument("--only", default=None, metavar="SUBSTRING")
    running.add_argument("--ghost-tools", type=Path, default=None, metavar="PATH",
                         help="the ghost_tools checkout (default: importable, "
                              "then $GHOST_TOOLS, then a sibling directory). A "
                              "path you give that is not a ghost_tools checkout "
                              "is an error (exit 2), never replaced by another")
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
                          help="ASSAY checkout. If you give it and it is missing "
                               "or has no published registry, that is an error "
                               "(exit 2); a sibling checkout is used only when "
                               "this is not given (default: $ASSAY, then a sibling)")
    touching.add_argument("--ghost-tools", type=Path, default=None, metavar="PATH",
                          help="the ghost_tools checkout; a bad path is an error (exit 2)")
    touching.add_argument("--floor", type=int, default=None, metavar="N",
                          help="exit 1 when Ghost caught fewer than N known "
                               "failure modes (default: no floor, and then exit 0 "
                               "only means the key was scored)")
    touching.add_argument("--ghost", action="append", default=[], metavar="PATH_OR_REV",
                          help="give twice, baseline first, to compare two revisions; "
                               "exits 1 if any specimen's outcome got worse")
    touching.add_argument("--json", action="store_true")

    governing = sub.add_parser(
        "governor", help="attack a governor (Warden) and report which invariants held")
    governing.add_argument("--warden", type=Path, default=None, metavar="PATH",
                           help="a Warden checkout (its package is imported only in a "
                                "subprocess). A relative path is fine.")
    governing.add_argument("--only", default=None, metavar="NAME[,NAME]",
                           help="scenarios whose name contains this (comma-separated); "
                                "a name that matches nothing is an error (exit 2)")
    governing.add_argument("--list", action="store_true",
                           help="print the scenarios, and which Warden layers defend each, then stop")
    governing.add_argument("--json", action="store_true",
                           help="a JSON list on stdout and nothing else; notes go to stderr")
    governing.epilog = ("exit codes: 1 if any selected scenario was violated; otherwise 2 if any "
                        "did not run (Warden crashed, timed out, or gave no usable decision); "
                        "otherwise 0, which means every selected scenario was held. A scenario "
                        "is held only when Warden ran to completion and gave a readable decision.")

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
        "governor": _governor,
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


def _governor(args) -> int:
    """Exit 1 if any scenario was violated, else 2 if any did not run, else 0."""
    from .governor.run import (BadSelection, WardenNotFound, as_dicts, attack, exit_code,
                               render)
    from .governor.scenarios import SCENARIOS
    if args.list:
        for sc in SCENARIOS:
            print("%-34s [%s] %s\n    defended by: %s" % (sc.name, sc.severity, sc.hypothesis, sc.layers or "not recorded"))
        return 0
    if args.warden is None:
        print("swizzle: governor needs --warden PATH (or --list).", file=sys.stderr)
        return 2
    try:
        findings = attack(args.warden, only=args.only)
    except BadSelection as exc:
        print("swizzle: %s" % exc, file=sys.stderr)
        return 2
    except WardenNotFound as exc:
        print("swizzle: %s" % exc, file=sys.stderr)
        return 2
    code = exit_code(findings)
    if args.json:
        print(json.dumps(as_dicts(findings), indent=2))
        print("swizzle: %s (exit %d)" % (_governor_summary(findings), code), file=sys.stderr)
    else:
        print(render(findings))
    return code


def _governor_summary(findings) -> str:
    from .governor.run import summary
    return summary(findings)


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


def _unknown_names(only: str | None, warps: List[Warp]) -> str | None:
    """A message when --only named something that is not in the catalogue."""
    if not only:
        return None
    everything = list(catalogue())
    for part in [p.strip() for p in only.split(",") if p.strip()]:
        if not any(part in w.name or part in w.targets for w in everything):
            return "no warp matches %r. Valid names: %s" % (part, ", ".join(w.name for w in everything))
    return None if warps else "--only selected no warps. Valid names: %s" % ", ".join(w.name for w in everything)


def _prove(args) -> int:
    """Exit 0: every selected proof holds. 1: one failed. 2: none ran or --only named nothing."""
    import tempfile
    only = args.only
    parts = [p.strip() for p in only.split(",") if p.strip()] if only else [None]
    warps: List[Warp] = []
    for part in parts:
        warps += [w for w in _selected(part) if w not in warps]
    bad = _unknown_names(only, warps)
    if bad:
        print("swizzle: %s" % bad, file=sys.stderr)
        return 2
    if not warps:
        print("swizzle: no proofs ran, so nothing is shown to hold.", file=sys.stderr)
        return 2
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
    print("Each proof shows that a planted defect is a real defect. None of them runs "
          "Ghost, so this says nothing about whether Ghost finds the defect; "
          "`swizzle assay` and `swizzle run` measure that.")
    return 1 if failed else 0


def _run(args) -> int:
    if not git_available():
        print("swizzle: git is not on PATH, and a warp is a repository.",
              file=sys.stderr)
        return 2
    ghost_tools = args.ghost_tools
    if ghost_tools is not None and not _is_ghost_tools(ghost_tools):
        print(_bad_ghost_tools(ghost_tools), file=sys.stderr)
        return 2
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


def _is_ghost_tools(path: Path) -> bool:
    return (Path(path) / "ghost_buster" / "cli.py").is_file()


def _bad_ghost_tools(path: Path) -> str:
    return ("swizzle: --ghost-tools %s is not a ghost_tools checkout (no ghost_buster/cli.py "
            "inside it). Not falling back to another checkout." % path)


def _assay(args) -> int:
    """ASSAY specimens against ghost_buster, scored by the MANIFEST.

    Exit 0: scored (and, with --floor N, at least N failure modes caught).
    Exit 1: compared two revisions and one got worse, or Ghost caught fewer
    than --floor. Exit 2: could not score at all (no ASSAY, a path you gave
    that does not exist, an unproven answer key, an unmapped failure mode,
    or ghost_buster would not run) -- never a pass.
    """
    from . import assay as ts
    try:
        root, assay_how = ts.resolve_assay(args.assay)
    except ts.AssayUnavailable as exc:
        print("swizzle: %s" % exc, file=sys.stderr)
        return 2
    if len(args.ghost) not in (0, 2):
        print("swizzle: give --ghost twice, baseline first", file=sys.stderr)
        return 2
    ghost_tools, ghost_how = None, ""
    if not args.ghost:
        if args.ghost_tools is not None:
            if not _is_ghost_tools(args.ghost_tools):
                print(_bad_ghost_tools(args.ghost_tools), file=sys.stderr)
                return 2
            ghost_tools, ghost_how = Path(args.ghost_tools).absolute(), "--ghost-tools"
        else:
            ghost_tools = locate_ghost_tools()
            if ghost_tools is not None:
                ghost_how = "$GHOST_TOOLS or sibling checkout (--ghost-tools was not given)"
            else:
                try:
                    import ghost_buster                  # noqa: F401
                except ImportError:
                    print("swizzle: ghost_buster is not importable and no ghost_tools checkout "
                          "was found. Pass --ghost-tools PATH or set GHOST_TOOLS.", file=sys.stderr)
                    return 2
                ghost_how = "importable ghost_buster"
    sources = {"assay": str(root), "assay_found_by": assay_how,
               "ghost_tools": str(ghost_tools) if ghost_tools else ghost_how,
               "ghost_tools_found_by": ghost_how}
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
            result = ts.run(root, ghost_tools)
            cards = [result]
    except (ts.AssayUnavailable, InvocationFailed, RuntimeError) as exc:
        print("swizzle: %s" % exc, file=sys.stderr)
        return 2
    candidate = cards[-1]
    caught = candidate.count("FAILURE_MODE", ts.BANISHED)
    modes = candidate.total("FAILURE_MODE")
    if args.floor is None:
        floor_note = "no floor set, exit 0 only means the key was scored"
    elif caught < args.floor:
        floor_note = "FLOOR NOT MET: Ghost caught %d of %d known failure modes, floor is %d" % (caught, modes, args.floor)
    else:
        floor_note = "floor met: Ghost caught %d of %d known failure modes, floor is %d" % (caught, modes, args.floor)
    if args.json:
        payload = (result.to_dict() if isinstance(result, ts.Scorecard)
                   else {"baseline": cards[0].to_dict(), "candidate": cards[1].to_dict(),
                         "changes": [list(c) for c in result.changes()]})
        payload["sources"] = sources
        payload["floor"] = args.floor
        payload["floor_note"] = floor_note
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("ASSAY checkout: %s (%s)" % (root, assay_how))
        if ghost_how:
            print("ghost_tools:    %s (%s)" % (ghost_tools or "", ghost_how))
        print(result.render())
        print("\n" + floor_note)
    stuck = [s for card in cards for s in ts.blocked(card)]
    unproven = [c for c in cards if not c.proven]
    if stuck or unproven:
        print("\nswizzle: cannot score %d specimen(s): %s" % (len(stuck), ", ".join(stuck[:5])),
              file=sys.stderr)
        return 2
    if args.floor is not None and caught < args.floor:
        print("swizzle: %s" % floor_note, file=sys.stderr)
        return 1
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
