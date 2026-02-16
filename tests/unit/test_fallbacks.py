"""Tests for deterministic fallback handlers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.fallbacks import handle_contractor_match_failure, handle_media_parse_failure


class TestContractorMatchFailure:
    def test_returns_escalation_payload(self):
        result = handle_contractor_match_failure(
            job_id="SF-42", discipline="PLUMBING", urgency="URGENT",
        )
        assert result["action"] == "ESCALATE"
        assert result["needs_review"] is True
        assert result["job_id"] == "SF-42"

    def test_alert_is_high_severity(self):
        result = handle_contractor_match_failure(
            job_id="SF-42", discipline="PLUMBING", urgency="URGENT",
        )
        assert result["alert"]["severity"] == "HIGH"
        assert result["alert"]["type"] == "CONTRACTOR_UNAVAILABLE"

    def test_includes_discipline_in_alert(self):
        result = handle_contractor_match_failure(
            job_id="SF-1", discipline="GAS_SAFE", urgency="EMERGENCY",
        )
        assert "GAS_SAFE" in result["alert"]["message"]


class TestMediaParseFailure:
    def test_continues_without_media(self):
        result = handle_media_parse_failure(
            job_id="SF-42", media_id="media_123", error="Download failed",
        )
        assert result["media_available"] is False
        assert result["media_url"] is None
        assert result["continue_flow"] is True

    def test_preserves_error_detail(self):
        result = handle_media_parse_failure(
            job_id="SF-42", error="Timeout fetching media from 360dialog",
        )
        assert "Timeout" in result["media_error"]

    def test_flow_is_never_blocked(self):
        result = handle_media_parse_failure(
            job_id="SF-42", error="any error",
        )
        assert result["continue_flow"] is True
