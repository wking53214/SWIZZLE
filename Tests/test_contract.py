"""`swizzle --contract`: what Warden (or any caller of the subprocess) can assert against."""

from __future__ import annotations

import dataclasses
import json
import re
import subprocess
import sys
from pathlib import Path

import swizzle
from swizzle import contract as contract_module
from swizzle.governor.run import Finding
from swizzle.governor.scenarios import SCENARIOS

ROOT = Path(__file__).resolve().parents[1]


def _run(*args, cwd=None):
    return subprocess.run([sys.executable, "-m", "swizzle.cli", *args], capture_output=True,
                          text=True, timeout=300, cwd=str(cwd or ROOT))


def test_contract_prints_only_json_and_exits_zero():
    done = _run("--contract")
    assert done.returncode == 0, done.stderr
    document = json.loads(done.stdout)
    assert document["name"] == "swizzle"
    assert document["contract"] == contract_module.CONTRACT
    assert isinstance(document["contract"], int)
    assert document["swizzle_version"] == swizzle.__version__


def test_contract_is_also_reachable_with_python_dash_m_swizzle():
    done = subprocess.run([sys.executable, "-m", "swizzle", "--contract"], capture_output=True,
                          text=True, timeout=300, cwd=str(ROOT))
    assert done.returncode == 0
    assert json.loads(done.stdout)["contract"] == contract_module.CONTRACT


def test_contract_describes_the_governor_report_Warden_reads():
    governor = contract_module.contract()["commands"]["governor"]
    assert governor["finding_fields"] == [f.name for f in dataclasses.fields(Finding)]
    # Warden reads scenario, severity and status; they must stay in the report.
    assert {"scenario", "severity", "status"} <= set(governor["finding_fields"])
    assert governor["status_values"] == ["held", "violated", "not_run"]
    assert governor["scenario_count"] == len(SCENARIOS)


def test_contract_summary_line_pattern_matches_what_prove_prints():
    pattern = re.compile(contract_module.contract()["commands"]["prove"]["stdout_summary_line"], re.M)
    done = _run("prove", "--only", "sql_through")
    assert done.returncode == 0, done.stderr
    found = pattern.search(done.stdout)
    assert found is not None, done.stdout
    assert found.group(1) == found.group(2) == "1"


def test_contract_changes_are_documented():
    text = (ROOT / "docs" / "CONTRACT.md").read_text(encoding="utf-8")
    assert "swizzle --contract" in text
    assert "contract: %d" % contract_module.CONTRACT in text, (
        "docs/CONTRACT.md must state the current contract number; bump both together")
