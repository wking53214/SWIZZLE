"""Attack memory, and the promotion rule that keeps it defensible."""

from __future__ import annotations

import json

import pytest

from swizzle.lab import attack
from swizzle.lab.corpus import BUCKETS, Corpus, PromotionRefused
from Tests import lab_cases
from Tests.fake_target import FakeTarget


@pytest.fixture()
def store(tmp_path):
    return Corpus(tmp_path / "corpus")


@pytest.fixture()
def confirmed_case():
    """A case two oracles agree on."""
    return attack.run(lab_cases.with_prose_in_block(), FakeTarget("replace_block"))


def test_every_bucket_exists(store):
    for bucket in BUCKETS:
        assert (store.root / bucket).is_dir()


def test_a_record_is_self_contained(store, confirmed_case):
    entry = store.record(confirmed_case)
    record = json.loads(entry.path.read_text())
    for key in ("genome", "target", "signals", "ground_truth", "swizzle",
                "environment", "reproduce", "recorded_at"):
        assert key in record, "an archived case without %r cannot be reproduced" % key


def test_an_archived_genome_rebuilds(store, confirmed_case):
    entry = store.record(confirmed_case)
    assert entry.genome == confirmed_case.genome


def test_a_corroborated_case_can_be_promoted(store, confirmed_case):
    store.record(confirmed_case, "minimized")
    entry = store.promote(confirmed_case.genome.name)
    assert entry.bucket == "regression"
    assert json.loads(entry.path.read_text())["promoted_from"] == "minimized"


def test_a_single_oracle_case_is_refused(store):
    """The cheapest way to look productive is to promote everything."""
    result = attack.run(lab_cases.simple(), FakeTarget("silent"))
    store.record(result, "discovered")
    with pytest.raises(PromotionRefused, match="independent oracles"):
        store.promote(result.genome.name)


def test_an_override_is_recorded_with_its_reason(store):
    result = attack.run(lab_cases.simple(), FakeTarget("silent"))
    store.record(result, "discovered")
    entry = store.promote(result.genome.name, force=True, reason="checked by hand")
    record = json.loads(entry.path.read_text())
    assert record["promotion_forced"] is True
    assert record["promotion_reason"] == "checked by hand"


def test_a_clean_case_is_kept_too(store):
    """A negative result that reproduces is evidence, not rubbish."""
    result = attack.run(lab_cases.simple(), FakeTarget("rewrite_count"))
    entry = store.record(result, "rejected")
    assert entry.bucket == "rejected"
    assert store.get(result.genome.name).bucket == "rejected"


def test_promoting_something_that_does_not_exist_fails_loudly(store):
    with pytest.raises(KeyError):
        store.promote("never_heard_of_it")
