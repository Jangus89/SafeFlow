"""Tests for the audit trail layer."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.audit import VALID_TRIGGERS, build_state_history_entry, record_transition


class TestRecordTransition:
    def test_returns_audit_entry(self):
        entry = record_transition(
            work_item_id="SF-42",
            previous_state="INTAKE",
            new_state="ASSESSMENT",
            triggered_by="ai",
            actor_id="system",
            notes="Confidence: 0.92",
        )
        assert entry["work_item_id"] == "SF-42"
        assert entry["previous_state"] == "INTAKE"
        assert entry["new_state"] == "ASSESSMENT"
        assert entry["triggered_by"] == "ai"
        assert "timestamp" in entry

    def test_none_previous_state_becomes_none(self):
        entry = record_transition(
            work_item_id="SF-1",
            previous_state=None,
            new_state="INTAKE",
            triggered_by="system",
        )
        assert entry["previous_state"] == "NONE"

    def test_invalid_trigger_defaults_to_system(self):
        entry = record_transition(
            work_item_id="SF-1",
            previous_state="A",
            new_state="B",
            triggered_by="invalid_value",
        )
        assert entry["triggered_by"] == "system"

    def test_valid_triggers(self):
        assert VALID_TRIGGERS == {"ai", "system", "user"}


class TestBuildStateHistoryEntry:
    def test_structure(self):
        entry = build_state_history_entry(
            from_state="ASSIGNED",
            to_state="ACCEPTED",
            trigger="ACCEPT",
            actor_id="rec_12345",
            actor_role="CONTRACTOR",
            notes="Accepted by contractor",
        )
        assert entry["from_state"] == "ASSIGNED"
        assert entry["to_state"] == "ACCEPTED"
        assert entry["trigger"] == "ACCEPT"
        assert entry["actor_id"] == "rec_12345"
        assert entry["actor_role"] == "CONTRACTOR"
        assert "timestamp" in entry

    def test_none_from_state(self):
        entry = build_state_history_entry(
            from_state=None, to_state="INTAKE", trigger="NEW_ISSUE",
        )
        assert entry["from_state"] == "NONE"
