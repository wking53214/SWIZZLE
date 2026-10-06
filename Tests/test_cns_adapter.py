"""Optional CNS adapter — works with or without cns installed."""
from __future__ import annotations

import pytest

from swizzle.schema import Verdict
from swizzle import cns_adapter


def test_cns_available_type():
    avail = cns_adapter.cns_available()
    assert isinstance(avail.ok, bool)


@pytest.mark.parametrize(
    "verdict,outcome",
    [
        (Verdict.BANISHED, "pass"),
        (Verdict.DISMISSED, "pass"),
        (Verdict.MISNAMED, "retry"),
        (Verdict.UNSUMMONED, "retry"),
        (Verdict.ESCAPED, "terminal_breach"),
        (Verdict.CONJURED, "terminal_breach"),
    ],
)
def test_mapping_table(verdict, outcome):
    r = cns_adapter.translate_verdict(verdict, {"warp": "sql_through_a_name", "path": "fixture"})
    assert r.translation.cns_outcome == outcome
    assert r.translation.information_lost
    if r.translation.cns_present:
        assert r.translation.authority == "cns.gate"
        assert r.gate_result is not None
        assert r.gate_result.subject_digest == r.translation.subject_digest
    else:
        assert r.translation.authority == "advisory_only"
        assert r.gate_result is None


def test_unknown_verdict_is_retry():
    r = cns_adapter.translate_verdict("not-a-verdict", {"warp": "x"})
    assert r.translation.cns_outcome == "retry"


def test_advisory_when_cns_forced_missing(monkeypatch):
    monkeypatch.setattr(
        cns_adapter,
        "cns_available",
        lambda: cns_adapter.CnsAvailability(ok=False, missing=("cns.gate",), error="forced"),
    )
    r = cns_adapter.translate_verdict(Verdict.BANISHED, {"warp": "x"})
    assert r.translation.cns_present is False
    assert r.gate_result is None
    assert r.translation.authority == "advisory_only"


def test_digest_stable_when_cns_present():
    if not cns_adapter.cns_available().ok:
        pytest.skip("cns not installed")
    s = {"warp": "a", "n": 1}
    a = cns_adapter.translate_verdict(Verdict.ESCAPED, s)
    b = cns_adapter.translate_verdict(Verdict.ESCAPED, s)
    assert a.translation.subject_digest == b.translation.subject_digest
