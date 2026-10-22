"""Optional adapter: SWIZZLE Verdict → cns.gate shapes.

CNS is never required to import or run SWIZZLE. When ``cns.gate`` is present,
this module can produce a ``GateResult`` whose ``subject_digest`` comes from
CNS. When CNS is absent, it returns an advisory translation with no digest
and no claimed gate authority.

This module does not modify CNS. It does not vendor CNS. It does not treat a
domain Verdict as a GateOutcome without an explicit mapping.
"""
from __future__ import annotations

import importlib
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Iterable, Mapping, Optional, Tuple

from .schema import Verdict

# Explicit translation — not identity.
_VERDICT_TO_OUTCOME: dict[str, tuple[str, str]] = {
    Verdict.BANISHED.value: ("pass", "planted defect named correctly; warp closed"),
    Verdict.DISMISSED.value: ("pass", "decoy stayed quiet; correct non-finding"),
    Verdict.MISNAMED.value: ("retry", "shape registered, reading wrong; re-examine"),
    Verdict.UNSUMMONED.value: ("retry", "SWIZZLE could not prove the warp; no scanner verdict authority"),
    Verdict.ESCAPED.value: ("terminal_breach", "proven defect met silence; blind spot"),
    Verdict.CONJURED.value: ("terminal_breach", "decoy fired; false positive"),
}

_REQUIRED_GATE = ("GateOutcome", "GateResult", "GatePosition", "subject_digest")


@dataclass(frozen=True)
class CnsAvailability:
    ok: bool
    missing: Tuple[str, ...] = ()
    error: str = ""


@dataclass(frozen=True)
class TranslationRecord:
    source_model: str
    source_value: str
    cns_outcome: str
    reason: str
    information_preserved: str
    information_lost: str
    cns_present: bool
    subject_digest: str
    authority: str  # "cns.gate" | "advisory_only"


@dataclass(frozen=True)
class AdapterResult:
    translation: TranslationRecord
    gate_result: Optional[Any] = None


def cns_available() -> CnsAvailability:
    try:
        gate = importlib.import_module("cns.gate")
    except ImportError as e:
        return CnsAvailability(ok=False, missing=("cns.gate",), error=str(e))
    missing = tuple(n for n in _REQUIRED_GATE if not hasattr(gate, n))
    if missing:
        return CnsAvailability(ok=False, missing=missing, error=f"cns.gate lacks {missing}")
    return CnsAvailability(ok=True)


def translate_verdict(
    verdict: Verdict | str,
    subject: Mapping[str, object],
    *,
    gate_name: str = "swizzle.cns_adapter",
) -> AdapterResult:
    """Map a warp verdict to a CNS gate outcome.

    ``subject`` is digested only via ``cns.gate.subject_digest`` when CNS is
    present (e.g. warp name, fixture path). Local hashes are never claimed
    to be equivalent.
    """
    if isinstance(verdict, Verdict):
        value = verdict.value
    else:
        value = str(verdict or "").strip().lower()

    outcome, reason = _VERDICT_TO_OUTCOME.get(
        value, ("retry", "unmapped or unknown verdict; do not invent certainty")
    )
    if value not in _VERDICT_TO_OUTCOME:
        value = value or "unknown"

    avail = cns_available()
    if not avail.ok:
        tr = TranslationRecord(
            source_model="swizzle.schema.Verdict",
            source_value=value,
            cns_outcome=outcome,
            reason=f"{reason} | CNS unavailable: {avail.error or avail.missing}",
            information_preserved="verdict label and explicit mapping table only",
            information_lost=(
                "canonical subject_digest; GateResult row; warp plant details; "
                "scanner under test; proof lines"
            ),
            cns_present=False,
            subject_digest="",
            authority="advisory_only",
        )
        return AdapterResult(translation=tr, gate_result=None)

    gate = importlib.import_module("cns.gate")
    digest = gate.subject_digest(dict(subject))
    gr = gate.GateResult(
        gate=gate_name,
        position=gate.GatePosition.ALPHA,
        outcome=gate.GateOutcome(outcome),
        reason=reason,
        subject=str(subject.get("warp") or subject.get("path") or subject.get("id") or ""),
        subject_digest=digest,
    )
    tr = TranslationRecord(
        source_model="swizzle.schema.Verdict",
        source_value=value,
        cns_outcome=outcome,
        reason=reason,
        information_preserved="verdict→outcome per mapping table; subject_digest from cns.gate",
        information_lost="warp plant details; scanner identity; proof spans; disclosure flags",
        cns_present=True,
        subject_digest=digest,
        authority="cns.gate",
    )
    return AdapterResult(translation=tr, gate_result=gr)


# ---------------------------------------------------------------------------
# Gates: SWIZZLE's own two questions, offered through the shared gate contract.
#
# translate_verdict (above) maps one warp Verdict. The two gates below answer
# the two questions Warden asks SWIZZLE, each in SWIZZLE's own vocabulary:
#
#   ProofGate (ALPHA)   Is the instrument sound? Did every proof hold?
#   AttackGate (OMEGA)  Did each attack on the governor hold?
#
# Neither decides what the answer means for a run; that is the Judge's. CNS is
# imported only when a gate is constructed, never when SWIZZLE is.
# ---------------------------------------------------------------------------

# Neither `swizzle` nor `cns` on PyPI is this project (they are unrelated packages), so the hint
# names a checkout install and the pinned git URL, never a bare PyPI name.
INSTALL_HINT = (
    "pip install -e '.[cns]' from a SWIZZLE checkout, or, for CNS alone, "
    "pip install \"cns @ git+https://github.com/wking53214/CNS.git@v2.0.0\""
)

#: What ``subject`` is set to when the caller does not name the judged content.
DEFAULT_PROOF_SUBJECT = "swizzle-proofs"

#: Deepest nesting the digest will follow. Reports are a few levels deep; this stops a cycle.
_MAX_DEPTH = 32

#: The proof kinds SWIZZLE produces. "failed" is what ``swizzle.run.prove`` reports for a crash.
_PROOF_KINDS = ("executed", "structural", "failed")


class CnsNotInstalled(ImportError):
    """Raised when a gate is constructed and the CNS package cannot be imported."""


def _cns(module: str) -> Any:
    """Import a CNS module on demand, or say exactly what is missing."""
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise CnsNotInstalled(
            "swizzle's CNS gates need %s from the CNS package (v1.8.0 or later), which is "
            "not installed. Install it with: %s. SWIZZLE itself works without it."
            % (module, INSTALL_HINT)
        ) from exc


def _plain(value: object, depth: int = 0) -> object:
    """Content a digest can bind: scalars, mappings and lists. Anything else is a TypeError."""
    if depth > _MAX_DEPTH:
        raise TypeError("the content is nested too deeply to bind a verdict to")
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {k: _plain(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v, depth + 1) for v in value]
    raise TypeError("cannot bind a verdict to %s" % type(value).__name__)


class _BoundGate:
    """What both gates share: a position, a name, and a verdict bound to what it judged."""

    name = ""
    _POSITION = ""

    def __init__(self, subject: str) -> None:
        self._gate = _cns("cns.gate")  # fail here, at construction, not on first use
        self._subject = subject

    @property
    def position(self) -> Any:
        return getattr(self._gate.GatePosition, self._POSITION)

    def _result(self, outcome: str, reason: str, digest: str = "") -> Any:
        return self._gate.GateResult(
            gate=self.name,
            position=self.position,
            outcome=getattr(self._gate.GateOutcome, outcome),
            reason=reason,
            subject=self._subject,
            subject_digest=digest,
        )

    def _unbound(self, why: str) -> Any:
        """The candidate cannot be described, so nothing is approved and nothing is bound."""
        return self._result(
            "TERMINAL_BREACH",
            "the candidate cannot be bound to a verdict, so nothing is approved (%s)" % why,
        )

    def _bind(self, content: Mapping[str, object]) -> str:
        return self._gate.subject_digest(_plain(content))


def run_proofs(warps: Any = None) -> list:
    """Run the proofs ``swizzle prove`` runs: ``[(warp name, Proof), ...]``, ProofGate's candidate.

    Does what ``swizzle.cli._prove`` does (summon each warp into a scratch directory, call
    ``swizzle.run.prove``) and returns the proofs instead of printing them. ``warps`` defaults to
    the whole catalogue. A proof that crashed is already a ``Proof(holds=False, kind="failed")``.
    """
    import tempfile
    from pathlib import Path

    from .run import prove
    from .summon import summon
    from .warps import catalogue

    chosen = list(catalogue() if warps is None else warps)
    done = []
    with tempfile.TemporaryDirectory(prefix="swizzle-prove-") as scratch:
        for warp in chosen:
            done.append((warp.name, prove(warp, summon(warp, Path(scratch)))))
    return done


def _proof_row(item: object) -> dict:
    """One proof as plain content: ``(name, Proof)`` or a mapping of warp, holds, kind, account."""
    from .schema import Proof

    if isinstance(item, (tuple, list)) and len(item) == 2 and isinstance(item[1], Proof):
        name, proof = item
        row = {"warp": name, "holds": proof.holds, "kind": proof.kind, "account": proof.account}
    elif isinstance(item, Mapping):
        missing = [k for k in ("warp", "holds", "kind", "account") if k not in item]
        if missing:
            raise ValueError("a proof row lacks %s" % ", ".join(missing))
        row = {k: item[k] for k in ("warp", "holds", "kind", "account")}
    else:
        raise ValueError("a proof is (name, Proof) or a mapping, not %s" % type(item).__name__)
    for key in ("warp", "kind", "account"):
        if not isinstance(row[key], str):
            raise ValueError("%s is %s, not text" % (key, type(row[key]).__name__))
    return row


class ProofGate(_BoundGate):
    """Is the instrument sound? SWIZZLE's own proofs, judged before anything is judged by it.

    ALPHA: a proof is evidence that a planted defect is real, and every verdict SWIZZLE gives
    later rests on that. The candidate is what ``swizzle prove`` computes, in the form it has:
    ``run_proofs()``, a list of ``(warp name, Proof)`` (or the same as mappings).

    =============================================  =============================================
    Candidate                                      Outcome
    =============================================  =============================================
    every expected warp has a proof and it holds   PASS
    some proof did not hold                        TERMINAL_BREACH (the instrument is broken, so
                                                   nothing it says counts; rerunning the same
                                                   proof is not a repair)
    no proofs, or an expected warp has none        RETRY (not measured yet; run them)
    not a list, a row unreadable, or unbindable    TERMINAL_BREACH, unbound
    holds not a bool, unknown kind, a warp not     TERMINAL_BREACH (an answer this gate does not
    expected, a warp listed twice                  recognise is never read as permission)
    =============================================  =============================================

    ``expected`` names the warps that must be covered (default: the whole catalogue, read when
    ``check`` is called). Pass the names you ran for a deliberate partial run. An exception from
    the catalogue propagates; it is never turned into a PASS.
    """

    name = "swizzle.proofs"
    _POSITION = "ALPHA"

    def __init__(self, expected: Any = None, *, subject: str = DEFAULT_PROOF_SUBJECT) -> None:
        super().__init__(subject)
        self._expected = None if expected is None else tuple(expected)

    def check(self, candidate: object) -> Any:
        if not isinstance(candidate, (list, tuple)):
            return self._unbound("the proofs are a list, not %s" % type(candidate).__name__)
        try:
            rows = [_proof_row(item) for item in candidate]
        except ValueError as exc:
            return self._unbound(str(exc))
        if self._expected is None:
            from .warps import catalogue

            expected = tuple(w.name for w in catalogue())
        else:
            expected = self._expected
        try:
            digest = self._bind({"expected": list(expected), "proofs": rows})
        except (TypeError, ValueError, RecursionError) as exc:
            return self._unbound(str(exc))

        names = [r["warp"] for r in rows]
        odd = {n for n in names if n not in expected} | {n for n in names if names.count(n) > 1}
        if odd:
            return self._result(
                "TERMINAL_BREACH",
                "a proof for a warp that is not expected, or listed twice: %s; an answer this "
                "gate does not recognise is never read as permission" % ", ".join(sorted(odd)),
                digest,
            )
        bad = [
            r["warp"] for r in rows
            if not isinstance(r["holds"], bool) or r["kind"] not in _PROOF_KINDS
            or (r["holds"] and r["kind"] == "failed")
        ]
        if bad:
            return self._result(
                "TERMINAL_BREACH",
                "a proof answered in a form this gate does not recognise (holds must be true or "
                "false; kind one of %s): %s" % (", ".join(_PROOF_KINDS), ", ".join(bad)),
                digest,
            )
        broken = [r["warp"] for r in rows if not r["holds"]]
        if broken:
            return self._result(
                "TERMINAL_BREACH",
                "the instrument is broken: %d of %d proofs did not hold (%s), so nothing it "
                "says counts" % (len(broken), len(rows), ", ".join(broken)),
                digest,
            )
        missing = [n for n in expected if n not in names]
        if not rows or missing:
            return self._result(
                "RETRY",
                "not every proof was run: %s; run them and ask again"
                % (", ".join(missing) if missing else "no proofs"),
                digest,
            )
        return self._result("PASS", "all %d proofs held" % len(rows), digest)


def _attack_dicts(attacks: Iterable[Any]) -> list:
    """The attack report as plain mappings.

    A ``Finding`` (what ``attack()`` returns) is read through its fields; a dict (what
    ``swizzle governor --json`` prints) is used as it is."""
    return [asdict(a) if is_dataclass(a) and not isinstance(a, type) else a for a in attacks]


def attack_rows(attacks: object) -> Tuple[Tuple[Any, ...], Tuple[str, ...]]:
    """Check SWIZZLE's own attack output against ``cns.attack.AttackResult``, at the source.

    ``attacks`` is the list ``swizzle governor --json`` prints, or the ``Finding`` list
    ``swizzle.governor.run.attack`` returns. Returns ``(rows, problems)``: every row as an
    ``AttackResult`` and no problems, or no rows and the problems, one per entry that does not
    meet the row, naming the field. A report that is not a list is one problem. Rows are never
    returned alongside problems, so nobody acts on a half-valid report. Extra keys are allowed.
    Needs CNS 1.8.0 or later: raises ``CnsNotInstalled`` otherwise.
    """
    row = _cns("cns.attack").AttackResult
    if not isinstance(attacks, (list, tuple)):
        return (), ("an attack report is a list, not %s" % type(attacks).__name__,)
    rows, problems = [], []
    for i, entry in enumerate(_attack_dicts(attacks)):
        try:
            rows.append(row.from_dict(entry))
        except ValueError as exc:
            problems.append("attack %d: %s" % (i, exc))
    return (() if problems else tuple(rows)), tuple(problems)


#: What ``subject`` is set to when the caller does not name the judged attack report.
DEFAULT_ATTACK_SUBJECT = "swizzle-governor-attacks"


class AttackGate(_BoundGate):
    """Did each attack on the governor hold? SWIZZLE's own question, in SWIZZLE's own words.

    OMEGA: the attacks have been run and this judges the report they produced. The candidate is
    the list of attack results (``swizzle governor --json``, or the ``Finding`` list
    ``attack()`` returns). Every entry is first read with ``cns.attack.AttackResult.from_dict``;
    an entry that does not meet it makes the whole report TERMINAL_BREACH and unbound.

    The only field read for the answer is ``status``, in the governor's vocabulary
    (``swizzle.governor.run.Finding``). ``severity`` is validated as text and not used: what a
    violated invariant weighs for a run is the Judge's to say, not SWIZZLE's.

    =============================================  =============================================
    status                                         Outcome
    =============================================  =============================================
    ``held``                                       PASS (Warden ran to completion, the invariant
                                                   stood)
    ``violated``                                   TERMINAL_BREACH (the governor broke an
                                                   invariant; no retry repairs a finding)
    ``not_run``                                    RETRY (no clean answer: Warden crashed, timed
                                                   out, was skipped as predating the check, or
                                                   the run was interrupted; says nothing about
                                                   the invariant, so ask again)
    anything else                                  TERMINAL_BREACH (never read as permission)
    an empty report                                RETRY (nothing was attacked, so nothing held;
                                                   `swizzle governor` exits 2 here too)
    not a list, an entry not meeting the row,      TERMINAL_BREACH, unbound
    or content a digest cannot bind
    =============================================  =============================================

    Across a report the worst entry decides: any breach, then any retry, then PASS.
    """

    name = "swizzle.governor_attacks"
    _POSITION = "OMEGA"

    def __init__(self, *, subject: str = DEFAULT_ATTACK_SUBJECT) -> None:
        super().__init__(subject)
        _cns("cns.attack")  # fail here too, not on first use, if CNS predates cns.attack

    def check(self, candidate: object) -> Any:
        rows, problems = attack_rows(candidate)
        if problems:
            more = "; and more" if len(problems) > 3 else ""
            return self._unbound("; ".join(problems[:3]) + more)
        if not isinstance(candidate, (list, tuple)):    # attack_rows has already reported this as a problem
            return self._unbound("an attack report is a list, not %s" % type(candidate).__name__)
        try:
            digest = self._bind({"attacks": _attack_dicts(candidate)})
        except (TypeError, ValueError, RecursionError) as exc:
            return self._unbound(str(exc))
        if not rows:
            return self._result(
                "RETRY", "no attack was reported, so nothing held; run them and ask again", digest
            )

        def named(status: str) -> str:
            return ", ".join(r.scenario for r in rows if r.status == status)

        unknown = sorted({r.status for r in rows} - {"held", "violated", "not_run"})
        if unknown or named("violated"):
            parts = ["violated: %s" % named("violated")] if named("violated") else []
            parts += ["unrecognised status %r: %s" % (s, named(s)) for s in unknown]
            if unknown:
                parts.append("an answer this gate does not recognise is never read as permission")
            return self._result("TERMINAL_BREACH", "; ".join(parts), digest)
        if named("not_run"):
            return self._result(
                "RETRY",
                "no clean answer for: %s; they say nothing about their invariants, so run them "
                "again" % named("not_run"),
                digest,
            )
        return self._result("PASS", "all %d attacks held" % len(rows), digest)
