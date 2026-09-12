"""Does the target settle, and can this harness tell?

Two different things are under test here and they are easy to confuse.

    the target      does accepting its output and running it again stop?
    the harness     can it tell "ran and changed nothing" apart from
                    "never ran"?

The second is the one that bites. Both leave an unchanged repository behind,
and a harness that reads them the same way reports a fixpoint for a target
it never actually ran -- the exact false negative that hid a real period-3
cycle in this project's own catalogue until it was measured.

Every test here uses the fake target, so a failure means the classifier is
wrong rather than that Ghost changed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from fake_target import FakeTarget
from lab_cases import simple
from swizzle.lab import convergence
from swizzle.lab.convergence import Settling


def _run(behaviour, *, rounds=6, **kw):
    return convergence.iterate(simple("convergence_%s" % behaviour),
                               FakeTarget(behaviour, **kw), rounds=rounds)


# --------------------------------------------------------- the four shapes

def test_a_target_with_nothing_to_do_is_inert():
    result = _run("abstain")
    assert result.settling is Settling.INERT
    assert not result.settling.is_a_loop


def test_a_target_that_writes_once_reaches_a_fixpoint():
    """The control. A harness that finds a loop everywhere fails here."""
    result = _run("settle", measured=99)
    assert result.settling is Settling.FIXPOINT
    assert result.settled_after == 1
    assert not result.settling.is_a_loop


def test_a_target_that_undoes_itself_is_a_cycle():
    result = _run("flip")
    assert result.settling is Settling.CYCLE
    assert result.period == 2
    assert result.settling.is_a_loop


def test_a_target_that_never_repeats_a_state_is_divergent():
    result = _run("count_up", rounds=4)
    assert result.settling is Settling.DIVERGENT
    assert result.settling.is_a_loop
    assert len({r.digest for r in result.rounds}) == len(result.rounds)


# -------------------------------------------------- the harness's own trap

def test_a_round_the_target_refused_to_begin_is_not_a_fixpoint():
    """THE REGRESSION.

    `refuse_after_one` acts once and then refuses to start. The tree after
    the refusal is identical to the tree before it, which is also exactly
    what settling looks like. Measured, before this was fixed: reported as
    a fixpoint, and the cycle underneath it stayed invisible for as long as
    the refusals kept landing.
    """
    result = _run("refuse_after_one", measured=99)
    assert result.settling is Settling.BROKEN
    assert result.settling is not Settling.FIXPOINT
    assert result.settled_after is None
    assert "never began" in result.note


def test_the_refused_round_is_recorded_rather_than_only_counted():
    """A reader has to be able to see WHICH round refused."""
    result = _run("refuse_after_one", measured=99)
    assert [r.ran for r in result.rounds] == [True, False]
    assert result.rounds[-1].note
    assert "NEVER RAN" in result.render()


def test_a_ran_round_is_marked_as_having_run():
    result = _run("settle", measured=99)
    assert all(r.ran for r in result.rounds)


# ---------------------------------------------------------- the bound

def test_the_bound_is_honoured_and_not_settling_is_the_finding():
    """Nothing here runs until it stops. An adversarial harness that can
    hang is an adversarial harness nobody will run."""
    result = _run("count_up", rounds=3)
    assert len(result.rounds) == 3
    assert result.settling is Settling.DIVERGENT


def test_a_cycle_shorter_than_the_bound_stops_early():
    result = _run("flip", rounds=6)
    assert len(result.rounds) < 6


# ----------------------------------------------------------- what it says

def test_a_cycle_says_what_came_back_and_when():
    result = _run("flip")
    rendered = result.render()
    assert "cycle" in rendered
    assert "came back at round" in rendered


def test_nothing_claims_a_target_is_correct():
    """A fixpoint is one property holding, not a verdict on the tool."""
    for behaviour in ("settle", "abstain", "flip", "count_up"):
        rendered = _run(behaviour, measured=99).render().lower()
        assert "correct" not in rendered
        assert "safe" not in rendered


def test_the_result_round_trips_through_json():
    import json
    result = _run("flip")
    payload = json.loads(json.dumps(result.to_dict()))
    assert payload["settling"] == "cycle"
    assert payload["period"] == 2
    assert all("ran" in r for r in payload["rounds"])


# --------------------------------------------- the window a repeat spans

def test_a_repeat_spanning_a_round_that_never_ran_is_not_called_a_cycle():
    """`_settles` directly.

    A state can come back across a window containing a round the target
    refused. The repeat is real; the CYCLE is not, because a cycle is a
    claim about what the target does and it did not do one of them.
    """
    from swizzle.lab.convergence import Round, _settles
    rounds = [Round(1, "a", (), (), True, ran=True),
              Round(2, "b", (), (), True, ran=False),
              Round(3, "a", (), (), True, ran=True)]
    assert _settles(rounds, 0, 3) is False
    assert _settles([r for r in rounds if r.ran], 0, 2) is True
    assert _settles(rounds, 3, 3) is False       # an empty window proves nothing
