"""What the run says, in the order a reader needs it.

The headline is not "how many warps escaped". It is the pair of numbers
that cannot be gamed in opposite directions: how much of a proven defect
surface the scanner named, and how often it spoke about code with nothing
wrong with it. A tool can win either one alone by being louder or quieter.

Escapes are then listed with their disclosure, most interesting first,
because an undisclosed blind spot is a bug report and a disclosed one is a
roadmap item, and a report that mixes them teaches its reader to skim --
which is ghost_buster's own argument, borrowed.
"""

from __future__ import annotations

import textwrap
from typing import Dict, Iterable, List, Mapping, Sequence

from .schema import Disclosure, Outcome, Verdict, Warp

_ORDER = (Disclosure.UNDISCLOSED, Disclosure.EXCLUSION_ABUSE,
          Disclosure.DISCLOSED)

_HEADING = {
    Disclosure.UNDISCLOSED: "UNDISCLOSED -- no part of ghost_tools mentions this gap",
    Disclosure.EXCLUSION_ABUSE: "EXCLUSION WORN AS A COSTUME -- a real exclusion, put on by code that is not entitled to it",
    Disclosure.DISCLOSED: "DISCLOSED -- ghost_tools states this scope limit itself",
}

_MARK = {
    Verdict.BANISHED: "banished ",
    Verdict.MISNAMED: "misnamed ",
    Verdict.ESCAPED: "ESCAPED  ",
    Verdict.CONJURED: "CONJURED ",
    Verdict.DISMISSED: "dismissed",
    Verdict.UNSUMMONED: "unsummoned",
}


def tally(outcomes: Iterable[Outcome]) -> Dict[Verdict, int]:
    counts = {verdict: 0 for verdict in Verdict}
    for outcome in outcomes:
        counts[outcome.verdict] += 1
    return counts


def render(outcomes: Sequence[Outcome], warps: Sequence[Warp]) -> str:
    """The whole report, one section per question a reader has."""
    index: Mapping[str, Warp] = {w.name: w for w in warps}
    sections = [
        _headline(outcomes, index),
        _every_warp(outcomes, index),
        _blind_spots(outcomes, index),
        _false_positives(outcomes, index),
        _not_measured(outcomes),
    ]
    return "\n".join("\n".join(section) for section in sections if section)


def _headline(outcomes: Sequence[Outcome], index: Mapping[str, Warp]) -> List[str]:
    """The two numbers that cannot both be gamed.

    A scanner wins "defects named" by reporting everything and "fixtures
    left alone" by reporting nothing, so neither means anything on its own
    and they are printed together or not at all.
    """
    counts = tally(outcomes)
    measured = [o for o in outcomes if o.verdict is not Verdict.UNSUMMONED]
    defects = [o for o in measured if not index[o.warp].is_decoy]
    decoys = [o for o in measured if index[o.warp].is_decoy]
    named = sum(1 for o in defects if o.verdict is Verdict.BANISHED)
    quiet = sum(1 for o in decoys if o.verdict is Verdict.DISMISSED)

    lines = [
        "SWIZZLE -- %d warps against ghost_buster" % len(outcomes),
        "=" * 66,
        "",
        "  proven defects named      %d of %d" % (named, len(defects)),
        "  clean fixtures left alone %d of %d" % (quiet, len(decoys)),
    ]
    if counts[Verdict.UNSUMMONED]:
        lines.append("  NOT MEASURED              %d (SWIZZLE's own failure, "
                     "see below)" % counts[Verdict.UNSUMMONED])
    lines.append("")
    return lines


def _every_warp(outcomes: Sequence[Outcome],
                index: Mapping[str, Warp]) -> List[str]:
    lines = ["Every warp", "-" * 66]
    for outcome in outcomes:
        warp = index[outcome.warp]
        lines.append("  %s  %-34s %s"
                     % (_MARK[outcome.verdict], warp.name, warp.targets))
        lines.append("      %s" % outcome.account)
    lines.append("")
    return lines


def _blind_spots(outcomes: Sequence[Outcome],
                 index: Mapping[str, Warp]) -> List[str]:
    escaped = [o for o in outcomes if o.verdict is Verdict.ESCAPED]
    if not escaped:
        return []
    lines = ["Blind spots", "-" * 66]
    for disclosure in _ORDER:
        group = [o for o in escaped if index[o.warp].disclosure is disclosure]
        if not group:
            continue
        lines.append("")
        lines.append("  %s" % _HEADING[disclosure])
        for outcome in group:
            lines.extend(_one_escape(outcome, index[outcome.warp]))
    lines.append("")
    return lines


def _one_escape(outcome: Outcome, warp: Warp) -> List[str]:
    true_name = warp.true_name
    lines = [
        "",
        "    %s  (target: %s)" % (warp.name, warp.targets),
        "      where   %s:%s" % (true_name.file, true_name.line_start or "-"),
        "      why     %s" % _wrap(true_name.why, 14),
        "      trick   %s" % _wrap(warp.intent, 14),
        "      proof   %s (%s)" % (_wrap(outcome.proof.account, 14),
                                   outcome.proof.kind),
    ]
    if outcome.attribution:
        lines.append("      control %s" % _wrap(outcome.attribution, 14))
    if warp.disclosure_quote:
        lines.append("      quoted  \"%s\"" % _wrap(warp.disclosure_quote, 14))
    return lines


def _false_positives(outcomes: Sequence[Outcome],
                     index: Mapping[str, Warp]) -> List[str]:
    conjured = [o for o in outcomes if o.verdict is Verdict.CONJURED]
    if not conjured:
        return []
    lines = ["False positives", "-" * 66]
    for outcome in conjured:
        warp = index[outcome.warp]
        lines.append("  %s" % warp.name)
        lines.append("      %s" % outcome.account)
        lines.append("      proof   %s" % _wrap(outcome.proof.account, 14))
        if warp.disclosure_quote:
            lines.append("      quoted  \"%s\"" % _wrap(warp.disclosure_quote, 14))
    lines.append("")
    return lines


def _not_measured(outcomes: Sequence[Outcome]) -> List[str]:
    unsummoned = [o for o in outcomes if o.verdict is Verdict.UNSUMMONED]
    if not unsummoned:
        return []
    lines = ["Not measured -- SWIZZLE could not do its job here", "-" * 66]
    for outcome in unsummoned:
        lines.append("  %-34s %s" % (outcome.warp, _wrap(outcome.account, 37)))
    lines.append("")
    return lines


def _wrap(text: str, indent: int, width: int = 66) -> str:
    """Fold `text` so continuation lines sit under the first one."""
    folded = textwrap.wrap(text or "", width=width)
    if not folded:
        return ""
    pad = " " * indent
    return ("\n" + pad).join(folded)


def as_dicts(outcomes: Sequence[Outcome], warps: Sequence[Warp]) -> List[dict]:
    """The same result, for a machine."""
    index = {w.name: w for w in warps}
    out = []
    for outcome in outcomes:
        warp = index[outcome.warp]
        true_name = warp.true_name
        out.append({
            "warp": warp.name,
            "targets": warp.targets,
            "verdict": outcome.verdict.value,
            "disclosure": warp.disclosure.value,
            "is_decoy": warp.is_decoy,
            "intent": warp.intent,
            "account": outcome.account,
            "attribution": outcome.attribution,
            "true_name": None if true_name is None else {
                "detector": true_name.detector,
                "file": true_name.file,
                "line_start": true_name.line_start,
                "line_end": true_name.line_end,
                "why": true_name.why,
            },
            "proof": None if outcome.proof is None else {
                "holds": outcome.proof.holds,
                "kind": outcome.proof.kind,
                "account": outcome.proof.account,
            },
            "findings": [{"detector": d, "file": f, "line": l}
                         for d, f, l in outcome.findings],
        })
    return out
