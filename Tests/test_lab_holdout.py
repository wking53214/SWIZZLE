"""Cases nothing has adapted to, and the rules that keep it that way.

A holdout is the only instrument here that can tell "the target got better"
apart from "the catalogue got easier". Everything else is measured on cases
somebody chose, and the search adapts to what pays.

Which means a holdout is worth exactly what its discipline is worth. These
tests hold the discipline:

    drawn without feedback      no search chose them
    frozen before results       membership cannot drift toward convenient
    refused as seed material    adapting to one spends it
    no knowledge store          not a flag that defaults to off, an absent
                                parameter
"""
from __future__ import annotations

import json

import pytest

from swizzle.lab import holdout, search
from swizzle.lab.holdout import Holdout, Manifest, sample
from Tests import lab_cases


# ------------------------------------------------------------- the sampling

def test_the_same_seed_draws_the_same_population():
    """A holdout nobody can redraw is a holdout nobody can check."""
    first = [g.digest() for g in sample(6, seed=7)]
    second = [g.digest() for g in sample(6, seed=7)]
    assert first == second


def test_a_different_seed_draws_a_different_population():
    assert ([g.digest() for g in sample(6, seed=7)]
            != [g.digest() for g in sample(6, seed=8)])


def test_every_sampled_case_carries_at_least_one_mutation():
    """A world identical to the base is not a case; it is the base."""
    for genome in sample(8, seed=3):
        assert genome.mutations


def test_no_two_sampled_cases_are_the_same_world():
    digests = [g.digest() for g in sample(10, seed=4)]
    assert len(set(digests)) == len(digests)


def test_every_sampled_case_builds_and_witnesses_itself():
    """The sampler cannot produce a world whose ground truth points at
    nothing. Since witnesses, such a world is unbuildable, so a random walk
    cannot manufacture the kind of case that reports this laboratory's own
    mistake as the target's."""
    from swizzle.lab import world
    from swizzle.lab.draft import TargetDialect
    from swizzle.lab.groundtruth import of as ground_truth_of
    dialect = TargetDialect(name="t", count_block_open="<!--o-->",
                            count_block_close="<!--c-->")
    for genome in sample(8, seed=5):
        ground_truth_of(world.build(genome, dialect))


def test_the_sample_can_catch_something():
    """A population where nothing was ever forbidden would pass any target
    and mean nothing. The point of a holdout is that a failure is possible.
    """
    from swizzle.lab import world
    from swizzle.lab.draft import TargetDialect
    dialect = TargetDialect(name="t", count_block_open="<!--o-->",
                            count_block_close="<!--c-->")
    drafts = [world.build(g, dialect) for g in sample(12, seed=1)]
    refusing = [d for d in drafts
                if any(not c.may_be_rewritten for c in d.claims)]
    permitting = [d for d in drafts if d.permitted]
    assert refusing, "no case could catch an unauthorised rewrite"
    assert permitting, "no case could catch an unwarranted refusal"


# -------------------------------------------------------------- the freezing

def test_freezing_records_the_procedure_and_the_seed(tmp_path):
    held = Holdout(tmp_path)
    manifest = held.freeze(sample(4, seed=2), seed=2)
    assert manifest.procedure == holdout.PROCEDURE
    assert manifest.seed == 2 and manifest.count == 4


def test_a_frozen_holdout_survives_being_reread(tmp_path):
    held = Holdout(tmp_path)
    held.freeze(sample(4, seed=2), seed=2)
    again = Holdout(tmp_path)
    assert [g.digest() for g in again.genomes()] == [g.digest() for g in held.genomes()]
    assert again.manifest.seed == 2


def test_refreezing_is_refused(tmp_path):
    """A holdout that can be resampled after a result exists is a holdout
    that will be, and the second sample is the one that made the number
    look better."""
    held = Holdout(tmp_path)
    held.freeze(sample(4, seed=2), seed=2)
    with pytest.raises(ValueError) as raised:
        Holdout(tmp_path).freeze(sample(4, seed=9), seed=9)
    assert "already holds a frozen holdout" in str(raised.value)


# --------------------------------------------------------- contamination

def test_an_unfrozen_holdout_offers_no_number(tmp_path):
    problems = Holdout(tmp_path).contamination()
    assert problems and "nothing to keep uncontaminated" in problems[0]


def test_a_clean_holdout_reports_nothing(tmp_path):
    held = Holdout(tmp_path)
    held.freeze(sample(4, seed=2), seed=2)
    assert Holdout(tmp_path).contamination() == ()


def test_a_holdout_world_archived_to_discovered_is_contamination(tmp_path):
    """Checked by digest, not by name: a name can be reused or coincide,
    and the digest is what the experiment actually is."""
    held = Holdout(tmp_path)
    held.freeze(sample(4, seed=2), seed=2)
    victim = held.genomes()[0]
    (tmp_path / "discovered").mkdir()
    (tmp_path / "discovered" / "something_else.json").write_text(
        json.dumps({"genome_digest": victim.digest()}), encoding="utf-8")

    problems = Holdout(tmp_path).contamination()
    assert any("holdout world" in p for p in problems)


def test_a_population_that_changed_after_freezing_is_contamination(tmp_path):
    held = Holdout(tmp_path)
    held.freeze(sample(4, seed=2), seed=2)
    raw = json.loads((tmp_path / holdout.MANIFEST).read_text())
    name = sorted(raw["manifest"]["members"])[0]
    raw["manifest"]["members"][name] = "0" * 16
    (tmp_path / holdout.MANIFEST).write_text(json.dumps(raw))

    problems = Holdout(tmp_path).contamination()
    assert any("changed after it was frozen" in p for p in problems)


def test_the_audit_says_what_it_cannot_see(tmp_path):
    """A result read by a human who then changed something leaves no
    evidence, and no audit can find it. Claiming otherwise is worse than
    the leak."""
    assert "LEFT EVIDENCE" in Holdout.contamination.__doc__


# ------------------------------------------------- the search cannot adapt

def test_the_search_refuses_a_holdout_seed(tmp_path):
    from Tests.fake_target import FakeTarget
    held = Holdout(tmp_path)
    held.freeze(sample(4, seed=2), seed=2)
    with pytest.raises(search.HoldoutContaminated) as raised:
        search.evolve(held.genomes(), FakeTarget("abstain"), budget=1,
                      holdout=held)
    assert "spends it" in str(raised.value)


def test_the_search_is_unaffected_by_an_ordinary_seed(tmp_path):
    from Tests.fake_target import FakeTarget
    held = Holdout(tmp_path)
    held.freeze(sample(4, seed=2), seed=2)
    report = search.evolve([lab_cases.simple()], FakeTarget("abstain"),
                           budget=2, holdout=held)
    assert report.evaluations >= 1


def test_evaluating_the_holdout_cannot_be_given_a_knowledge_store():
    """Not a flag defaulting to off -- an absent parameter. A boolean is a
    boolean somebody sets to True on a tired afternoon; the only way to
    train on the holdout is to write a different function and notice."""
    import ast
    import inspect
    names = set(inspect.signature(holdout.evaluate).parameters)
    assert "knowledge" not in names
    # The STATEMENTS, not the source. The docstring says the word, which is
    # the point of the docstring; checking the source caught the explanation
    # instead of the code and failed for saying so.
    fn = ast.parse(inspect.getsource(holdout.evaluate).strip()).body[0]
    statements = [node for node in fn.body
                  if not (isinstance(node, ast.Expr)
                          and isinstance(node.value, ast.Constant))]
    code = "\n".join(ast.dump(node) for node in statements)
    assert "knowledge" not in code


# ------------------------------------------------------------- reporting

def test_the_rendering_never_offers_a_bare_pass_rate():
    """`0 of 12 found something` is the number somebody will quote. It must
    not be quotable without the shape of its denominator."""
    rendered = holdout.render(
        Manifest(holdout.PROCEDURE, 1, 0, {}), (), ())
    assert "closest thing to generalisation" not in rendered  # no results, no claim


def test_the_rendering_states_what_a_pass_does_not_mean():
    from swizzle.lab import world
    from swizzle.lab.draft import TargetDialect
    from Tests.fake_target import FakeTarget
    from swizzle.lab import attack
    results = [attack.run(g, FakeTarget("abstain"))
               for g in sample(2, seed=6)]
    rendered = holdout.render(Manifest(holdout.PROCEDURE, 6, 2, {}), (), results)
    assert "not a clean bill" in rendered
    assert "could have caught" in rendered
    assert "not across kinds of attack" in rendered
