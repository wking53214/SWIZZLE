"""The CI workflow says what it runs: pinned siblings, live tests on, static gates present."""

from __future__ import annotations

import re
import shlex
import tomllib
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")


def _job(name: str) -> str:
    """The text of one top-level job."""
    match = re.search(r"^  %s:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)" % re.escape(name), WORKFLOW, re.S | re.M)
    assert match, "no job called %s" % name
    return match.group(1)


def test_the_blocking_tests_job_pins_every_sibling_to_a_full_sha():
    job = _job("tests")
    repos = re.findall(r"repository: (\S+)\n\s+ref: (\S+)", job)
    assert {r for r, _ in repos} == {"wking53214/ghost_tools", "wking53214/ASSAY", "wking53214/WARDEN"}
    for repository, ref in repos:
        assert re.fullmatch(r"[0-9a-f]{40}", ref), "%s is pinned to %r, not a full commit SHA" % (repository, ref)


def test_every_pin_names_its_tag_in_a_comment():
    for line in _job("tests").splitlines():
        if re.search(r"\bref: [0-9a-f]{40}", line):
            assert "#" in line, "a pin without the tag it corresponds to: %s" % line.strip()


def test_nothing_that_blocks_is_continue_on_error():
    for name in ("static", "tests"):
        assert "continue-on-error" not in _job(name), "%s must fail when a step fails" % name


def test_the_latest_siblings_job_is_separate_and_non_blocking():
    job = _job("siblings-latest")
    assert re.search(r"^    continue-on-error: true", job, re.M)
    assert "non-blocking" in WORKFLOW


def test_the_live_tests_have_what_they_need_to_run():
    job = _job("tests")
    for variable in ("GHOST_TOOLS", "ASSAY", "WARDEN_ROOT"):
        assert re.search(r"^      %s: \$\{\{ github.workspace \}\}/" % variable, job, re.M), variable
    assert 'pip install -e ".[dev,cns]"' in job


def test_matrix_covers_311_312_313():
    versions = re.search(r'python-version: \[([^\]]*)\]', _job("tests")).group(1)
    assert [v.strip(' "') for v in versions.split(",")] == ["3.11", "3.12", "3.13"]


def test_static_gates_are_run():
    job = _job("static")
    assert "ruff check ." in job
    assert re.search(r"^\s+run: mypy$", job, re.M)


def test_the_cns_extra_is_pinned_to_the_v1_9_0_tag():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    (requirement,) = data["project"]["optional-dependencies"]["cns"]
    assert re.search(r"CNS\.git@v1\.9\.0$", requirement), requirement


def test_readme_does_not_hard_code_a_pass_count():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert not re.search(r"\b\d[\d,]*\s+passed\b", readme), (
        "a test count in the README drifts; say what CI runs and let the suite report its own numbers")


def test_readme_describes_the_ci_siblings_the_workflow_really_checks_out():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in ("ghost_tools", "ASSAY", "WARDEN"):
        assert name in readme
    assert ".github/workflows/tests.yml" in readme


def test_every_action_is_pinned_by_full_commit_sha_with_its_tag_in_a_comment():
    uses = re.findall(r"^\s*- uses: (\S+?)(?:\s+#\s*(.*))?$", WORKFLOW, re.M)
    assert uses, "the workflow uses no actions?"
    for action, comment in uses:
        name, _, ref = action.partition("@")
        assert re.fullmatch(r"[0-9a-f]{40}", ref), "%s is not pinned to a full commit SHA" % action
        assert re.fullmatch(r"v\d+(\.\d+){2}", (comment or "").strip()), (
            "%s has no release tag in its comment (got %r)" % (name, comment))


def _pin_versions(job: str) -> dict:
    """{repository: version named in the pin's comment}, for the sibling checkouts of one job."""
    found = {}
    for repository, comment in re.findall(r"repository: (\S+)\n\s+ref: [0-9a-f]{40}\s+# (.*)", job):
        match = re.search(r"\b(\d+\.\d+\.\d+)\b", comment)
        assert match, "the pin for %s names no version: %r" % (repository, comment)
        found[repository.split("/")[-1]] = match.group(1)
    return found


def test_the_tested_set_is_the_one_the_readme_names():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    versions = _pin_versions(_job("tests"))
    assert set(versions) == {"ghost_tools", "ASSAY", "WARDEN"}
    for name, version in versions.items():
        assert "%s %s" % (name, version) in readme, "README does not name the tested %s %s" % (name, version)


def test_the_tested_set_is_the_current_known_good_one():
    """Guards against the pins silently sliding back to a Warden that predates the SWIZZLE --contract check."""
    job = _job("tests")
    assert _pin_versions(job) == {"ghost_tools": "1.10.5", "ASSAY": "0.11.2", "WARDEN": "0.13.7"}
    assert "ref: 1636e1a21f124eedbf6e158db95dc75344f4308d" in job
    assert "ref: c2ada82d2f6c0404074a668ba749c7872743aad9" in job
    assert "ref: 54248beb5a36600f69de7c816cb2271dda20a879" in job


# The oldest CPython each numpy release supports (its Requires-Python). numpy 2.5.x dropped 3.11, so an
# unmarked `numpy==2.5.4` cannot be installed by the 3.11 matrix job; that is the regression this guards.
NUMPY_MIN_PYTHON = {"2.4.6": (3, 11), "2.5.4": (3, 12)}


def _interpreters(job: str) -> list[str]:
    """The Python versions a job runs on: its matrix, or the single version it sets up."""
    matrix = re.search(r"python-version: \[([^\]]*)\]", job)
    if matrix:
        return [v.strip(' "') for v in matrix.group(1).split(",")]
    single = re.findall(r'python-version: "([0-9.]+)"', job)
    assert len(single) == 1, "cannot tell which Python this job uses: %r" % single
    return single


def _verifier_requirements(job: str) -> list[Requirement]:
    """The requirements installed by the step that installs ASSAY's verifier dependencies."""
    match = re.search(r"name: Install ASSAY's verifier dependencies\n\s+run: pip install (.*)\n", job)
    assert match, "the job has no step installing ASSAY's verifier dependencies"
    return [Requirement(token) for token in shlex.split(match.group(1))]


def test_every_job_that_runs_the_suite_installs_the_assay_verifier_dependencies():
    """ASSAY 0.11.1 exits 1 on a skipped claim, and it skips claims without numpy and matplotlib.

    The policy, not a string: every job that runs the ASSAY-dependent tests installs numpy and matplotlib, each
    pinned to one exact version, and on every Python that job runs, exactly one numpy pin applies and that
    version supports that Python.
    """
    for name in ("tests", "siblings-latest"):
        job = _job(name)
        requirements = _verifier_requirements(job)
        assert {r.name for r in requirements} == {"numpy", "matplotlib"}, name
        for requirement in requirements:
            specs = list(requirement.specifier)
            assert len(specs) == 1 and specs[0].operator == "==", "%s: %s is not an exact pin" % (name, requirement)
        for python in _interpreters(job):
            env = {"python_version": python}
            applicable = [r for r in requirements if r.marker is None or r.marker.evaluate(env)]
            by_name: dict[str, list[Requirement]] = {}
            for requirement in applicable:
                by_name.setdefault(requirement.name, []).append(requirement)
            assert set(by_name) == {"numpy", "matplotlib"}, "%s on %s installs %s" % (name, python, sorted(by_name))
            for pins in by_name.values():
                assert len(pins) == 1, "%s on %s has conflicting pins: %s" % (name, python, [str(p) for p in pins])
            version = next(iter(by_name["numpy"][0].specifier)).version
            assert version in NUMPY_MIN_PYTHON, "teach NUMPY_MIN_PYTHON about numpy %s" % version
            assert tuple(int(x) for x in python.split(".")) >= NUMPY_MIN_PYTHON[version], (
                "%s: numpy %s cannot be installed on Python %s" % (name, version, python)
            )
