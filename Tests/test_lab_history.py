"""Recording that a case was fixed, without ever saying it was fixed.

The point of writing down that a case stopped reproducing is to make it
possible to find out later that it did not stay stopped. An arc that closed
the question would defeat the file it lives in, so `held` is the strongest
thing available and it is a statement about the RECORD, not about the defect.

Every test here builds episodes directly. Nothing runs a target, because
what is under test is the shape the record takes, not what produced it.
"""
from __future__ import annotations

import json

import pytest

from swizzle.lab.history import Arc, CaseHistory, Episode, History, render
from swizzle.lab.standing import Standing

# The spellings as they are actually STORED. Taken from the enum rather than
# retyped: retyping them is the defect this file's own history records.
REPRODUCES = Standing.REPRODUCES.value
RECURRED = Standing.RECURRED.value
RESOLVED = Standing.STRUCTURE_SUPPORTS_RESOLVED.value
DEFEATED = Standing.UNREPRODUCED_BUT_DEFEATED.value
UNPROBED = Standing.UNREPRODUCED_UNPROBED.value
NEVER = Standing.NEVER_REPRODUCED.value
AMBIGUOUS = Standing.AMBIGUOUS.value


def _history(*standings, defeats=()):
    episodes = tuple(
        Episode(case="c", revision="r%d" % i, standing=standing,
                defeated_by=("variant",) if i in defeats else ())
        for i, standing in enumerate(standings))
    return CaseHistory(case="c", episodes=episodes)


# ------------------------------------------------- the vocabulary matches

def test_every_standing_is_classified_exactly_once():
    """THE REGRESSION.

    The strings were retyped beside the enum and two of them were wrong.
    Nothing raised: the episodes fell through to "neither", every arc came
    back `unknown`, and a ledger whose whole purpose is to notice a case
    coming back would have said `unknown` forever without ever failing.

    Silence is the failure mode of a lookup table, so the table is checked
    against its source rather than trusted.
    """
    from swizzle.lab.history import _QUIET, _REPRODUCING
    for member in Standing:
        reproducing = member.value in _REPRODUCING
        quiet = member.value in _QUIET
        if member is Standing.AMBIGUOUS:
            assert not reproducing and not quiet, (
                "an oracle that declined to say did not say no")
        else:
            assert reproducing != quiet, member.name


def test_a_record_written_with_the_member_name_still_reads():
    """Widening what is read is safe. Guessing it is not."""
    history = CaseHistory("c", (
        Episode("c", "r0", "reproduces"),
        Episode("c", "r1", "structure_supports_resolved")))
    assert history.arc is Arc.HELD


def test_the_standing_a_real_run_writes_is_understood():
    """The exact string the first real `--record` run produced."""
    from swizzle.lab.history import _QUIET
    assert "unreproduced, unprobed" in _QUIET


# ------------------------------------------------------------- the arcs

@pytest.mark.parametrize("standings,expected", [
    ((REPRODUCES,), Arc.OPEN),
    ((REPRODUCES, REPRODUCES), Arc.OPEN),
    ((NEVER,), Arc.NEVER_ESTABLISHED),
    ((REPRODUCES, UNPROBED), Arc.HELD),
    ((REPRODUCES, UNPROBED, REPRODUCES), Arc.RETURNED),
    ((NEVER, NEVER), Arc.NEVER_ESTABLISHED),
    ((REPRODUCES, RESOLVED), Arc.HELD),
    ((REPRODUCES, RESOLVED, RESOLVED), Arc.HELD),
    ((REPRODUCES, RESOLVED, REPRODUCES), Arc.RETURNED),
    ((REPRODUCES, RESOLVED, RECURRED), Arc.RETURNED),
    ((AMBIGUOUS, AMBIGUOUS), Arc.UNKNOWN),
])
def test_the_arc_follows_the_sequence(standings, expected):
    assert _history(*standings).arc is expected


def test_a_case_that_only_just_started_working_has_not_come_back():
    """`never_reproduced` then `reproduces` is a case that was never
    established, not a regression. Calling it one sends somebody looking for
    a fix that was never made."""
    assert _history(NEVER, REPRODUCES).arc is Arc.OPEN
    assert _history(NEVER, REPRODUCES).returned_at is None


def test_a_quiet_that_a_probe_defeated_is_contested_not_held():
    assert _history(REPRODUCES, DEFEATED, defeats=(1,)).arc is Arc.CONTESTED


def test_returned_names_the_revision_it_came_back_at():
    assert _history(REPRODUCES, RESOLVED, REPRODUCES).returned_at == "r2"


def test_an_ambiguous_episode_does_not_manufacture_a_quiet_spell():
    """An oracle that declined did not say the case stopped reproducing.
    Reading "we could not tell" as "it did not happen" would turn a run of
    broken worlds into a fix."""
    assert _history(REPRODUCES, AMBIGUOUS, REPRODUCES).arc is Arc.OPEN
    assert _history(REPRODUCES, AMBIGUOUS).arc is Arc.OPEN


def test_only_returned_contested_and_open_want_attention():
    assert Arc.RETURNED.wants_attention and Arc.CONTESTED.wants_attention
    assert Arc.OPEN.wants_attention
    assert not Arc.HELD.wants_attention
    assert not Arc.NEVER_ESTABLISHED.wants_attention


# ----------------------------------------------------- nothing says fixed

def test_no_arc_reads_as_fixed():
    for arc in Arc:
        assert "fix" not in arc.value


def test_the_rendering_refuses_the_word_and_says_why():
    rendered = render([_history(REPRODUCES, RESOLVED)])
    assert "held" in rendered
    for line in rendered.splitlines():
        if "fixed" in line:
            assert "not" in line, line
    assert "shape of the record" in rendered


def test_doubts_from_the_newest_episode_are_carried_forward():
    """Flattening a sequence of provisional answers into one confident shape
    is how a corpus fills with conclusions nobody reached."""
    episodes = (Episode("c", "r0", REPRODUCES),
                Episode("c", "r1", RESOLVED, unprobed=("variant", "scope")))
    history = CaseHistory("c", episodes)
    assert history.unsettled == ("variant", "scope")
    assert "never asked" in render([history])


# ------------------------------------------------------------- the store

class _Resolution:
    """The shape `History.record` reads, without importing the world."""

    def __init__(self, case, standing, classes=(), severity="HIGH",
                 defeated=(), unprobed=()):
        self.observation = type("O", (), {
            "case": case, "classes": classes, "top_severity": severity})()
        self.standing = type("S", (), {"value": standing})()
        self.defeated_by = defeated
        self.unprobed = unprobed


def test_a_second_interrogation_appends_rather_than_replacing(tmp_path):
    """Two interrogations that disagree are evidence about how stable the
    answer is. Keeping only the last one throws that away -- and a store
    that overwrote would be a store in which no case had ever regressed."""
    ledger = History(tmp_path / "standings.json")
    ledger.record(_Resolution("c", REPRODUCES), "r0")
    ledger.record(_Resolution("c", RESOLVED), "r1")
    ledger.record(_Resolution("c", REPRODUCES), "r2")
    assert len(ledger.of("c").episodes) == 3
    assert ledger.of("c").arc is Arc.RETURNED


def test_it_round_trips_through_disk(tmp_path):
    path = tmp_path / "standings.json"
    ledger = History(path)
    ledger.record(_Resolution("c", REPRODUCES, classes=("escape",)), "r0")
    ledger.record(_Resolution("c", RESOLVED), "r1")
    ledger.save()

    reread = History(path)
    assert [e.standing for e in reread.of("c").episodes] == [REPRODUCES, RESOLVED]
    assert reread.of("c").episodes[0].classes == ("escape",)
    assert reread.of("c").arc is Arc.HELD


def test_a_file_from_another_schema_is_declined_rather_than_guessed_at(tmp_path):
    path = tmp_path / "standings.json"
    path.write_text(json.dumps({"schema": "something.else.v9",
                                "episodes": [{"case": "c"}]}))
    assert History(path).cases() == ()


def test_a_corrupt_file_does_not_take_the_run_down(tmp_path):
    path = tmp_path / "standings.json"
    path.write_text("{not json")
    assert History(path).all() == []


def test_returned_lists_only_the_cases_worth_waking_somebody_for(tmp_path):
    ledger = History(tmp_path / "s.json")
    for standing in (REPRODUCES, RESOLVED, REPRODUCES):
        ledger.record(_Resolution("came_back", standing), "r")
    for standing in (REPRODUCES, RESOLVED):
        ledger.record(_Resolution("still_quiet", standing), "r")
    assert [h.case for h in ledger.returned()] == ["came_back"]


def test_one_case_history_does_not_see_another(tmp_path):
    ledger = History(tmp_path / "s.json")
    ledger.record(_Resolution("a", REPRODUCES), "r0")
    ledger.record(_Resolution("b", RESOLVED), "r0")
    assert [e.case for e in ledger.of("a").episodes] == ["a"]
    assert ledger.of("a").arc is Arc.OPEN


def test_the_history_round_trips_through_json(tmp_path):
    ledger = History(tmp_path / "s.json")
    ledger.record(_Resolution("c", REPRODUCES), "r0")
    ledger.record(_Resolution("c", RESOLVED), "r1")
    payload = json.loads(json.dumps(ledger.of("c").to_dict()))
    assert payload["arc"] == "held"
    assert payload["revisions"] == ["r0", "r1"]
