"""SWIZZLE's two CNS gates (``swizzle.cns_adapter``): ProofGate (ALPHA) and AttackGate (OMEGA).

Skipped where CNS is absent; in CI the cns extra is installed and these run. Nothing here
shares mutable state: every candidate is built fresh by a function, never by a module-level
fixture that one test could change under another.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

gate = pytest.importorskip("cns.gate")
attack_mod = pytest.importorskip("cns.attack")

from swizzle import cns_adapter  # noqa: E402
from swizzle.cns_adapter import AttackGate, ProofGate, attack_rows, run_proofs  # noqa: E402
from swizzle.governor.run import Finding, as_dicts  # noqa: E402
from swizzle.governor.scenarios import SCENARIOS  # noqa: E402
from swizzle.schema import Proof  # noqa: E402

NAMES = ("alpha_warp", "beta_warp", "gamma_warp")


def proofs(holds=(True, True, True), kind="executed", names=NAMES):
    return [(n, Proof(h, kind, "account of %s" % n)) for n, h in zip(names, holds, strict=True)]


def attacks(*statuses, severity="high"):
    return [
        {"scenario": "s%d" % i, "hypothesis": "h", "severity": severity, "status": st,
         "detail": "", "decision": "", "kind": ""}
        for i, st in enumerate(statuses)
    ]


def proof_gate():
    return ProofGate(expected=NAMES)


# ---- protocol conformance ----------------------------------------------------------------------


def test_both_gates_satisfy_the_cns_gate_protocol():
    for g in (proof_gate(), AttackGate()):
        assert isinstance(g, gate.Gate)
        assert g.name and g.position in (gate.GatePosition.ALPHA, gate.GatePosition.OMEGA)


def test_each_gate_declares_the_end_it_really_judges_at():
    assert proof_gate().position is gate.GatePosition.ALPHA  # before anything is judged by SWIZZLE
    assert AttackGate().position is gate.GatePosition.OMEGA  # on a produced report
    assert proof_gate().name != AttackGate().name


def test_a_chain_puts_each_gate_in_its_own_slot_and_a_swapped_chain_says_so():
    chain = gate.GateChain(alpha=(proof_gate(),), omega=(AttackGate(),))
    assert chain.misplaced() == ()
    swapped = gate.GateChain(alpha=(AttackGate(),), omega=(proof_gate(),))
    assert set(swapped.misplaced()) == {AttackGate().name, proof_gate().name}


def test_every_result_carries_the_gate_name_and_position():
    r = proof_gate().check(proofs())
    assert (r.gate, r.position) == ("swizzle.proofs", gate.GatePosition.ALPHA)
    r = AttackGate().check(attacks("held"))
    assert (r.gate, r.position) == ("swizzle.governor_attacks", gate.GatePosition.OMEGA)


# ---- ProofGate: every mapping --------------------------------------------------------------------


def test_every_proof_held_and_every_warp_covered_is_pass():
    r = proof_gate().check(proofs())
    assert r.outcome is gate.GateOutcome.PASS and r.bound()


def test_a_structural_proof_that_holds_is_also_pass():
    assert proof_gate().check(proofs(kind="structural")).outcome is gate.GateOutcome.PASS


@pytest.mark.parametrize("holds", [(True, False, True), (False, False, False), (True, True, False)])
def test_a_proof_that_did_not_hold_means_the_instrument_is_broken(holds):
    r = proof_gate().check(proofs(holds))
    assert r.outcome is gate.GateOutcome.TERMINAL_BREACH and r.bound()
    assert "instrument is broken" in r.reason


def test_a_proof_that_crashed_is_a_broken_instrument():
    candidate = proofs()
    candidate[1] = (NAMES[1], Proof(False, "failed", "ValueError: boom"))
    assert proof_gate().check(candidate).outcome is gate.GateOutcome.TERMINAL_BREACH


def test_a_broken_proof_outranks_a_missing_one():
    r = proof_gate().check(proofs((False, True), names=NAMES[:2]))
    assert r.outcome is gate.GateOutcome.TERMINAL_BREACH


@pytest.mark.parametrize("count", [0, 1, 2])
def test_proofs_not_run_or_not_all_run_is_retry(count):
    r = proof_gate().check(proofs(names=NAMES[:count], holds=(True,) * count))
    assert r.outcome is gate.GateOutcome.RETRY and r.bound()


def test_the_default_expectation_is_the_whole_catalogue():
    from swizzle.warps import catalogue

    names = [w.name for w in catalogue()]
    everything = [(n, Proof(True, "executed", "ok")) for n in names]
    assert ProofGate().check(everything).outcome is gate.GateOutcome.PASS
    assert ProofGate().check(everything[1:]).outcome is gate.GateOutcome.RETRY


@pytest.mark.parametrize(
    "candidate",
    [
        [(NAMES[0], Proof("yes", "executed", "a"))],      # holds is not a bool
        [(NAMES[0], Proof(1, "executed", "a"))],          # 1 is not True
        [(NAMES[0], Proof(True, "assumed", "a"))],        # a kind SWIZZLE does not produce
        [(NAMES[0], Proof(True, "failed", "a"))],         # contradicts itself
        [("not_a_warp", Proof(True, "executed", "a"))],   # a warp nobody expected
        [(NAMES[0], Proof(True, "executed", "a"))] * 2,   # the same warp twice
    ],
)
def test_an_answer_the_gate_does_not_recognise_is_terminal_breach(candidate):
    r = ProofGate(expected=NAMES).check(candidate)
    assert r.outcome is gate.GateOutcome.TERMINAL_BREACH
    assert r.bound()  # it could be described, so it is bound to what it judged


@pytest.mark.parametrize(
    "candidate",
    [
        None, "proofs", 7, {"warp": "a"}, b"x", object(),
        [object()], [("a", "not a Proof")], [("a", Proof(True, "executed", "x"), 3)],
        [{"warp": "a", "holds": True, "kind": "executed"}],                   # no account
        [{"warp": 1, "holds": True, "kind": "executed", "account": "x"}],     # warp not text
        [{"warp": "a", "holds": {1}, "kind": "executed", "account": "x"}],    # a set cannot be bound
        [{"warp": "a", "holds": float("nan"), "kind": "executed", "account": "x"}],
    ],
)
def test_a_candidate_that_cannot_be_read_or_bound_is_terminal_breach_and_unbound(candidate):
    r = ProofGate(expected=("a",)).check(candidate)
    assert r.outcome is gate.GateOutcome.TERMINAL_BREACH
    assert not r.bound() and r.subject_digest == ""
    assert gate.unbound([r]) == ("swizzle.proofs",)


def test_a_mapping_row_is_read_like_a_proof_pair():
    rows = [{"warp": n, "holds": True, "kind": "executed", "account": "a"} for n in NAMES]
    assert proof_gate().check(rows).outcome is gate.GateOutcome.PASS


def test_the_real_proofs_pass_and_the_gate_judges_what_swizzle_prove_computes():
    real = run_proofs()
    r = ProofGate().check(real)
    assert r.outcome is gate.GateOutcome.PASS, r.reason
    assert all(isinstance(p, Proof) for _, p in real)


def test_run_proofs_takes_a_subset_and_a_deliberate_partial_run_is_judged_against_it():
    from swizzle.warps import catalogue

    chosen = [w for w in catalogue() if "sql" in w.name or "sql" in w.targets][:2]
    got = run_proofs(chosen)
    assert [n for n, _ in got] == [w.name for w in chosen]
    assert ProofGate(expected=[w.name for w in chosen]).check(got).outcome is gate.GateOutcome.PASS
    assert ProofGate().check(got).outcome is gate.GateOutcome.RETRY


# ---- AttackGate: every mapping -------------------------------------------------------------------


def test_an_attack_that_held_is_pass():
    r = AttackGate().check(attacks("held", "held"))
    assert r.outcome is gate.GateOutcome.PASS and r.bound()


def test_a_violated_invariant_is_terminal_breach():
    r = AttackGate().check(attacks("held", "violated"))
    assert r.outcome is gate.GateOutcome.TERMINAL_BREACH and r.bound()
    assert "s1" in r.reason


def test_an_attack_that_gave_no_clean_answer_is_retry():
    r = AttackGate().check(attacks("held", "not_run"))
    assert r.outcome is gate.GateOutcome.RETRY and r.bound()


@pytest.mark.parametrize("kind", ["feature_absent", "interrupted", ""])
def test_not_run_is_retry_whatever_the_reason_it_did_not_run(kind):
    candidate = attacks("not_run")
    candidate[0]["kind"] = kind
    assert AttackGate().check(candidate).outcome is gate.GateOutcome.RETRY


@pytest.mark.parametrize("status", ["Held", "HELD", " held", "ok", "error", "timeout", "passed", "skipped"])
def test_a_status_swizzle_does_not_use_is_terminal_breach(status):
    r = AttackGate().check(attacks("held", status))
    assert r.outcome is gate.GateOutcome.TERMINAL_BREACH and r.bound()
    assert "never read as permission" in r.reason


def test_an_empty_report_is_retry_because_nothing_was_attacked():
    r = AttackGate().check([])
    assert r.outcome is gate.GateOutcome.RETRY and r.bound()


@pytest.mark.parametrize(
    "statuses,outcome",
    [
        (("held", "not_run", "violated"), gate.GateOutcome.TERMINAL_BREACH),
        (("held", "not_run", "weird"), gate.GateOutcome.TERMINAL_BREACH),
        (("held", "not_run", "held"), gate.GateOutcome.RETRY),
        (("held", "held", "held"), gate.GateOutcome.PASS),
    ],
)
def test_the_worst_entry_decides_the_report(statuses, outcome):
    assert AttackGate().check(attacks(*statuses)).outcome is outcome


@pytest.mark.parametrize("severity", ["high", "medium", "low", "critical", "whatever"])
def test_severity_is_validated_as_text_and_never_changes_the_answer(severity):
    g = AttackGate()
    assert g.check(attacks("held", severity=severity)).outcome is gate.GateOutcome.PASS
    assert g.check(attacks("violated", severity=severity)).outcome is gate.GateOutcome.TERMINAL_BREACH
    assert g.check(attacks("not_run", severity=severity)).outcome is gate.GateOutcome.RETRY


@pytest.mark.parametrize(
    "candidate",
    [
        None, "held", 3, {"scenario": "a", "severity": "high", "status": "held"}, b"x",
        [None], ["held"], [3], [[]],
        [{"severity": "high", "status": "held"}],                                    # no scenario
        [{"scenario": "a", "status": "held"}],                                       # no severity
        [{"scenario": "a", "severity": "high"}],                                     # no status
        [{"scenario": "a", "severity": "high", "status": None}],                     # null
        [{"scenario": "a", "severity": 3, "status": "held"}],                        # not text
        [{"scenario": "a", "severity": "high", "status": True}],                     # not text
        [{"scenario": "  ", "severity": "high", "status": "held"}],                  # blank
        [{"scenario": "a", "severity": "high", "status": "held", "detail": {1}}],    # unbindable extra
        [{"scenario": "a", "severity": "high", "status": "held", "x": float("inf")}],
    ],
)
def test_a_report_that_does_not_meet_the_row_is_terminal_breach_and_unbound(candidate):
    r = AttackGate().check(candidate)
    assert r.outcome is gate.GateOutcome.TERMINAL_BREACH
    assert not r.bound() and r.subject_digest == ""


def test_one_bad_entry_makes_the_whole_report_unbound_even_beside_good_ones():
    r = AttackGate().check(attacks("held") + [{"scenario": "x"}])
    assert r.outcome is gate.GateOutcome.TERMINAL_BREACH and not r.bound()


def test_a_finding_list_is_read_like_the_json_the_cli_prints():
    findings = [Finding("a", "h", "high", "held"), Finding("b", "h", "low", "violated", "d")]
    from_findings = AttackGate().check(findings)
    from_json = AttackGate().check(json.loads(json.dumps(as_dicts(findings))))
    assert from_findings.outcome is from_json.outcome is gate.GateOutcome.TERMINAL_BREACH
    assert from_findings.subject_digest == from_json.subject_digest


# ---- binding ----------------------------------------------------------------------------------


def test_same_input_same_digest_and_changed_input_different_digest_for_proofs():
    g = proof_gate()
    a, b = g.check(proofs()), g.check(proofs())
    assert a.subject_digest == b.subject_digest != ""
    changed = proofs()
    changed[2] = (NAMES[2], Proof(True, "executed", "a different account"))
    assert g.check(changed).subject_digest != a.subject_digest
    assert ProofGate(expected=NAMES[:2]).check(proofs(names=NAMES[:2], holds=(True, True))
                                                ).subject_digest != g.check(proofs()).subject_digest


def test_same_input_same_digest_and_changed_input_different_digest_for_attacks():
    g = AttackGate()
    a, b = g.check(attacks("held", "held")), g.check(attacks("held", "held"))
    assert a.subject_digest == b.subject_digest != ""
    assert g.check(attacks("held", "violated")).subject_digest != a.subject_digest
    extra = attacks("held", "held")
    extra[0]["detail"] = "a note the answer does not depend on"
    assert g.check(extra).subject_digest != a.subject_digest  # everything judged is bound


def test_the_digest_is_cns_s_own_digest_of_the_content_judged():
    candidate = attacks("held")
    r = AttackGate().check(candidate)
    assert r.subject_digest == gate.subject_digest({"attacks": candidate})
    pr = proof_gate().check(proofs())
    rows = [{"warp": n, "holds": True, "kind": "executed", "account": "account of %s" % n}
            for n in NAMES]
    assert pr.subject_digest == gate.subject_digest({"expected": list(NAMES), "proofs": rows})


def test_a_verdict_cannot_be_moved_to_other_content():
    g = AttackGate()
    passed = g.check(attacks("held"))
    other = g.check(attacks("violated"))
    assert passed.binds(passed.subject, passed.subject_digest)
    assert not passed.binds(passed.subject, other.subject_digest)
    pg = proof_gate()
    ok = pg.check(proofs())
    assert not ok.binds(ok.subject, pg.check(proofs((True, True, False))).subject_digest)


def test_every_judged_result_is_bound_and_unbindable_ones_are_named_by_unbound():
    results = [proof_gate().check(proofs()), AttackGate().check(attacks("held")),
               proof_gate().check(None), AttackGate().check("held")]
    assert gate.unbound(results) == ("swizzle.proofs", "swizzle.governor_attacks")


def test_the_subject_label_can_be_named_and_defaults_are_stable():
    assert AttackGate(subject="run 7").check(attacks("held")).subject == "run 7"
    assert ProofGate(subject="p").check(proofs()).subject == "p"
    assert AttackGate().check(attacks("held")).subject == cns_adapter.DEFAULT_ATTACK_SUBJECT
    assert ProofGate().check([]).subject == cns_adapter.DEFAULT_PROOF_SUBJECT


# ---- exceptions propagate -----------------------------------------------------------------------


def test_an_exception_from_swizzle_s_own_logic_is_never_turned_into_a_pass(monkeypatch):
    import swizzle.warps as warps

    def boom():
        raise RuntimeError("catalogue broke")

    monkeypatch.setattr(warps, "catalogue", boom)
    with pytest.raises(RuntimeError, match="catalogue broke"):
        ProofGate().check(proofs())

    monkeypatch.setattr(cns_adapter, "attack_rows", lambda c: (_ for _ in ()).throw(KeyError("x")))
    with pytest.raises(KeyError):
        AttackGate().check(attacks("held"))


# ---- the chain and resolve ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "holds,statuses,outcome",
    [
        ((True, True, True), ("held",), gate.GateOutcome.PASS),
        ((True, True, True), ("not_run",), gate.GateOutcome.RETRY),
        ((True, True, True), ("violated",), gate.GateOutcome.TERMINAL_BREACH),
        ((True, False, True), ("held",), gate.GateOutcome.TERMINAL_BREACH),
        ((True, False, True), ("not_run",), gate.GateOutcome.TERMINAL_BREACH),
    ],
)
def test_the_two_ends_resolve_fail_closed(holds, statuses, outcome):
    chain = gate.GateChain(alpha=(proof_gate(),), omega=(AttackGate(),))
    results = [chain.alpha[0].check(proofs(holds)), chain.omega[0].check(attacks(*statuses))]
    assert gate.resolve(results) is outcome
    assert gate.unbound(results) == ()


# ---- the row helper, at the source --------------------------------------------------------------


def test_attack_rows_returns_the_rows_when_the_report_meets_the_row():
    rows, problems = attack_rows(attacks("held", "violated"))
    assert problems == () and len(rows) == 2
    assert all(isinstance(r, attack_mod.AttackResult) for r in rows)
    assert [r.status for r in rows] == ["held", "violated"]


def test_attack_rows_returns_the_problems_and_no_rows_when_it_does_not():
    rows, problems = attack_rows(attacks("held") + [{"scenario": "x"}, 5])
    assert rows == ()
    assert len(problems) == 2 and "attack 1" in problems[0] and "severity" in problems[0]
    assert attack_rows("held") == ((), ("an attack report is a list, not str",))


def test_every_scenario_swizzle_has_meets_the_row_in_every_status():
    # SWIZZLE's own CI notices a drifted field, not a reader of the report at read time.
    assert SCENARIOS
    for status in ("held", "violated", "not_run"):
        report = [Finding(s.name, s.hypothesis, s.severity, status, "d") for s in SCENARIOS]
        printed = json.loads(json.dumps(as_dicts(report)))  # what `swizzle governor --json` prints
        rows, problems = attack_rows(printed)
        assert problems == () and len(rows) == len(SCENARIOS)
        assert attack_rows(report) == (rows, ())


def test_the_row_helper_leaves_what_swizzle_emits_alone():
    report = [Finding("a", "h", "high", "held")]
    before = as_dicts(report)
    attack_rows(report)
    assert as_dicts(report) == before
    assert set(before[0]) == {"scenario", "hypothesis", "severity", "status", "detail", "decision", "kind"}


# ---- the existing seam is untouched -------------------------------------------------------------


def test_translate_verdict_is_still_the_same_table():
    from swizzle.schema import Verdict

    got = {v.value: cns_adapter.translate_verdict(v, {"warp": "w"}).translation.cns_outcome
           for v in Verdict}
    assert got == {"banished": "pass", "dismissed": "pass", "misnamed": "retry",
                   "unsummoned": "retry", "escaped": "terminal_breach",
                   "conjured": "terminal_breach"}


# ---- live: the real governor, when a Warden checkout is given ------------------------------------


@pytest.mark.skipif(not os.environ.get("WARDEN_ROOT"), reason="set WARDEN_ROOT to a Warden checkout")
def test_the_real_attack_output_meets_the_row_and_the_gate_reads_it():
    from swizzle.governor.run import attack

    findings = attack(Path(os.environ["WARDEN_ROOT"]), only="symlink_into_protected_file")
    printed = json.loads(json.dumps(as_dicts(findings)))
    rows, problems = attack_rows(printed)
    assert problems == () and rows
    expected = {"held": gate.GateOutcome.PASS, "not_run": gate.GateOutcome.RETRY,
                "violated": gate.GateOutcome.TERMINAL_BREACH}[printed[0]["status"]]
    result = AttackGate().check(printed)
    assert result.outcome is expected and result.bound()
