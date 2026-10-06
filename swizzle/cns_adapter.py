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
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

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
