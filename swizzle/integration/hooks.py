"""Git hooks that trigger integration events on code changes.

Post-commit hooks watch for changes to key integration files and emit events
when they're updated. This enables real-time feedback between tools.

Hooks:
- post-commit: Watch for changes in integration models and emit events
- Integration files trigger triage, violation, or performance events
"""

from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
import subprocess
import json


class HookManager:
    """Manages git hooks that trigger integration events."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.hooks_dir = repo_path / ".git" / "hooks"
        self.integration_dir = repo_path / "swizzle" / "integration"

    def install_hooks(self) -> None:
        """Install integration hooks in repo."""
        self.hooks_dir.mkdir(parents=True, exist_ok=True)

        # Install post-commit hook
        hook_file = self.hooks_dir / "post-commit"
        hook_file.write_text(self._get_post_commit_script())
        hook_file.chmod(0o755)

    def _get_post_commit_script(self) -> str:
        """Get the post-commit hook script."""
        return '''#!/bin/bash
# Auto-generated integration post-commit hook
# Triggers events when integration models are updated

REPO_ROOT=$(git rev-parse --show-toplevel)
INTEGRATION_DIR="$REPO_ROOT/swizzle/integration"

# Check which files changed in this commit
git diff-tree --no-commit-id --name-only -r HEAD | grep -E "integration/.*\\.py|.*casefile" | while read file; do
    echo "Integration file changed: $file"

    # Trigger event based on file type
    case "$file" in
        *triage_ledger* | *casefile*)
            echo "Triage event triggered"
            python3 -c "from swizzle.integration.hooks import trigger_triage_event; trigger_triage_event()" ;;
        *architecture_audit*)
            echo "Architecture event triggered"
            python3 -c "from swizzle.integration.hooks import trigger_violation_event; trigger_violation_event()" ;;
        *performance_contract*)
            echo "Performance event triggered"
            python3 -c "from swizzle.integration.hooks import trigger_regression_event; trigger_regression_event()" ;;
        *feedback_loop*)
            echo "Feedback event triggered"
            python3 -c "from swizzle.integration.hooks import trigger_false_positive_event; trigger_false_positive_event()" ;;
        *mutation_transfer*)
            echo "Mutation event triggered"
            python3 -c "from swizzle.integration.hooks import trigger_mutation_event; trigger_mutation_event()" ;;
    esac
done

exit 0
'''

    def uninstall_hooks(self) -> None:
        """Remove integration hooks."""
        hook_file = self.hooks_dir / "post-commit"
        if hook_file.exists():
            hook_file.unlink()


def trigger_triage_event() -> None:
    """Trigger event when triage ledger is updated."""
    from swizzle.integration.event_system import (
        get_event_bus, create_triage_event
    )
    from swizzle.integration.triage_ledger import DEFAULT_LEDGER

    if DEFAULT_LEDGER.entries:
        latest = DEFAULT_LEDGER.entries[-1]
        event = create_triage_event(
            finding_id=latest.id,
            finding_type=latest.finding_type,
            decision=latest.decision.value,
            reasoning=latest.reasoning,
            severity=latest.severity_initial.value,
        )
        bus = get_event_bus()
        bus.publish(event)
        print(f"Published triage event: {event.id}")


def trigger_violation_event() -> None:
    """Trigger event when architecture violations are detected."""
    from swizzle.integration.event_system import (
        get_event_bus, create_violation_event
    )
    from swizzle.integration.architecture_audit import SWIZZLE_AUDIT

    unresolved = SWIZZLE_AUDIT.unresolved_violations()
    if unresolved:
        latest = unresolved[-1]
        event = create_violation_event(
            violation_id=latest.id,
            violation_type=latest.violation_type.value if hasattr(latest.violation_type, 'value') else str(latest.violation_type),
            boundary_id=latest.boundary_id,
            location=latest.location,
            severity=latest.severity,
        )
        bus = get_event_bus()
        bus.publish(event)
        print(f"Published violation event: {event.id}")


def trigger_regression_event() -> None:
    """Trigger event when performance regression is detected."""
    from swizzle.integration.event_system import (
        get_event_bus, create_regression_event
    )
    from swizzle.integration.performance_contract import DEFAULT_PERFORMANCE_REPORT

    regressions = DEFAULT_PERFORMANCE_REPORT.detect_regressions(threshold_percent=10)
    if regressions:
        for case_id, regression_messages in regressions.items():
            # Trigger event for first regression message
            if regression_messages:
                msg = regression_messages[0]
                event = create_regression_event(
                    contract_id="performance_regression",
                    case_id=case_id,
                    metric_name="wall_time",
                    baseline_value=0.0,  # Would extract from message
                    current_value=0.0,  # Would extract from message
                    regression_percent=10.0,  # Would extract from message
                )
                bus = get_event_bus()
                bus.publish(event)
                print(f"Published regression event: {event.id}")


def trigger_false_positive_event() -> None:
    """Trigger event when false positive patterns are confirmed."""
    from swizzle.integration.event_system import (
        get_event_bus, create_false_positive_event
    )
    from swizzle.integration.feedback_loop import DEFAULT_FEEDBACK_REPORT

    if DEFAULT_FEEDBACK_REPORT.false_positive_patterns:
        latest = list(DEFAULT_FEEDBACK_REPORT.false_positive_patterns.values())[-1]
        event = create_false_positive_event(
            false_positive_id=latest.id,
            finding_type=latest.finding_type.value,
            confidence=latest.confidence,
            indicators=latest.indicators,
        )
        bus = get_event_bus()
        bus.publish(event)
        print(f"Published false positive event: {event.id}")


def trigger_mutation_event() -> None:
    """Trigger event when mutation cases are discovered."""
    from swizzle.integration.event_system import (
        get_event_bus, create_mutation_event
    )
    from swizzle.integration.mutation_transfer import DEFAULT_MUTATION_CATALOG

    if DEFAULT_MUTATION_CATALOG.cases:
        latest_id = list(DEFAULT_MUTATION_CATALOG.cases.keys())[-1]
        latest = DEFAULT_MUTATION_CATALOG.cases[latest_id]
        event = create_mutation_event(
            case_id=latest.id,
            hypothesis=latest.hypothesis,
            severity=latest.severity,
            minimized=latest.minimized,
        )
        bus = get_event_bus()
        bus.publish(event)
        print(f"Published mutation event: {event.id}")
