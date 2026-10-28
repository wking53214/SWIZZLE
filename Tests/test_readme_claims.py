"""The README makes claims a reader acts on. These tests hold the ones that can be held.

They do not prove the README is true. They fail when a number, a test it cites, a section it promises or a
word it was told never to use drifts away from the repository.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from swizzle.warps import catalogue

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

SECTIONS = [
    "## What this is",
    "## How to install and run",
    "### What works",
    "### What does not work, and what is not proven",
    "### Known defects",
    "### What broke and how it was fixed",
    "### Self-hosting",
    "### Ceilings code cannot fix",
]

#: Words the README must not use to describe itself. A claim is made by naming the test that shows it.
BANNED = ["robust", "powerful", "production-ready", "production ready", "seamless", "comprehensive",
          "blazing", "enterprise", "battle-tested", "state-of-the-art"]


def _section(heading: str) -> str:
    start = README.index(heading + "\n")
    level = len(heading.split(" ")[0])
    rest = README[start + len(heading):]
    end = re.search(r"^#{1,%d} " % level, rest, re.M)
    return rest[: end.start()] if end else rest


def test_every_promised_section_is_there_once_and_in_order():
    positions = []
    for heading in SECTIONS:
        assert README.count(heading + "\n") == 1, "%s is missing or appears more than once" % heading
        positions.append(README.index(heading + "\n"))
    assert positions == sorted(positions), "the README sections are out of order"


def test_the_readme_uses_none_of_the_banned_words_and_no_em_dash():
    lowered = README.lower()
    for word in BANNED:
        assert word not in lowered, "the README uses %r" % word
    assert "—" not in README


def test_the_readme_does_not_say_whether_tags_exist():
    """Whether a tag exists goes stale the day the owner tags; the README points at the repository instead."""
    assert "v0.10.0" not in README
    assert not re.search(r"\b(not tagged|no tags?|is tagged|are tagged yet|tag exists)\b", README, re.I)


def test_the_number_of_proofs_the_readme_states_is_the_number_of_warps():
    stated = {int(n) for n in re.findall(r"\b(\d+) planted-defect proofs", README)}
    assert stated == {len(catalogue())}, "the README says %s, the catalogue has %d" % (stated, len(catalogue()))


def test_the_lint_numbers_the_readme_states_are_the_ones_pyproject_sets():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["ruff"]
    assert "line length %d" % data["line-length"] in README
    rules = ", ".join(data["lint"]["select"])
    assert "rules %s;" % rules in README


def test_the_install_lines_are_in_the_readme():
    assert "pip install -e '.[dev,cns]'" in README
    assert 'pip install "git+https://github.com/wking53214/SWIZZLE.git"' in README
    assert "from PyPI by bare name" in _section("## How to install and run"), "the warning about the PyPI name is gone"


def test_every_test_the_readme_cites_exists():
    """A README that names a test as evidence must name one that is there."""
    checked = 0
    for line in README.splitlines():
        last_file = None
        for token in re.findall(r"`([^`]+)`", line):
            match = re.fullmatch(r"(Tests/[\w/]+\.py)(?:::(\w+))?", token)
            name = None
            if match:
                last_file, name = ROOT / match.group(1), match.group(2)
                assert last_file.is_file(), "the README cites %s, which does not exist" % token
            elif token.startswith("::") and re.fullmatch(r"::\w+", token):
                assert last_file is not None, "the README cites %s with no file before it" % token
                name = token[2:]
            if name:
                text = last_file.read_text(encoding="utf-8")
                assert re.search(r"^\s*def %s\(" % re.escape(name), text, re.M), (
                    "the README cites %s in %s, which has no such test" % (name, last_file.name))
                checked += 1
    assert checked >= 30, "the README cites far fewer tests than it did (%d)" % checked


def test_every_version_in_the_ledger_is_a_changelog_version():
    ledger = _section("### What broke and how it was fixed")
    versions = re.findall(r"^- \*\*(\d+\.\d+\.\d+)", ledger, re.M)
    assert versions, "the ledger names no versions"
    for version in versions:
        assert "## [%s]" % version in CHANGELOG, "the ledger names %s, which the CHANGELOG does not" % version


def test_the_ledger_and_the_defects_say_what_prevents_each_item_or_that_nothing_does():
    ledger = _section("### What broke and how it was fixed")
    entries = [e for e in ledger.split("\n- ")[1:] if e.strip()]
    assert len(entries) >= 15
    for entry in entries:
        assert "Guard" in entry or "no test yet" in entry or "No single guard" in entry, (
            "a ledger entry names no guard: %s" % entry[:80])


# --- the self-hosting paragraph ------------------------------------------------------------------------------

#: Copied from the CNS repository's docs/evidence/SELFHOSTING_2026-10-23.md (branch
#: claude/horsemen-production-status-5wsndb until merged): the SWIZZLE rows of its two tables and its
#: "Re-run after BURNISH 0.3.12" section. They are the numbers of one recorded run at commit 3f35dad, so they
#: do not change when this repository does. If the evidence file is corrected, change them here and in the README.
SELFHOSTING_EVIDENCE_FILE = "docs/evidence/SELFHOSTING_2026-10-23.md"
SELFHOSTING_COMMIT = "3f35dad5568b590c2ee36e60533d50a35db94aa2"
SELFHOSTING_VERSION = "0.8.7"
SELFHOSTING_RUN_1_DECISION = "FINISH_REJECTED"
SELFHOSTING_RUN_2_DECISION = "ACCEPT"
SELFHOSTING_RUN_2_RECORD_FILE = "SWIZZLE.run2.json"
SELFHOSTING_RUN_2_RECORDS_DIRECTORY = "docs/evidence/selfhosting-records-2026-10-23/"
SELFHOSTING_DECLINED_CHECKS = ["mutate", "kernel", "structure", "tests", "project", "secrets", "correlate"]
SELFHOSTING_GHOST_FINDINGS_STANDING = 215


def test_the_self_hosting_paragraph_states_the_recorded_run_and_what_it_does_not_mean():
    text = _section("### Self-hosting")
    assert SELFHOSTING_EVIDENCE_FILE in text
    assert "claude/horsemen-production-status-5wsndb" in text and "until that branch is merged" in text
    assert SELFHOSTING_COMMIT in text and SELFHOSTING_VERSION in text
    assert SELFHOSTING_RUN_1_DECISION in text and "Burnish 0.3.12" in text
    assert re.search(r"\bended %s \(exit 0\)" % SELFHOSTING_RUN_2_DECISION, text)
    run_2 = text[text.index("Run 2 ended"):text.index("The record also shows")]
    assert "with a green suite" in run_2
    assert SELFHOSTING_RUN_2_RECORD_FILE in run_2 and SELFHOSTING_RUN_2_RECORDS_DIRECTORY in run_2
    assert not re.search(r"\b\d[\d,]*\s+(tests?|passed|passing|skipped)\b", run_2), (
        "the run 2 sentence quotes a count; the counts are in the record, and a count here drifts")
    assert "%d Ghost findings still standing" % SELFHOSTING_GHOST_FINDINGS_STANDING in text
    assert "%d Ghost checks declined" % len(SELFHOSTING_DECLINED_CHECKS) in text
    assert "(%s)" % ", ".join(SELFHOSTING_DECLINED_CHECKS) in text
    # what the record does not mean
    assert "no secrets or no weak tests" in text
    assert "does not mean the %d standing findings are resolved" % SELFHOSTING_GHOST_FINDINGS_STANDING in text
    assert "not the commits after it" in text
    assert "names the finisher as Burnish 0.3.11 although 0.3.12 ran" in text


def test_no_sentence_that_has_gone_stale_is_left_in_the_documents_or_the_workflow():
    stale = ["no fresh run", "A fresh run is meant to be recorded", "no such page was there",
             "assumed to arrive in 0.9.0", "the head of", "wave D main", "ASSAY's `main`", "ASSAY's main",
             "tested set;", "(a tested set"]
    documents = {"README.md": README}
    for name in ("docs/IMPLEMENTATION_STATUS.md", "STACK.md", ".github/workflows/tests.yml"):
        documents[name] = (ROOT / name).read_text(encoding="utf-8")
    for name, text in documents.items():
        for phrase in stale:
            assert phrase not in text, "%s still says %r" % (name, phrase)


def test_the_tested_set_is_described_as_what_this_repository_tested_not_as_the_siblings_heads():
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    sentence = "the last set this repository's CI tested on its own"
    assert sentence in README
    assert "`stack` job in the CNS repository" in README
    pins = re.findall(r"ref: [0-9a-f]{40}\s+# (.*)", workflow)
    assert len(pins) == 3
    for comment in pins:
        assert sentence in comment, comment
    assert "the `stack` job in the CNS repository" in workflow


def test_the_version_floor_is_described_as_a_label_not_a_measured_release():
    from swizzle.governor.scenarios import NEW_CHECKS_SINCE
    assert NEW_CHECKS_SINCE == "0.9.0"
    assert "`NEW_CHECKS_SINCE` in `swizzle/governor/scenarios.py`, not a measured release boundary" in README
    assert "nothing checks that Warden 0.9.0 really has those checks" in README


def test_the_inventory_in_the_implementation_status_is_the_code_s():
    """docs/IMPLEMENTATION_STATUS.md says how many warps, mutators, seed cases and scenarios there are."""
    from swizzle.governor.scenarios import SCENARIOS
    from swizzle.lab import catalogue as lab_catalogue
    from swizzle.lab.mutators import registry
    text = (ROOT / "docs" / "IMPLEMENTATION_STATUS.md").read_text(encoding="utf-8")
    rows = {m.group(1): int(m.group(2)) for m in re.finditer(r"^\| (.+?) \| (\d+) \|", text, re.M)}
    assert rows["Original warps (planted-defect proofs)"] == len(catalogue())
    assert rows["Laboratory mutators"] == len(registry())
    assert rows["Seed attack cases"] == len(lab_catalogue.by_name())
    assert rows["Governor scenarios (attacks on Warden)"] == len(SCENARIOS)
