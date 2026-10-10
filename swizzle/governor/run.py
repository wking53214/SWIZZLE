"""Build each attack, run the governor on it, judge from the files, report.

Report only. A Finding says whether an invariant held; it does not say what
the governor should now do, and nothing here can change the governor.
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .. import sources
from .scenarios import NEW_CHECKS_SINCE, SCENARIOS, Scenario, Tree

_SKIP = {".git", "__pycache__", ".pytest_cache", ".venv"}


@dataclass(frozen=True)
class Finding:
    scenario: str
    hypothesis: str
    severity: str
    status: str          # held | violated | not_run
    detail: str = ""
    decision: str = ""
    #: "feature_absent" when the scenario was not run because this Warden predates the check it
    #: tests (that is a skip, not a fault of Warden's); "interrupted" when Ctrl-C stopped the run
    #: before it; empty otherwise.
    kind: str = ""


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


#: Decisions that mean Warden finished and said something. ERROR is not one of
#: them: it means a seat failed and the run was abandoned, so nothing was judged.
_NO_DECISION = {"", "ERROR"}

_live_dirs: set = set()


def _cleanup_all() -> None:
    for path in list(_live_dirs):
        shutil.rmtree(path, ignore_errors=True)
        _live_dirs.discard(path)


atexit.register(_cleanup_all)


def _not_run(scenario: Scenario, why: str, kind: str = "") -> Finding:
    return Finding(scenario.name, scenario.hypothesis, scenario.severity, "not_run", why, kind=kind)


def parse_version(text: object):
    """(major, minor, patch) from a version string, or None. Anything after the numbers is ignored."""
    import re
    found = re.match(r"\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(text or ""))
    return tuple(int(x or 0) for x in found.groups()) if found else None


def feature_check(scenario: Scenario, caps: Dict[str, object], files_version: Optional[str],
                  assume: bool = False) -> Optional[str]:
    """None when Warden is expected to pass this scenario; else a plain reason it is not run.

    Expected means: the caller said to assume every check (`assume`), or Warden itself shows the
    check (a probed capability), or its version is at least the one that is assumed to bring it.
    A Warden whose version cannot be read is NOT assumed to have the check.
    """
    if not scenario.feature or assume:
        return None
    probed = (caps.get("features") or {}).get(scenario.feature)
    if probed is True:
        return None
    version = caps.get("warden_version") or files_version
    have, need = parse_version(version), parse_version(scenario.since)
    if have is not None and need is not None and have >= need:
        return None
    what = ("Warden %s" % version) if version else "this Warden (its version could not be read)"
    return ("skipped, not judged: %s does not show the check this tests (%s) and is older than %s, the first "
            "release assumed to have it. Pass --assume-new-checks to judge it anyway."
            % (what, scenario.feature, scenario.since))


def _first_line(text: object) -> str:
    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    return lines[0][:200] if lines else "no reason given"


def _kill_group(proc: subprocess.Popen) -> None:
    """Kill the probe and everything it started (Warden runs the target's tests)."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        proc.kill()


def _launch(cmd, cwd: str, env, timeout: float):
    """Run the probe in its own process group. (stdout, stderr, returncode) or raise TimeoutExpired."""
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except BaseException:
        _kill_group(proc)
        proc.communicate()
        raise
    return out, err, proc.returncode


def judge_outcome(scenario: Scenario, outcome: Optional[Dict[str, object]], stderr: str = "",
                  returncode: int = 0) -> Optional[Finding]:
    """The one place that decides whether a run produced anything to judge.

    A scenario is `held` only on a positive signal: the probe ran Warden to
    completion and got back a readable decision (or, where refusal is the
    expected behavior, a refusal of the expected kind). Anything else is
    `not_run`, because unchanged files are what a crashed governor leaves too.
    Returns a not_run Finding, or None when the outcome is fit to be judged.
    """
    if outcome is None:
        tail = _first_line(stderr) if stderr.strip() else "the probe printed no result"
        return _not_run(scenario, "Warden produced no readable result (probe exit %s): %s" % (returncode, tail))
    if "unavailable" in outcome:
        return _not_run(scenario, "Warden could not be loaded: %s" % _first_line(outcome["unavailable"]))
    if outcome.get("crashed"):
        return _not_run(scenario, "Warden crashed before deciding: %s" % _first_line(outcome.get("error")))
    if not outcome.get("completed"):
        return _not_run(scenario, "the probe did not report that Warden ran to completion")
    if outcome.get("refused"):
        if scenario.expects_refusal:
            return None
        return _not_run(scenario, "Warden refused the grant before running, which this scenario does not expect: %s"
                        % _first_line(outcome.get("error")))
    decision = outcome.get("decision")
    if scenario.error_is_answer and decision == "ERROR":
        return None
    if not isinstance(decision, str) or decision in _NO_DECISION:
        notes = outcome.get("notes") or []
        extra = (": " + _first_line(notes[-1])) if notes else ""
        return _not_run(scenario, "Warden gave no usable decision (%r)%s" % (decision, extra))
    return None


def _build_case(scenario: Scenario, case: Path) -> Optional[str]:
    """Write the scenario's files, symlinks and git state. A sentence if that could not be done."""
    for rel, text in scenario.files.items():
        (case / rel).parent.mkdir(parents=True, exist_ok=True)
        (case / rel).write_text(text, encoding="utf-8")
    for link, target in scenario.symlinks.items():
        (case / link).parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(target, case / link)
        except OSError as exc:
            return "this machine could not make the symlink the scenario needs: %s" % exc
    if scenario.git:
        if shutil.which("git") is None:
            return "git is not on PATH, and this scenario needs a repository"
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
        steps = (("init", "-q"), ("add", "-A"),
                 ("-c", "user.name=swizzle", "-c", "user.email=swizzle@invalid", "-c", "commit.gpgsign=false",
                  "commit", "-q", "-m", "base"))
        for step in steps:
            done = subprocess.run(("git",) + step, cwd=str(case), env=env, capture_output=True, text=True)
            if done.returncode != 0:
                return "git %s failed while building the scenario: %s" % (step[0], _first_line(done.stderr))
        for rel, text in scenario.dirty.items():
            (case / rel).parent.mkdir(parents=True, exist_ok=True)
            (case / rel).write_text(text, encoding="utf-8")
    return None


def _caps(stdout: str) -> Dict[str, object]:
    """Everything the probe said about what Warden is, merged, last word winning."""
    merged: Dict[str, object] = {"features": {}}
    for line in stdout.splitlines():
        if not line.startswith("SWIZZLE_CAPS "):
            continue
        try:
            value = json.loads(line[len("SWIZZLE_CAPS "):])
        except ValueError:
            continue
        if isinstance(value, dict):
            if value.get("warden_version"):
                merged["warden_version"] = value["warden_version"]
            if isinstance(value.get("features"), dict):
                merged["features"].update(value["features"])
    return merged


_SIGTERM_DEATHS = (-signal.SIGTERM, 128 + signal.SIGTERM)


def run_scenario(scenario: Scenario, warden_root: Path, swizzle_root: Path,
                 python: str = sys.executable, timeout: float = 600.0,
                 assume_new_checks: bool = False) -> Finding:
    warden_root, swizzle_root = Path(warden_root).resolve(), Path(swizzle_root).resolve()
    files_version = sources.package_version(warden_root)
    expected = feature_check(scenario, {}, files_version, assume_new_checks) is None
    outer = Path(tempfile.mkdtemp(prefix="swizzle-governor-"))
    _live_dirs.add(outer)
    try:
        base = outer / "work"
        case = base / "case"
        case.mkdir(parents=True)
        problem = _build_case(scenario, case)
        if problem:
            return _not_run(scenario, problem)
        before = snapshot(base)
        spec = outer / "spec.json"
        params = dict(scenario.params)
        params["probe_protected"] = [scenario.feature[len("protected:"):]] if scenario.feature.startswith("protected:") else []
        # Where the check is expected, SIGTERM is sent even to a Warden that has no handler for it:
        # leaving the tree changed is then the finding. Where it is not expected, it is not sent.
        params["send_anyway"] = bool(scenario.feature and expected)
        spec.write_text(json.dumps({"target": str(case), "behavior": scenario.behavior,
                                    "scope": scenario.scope, "params": params}), encoding="utf-8")
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(warden_root), str(swizzle_root)]))
        try:
            stdout, stderr, code = _launch([python, "-m", "swizzle.governor.probe", str(spec)],
                                           str(base), env, timeout)
        except subprocess.TimeoutExpired:
            return _not_run(scenario, "Warden timed out after %ds; the probe was killed" % int(timeout))
        except OSError as exc:
            return _not_run(scenario, "the probe could not be started: %s" % exc)
        caps = _caps(stdout)
        outcome = _outcome(stdout)
        if outcome is None and scenario.ends_by_signal and code in _SIGTERM_DEATHS and "SWIZZLE_CAPS" in stdout:
            # The process was ended by the signal it was sent: the files are the answer.
            outcome = {"completed": True, "decision": "TERMINATED", "terminated": True, "notes": []}
        bad = judge_outcome(scenario, outcome, stderr, code)
        if bad is not None:
            return bad
        absent = feature_check(scenario, caps, files_version, assume_new_checks)
        if absent:
            return _not_run(scenario, absent, kind="feature_absent")
        after = snapshot(base)
    finally:
        shutil.rmtree(outer, ignore_errors=True)
        _live_dirs.discard(outer)
    problem = scenario.invariant(before, after, outcome)
    return Finding(scenario.name, scenario.hypothesis, scenario.severity,
                   "violated" if problem else "held", problem or "", str(outcome.get("decision") or ""))


def _outcome(stdout: str) -> Optional[Dict[str, object]]:
    for line in reversed(stdout.splitlines()):
        try:
            if line.startswith("SWIZZLE_RESULT "):
                value = json.loads(line[len("SWIZZLE_RESULT "):])
            elif line.startswith("{") and "unavailable" in line:
                value = json.loads(line)
            else:
                continue
        except ValueError:
            return None
        return value if isinstance(value, dict) else None
    return None


class BadSelection(ValueError):
    """--only named something that is not a scenario."""


def scenario_names() -> List[str]:
    return [s.name for s in SCENARIOS]


def select(only: Optional[str]) -> List[Scenario]:
    """Scenarios matching --only (comma-separated; each part is a name or part of one).

    A part that matches nothing is an error, never a silently smaller run.
    """
    if not only:
        return list(SCENARIOS)
    chosen: List[Scenario] = []
    for part in [p.strip() for p in only.split(",") if p.strip()]:
        hits = [s for s in SCENARIOS if part in s.name]
        if not hits:
            raise BadSelection("no scenario called %r. Valid names: %s" % (part, ", ".join(scenario_names())))
        chosen += [s for s in hits if s not in chosen]
    if not chosen:
        raise BadSelection("--only was empty. Valid names: %s" % ", ".join(scenario_names()))
    return chosen


class WardenNotFound(ValueError):
    """--warden does not point at a Warden checkout."""


def locate_warden(path: Path) -> Path:
    """The absolute Warden checkout, or WardenNotFound. Relative paths are fine."""
    root = Path(path).expanduser().resolve()
    if not (root / "warden").is_dir():
        raise WardenNotFound("%s is not a Warden checkout (no warden/ folder inside it)" % root)
    return root


class Interrupted(Exception):
    """Ctrl-C stopped the run. `findings` has every scenario, those not reached marked not_run."""

    def __init__(self, findings: List[Finding]) -> None:
        super().__init__("interrupted")
        self.findings = findings


def attack(warden_root: Path, swizzle_root: Optional[Path] = None,
           only: Optional[str] = None, python: str = sys.executable,
           assume_new_checks: bool = False) -> List[Finding]:
    swizzle_root = Path(swizzle_root or Path(__file__).resolve().parents[2]).resolve()
    warden_root = locate_warden(warden_root)
    chosen = select(only)
    previous = None
    if threading.current_thread() is threading.main_thread():
        # A kill signal must still run the cleanup in `finally`.
        previous = signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    done: List[Finding] = []
    try:
        for scenario in chosen:
            done.append(run_scenario(scenario, warden_root, swizzle_root, python,
                                     assume_new_checks=assume_new_checks))
        return done
    except KeyboardInterrupt:
        rest = [_not_run(s, "interrupted by the user (Ctrl-C) before this scenario ran", kind="interrupted")
                for s in chosen[len(done):]]
        raise Interrupted(done + rest) from None
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)


def exit_code(findings: Sequence[Finding]) -> int:
    """1 if anything was violated, else 2 if anything was not run, else 0 (and there was something to run)."""
    if any(f.status == "violated" for f in findings):
        return 1
    if not findings or any(f.status == "not_run" for f in findings):
        return 2
    return 0


def summary(findings: Sequence[Finding]) -> str:
    count = lambda status: sum(f.status == status for f in findings)  # noqa: E731
    return "%d attacks: %d held, %d violated, %d not run" % (
        len(findings), count("held"), count("violated"), count("not_run"))


def render(findings: Sequence[Finding]) -> str:
    lines = []
    for f in findings:
        mark = {"held": "held    ", "violated": "VIOLATED", "not_run": "not run "}[f.status]
        if f.kind == "feature_absent":
            mark = "skipped "
        lines.append(f"{mark} [{f.severity:6}] {f.scenario}" + (f"  -> {f.detail}" if f.detail else ""))
    lines.append(f"\n{summary(findings)}. "
                 "SWIZZLE reports; it does not decide what the governor should do about it.")
    if any(f.kind == "feature_absent" for f in findings):
        lines.append("A skipped scenario tests a check this Warden predates; it counts as not run (exit 2), "
                     "never as held.")
    if any(f.status == "not_run" for f in findings):
        lines.append("A scenario that did not run says nothing about that invariant. "
                     "Exit code: 1 if any violated, else 2 if any did not run, else 0.")
    return "\n".join(lines)


def as_dicts(findings: Sequence[Finding]) -> List[dict]:
    return [asdict(f) for f in findings]
