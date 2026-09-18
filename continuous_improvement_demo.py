#!/usr/bin/env python
"""Demonstrate continuous improvement loop between Swizzle and Ghost Tools.

Shows how the two repositories iteratively improve each other through
a feedback loop with arbitration validation.
"""

from pathlib import Path
from datetime import datetime
import time

from swizzle.integration.test_track import TestTrack, Metric
from swizzle.integration.arbiter import Arbiter, ValidationMetric
from swizzle.integration.loop_orchestrator import LoopOrchestrator


def simulate_repo_improvement(repo_name: str, iteration: int) -> tuple:
    """Simulate an improvement proposed by a repository."""
    # Each iteration suggests improvements with diminishing returns
    base_improvement = 0.10 - (iteration * 0.01)
    noise = 0.001 * (iteration % 3)

    return {
        "id": f"{repo_name}_imp_{iteration:03d}",
        "accuracy": base_improvement + noise,
        "performance": base_improvement * 0.8 + noise * 0.5,
    }


def run_continuous_loop_demo():
    """Run continuous improvement loop demonstration."""
    print("=" * 80)
    print("CONTINUOUS IMPROVEMENT LOOP DEMONSTRATION")
    print("Swizzle ⇄ Ghost Tools Iterative Improvement")
    print("=" * 80)
    print()

    workspace = Path("/tmp/continuous_loop")
    workspace.mkdir(exist_ok=True)

    # Initialize systems
    orchestrator = LoopOrchestrator(workspace)
    swizzle_arbiter = Arbiter("swizzle")
    ghost_tools_arbiter = Arbiter("ghost_tools")

    # Set thresholds
    swizzle_arbiter.set_acceptance_threshold(0.0)
    ghost_tools_arbiter.set_acceptance_threshold(0.0)

    # Add critical metrics
    swizzle_arbiter.add_critical_metric("test_pass_rate")
    ghost_tools_arbiter.add_critical_metric("test_pass_rate")

    # Start loop
    orchestrator.start_loop()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting continuous improvement loop")
    print(f"Configuration:")
    print(f"  • Max iterations: {orchestrator.loop_state.max_iterations}")
    print(f"  • Convergence threshold: {orchestrator.loop_state.convergence_threshold*100:.2f}%")
    print()

    iteration_num = 0
    alternating_sender = True

    while orchestrator.loop_state.should_continue() and iteration_num < 15:
        iteration_num += 1

        # Alternate between senders
        if alternating_sender:
            sender = "swizzle"
            receiver = "ghost_tools"
            arbiter = ghost_tools_arbiter
        else:
            sender = "ghost_tools"
            receiver = "swizzle"
            arbiter = swizzle_arbiter

        # Simulate improvement proposal
        improvement = simulate_repo_improvement(sender, iteration_num)
        baseline_accuracy = 0.90
        baseline_perf = 100.0

        print(f"[Iteration {iteration_num}] {sender.upper()} → {receiver.upper()}")
        print(f"  Improvement: {improvement['id']}")

        # Create validation metrics
        metrics = [
            ValidationMetric(
                name="accuracy",
                before_value=baseline_accuracy,
                after_value=baseline_accuracy * (1 + improvement["accuracy"]),
                unit="percent",
                importance=2.0,
            ),
            ValidationMetric(
                name="performance",
                before_value=baseline_perf,
                after_value=baseline_perf * (1 + improvement["performance"]),
                unit="ops/sec",
                importance=1.0,
            ),
            ValidationMetric(
                name="test_pass_rate",
                before_value=0.99,
                after_value=0.995,
                unit="percent",
                importance=3.0,
            ),
        ]

        # Validate improvement
        verdict = arbiter.validate_improvement(sender, improvement["id"], metrics)
        accepted = verdict.verdict.value == "accept"

        print(f"  Verdict: {verdict.verdict.value.upper()}")
        print(f"  Reason: {verdict.reason}")
        print(f"  Confidence: {verdict.confidence*100:.1f}%")
        print(f"  Score: {verdict.weighted_score()*100:+.2f}%")
        print()

        # Record iteration
        net_improvement = verdict.weighted_score()
        orchestrator.record_iteration(
            sender,
            receiver,
            improvement["id"],
            accepted,
            net_improvement,
        )

        # Alternate sender for next iteration
        alternating_sender = not alternating_sender
        time.sleep(0.1)  # Small delay for readability

    # Final report
    print("=" * 80)
    print("LOOP EXECUTION COMPLETED")
    print("=" * 80)
    print()

    print(orchestrator.get_loop_report())
    print()

    # Summary statistics
    status = orchestrator.get_loop_status()
    print(f"Final Statistics:")
    print(f"  • Total iterations: {status['total_iterations']}")
    print(f"  • Acceptance rate: {status['acceptance_rate']*100:.1f}%")
    print(f"  • Total improvement: {status['total_improvement']*100:+.2f}%")
    print(f"  • Converged: {'YES ✓' if status['converged'] else 'NO'}")
    print()

    # Arbiter reports
    print(f"Swizzle Arbiter:")
    swizzle_report = swizzle_arbiter.get_validation_report()
    print(f"  • Validations: {swizzle_report['total_validations']}")
    print(f"  • Acceptance rate: {swizzle_report['acceptance_rate']*100:.1f}%")
    print()

    print(f"Ghost Tools Arbiter:")
    ghost_report = ghost_tools_arbiter.get_validation_report()
    print(f"  • Validations: {ghost_report['total_validations']}")
    print(f"  • Acceptance rate: {ghost_report['acceptance_rate']*100:.1f}%")
    print()

    print("=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    run_continuous_loop_demo()
