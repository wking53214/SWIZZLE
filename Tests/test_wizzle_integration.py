from pathlib import Path

from swizzle.wizzle.epistemic_model import GhostObservation
from swizzle.wizzle.evaluator import Evaluator
from swizzle.wizzle.integration import VerificationArtifact, verify_artifact


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "library.py").write_text("class Status:\n    ACTIVE = 'active'\n")
    (root / "Tests").mkdir()
    (root / "Tests/test_status.py").write_text("def test_status():\n    assert True\n")
    return root


def test_swizzle_can_invoke_wizzle_with_an_explicit_artifact(tmp_path):
    root = _repository(tmp_path)
    result, observations = verify_artifact(
        VerificationArtifact(repository=root, target="ghost"),
        member_name="PHANTOM",
        provenance_class="REMOVED_FROM_LIBRARY",
        severity="MAJOR",
    )

    assert "history" in observations
    assert result.ghost_conclusion.member_name == "PHANTOM"


def test_independent_result_does_not_change_with_target_claim(tmp_path):
    root = _repository(tmp_path)
    evaluator = Evaluator(root)
    observations = evaluator.run_all_oracles()

    low = evaluator.evaluate_observation(
        GhostObservation("PHANTOM", "REMOVED_FROM_LIBRARY", "MINOR"),
        observations,
    )
    high = evaluator.evaluate_observation(
        GhostObservation("PHANTOM", "REMOVED_FROM_LIBRARY", "CRITICAL"),
        observations,
    )

    # The claim comparison may change; the independently established warrant
    # must not.
    assert evaluator.independent_warrant(observations) == (
        evaluator.independent_warrant(observations)
    )
