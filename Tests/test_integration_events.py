"""Tests for real-time event system integration.

Validates event creation, streaming, handlers, and hooks.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime

from swizzle.integration.event_system import (
    Event, EventType, EventSeverity, EventBus, get_event_bus, reset_event_bus,
    create_triage_event, create_violation_event, create_regression_event,
    create_false_positive_event, create_mutation_event, create_oracle_event,
)
from swizzle.integration.event_handlers import (
    EventHandlerRegistry, get_handler_registry, reset_handlers, setup_event_handlers
)
from swizzle.integration.hooks import HookManager


class TestEventCreation:
    """Test event factory functions."""

    def test_create_triage_event(self):
        """Verify triage events are created correctly."""
        event = create_triage_event(
            finding_id="f1",
            finding_type="dated_claim",
            decision="false",
            reasoning="Has date marker",
            severity="MEDIUM",
        )

        assert event.type == EventType.FINDING_TRIAGED
        assert event.source_tool == "ghost_tools"
        assert event.target_tool == "swizzle"
        assert event.data["decision"] == "false"

    def test_create_violation_event(self):
        """Verify violation events are created correctly."""
        event = create_violation_event(
            violation_id="v1",
            violation_type="boundary_violation",
            boundary_id="lab_independence",
            location="swizzle/lab/test.py:42",
            severity="CRITICAL",
        )

        assert event.type == EventType.VIOLATION_DETECTED
        assert event.source_tool == "swizzle"
        assert event.target_tool == "ghost_tools"
        assert event.severity == EventSeverity.ERROR

    def test_create_regression_event(self):
        """Verify regression events are created correctly."""
        event = create_regression_event(
            contract_id="ghost_scan_per_file",
            case_id="case_1",
            metric_name="wall_time",
            baseline_value=50.0,
            current_value=60.0,
            regression_percent=20.0,
        )

        assert event.type == EventType.PERFORMANCE_REGRESSED
        assert event.data["regression_percent"] == 20.0
        assert event.severity == EventSeverity.ERROR  # 20% is significant, should be ERROR

    def test_create_false_positive_event(self):
        """Verify false positive events are created correctly."""
        event = create_false_positive_event(
            false_positive_id="fp1",
            finding_type="dated_claim",
            confidence=0.95,
            indicators=["generated on", "auto-generated"],
        )

        assert event.type == EventType.FALSE_POSITIVE_CONFIRMED
        assert event.data["confidence"] == 0.95
        assert len(event.data["indicators"]) == 2

    def test_create_mutation_event(self):
        """Verify mutation events are created correctly."""
        event = create_mutation_event(
            case_id="symlink_escape",
            hypothesis="tool fails on symlinks escaping repo",
            severity="CRITICAL",
            minimized=True,
        )

        assert event.type == EventType.MUTATION_CASE_DISCOVERED
        assert event.data["minimized"] is True

    def test_create_oracle_event(self):
        """Verify oracle events are created correctly."""
        event = create_oracle_event(
            finding_type="dated_claim",
            accuracy=0.92,
            training_size=150,
            improvement_percent=5.0,
        )

        assert event.type == EventType.ORACLE_TRAINING_IMPROVED
        assert event.data["accuracy"] == 0.92


class TestEventBus:
    """Test event bus pub-sub functionality."""

    def test_event_bus_singleton(self):
        """Verify event bus is singleton."""
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_event_bus_reset(self):
        """Verify event bus can be reset."""
        bus1 = get_event_bus()
        reset_event_bus()
        bus2 = get_event_bus()
        assert bus1 is not bus2

    def test_subscribe_and_publish(self):
        """Verify subscribe/publish mechanism."""
        reset_event_bus()
        bus = get_event_bus()

        received = []

        def handler(event: Event):
            received.append(event)

        bus.subscribe(EventType.FINDING_TRIAGED, handler)

        event = create_triage_event("f1", "dated_claim", "false", "test", "MEDIUM")
        bus.publish(event)

        assert len(received) == 1
        assert received[0].id == event.id

    def test_multiple_handlers(self):
        """Verify multiple handlers for same event type."""
        reset_event_bus()
        bus = get_event_bus()

        received1 = []
        received2 = []

        def handler1(event: Event):
            received1.append(event)

        def handler2(event: Event):
            received2.append(event)

        bus.subscribe(EventType.FINDING_TRIAGED, handler1)
        bus.subscribe(EventType.FINDING_TRIAGED, handler2)

        event = create_triage_event("f1", "dated_claim", "false", "test", "MEDIUM")
        bus.publish(event)

        assert len(received1) == 1
        assert len(received2) == 1

    def test_unsubscribe(self):
        """Verify unsubscribe removes handler."""
        reset_event_bus()
        bus = get_event_bus()

        received = []

        def handler(event: Event):
            received.append(event)

        bus.subscribe(EventType.FINDING_TRIAGED, handler)
        bus.unsubscribe(EventType.FINDING_TRIAGED, handler)

        event = create_triage_event("f1", "dated_claim", "false", "test", "MEDIUM")
        bus.publish(event)

        assert len(received) == 0

    def test_event_log_persistence(self, tmp_path):
        """Verify event log can be saved and loaded."""
        reset_event_bus()
        bus = get_event_bus()

        # Publish events
        event1 = create_triage_event("f1", "dated_claim", "false", "test", "MEDIUM")
        event2 = create_violation_event("v1", "boundary_violation", "lab", "file:1", "HIGH")
        bus.publish(event1)
        bus.publish(event2)

        # Save log
        log_file = tmp_path / "events.json"
        bus.save_log(log_file)
        assert log_file.exists()

        # Load log
        reset_event_bus()
        bus2 = get_event_bus()
        bus2.load_log(log_file)

        assert len(bus2.event_log) == 2

    def test_get_unprocessed_events(self):
        """Verify getting unprocessed events."""
        reset_event_bus()
        bus = get_event_bus()

        event1 = create_triage_event("f1", "dated_claim", "false", "test", "MEDIUM")
        event2 = create_violation_event("v1", "boundary_violation", "lab", "file:1", "HIGH")
        bus.publish(event1)
        bus.publish(event2)

        # Both should be unprocessed initially
        unprocessed = bus.get_unprocessed()
        assert len(unprocessed) == 2

        # Mark one as processed
        event1.processed = True
        event1.processed_at = datetime.now().isoformat()

        unprocessed = bus.get_unprocessed()
        assert len(unprocessed) == 1
        assert unprocessed[0].id == event2.id


class TestEventHandlers:
    """Test event handler registry and dispatch."""

    def test_handler_registry_singleton(self):
        """Verify handler registry is singleton."""
        reset_handlers()
        reg1 = get_handler_registry()
        reg2 = get_handler_registry()
        assert reg1 is reg2

    def test_handler_registration(self):
        """Verify handlers are registered."""
        stale = get_handler_registry()
        reset_handlers()
        registry = get_handler_registry()
        assert registry is not stale, "reset must give a fresh registry"

        assert registry.get(EventType.FINDING_TRIAGED) is not None
        assert registry.get(EventType.VIOLATION_DETECTED) is not None
        assert registry.get(EventType.PERFORMANCE_REGRESSED) is not None
        assert registry.get(EventType.FALSE_POSITIVE_CONFIRMED) is not None
        assert registry.get(EventType.MUTATION_CASE_DISCOVERED) is not None
        assert registry.get(EventType.ORACLE_TRAINING_IMPROVED) is not None

    def test_custom_handler_registration(self):
        """Verify custom handlers can be registered."""
        reset_handlers()
        registry = get_handler_registry()

        received = []

        def custom_handler(event: Event):
            received.append(event)

        registry.register(EventType.FINDING_TRIAGED, custom_handler)

        event = create_triage_event("f1", "dated_claim", "false", "test", "MEDIUM")
        registry.handle(event)

        assert len(received) == 1

    def test_setup_event_handlers(self):
        """Verify handlers are connected to event bus."""
        reset_event_bus()
        reset_handlers()
        assert len(get_event_bus().handlers) == 0, "a fresh bus has no handlers"
        setup_event_handlers()

        bus = get_event_bus()
        assert len(bus.handlers) > 0

    def test_triage_event_handler(self):
        """Verify triage event updates ledger."""
        stale = get_handler_registry()
        reset_handlers()
        registry = get_handler_registry()
        assert registry is not stale, "reset must give a fresh registry"

        from swizzle.integration.triage_ledger import DEFAULT_LEDGER
        before = len(DEFAULT_LEDGER.entries)
        event = create_triage_event("f1", "dated_claim", "false", "test reasoning", "MEDIUM")
        registry.handle(event)

        # Handler should have processed this event, adding to the ledger
        assert len(DEFAULT_LEDGER.entries) > before


class TestEventSerialization:
    """Test event JSON serialization."""

    def test_event_to_json(self):
        """Verify events serialize to JSON."""
        event = create_triage_event("f1", "dated_claim", "false", "test", "MEDIUM")
        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["id"] == event.id
        assert data["type"] == "finding_triaged"
        assert data["source_tool"] == "ghost_tools"

    def test_event_from_json(self):
        """Verify events deserialize from JSON."""
        event1 = create_triage_event("f1", "dated_claim", "false", "test", "MEDIUM")
        json_str = event1.to_json()
        event2 = Event.from_json(json_str)

        assert event2.id == event1.id
        assert event2.type == event1.type
        assert event2.data == event1.data

    def test_event_roundtrip(self):
        """Verify event survives JSON roundtrip."""
        original = create_violation_event("v1", "boundary_violation", "lab", "file:1", "CRITICAL")
        json_str = original.to_json()
        restored = Event.from_json(json_str)

        assert restored.id == original.id
        assert restored.type == original.type
        assert restored.severity == original.severity
        assert restored.data == original.data


class TestHookManager:
    """Test git hook installation and triggering."""

    def test_hook_manager_init(self, tmp_path):
        """Verify hook manager initializes."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git" / "hooks").mkdir(parents=True, exist_ok=True)

        manager = HookManager(repo_path)
        assert manager.repo_path == repo_path
        assert manager.hooks_dir.exists()

    def test_install_hooks(self, tmp_path):
        """Verify hooks are installed."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git" / "hooks").mkdir(parents=True, exist_ok=True)

        manager = HookManager(repo_path)
        manager.install_hooks()

        hook_file = repo_path / ".git" / "hooks" / "post-commit"
        assert hook_file.exists()
        assert hook_file.stat().st_mode & 0o111  # Check executable bit

    def test_uninstall_hooks(self, tmp_path):
        """Verify hooks can be uninstalled."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git" / "hooks").mkdir(parents=True, exist_ok=True)

        manager = HookManager(repo_path)
        manager.install_hooks()

        hook_file = repo_path / ".git" / "hooks" / "post-commit"
        assert hook_file.exists()

        manager.uninstall_hooks()
        assert not hook_file.exists()
