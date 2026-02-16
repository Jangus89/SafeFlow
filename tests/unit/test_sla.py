"""Tests for the SLA breach detection and escalation logic."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.sla import SLA_TIERS, calculate_sla_deadline, check_sla_breach


class TestSLATiers:
    def test_all_urgencies_defined(self):
        for urgency in ["EMERGENCY", "URGENT", "STANDARD", "SCHEDULED"]:
            assert urgency in SLA_TIERS

    def test_emergency_is_fastest(self):
        assert SLA_TIERS["EMERGENCY"]["response_minutes"] == 15
        assert SLA_TIERS["EMERGENCY"]["resolution_hours"] == 4

    def test_escalation_intervals_exist(self):
        for tier in SLA_TIERS.values():
            assert len(tier["escalation_intervals_minutes"]) == 3


class TestCheckSLABreach:
    def test_no_breach_when_before_deadline(self):
        now = datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc)
        deadline = (now + timedelta(hours=1)).isoformat()
        result = check_sla_breach(
            work_item_id="SF-1", urgency="STANDARD",
            sla_due_at=deadline, current_state="IN_PROGRESS", now=now,
        )
        assert result["breached"] is False
        assert result["minutes_overdue"] == 0.0

    def test_breach_detected_when_overdue(self):
        now = datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc)
        deadline = (now - timedelta(hours=1)).isoformat()
        result = check_sla_breach(
            work_item_id="SF-1", urgency="STANDARD",
            sla_due_at=deadline, current_state="IN_PROGRESS", now=now,
        )
        assert result["breached"] is True
        assert result["minutes_overdue"] == 60.0

    def test_escalation_level_increases(self):
        now = datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc)
        # STANDARD tier: intervals at 240, 480, 1440 min
        # 500 minutes overdue → should be level 2 (past 480)
        deadline = (now - timedelta(minutes=500)).isoformat()
        result = check_sla_breach(
            work_item_id="SF-1", urgency="STANDARD",
            sla_due_at=deadline, current_state="IN_PROGRESS",
            escalation_level=0, now=now,
        )
        assert result["new_escalation_level"] == 2
        assert result["escalation_required"] is True

    def test_no_escalation_if_already_at_level(self):
        now = datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc)
        deadline = (now - timedelta(minutes=500)).isoformat()
        result = check_sla_breach(
            work_item_id="SF-1", urgency="STANDARD",
            sla_due_at=deadline, current_state="IN_PROGRESS",
            escalation_level=2, now=now,
        )
        assert result["escalation_required"] is False

    def test_terminal_states_never_breach(self):
        now = datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc)
        deadline = (now - timedelta(hours=100)).isoformat()
        for state in ["CLOSED", "CANCELLED"]:
            result = check_sla_breach(
                work_item_id="SF-1", urgency="EMERGENCY",
                sla_due_at=deadline, current_state=state, now=now,
            )
            assert result["breached"] is False

    def test_missing_sla_deadline(self):
        result = check_sla_breach(
            work_item_id="SF-1", urgency="STANDARD",
            sla_due_at=None, current_state="IN_PROGRESS",
        )
        assert result["breached"] is False

    def test_alert_payload_on_breach(self):
        now = datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc)
        deadline = (now - timedelta(minutes=20)).isoformat()
        result = check_sla_breach(
            work_item_id="SF-1", urgency="EMERGENCY",
            sla_due_at=deadline, current_state="IN_PROGRESS",
            escalation_level=0, now=now,
        )
        assert result["alert"] is not None
        assert result["alert"]["type"] == "SLA_BREACH"
        assert "SF-1" in result["alert"]["message"]

    def test_emergency_escalation_is_critical(self):
        now = datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc)
        deadline = (now - timedelta(minutes=60)).isoformat()
        result = check_sla_breach(
            work_item_id="SF-1", urgency="EMERGENCY",
            sla_due_at=deadline, current_state="IN_PROGRESS",
            escalation_level=0, now=now,
        )
        assert result["alert"]["severity"] == "CRITICAL"


class TestCalculateSLADeadline:
    def test_emergency_deadline(self):
        created = datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc)
        deadline = calculate_sla_deadline("EMERGENCY", created)
        expected = (created + timedelta(hours=4)).isoformat()
        assert deadline == expected

    def test_standard_deadline(self):
        created = datetime(2026, 2, 16, 10, 0, tzinfo=timezone.utc)
        deadline = calculate_sla_deadline("STANDARD", created)
        expected = (created + timedelta(hours=72)).isoformat()
        assert deadline == expected
