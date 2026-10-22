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
