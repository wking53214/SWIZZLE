"""Build each attack, run the governor on it, judge from the files, report.

Report only. A Finding says whether an invariant held; it does not say what
the governor should now do, and nothing here can change the governor.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .scenarios import SCENARIOS, Scenario, Tree

_SKIP = {".git", "__pycache__", ".pytest_cache", ".venv"}


@dataclass(frozen=True)
class Finding:
    scenario: str
    hypothesis: str
    severity: str
    status: str          # held | violated | not_run
    detail: str = ""
    decision: str = ""


def snapshot(base: Path) -> Tree:
    """The case and anything beside it, so an escape out of the case is visible."""
    out: Tree = {}
    case = base / "case"
    for path in sorted(case.rglob("*")):
        if path.is_file() and not _SKIP.intersection(path.relative_to(case).parts):
            out[str(path.relative_to(case))] = path.read_text(encoding="utf-8", errors="replace")
    for path in sorted(base.iterdir()):
        if path.is_file():
            out["../" + path.name] = path.read_text(encoding="utf-8", errors="replace")
    return out


def run_scenario(scenario: Scenario, warden_root: Path, swizzle_root: Path,
                 python: str = sys.executable, timeout: float = 600.0) -> Finding:
    with tempfile.TemporaryDirectory(prefix="swizzle-governor-") as tmp:
        base = Path(tmp)
        case = base / "case"
        for rel, text in scenario.files.items():
            (case / rel).parent.mkdir(parents=True, exist_ok=True)
            (case / rel).write_text(text, encoding="utf-8")
        before = snapshot(base)
        spec = base.parent / (base.name + ".json")
        spec.write_text(json.dumps({"target": str(case), "behavior": scenario.behavior,
                                    "scope": scenario.scope, "params": scenario.params}), encoding="utf-8")
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(warden_root), str(swizzle_root)]))
        try:
            done = subprocess.run([python, "-m", "swizzle.governor.probe", str(spec)], cwd=str(base),
                                  env=env, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return Finding(scenario.name, scenario.hypothesis, scenario.severity, "not_run", "timed out")
        finally:
            spec.unlink(missing_ok=True)
        outcome = _outcome(done.stdout)
        if outcome is None or "unavailable" in outcome:
            why = (outcome or {}).get("unavailable") or (done.stderr.strip().splitlines() or ["no output"])[-1]
            return Finding(scenario.name, scenario.hypothesis, scenario.severity, "not_run", str(why))
        after = snapshot(base)
    problem = scenario.invariant(before, after, outcome)
    return Finding(scenario.name, scenario.hypothesis, scenario.severity,
                   "violated" if problem else "held", problem or "", str(outcome.get("decision") or ""))


def _outcome(stdout: str) -> Optional[Dict[str, object]]:
    for line in reversed(stdout.splitlines()):
        if line.startswith("SWIZZLE_RESULT "):
            return json.loads(line[len("SWIZZLE_RESULT "):])
        if line.startswith("{") and "unavailable" in line:
            return json.loads(line)
    return None


def attack(warden_root: Path, swizzle_root: Optional[Path] = None,
           only: Optional[str] = None, python: str = sys.executable) -> List[Finding]:
    swizzle_root = swizzle_root or Path(__file__).resolve().parents[2]
    chosen: Sequence[Scenario] = [s for s in SCENARIOS if not only or only in s.name]
    return [run_scenario(s, Path(warden_root), swizzle_root, python) for s in chosen]


def render(findings: Sequence[Finding]) -> str:
    lines = []
    for f in findings:
        mark = {"held": "held    ", "violated": "VIOLATED", "not_run": "not run "}[f.status]
        lines.append(f"{mark} [{f.severity:6}] {f.scenario}" + (f"  -> {f.detail}" if f.detail else ""))
    bad = [f for f in findings if f.status == "violated"]
    lines.append(f"\n{len(findings)} attacks, {len(bad)} invariant(s) violated. "
                 "SWIZZLE reports; it does not decide what the governor should do about it.")
    return "\n".join(lines)


def as_dicts(findings: Sequence[Finding]) -> List[dict]:
    return [asdict(f) for f in findings]
