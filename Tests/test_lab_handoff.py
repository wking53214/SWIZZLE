"""Lessons are sent once, wait for a human, and come back if a fix regresses."""

from types import SimpleNamespace

import pytest

from swizzle.lab.handoff import Handoff, fingerprint, lessons_from


def _entry(name, kind="missed_current_claim", oracle="reporting", judgement="violation",
           genome=None):
    signal = {"oracle": oracle, "judgement": judgement, "kind": kind, "severity": "MEDIUM"}
    return SimpleNamespace(name=name, record={"genome": genome or {"name": name, "a": 1},
                                              "signals": [signal]})


def test_only_reporting_violations_become_lessons():
    entries = [_entry("a"), _entry("b", oracle="structural"), _entry("c", judgement="ok"),
               _entry("d", kind="something_else")]
    assert [l.source_case for l in lessons_from(entries)] == ["a"]


def test_the_same_shape_gets_the_same_id_whatever_it_is_called():
    one = fingerprint("missed_current_claim", {"name": "x", "seed": 1, "a": 1})
    two = fingerprint("missed_current_claim", {"name": "y", "seed": 2, "a": 1})
    assert one == two
    assert one != fingerprint("over_cautious_flag", {"a": 1})
    assert one != fingerprint("missed_current_claim", {"a": 2})


def test_two_cases_with_one_shape_make_one_lesson():
    entries = [_entry("a", genome={"name": "a", "x": 1}), _entry("b", genome={"name": "b", "x": 1})]
    assert len(lessons_from(entries)) == 1


def test_a_lesson_is_sent_once_and_waits_for_approval(tmp_path):
    store = Handoff(tmp_path)
    lessons = lessons_from([_entry("a")])
    assert len(store.propose(lessons)) == 1
    assert store.propose(lessons) == []
    assert store.status(lessons[0].id) == "pending"
    assert not list((tmp_path / "approved").iterdir())


def test_approval_moves_the_lesson_out_of_pending(tmp_path):
    store = Handoff(tmp_path)
    (lesson,) = lessons_from([_entry("a")])
    store.propose([lesson])
    store.approve(lesson.id)
    assert (tmp_path / "approved" / ("%s.json" % lesson.id)).exists()
    assert not (tmp_path / "pending" / ("%s.json" % lesson.id)).exists()
    assert store.status(lesson.id) == "approved"


def test_unknown_or_unapproved_lessons_cannot_be_advanced(tmp_path):
    store = Handoff(tmp_path)
    (lesson,) = lessons_from([_entry("a")])
    store.propose([lesson])
    with pytest.raises(KeyError):
        store.approve("nope")
    with pytest.raises(KeyError):
        store.mark_fixed(lesson.id)


def test_a_fixed_lesson_that_returns_is_reopened_and_sent_again(tmp_path):
    store = Handoff(tmp_path)
    (lesson,) = lessons_from([_entry("a")])
    store.propose([lesson])
    store.approve(lesson.id)
    store.mark_fixed(lesson.id)
    assert store.propose([lesson]) == [lesson]
    assert store.status(lesson.id) == "reopened"
    assert (tmp_path / "pending" / ("%s.json" % lesson.id)).exists()
