"""Defects the type checker found that no test had: each one is pinned here."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from swizzle.integration.decision_engine import (AutomatedDecision, ConfidenceScore, ConfidenceSource,
                                                 DecisionType, RiskLevel)
from swizzle.integration.decision_handlers import DecisionHandlers
from swizzle.integration.event_handlers import EventHandler
from swizzle.integration.event_system import create_false_positive_event
from swizzle.integration.feedback_loop import DEFAULT_FEEDBACK_REPORT, FindingType
from swizzle.integration.orchestrator import IntegrationOrchestrator
from swizzle.integration.triage_ledger import Decision, Severity, TriageEntry, TriageLedger


def test_a_boundary_violated_false_positive_is_handled_not_a_crash():
    event = create_false_positive_event("fp-boundary", "boundary_violated", 0.9, ["x"])
    EventHandler().handle_false_positive_event(event)
    pattern = DEFAULT_FEEDBACK_REPORT.false_positive_patterns["pattern_fp-boundary"]
    assert pattern.finding_type is FindingType.WRITE_OUTSIDE_BOUNDARY
    del DEFAULT_FEEDBACK_REPORT.false_positive_patterns["pattern_fp-boundary"]


def _decision(finding_type: str) -> AutomatedDecision:
    event = create_false_positive_event("fp-d", finding_type, 0.9, ["x"])
    return AutomatedDecision(
        id="d1", type=DecisionType.APPLY_FILTER_PATTERN if hasattr(DecisionType, "APPLY_FILTER_PATTERN")
        else list(DecisionType)[0],
        risk_level=list(RiskLevel)[0],
        confidence=ConfidenceScore(0.9, ConfidenceSource.PATTERN_MATCH, ["test"]),
        triggered_by=event,
        action_data={"false_positive_id": "fp-d", "finding_type": finding_type, "indicators": ["x"]})


def test_decision_handlers_map_boundary_violated():
    DecisionHandlers.handle_apply_filter_pattern(_decision("boundary_violated"))
    pattern = DEFAULT_FEEDBACK_REPORT.false_positive_patterns["pattern_fp-d"]
    assert pattern.finding_type is FindingType.WRITE_OUTSIDE_BOUNDARY
    del DEFAULT_FEEDBACK_REPORT.false_positive_patterns["pattern_fp-d"]
    DecisionHandlers.handle_update_oracle_training(_decision("boundary_violated"))
    assert any(dp.finding_type is FindingType.WRITE_OUTSIDE_BOUNDARY
               for dp in DEFAULT_FEEDBACK_REPORT.oracle_training_data.values())
    DEFAULT_FEEDBACK_REPORT.oracle_training_data.clear()


def test_the_orchestrator_publishes_a_bundle_that_includes_a_triage_ledger(tmp_path):
    ledger = TriageLedger()
    ledger.add_entry(TriageEntry(
        id="t1", finding_type="dated_claim", location="README.md", description="d",
        severity_initial=list(Severity)[0], decision=list(Decision)[0], decided_by="test",
        decided_at="2026-10-17T00:00:00", reasoning="r"))
    orch = IntegrationOrchestrator(tmp_path / "ws")
    orch.triage_ledger = ledger
    orch.publish_swizzle_integration_bundle(tmp_path / "out")
    written = json.loads((tmp_path / "out" / "triage-training-data.json").read_text())
    assert "dated_claim" in written["training_data"]


def test_the_triage_hook_reads_the_latest_entry(tmp_path, monkeypatch):
    from swizzle.integration import hooks, triage_ledger
    ledger = TriageLedger()
    ledger.add_entry(TriageEntry(
        id="t1", finding_type="dated_claim", location="README.md", description="d",
        severity_initial=list(Severity)[0], decision=list(Decision)[0], decided_by="test",
        decided_at="2026-10-17T00:00:00", reasoning="r"))
    monkeypatch.setattr(triage_ledger, "DEFAULT_LEDGER", ledger)
    published = []

    class Bus:
        def publish(self, event):
            published.append(event)
    from swizzle.integration import event_system
    monkeypatch.setattr(event_system, "get_event_bus", lambda: Bus())
    hooks.trigger_triage_event()
    assert len(published) == 1


def test_a_timed_out_sandbox_command_returns_text(tmp_path):
    from swizzle.lab.sandbox import Sandbox
    with Sandbox() as sandbox:
        done = sandbox.run([sys.executable, "-c",
                            "import sys, time; sys.stdout.write('partial'); sys.stdout.flush(); time.sleep(30)"],
                           timeout=1)
    assert done.timed_out
    assert isinstance(done.stdout, str) and isinstance(done.stderr, str)


def test_the_reporting_oracle_copes_with_a_run_that_has_no_scan():
    from swizzle.lab.oracles.reporting import _report_for

    class Evidence:
        scan = None
    assert _report_for(Evidence(), "README.md", 3) is None


def test_the_pydantic_scan_reports_one_mapping_per_file(tmp_path):
    pytest.importorskip("libcst")
    from swizzle.lab.adapters.pydantic_v2 import PydanticV2MigratorAdapter
    from swizzle.lab.sandbox import Sandbox
    root = tmp_path / "repo"
    root.mkdir()
    (root / "models.py").write_text(
        "from pydantic import BaseModel, validator\n\n\nclass M(BaseModel):\n    x: int\n\n"
        "    @validator('x')\n    def check(cls, v):\n        return v\n")
    with Sandbox() as sandbox:
        observation = PydanticV2MigratorAdapter().scan(root, sandbox)
    assert observation.findings, "the v1 validator should have been found"
    for finding in observation.findings:
        assert finding["evidence"]["file"].endswith("models.py")


def test_fitness_is_a_five_tuple():
    from swizzle.lab.fitness import score
    assert len(score([]).counts) == 5


def test_mypy_gate_is_declared_in_pyproject():
    import tomllib
    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["tool"]["mypy"]["check_untyped_defs"] is True
    assert set("EFWB") <= set("".join(data["tool"]["ruff"]["lint"]["select"]))


def test_every_seed_cases_ground_truth_is_json_serialisable():
    """`swizzle attack --json` and every corpus record dump ground truth; a claim's witness is an object."""
    from swizzle.lab import catalogue, world
    from swizzle.lab.groundtruth import of as ground_truth_of
    from Tests.fake_target import FakeTarget
    dialect = FakeTarget("abstain").dialect()
    saw_witness = False
    for genome in catalogue.CATALOGUE:
        truth = ground_truth_of(world.build(genome, dialect))
        text = json.dumps(truth.to_dict(), sort_keys=True)
        saw_witness = saw_witness or '"witness"' in text and '"expectation"' in text
    assert saw_witness, "no seed case carries a witness any more; this test no longer exercises the fix"
