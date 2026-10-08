"""A resolution is a claim, and claims have to earn what they assert.

    "I didn't say she stole my money."

Seven words, seven meanings, one sentence. The same thing happens to "it no
longer reproduces", and these tests pin the decomposition down: what the
standing is allowed to be, what it is never allowed to be, and which of the
seven readings each probe interrogates.

The failure being guarded against is epistemic promotion -- an observation
acquiring more authority, certainty and historical status than it earned --
and the shape it takes here is a single word, `fixed`, which no code path
in this framework is permitted to produce.
"""

from __future__ import annotations

import json

import pytest

from swizzle.lab.standing import (ADJACENCY, EMPHASES, Observation, ProbeResult,
                                  Resolution, Standing, unprobed)


def _seen(reproduced, **over):
    base = dict(case="c", genome_digest="d", target_revision="abc1234567",
                observed_at="2026-09-12T00:00:00Z", reproduced=reproduced,
                oracles_ran=("structural", "expectation"), top_severity="NONE")
    base.update(over)
    return Observation(**base)


def _held(name):
    return ProbeResult(probe=name, defeated=False, held=True, account="looked")


def _defeated(name):
    return ProbeResult(probe=name, defeated=True, held=False, account="found it")


ALL_PROBES = tuple(probe for _, _, probe in EMPHASES) + (ADJACENCY[2],)


# ------------------------------------------------------------- the ladder

def test_a_clean_run_alone_is_not_a_resolution():
    """The default after a fix, and the one most likely to be misread."""
    r = Resolution(observation=_seen(False),
                   previously_reproduced=_seen(True, top_severity="CRITICAL"))
    assert r.standing is Standing.UNREPRODUCED_UNPROBED


def test_asking_every_question_gets_the_strongest_standing_available():
    r = Resolution(observation=_seen(False),
                   probes=tuple(_held(p) for p in ALL_PROBES),
                   previously_reproduced=_seen(True, top_severity="CRITICAL"))
    assert r.standing is Standing.STRUCTURE_SUPPORTS_RESOLVED


def test_one_probe_defeats_the_whole_reading():
    r = Resolution(observation=_seen(False),
                   probes=tuple(_held(p) for p in ALL_PROBES[:-1]) + (
                       _defeated(ALL_PROBES[-1]),),
                   previously_reproduced=_seen(True, top_severity="CRITICAL"))
    assert r.standing is Standing.UNREPRODUCED_BUT_DEFEATED
    assert r.defeated_by == (ALL_PROBES[-1],)


def test_an_inconclusive_oracle_is_not_agreement():
    """Reading an oracle's refusal to say as assent is the promotion this
    module exists to stop."""
    r = Resolution(observation=_seen(False, oracles_inconclusive=("temporal",)),
                   probes=tuple(_held(p) for p in ALL_PROBES),
                   previously_reproduced=_seen(True))
    assert r.standing is Standing.AMBIGUOUS


def test_a_case_that_never_worked_is_not_resolved():
    """Without a record of it reproducing, "fixed" and "never worked" are
    the same observation, and calling the second one resolved is the same
    promotion pointed the other way."""
    r = Resolution(observation=_seen(False),
                   probes=tuple(_held(p) for p in ALL_PROBES))
    assert r.standing is Standing.NEVER_REPRODUCED


def test_reproducing_again_is_a_recurrence_not_a_fresh_finding():
    r = Resolution(observation=_seen(True, top_severity="HIGH"),
                   previously_reproduced=_seen(True, top_severity="CRITICAL"))
    assert r.standing is Standing.RECURRED


def test_a_broken_run_establishes_nothing():
    r = Resolution(observation=_seen(False, broken="the target could not be run"),
                   previously_reproduced=_seen(True))
    assert r.standing is Standing.AMBIGUOUS


# --------------------------------------------------------- the refusal

def test_no_standing_settles_anything():
    for standing in Standing:
        assert standing.settles_anything is False


@pytest.mark.parametrize("standing", list(Standing), ids=lambda s: s.name)
def test_the_word_fixed_is_never_produced(standing):
    """The whole point, as an assertion. `fixed` is a claim to completion and
    nothing here is entitled to make one."""
    assert "fixed" not in standing.value.lower()


def test_the_report_never_claims_fixed_only_refuses_it():
    """The word may appear. It may not appear as an assertion.

    The report's last line is "it is still not `fixed`", which contains the
    word in the act of refusing it -- so the check is not that the string is
    absent but that every occurrence is negated. A blunter assertion would
    have forbidden the sentence that does the work.
    """
    import re
    r = Resolution(observation=_seen(False),
                   probes=tuple(_held(p) for p in ALL_PROBES),
                   previously_reproduced=_seen(True, top_severity="CRITICAL"))
    rendered = r.render()
    assert "current structure supports the" in rendered.lower()
    occurrences = list(re.finditer(r"fixed", rendered, re.I))
    assert occurrences, "the refusal itself should be in the report"
    for hit in occurrences:
        preceding = rendered[max(0, hit.start() - 12):hit.start()].lower()
        assert "not " in preceding, (
            "%r reads as a claim rather than a refusal"
            % rendered[max(0, hit.start() - 40):hit.end() + 10])


def test_an_unprobed_resolution_says_so_in_its_own_report():
    r = Resolution(observation=_seen(False), previously_reproduced=_seen(True))
    rendered = r.render()
    assert "Never asked" in rendered
    assert "observation wearing the clothes of a conclusion" in rendered


def test_a_defeated_resolution_names_what_overturned_it():
    """The first renderer took a shortcut here and hid a defeat behind a
    one-line summary, on a CRITICAL."""
    r = Resolution(observation=_seen(False),
                   probes=(_defeated("variant"),),
                   previously_reproduced=_seen(True, top_severity="CRITICAL"))
    rendered = r.render()
    assert "REFUSED" in rendered
    assert "variant" in rendered
    assert "found it" in rendered


# ------------------------------------------------------- the seven readings

def test_every_emphasis_names_an_unestablished_thing_and_a_probe():
    for word, unestablished, probe in EMPHASES + (ADJACENCY,):
        assert word and len(unestablished) > 30, word
        assert probe in ALL_PROBES


def test_the_emphases_cover_the_whole_sentence():
    """Seven readings of seven words, plus the one about a word that is not
    in the sentence at all: the surface it is one case on."""
    assert len(EMPHASES) == 7
    assert ADJACENCY[2] == "adjacency"


def test_unprobed_lists_exactly_what_was_not_asked():
    r = Resolution(observation=_seen(False),
                   probes=(_held("variant"), _held("scope")),
                   previously_reproduced=_seen(True))
    assert set(r.unprobed) == set(ALL_PROBES) - {"variant", "scope"}


def test_a_probe_that_did_not_run_is_not_a_probe_that_found_nothing():
    """Three states, not two. Collapsing them is how a corpus fills up with
    conclusions nobody reached."""
    never = unprobed("variant", "not run")
    assert not never.ran and not never.held and not never.defeated
    assert _held("variant").ran and _held("variant").held


# ------------------------------------------------------------ round trip

def test_a_resolution_round_trips():
    r = Resolution(observation=_seen(False),
                   probes=tuple(_held(p) for p in ALL_PROBES),
                   previously_reproduced=_seen(True, top_severity="CRITICAL"))
    back = Resolution.from_dict(json.loads(json.dumps(r.to_dict())))
    assert back.standing is r.standing
    assert back.unprobed == r.unprobed
    assert back.observation == r.observation


def test_the_serialised_form_carries_the_decomposition():
    """An archived resolution has to be readable by somebody who does not
    have this code, or it is just a status string again."""
    r = Resolution(observation=_seen(False), previously_reproduced=_seen(True))
    payload = r.to_dict()
    assert len(payload["unestablished"]) == 8
    assert all(set(row) == {"emphasis", "unestablished", "probe", "status"}
               for row in payload["unestablished"])
    assert payload["interpretation"].startswith("the current structure supports")


# ----------------------------------------------- a probe that cannot ask

def test_a_probe_that_raised_is_not_a_probe_that_held():
    """The single worst thing this module could do is turn a crash into
    evidence of a fix.

    A variant probe composing two mutators that contradict each other -- one
    removes the document the other targets -- took the first full sweep down
    mid-run. Whatever it does instead, it must not come back saying it
    looked.
    """
    from swizzle.lab import probes
    from swizzle.lab.adapter import TargetAdapter

    class Exploding(TargetAdapter):
        name = "exploding"

        def dialect(self):
            from Tests.fake_target import FakeTarget
            return FakeTarget().dialect()

        def version(self):
            return {"commit": "x"}

        def scan(self, root, sandbox, timeout=900.0):
            raise RuntimeError("deliberate")

        def act(self, root, sandbox, timeout=900.0):
            raise RuntimeError("deliberate")

        def export_output(self, root, sandbox, observation, into):
            return None

    from Tests import lab_cases
    context = probes.ProbeContext(genome=lab_cases.simple(), adapter=Exploding(),
                                  resolved_classes=("unauthorised_mutation",),
                                  resolved_severity="CRITICAL", budget=1)
    seen = Observation(case="c", genome_digest="d", target_revision="x",
                       observed_at="now", reproduced=False)
    _, results = probes.interrogate(context, now=seen)
    # One result per probe, in order. Nothing is silently added or dropped.
    assert [r.probe for r in results] == ["concealment", "recurrence", "scope",
                                          "adjacency", "variant"]
    by_name = {r.probe: r for r in results}
    # The three that invoke the target. `recurrence` is excluded on purpose:
    # it interrogates the observation it was handed rather than running
    # anything, so with a clean observation it holds, correctly.
    # `concealment` compares two records and reports unprobed when there is
    # no prior one.
    for name in ("scope", "adjacency", "variant"):
        assert not by_name[name].held, "%s claimed to have looked" % name
    resolution = Resolution(observation=seen, probes=results,
                            previously_reproduced=_seen(True))
    assert resolution.standing is Standing.UNREPRODUCED_UNPROBED
    # Exactly these: the three that crashed, and `concealment`, which has no prior
    # record to compare against. `recurrence` ran and held, so it is not here.
    assert set(resolution.unprobed) == {"scope", "adjacency", "variant", "concealment"}


def test_a_variant_reproducing_something_lesser_is_not_a_defeat():
    """The probe's own first run committed the promotion it exists to refuse:
    a variant producing a LOW over-caution was reported as evidence that a
    CRITICAL fix had closed the case and not the class. A different and
    lesser failure is a case to file, not a defeat of this one."""
    from swizzle.lab import probes
    assert probes._severity_rank("LOW") < probes._severity_rank("CRITICAL")


def test_adjacency_and_variant_apply_the_same_rule():
    """A probe that defeats on a lesser failure cries wolf, and two probes
    that disagree about what counts as a defeat make the standing arbitrary.

    The rule was applied to `variant` when it first overclaimed and not to
    `adjacency`, which then reported a CRITICAL escape resolution as defeated
    because a sibling produced LOW over-caution. Found by the framework, in
    itself, twice in one session.
    """
    import inspect
    from swizzle.lab import probes
    for probe in (probes.variant, probes.adjacency):
        source = inspect.getsource(probe)
        assert "resolved_classes" in source, (
            "%s does not consult the failure the resolution is about"
            % probe.__name__)
        assert "found & resolved" in source or "found & resolved" in source, (
            "%s does not compare what it found against what was resolved"
            % probe.__name__)


def test_a_different_failure_is_not_a_recurrence():
    """"Recurred" tells a reader the old defect is back. A case that now
    produces a different and lesser failure has become a different finding,
    and saying otherwise is the same unearned claim in the other direction.
    """
    r = Resolution(
        observation=_seen(True, classes=("over_caution",), top_severity="LOW"),
        previously_reproduced=_seen(True, classes=("unauthorised_mutation",),
                                    top_severity="HIGH"))
    assert r.standing is Standing.REPRODUCES

    same = Resolution(
        observation=_seen(True, classes=("unauthorised_mutation",),
                          top_severity="HIGH"),
        previously_reproduced=_seen(True, classes=("unauthorised_mutation",),
                                    top_severity="CRITICAL"))
    assert same.standing is Standing.RECURRED


def test_a_case_that_was_never_minimised_can_still_reach_the_ceiling():
    """"Never reduced" is not "unanswerable".

    The first `scope` probe returned "not asked" for any case without a
    pre-minimisation world, so most of the corpus could never reach the
    strongest standing and the distinction stopped meaning anything. The
    emphasis is `THIS world`, and for an un-reduced case the question is
    "does it hold when the world is bigger" -- which is answerable by
    growing one.
    """
    from swizzle.lab import probes
    from Tests import lab_cases
    small = lab_cases.simple()
    grown = probes._grown(small)
    assert grown.digest() != small.digest()
    assert grown.filesystem.filler_modules > 0
    assert len(grown.documents) > len(small.documents)
    assert grown.tests.count >= small.tests.count
    # The case itself is untouched: only scenery was added.
    assert grown.mutations == small.mutations
    assert grown.claims == small.claims
    assert grown.count_blocks == small.count_blocks
