"""Tests for cross-repository queries and analytics."""

import pytest
from pathlib import Path
from datetime import datetime

from swizzle.integration.unified_index import (
    UnifiedIndex, IndexedEvent, IndexedDecision, get_unified_index, reset_unified_index
)
from swizzle.integration.trend_analyzer import TrendAnalyzer, create_trend_analyzer
from swizzle.integration.query_engine import QueryEngine, create_query_engine
from swizzle.integration.cross_repo import CrossRepoManager


class TestUnifiedIndex:
    """Test unified index functionality."""

    def test_index_add_event(self):
        """Verify events can be added to index."""
        reset_unified_index()
        index = get_unified_index()

        event = IndexedEvent(
            event_id="e1",
            repo="swizzle",
            type="false_positive_confirmed",
            timestamp=datetime.now().isoformat(),
            data={"finding_type": "dated_claim", "confidence": 0.95},
        )

        index.add_event("swizzle", event)

        assert "e1" in index.events
        assert index.repo_event_counts["swizzle"] == 1

    def test_query_events_by_type(self):
        """Verify querying events by type."""
        reset_unified_index()
        index = get_unified_index()

        for i in range(3):
            event = IndexedEvent(
                event_id=f"e{i}",
                repo="swizzle",
                type="false_positive_confirmed",
                timestamp=datetime.now().isoformat(),
                data={},
            )
            index.add_event("swizzle", event)

        results = index.query_events_by_type("false_positive_confirmed")
        assert len(results) == 3
        assert all(r.type == "false_positive_confirmed" for r in results)

    def test_approval_stats(self):
        """Verify approval statistics calculation."""
        reset_unified_index()
        index = get_unified_index()

        for i in range(5):
            decision = IndexedDecision(
                decision_id=f"d{i}",
                repo="swizzle",
                type="apply_filter_pattern",
                risk_level="low",
                confidence=0.95,
                approved=(i < 3),
                executed=(i < 2),
                created_at=datetime.now().isoformat(),
            )
            index.add_decision("swizzle", decision)

        stats = index.get_approval_stats()
        assert stats["total"] == 5
        assert stats["approved"] == 3
        assert stats["executed"] == 2


class TestTrendAnalyzer:
    """Test trend analysis functionality."""

    def test_analyzer_creation(self):
        """Verify trend analyzer can be created."""
        reset_unified_index()
        index = get_unified_index()
        analyzer = create_trend_analyzer(index)

        assert analyzer is not None
        assert analyzer.index is index

    def test_anomaly_detection(self):
        """Verify anomaly detection."""
        reset_unified_index()
        index = get_unified_index()

        for i in range(5):
            decision = IndexedDecision(
                decision_id=f"d{i}",
                repo="swizzle",
                type="apply_filter_pattern",
                risk_level="low",
                confidence=0.95,
                approved=True,
                executed=False,
                created_at=datetime.now().isoformat(),
            )
            index.add_decision("swizzle", decision)

        analyzer = create_trend_analyzer(index)
        anomalies = analyzer.detect_anomalies()

        non_exec_anomalies = [a for a in anomalies if a.type == "non_execution_anomaly"]
        assert len(non_exec_anomalies) > 0


class TestQueryEngine:
    """Test query engine functionality."""

    def test_engine_creation(self):
        """Verify query engine can be created."""
        reset_unified_index()
        engine = create_query_engine()

        assert engine is not None
        assert engine.index is not None

    def test_query_stats(self):
        """Verify stats query."""
        reset_unified_index()
        index = get_unified_index()

        for i in range(3):
            decision = IndexedDecision(
                decision_id=f"d{i}",
                repo="swizzle",
                type="apply_filter_pattern",
                risk_level="low",
                confidence=0.95,
                approved=True,
                executed=True,
                created_at=datetime.now().isoformat(),
            )
            index.add_decision("swizzle", decision)

        engine = create_query_engine(index)
        stats = engine.query_stats()

        assert "decisions" in stats
        assert stats["decisions"]["total"] == 3
        assert stats["decisions"]["approved"] == 3

    def test_summary_report(self):
        """Verify summary report generation."""
        reset_unified_index()
        index = get_unified_index()

        for i in range(3):
            decision = IndexedDecision(
                decision_id=f"d{i}",
                repo="swizzle",
                type="apply_filter_pattern",
                risk_level="low",
                confidence=0.95,
                approved=True,
                executed=True,
                created_at=datetime.now().isoformat(),
            )
            index.add_decision("swizzle", decision)

        engine = create_query_engine(index)
        report = engine.generate_summary_report()

        assert "summary" in report
        assert "stats" in report
        assert "trends" in report


class TestCrossRepoManager:
    """Test cross-repo manager."""

    def test_manager_creation(self, tmp_path):
        """Verify manager can be created."""
        reset_unified_index()
        manager = CrossRepoManager(tmp_path)

        assert manager is not None
        assert manager.workspace == tmp_path

    def test_sync_and_load(self, tmp_path):
        """Verify index sync and load."""
        reset_unified_index()
        index = get_unified_index()

        decision = IndexedDecision(
            decision_id="d1",
            repo="swizzle",
            type="apply_filter_pattern",
            risk_level="low",
            confidence=0.95,
            approved=True,
            executed=True,
            created_at=datetime.now().isoformat(),
        )
        index.add_decision("swizzle", decision)

        manager = CrossRepoManager(tmp_path)
        manager.sync_index()

        assert manager.index_path.exists()

        reset_unified_index()
        manager2 = CrossRepoManager(tmp_path)
        manager2.load_index()

        assert len(manager2.index.decisions) == 1

    def test_html_report_save(self, tmp_path):
        """Verify HTML report can be saved."""
        reset_unified_index()
        manager = CrossRepoManager(tmp_path)

        filepath = manager.save_html_report()

        assert filepath.exists()
        assert filepath.suffix == ".html"
