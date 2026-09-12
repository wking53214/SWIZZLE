"""Learning, and the three ways anything here comes to be known.

    ENHANCEMENT   a structure exists and new evidence refines it
    CONNECTION    two separately known things turn out to be related
    ZERO BASE     genuinely new, with no prior structure at all

The failure these tests guard is the third one being handled as though it
were the first: a key with no history handed an invented number, which is
then used as evidence. That is the same unearned promotion `standing.py`
refuses about a fix, one layer down.
"""

from __future__ import annotations

import json

import pytest

from swizzle.lab.knowledge import Acquisition, Knowledge, Store, Tally


@pytest.fixture()
def store(tmp_path):
    return Store(tmp_path / "knowledge.json")


REV_A = "aaaaaaaaaaaa"
REV_B = "bbbbbbbbbbbb"


# ------------------------------------------------------------- zero base

def test_a_key_never_offered_has_no_weight_at_all(store):
    """None, not a small number.

    None is the absence of a measurement. A float here would be a prior
    invented by the framework and then consumed as though it had been
    observed, which is the whole thing this module exists to refuse.
    """
    knowledge = store.about("never_tried", REV_A)
    assert knowledge.acquisition is Acquisition.ZERO_BASE
    assert knowledge.weight() is None


def test_zero_base_keys_are_listed_for_exploration(store):
    store.observe("known", REV_A, improved=True, critical=False)
    assert store.zero_base(["known", "new_one", "other"], REV_A) == ("new_one",
                                                                    "other")


def test_the_search_reaches_a_zero_base_through_exploration_not_weight():
    """A reserved share of the budget, not a floor on the weight.

    A floor invents a number and treats the result as evidence. A share says
    plainly that some budget is spent on the unknown BECAUSE it is unknown.
    """
    import inspect
    from swizzle.lab import search
    source = inspect.getsource(search._choose)
    assert "EXPLORE_SHARE" in source
    assert "ZERO_BASE" in source
    assert search.EXPLORE_SHARE > 0


# ----------------------------------------------------------- enhancement

def test_observation_against_this_revision_is_a_real_posterior(store):
    for improved in (True, True, False, False):
        store.observe("m", REV_A, improved=improved, critical=False)
    knowledge = store.about("m", REV_A)
    assert knowledge.acquisition is Acquisition.OBSERVED
    assert knowledge.weight() == pytest.approx(0.5)


def test_evidence_is_never_merged_across_revisions(store):
    store.observe("m", REV_A, improved=True, critical=False)
    assert store.about("m", REV_B).acquisition is Acquisition.CARRIED
    assert store.about("m", REV_A).acquisition is Acquisition.OBSERVED


def test_carried_evidence_is_inference_and_cannot_outrank_observation(store):
    """A phase 3 result is not a post-market observation.

    Statistics gathered against one revision become inference when the
    revision moves. Not discarded -- still the best guess available -- and
    never competing on equal terms with something measured where the
    question is actually being asked.

    Structurally subordinate, not discounted. A discount factor would be a
    judgement disguised as arithmetic, which is the failure this module is
    about; an earlier version halved carried evidence and thereby put a
    perfect record from elsewhere level with a coin flip measured here.
    """
    for _ in range(4):
        store.observe("carried_key", REV_A, improved=True, critical=False)
    for improved in (True, False):
        store.observe("measured_key", REV_B, improved=improved, critical=False)

    carried = store.about("carried_key", REV_B)
    measured = store.about("measured_key", REV_B)
    assert carried.acquisition is Acquisition.CARRIED
    assert carried.tally.improved == 4 and carried.tally.offered == 4
    # Its raw rate is better. It still loses, because the ordering is not
    # about the number.
    assert carried.weight() > measured.weight()
    assert not carried.outranks_carried
    assert measured.outranks_carried


def test_the_search_prefers_observation_to_inference():
    import inspect
    from swizzle.lab import search
    source = inspect.getsource(search._choose)
    assert "outranks_carried" in source
    assert "here or elsewhere" in source


# ------------------------------------------------------------ connection

def test_a_connection_is_its_own_key_not_a_bigger_number(store):
    """The finding is that two things relate. Neither member's own tally can
    express that, so it is recorded as a third thing."""
    store.connect(["a", "b"], REV_A, lift=0.4)
    connection = store.about("a + b", REV_A)
    assert connection.acquisition is Acquisition.CONNECTED
    assert connection.members == ("a", "b")
    # The members are untouched: still zero base, because nothing was
    # observed about either one alone.
    assert store.about("a", REV_A).acquisition is Acquisition.ZERO_BASE
    assert store.about("b", REV_A).acquisition is Acquisition.ZERO_BASE


def test_a_connection_is_ordered_by_lift(store):
    store.connect(["a", "b"], REV_A, lift=0.1)
    store.connect(["c", "d"], REV_A, lift=0.9)
    assert [k.key for k in store.connections(REV_A)] == ["c + d", "a + b"]


def test_connection_members_are_order_independent(store):
    store.connect(["b", "a"], REV_A, lift=0.2)
    assert store.about("a + b", REV_A).acquisition is Acquisition.CONNECTED


# ------------------------------------------------------------ persistence

def test_knowledge_round_trips(store, tmp_path):
    store.observe("m", REV_A, improved=True, critical=True)
    store.connect(["a", "b"], REV_A, lift=0.3)
    store.save()

    again = Store(tmp_path / "knowledge.json")
    assert again.about("m", REV_A).acquisition is Acquisition.OBSERVED
    assert again.about("m", REV_A).tally.critical == 1
    assert again.about("a + b", REV_A).members == ("a", "b")


def test_a_file_this_version_cannot_read_is_not_merged_under_a_guess(tmp_path):
    """The honest answer is everything reads zero base, not the convenient
    one where a foreign schema is interpreted hopefully."""
    path = tmp_path / "knowledge.json"
    path.write_text(json.dumps({"schema": "something.else.v9",
                                "revisions": {REV_A: [{"key": "m"}]}}))
    assert Store(path).about("m", REV_A).acquisition is Acquisition.ZERO_BASE


def test_an_unreadable_file_does_not_take_the_run_down(tmp_path):
    path = tmp_path / "knowledge.json"
    path.write_text("{ not json")
    assert Store(path).about("m", REV_A).acquisition is Acquisition.ZERO_BASE


# -------------------------------------------------------------- reporting

def test_the_report_says_what_has_no_prior(store):
    from swizzle.lab.knowledge import render
    store.observe("m", REV_A, improved=True, critical=False)
    rows = store.table(REV_A, ["m", "never_tried"])
    text = render(rows, REV_A)
    assert "TRUE ZERO BASE" in text
    assert "an experiment" in text
    assert "not a bet" in text
