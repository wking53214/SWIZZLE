"""Archived cases must still rebuild, and still mean what they meant.

This is the test that keeps the corpus honest over time. An entry that no
longer round-trips is an entry whose experiment has silently changed, and
the first anyone would know about it is a regression run failing for a
reason nobody can reconstruct.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from swizzle.lab import world
from swizzle.lab.genome import RepositoryGenome
from swizzle.lab.groundtruth import of as ground_truth_of
from Tests.fake_target import FakeTarget

CORPUS = Path(__file__).resolve().parents[1] / "corpus"

#: Only the bucket directories. The corpus root also holds `knowledge.json`,
#: which is not a case record and has no genome in it -- globbing the whole
#: tree made every run assert that the knowledge file was a reproducible
#: attack, which it is not and was never claimed to be.
BUCKETS = ("discovered", "minimized", "regression", "rejected")
ENTRIES = sorted(path for bucket in BUCKETS
                 for path in (CORPUS / bucket).glob("*.json")) if CORPUS.is_dir() else []


@pytest.mark.skipif(not ENTRIES, reason="the corpus is empty")
@pytest.mark.parametrize("path", ENTRIES, ids=lambda p: "%s/%s" % (p.parent.name, p.stem))
def test_an_archived_case_still_rebuilds(path):
    record = json.loads(path.read_text(encoding="utf-8"))
    genome = RepositoryGenome.from_dict(record["genome"])
    assert genome.to_dict() == record["genome"], (
        "this entry no longer round-trips: replaying it would run a different "
        "experiment from the one that was archived")
    draft = world.build(genome, FakeTarget().dialect())
    assert draft.files


@pytest.mark.skipif(not ENTRIES, reason="the corpus is empty")
@pytest.mark.parametrize("path", ENTRIES, ids=lambda p: "%s/%s" % (p.parent.name, p.stem))
def test_an_archived_case_carries_what_reproduction_needs(path):
    record = json.loads(path.read_text(encoding="utf-8"))
    for key in ("genome", "target", "swizzle", "environment", "reproduce",
                "recorded_at", "hypothesis"):
        assert key in record, "%s has no %r" % (path.name, key)
    assert record["target"].get("commit"), (
        "an attack recorded without the target revision cannot be attributed "
        "to anything")


@pytest.mark.skipif(not ENTRIES, reason="the corpus is empty")
def test_discovered_cases_actually_found_something():
    for path in sorted((CORPUS / "discovered").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        assert record["top_severity"] != "NONE", (
            "%s is filed as discovered and violated nothing" % path.name)


@pytest.mark.skipif(not ENTRIES, reason="the corpus is empty")
def test_rejected_cases_really_are_clean():
    """A negative result filed as a negative result. If one of these starts
    failing, the target changed and the file should move buckets."""
    for path in sorted((CORPUS / "rejected").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        assert record["top_severity"] == "NONE", (
            "%s is filed as rejected and has a violation in it" % path.name)
