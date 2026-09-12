"""Deciding, for one warp, whether the imp was named.

The comparison is deliberately strict in one direction and forgiving in
the other. Strict: naming the right detector in the wrong file, or the
right file at the wrong place, is MISNAMED and not a win, because a
finding a reader cannot follow to the defect has not found the defect.
Forgiving: a finding that does not localise to a line at all is accepted,
since some detectors report whole files by design and holding that against
them would be measuring the report format rather than the reading.

WHY TOLERATED EXISTS

A fixture small enough to read in one screen has unreferenced definitions
in it, and `dead_code` is right about every one of them. Those findings are
true, irrelevant to the warp, and would otherwise turn every ESCAPED into a
MISNAMED and make the report useless. Each warp declares what noise it
expects; the true name is checked first, so a warp can never tolerate its
own answer away.

WHAT COUNTS AS NEARLY RIGHT

Two things, and deliberately not a third. The right detector in the right
file at the wrong line: it found the file and read it wrongly. Any other
detector pointing AT the true name's lines: it saw the code and called it
something else. Not counted: the right detector somewhere else entirely in
the warp, which in a four-file fixture is usually a true finding about a
different function and says nothing about whether the planted defect was
seen.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from .schema import Outcome, Proof, Verdict, Warp

#: (detector, file, line) -- everything the judgement looks at.
Placed = Tuple[str, str, Optional[int]]


def placed_findings(findings: Sequence[dict]) -> List[Placed]:
    out = []
    for finding in findings:
        evidence = finding.get("evidence") or {}
        out.append((
            str(finding.get("detector", "")),
            _normalise(str(evidence.get("file", ""))),
            evidence.get("line_start"),
        ))
    return sorted(out, key=lambda p: (p[1], p[2] or 0, p[0]))


def _normalise(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def judge(warp: Warp, findings: Sequence[dict],
          proof: Optional[Proof]) -> Outcome:
    """The verdict for one warp, given what the scan said about it."""
    placed = placed_findings(findings)

    if proof is None or not proof.holds:
        return Outcome(
            warp=warp.name, verdict=Verdict.UNSUMMONED, proof=proof,
            findings=tuple(placed),
            account=("the warp did not prove itself: %s"
                     % (proof.account if proof else "no proof was run")),
        )

    if warp.is_decoy:
        return _judge_decoy(warp, placed, proof)
    return _judge_defect(warp, placed, proof)


def _judge_decoy(warp: Warp, placed: List[Placed], proof: Proof) -> Outcome:
    offending = [p for p in placed if p[0] in warp.forbidden]
    if offending:
        return Outcome(
            warp=warp.name, verdict=Verdict.CONJURED, proof=proof,
            findings=tuple(placed),
            account=("reported %s on code with no defect in it"
                     % ", ".join(sorted({p[0] for p in offending}))),
        )
    return Outcome(
        warp=warp.name, verdict=Verdict.DISMISSED, proof=proof,
        findings=tuple(placed),
        account=("silent on %s, which is correct"
                 % ", ".join(warp.forbidden) if warp.forbidden else "silent"),
    )


def _judge_defect(warp: Warp, placed: List[Placed], proof: Proof) -> Outcome:
    true_name = warp.true_name
    assert true_name is not None        # guarded by Warp.is_decoy

    exact = [p for p in placed
             if p[0] == true_name.detector
             and p[1] == _normalise(true_name.file)
             and true_name.covers(p[2])]
    if exact:
        return Outcome(
            warp=warp.name, verdict=Verdict.BANISHED, proof=proof,
            findings=tuple(placed),
            account=("named `%s` at %s:%s" % (exact[0][0], exact[0][1],
                                              exact[0][2] if exact[0][2] else "-")),
        )

    here = _normalise(true_name.file)
    near = [p for p in placed
            if (p[0] == true_name.detector and p[1] == here)
            or (p[1] == here and p[2] is not None and true_name.covers(p[2])
                and p[0] not in warp.tolerated)]
    if near:
        return Outcome(
            warp=warp.name, verdict=Verdict.MISNAMED, proof=proof,
            findings=tuple(placed),
            account=("said %s; the true name is `%s` at %s:%s"
                     % (", ".join("`%s` at %s:%s" % (d, f, l or "-")
                                  for d, f, l in near[:3]),
                        true_name.detector, true_name.file,
                        true_name.line_start or "-")),
        )

    return Outcome(
        warp=warp.name, verdict=Verdict.ESCAPED, proof=proof,
        findings=tuple(placed),
        account=("nothing was said about `%s` at %s:%s"
                 % (true_name.detector, true_name.file,
                    true_name.line_start or "-")),
    )
