"""Tests for the metrics counters module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.metrics import MetricsCounters


class TestMetricsCounters:
    def test_known_counters_initialized_to_zero(self):
        m = MetricsCounters()
        assert m.get("total_jobs_created") == 0
        assert m.get("ai_failures") == 0
        assert m.get("sla_breaches") == 0

    def test_increment(self):
        m = MetricsCounters()
        m.increment("total_jobs_created")
        assert m.get("total_jobs_created") == 1
        m.increment("total_jobs_created", 5)
        assert m.get("total_jobs_created") == 6

    def test_custom_counter(self):
        m = MetricsCounters()
        m.increment("custom_event")
        assert m.get("custom_event") == 1

    def test_summary_structure(self):
        m = MetricsCounters()
        m.increment("total_jobs_created", 10)
        summary = m.summary()
        assert summary["service"] == "safeflow"
        assert "started_at" in summary
        assert "snapshot_at" in summary
        assert summary["counters"]["total_jobs_created"] == 10

    def test_reset(self):
        m = MetricsCounters()
        m.increment("total_jobs_created", 100)
        m.reset()
        assert m.get("total_jobs_created") == 0

    def test_all_predefined_counters_exist(self):
        m = MetricsCounters()
        expected = [
            "total_jobs_created", "low_confidence_jobs", "ai_failures",
            "sla_breaches", "contractor_unassigned_events", "ai_fallback_used",
            "media_parse_failures", "state_transitions", "escalations_triggered",
            "audit_entries_written",
        ]
        for name in expected:
            assert m.get(name) == 0, f"Counter {name} not initialized"
