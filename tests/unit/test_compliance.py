"""Tests for the contractor compliance expiry checking module."""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.compliance import (
    build_compliance_alert,
    check_contractor_compliance,
    get_expiring_contractors,
)


def _make_contractor(**overrides):
    base = {
        "contractor_id": 1,
        "company_name": "Test Plumbing Ltd",
        "status": "ACTIVE",
        "trade_disciplines": ["PLUMBING"],
        "gas_safe_expiry": None,
        "niceic_expiry": None,
    }
    base.update(overrides)
    return base


class TestCheckContractorCompliance:
    def test_no_expiry_dates_returns_not_verified(self):
        c = _make_contractor()
        result = check_contractor_compliance(c, today=date(2026, 2, 16))
        assert result["compliance_status"] == "NOT_VERIFIED"
        assert result["next_expiry_date"] is None

    def test_all_certs_valid_returns_compliant(self):
        c = _make_contractor(
            gas_safe_expiry="2027-06-15",
            niceic_expiry="2027-09-01",
        )
        result = check_contractor_compliance(c, today=date(2026, 2, 16))
        assert result["compliance_status"] == "COMPLIANT"
        assert result["next_expiry_date"] == "2027-06-15"
        assert result["expired_certs"] == []
        assert result["expiring_soon_certs"] == []

    def test_gas_safe_expiring_soon(self):
        today = date(2026, 2, 16)
        c = _make_contractor(
            gas_safe_expiry=(today + timedelta(days=15)).isoformat(),
        )
        result = check_contractor_compliance(c, today=today)
        assert result["compliance_status"] == "EXPIRING_SOON"
        assert len(result["expiring_soon_certs"]) == 1
        assert result["expiring_soon_certs"][0]["cert"] == "Gas Safe"

    def test_niceic_expired(self):
        today = date(2026, 2, 16)
        c = _make_contractor(
            niceic_expiry=(today - timedelta(days=10)).isoformat(),
        )
        result = check_contractor_compliance(c, today=today)
        assert result["compliance_status"] == "EXPIRED"
        assert len(result["expired_certs"]) == 1
        assert result["expired_certs"][0]["cert"] == "NICEIC"

    def test_expired_takes_precedence_over_expiring_soon(self):
        today = date(2026, 2, 16)
        c = _make_contractor(
            gas_safe_expiry=(today - timedelta(days=5)).isoformat(),
            niceic_expiry=(today + timedelta(days=20)).isoformat(),
        )
        result = check_contractor_compliance(c, today=today)
        assert result["compliance_status"] == "EXPIRED"
        assert len(result["expired_certs"]) == 1
        assert len(result["expiring_soon_certs"]) == 1

    def test_next_expiry_date_is_earliest(self):
        c = _make_contractor(
            gas_safe_expiry="2027-03-01",
            niceic_expiry="2026-12-01",
        )
        result = check_contractor_compliance(c, today=date(2026, 2, 16))
        assert result["next_expiry_date"] == "2026-12-01"

    def test_boundary_30_days_is_expiring_soon(self):
        today = date(2026, 2, 16)
        c = _make_contractor(
            gas_safe_expiry=(today + timedelta(days=30)).isoformat(),
        )
        result = check_contractor_compliance(c, today=today)
        assert result["compliance_status"] == "EXPIRING_SOON"

    def test_boundary_31_days_is_compliant(self):
        today = date(2026, 2, 16)
        c = _make_contractor(
            gas_safe_expiry=(today + timedelta(days=31)).isoformat(),
        )
        result = check_contractor_compliance(c, today=today)
        assert result["compliance_status"] == "COMPLIANT"

    def test_custom_expiring_soon_days(self):
        today = date(2026, 2, 16)
        c = _make_contractor(
            gas_safe_expiry=(today + timedelta(days=50)).isoformat(),
        )
        result = check_contractor_compliance(c, today=today, expiring_soon_days=60)
        assert result["compliance_status"] == "EXPIRING_SOON"

    def test_handles_datetime_string_with_time(self):
        c = _make_contractor(gas_safe_expiry="2027-06-15T00:00:00+00:00")
        result = check_contractor_compliance(c, today=date(2026, 2, 16))
        assert result["compliance_status"] == "COMPLIANT"

    def test_handles_empty_string_expiry(self):
        c = _make_contractor(gas_safe_expiry="", niceic_expiry="")
        result = check_contractor_compliance(c, today=date(2026, 2, 16))
        assert result["compliance_status"] == "NOT_VERIFIED"


class TestGetExpiringContractors:
    def test_returns_expired_and_expiring_soon(self):
        today = date(2026, 2, 16)
        contractors = [
            _make_contractor(
                contractor_id=1,
                gas_safe_expiry=(today - timedelta(days=5)).isoformat(),
            ),
            _make_contractor(
                contractor_id=2,
                gas_safe_expiry=(today + timedelta(days=15)).isoformat(),
            ),
            _make_contractor(
                contractor_id=3,
                gas_safe_expiry="2028-01-01",
            ),
        ]
        results = get_expiring_contractors(contractors, today=today)
        assert len(results) == 2
        statuses = {r["compliance_status"] for r in results}
        assert statuses == {"EXPIRED", "EXPIRING_SOON"}

    def test_excludes_inactive_contractors(self):
        today = date(2026, 2, 16)
        contractors = [
            _make_contractor(
                contractor_id=1,
                status="SUSPENDED",
                gas_safe_expiry=(today - timedelta(days=5)).isoformat(),
            ),
        ]
        results = get_expiring_contractors(contractors, today=today)
        assert len(results) == 0

    def test_exclude_expired_flag(self):
        today = date(2026, 2, 16)
        contractors = [
            _make_contractor(
                contractor_id=1,
                gas_safe_expiry=(today - timedelta(days=5)).isoformat(),
            ),
            _make_contractor(
                contractor_id=2,
                gas_safe_expiry=(today + timedelta(days=15)).isoformat(),
            ),
        ]
        results = get_expiring_contractors(
            contractors, today=today, include_expired=False,
        )
        assert len(results) == 1
        assert results[0]["compliance_status"] == "EXPIRING_SOON"


class TestBuildComplianceAlert:
    def test_expired_alert_high_severity(self):
        check = {
            "contractor_id": 1,
            "company_name": "Gas Co Ltd",
            "compliance_status": "EXPIRED",
            "next_expiry_date": "2026-01-15",
            "expired_certs": [{"cert": "Gas Safe", "expiry": "2026-01-15"}],
            "expiring_soon_certs": [],
        }
        alert = build_compliance_alert(check)
        assert alert["alert_required"] is True
        assert alert["severity"] == "HIGH"
        assert alert["type"] == "COMPLIANCE_EXPIRY"
        assert "BLOCKED" in alert["message"]
        assert "Gas Safe" in alert["message"]

    def test_expiring_soon_alert_medium_severity(self):
        check = {
            "contractor_id": 2,
            "company_name": "Spark Electric",
            "compliance_status": "EXPIRING_SOON",
            "next_expiry_date": "2026-03-10",
            "expired_certs": [],
            "expiring_soon_certs": [{"cert": "NICEIC", "expiry": "2026-03-10"}],
        }
        alert = build_compliance_alert(check)
        assert alert["alert_required"] is True
        assert alert["severity"] == "MEDIUM"
        assert "NICEIC" in alert["message"]

    def test_compliant_no_alert(self):
        check = {
            "contractor_id": 3,
            "company_name": "Safe Builder",
            "compliance_status": "COMPLIANT",
            "next_expiry_date": "2027-06-01",
            "expired_certs": [],
            "expiring_soon_certs": [],
        }
        alert = build_compliance_alert(check)
        assert alert["alert_required"] is False

    def test_not_verified_no_alert(self):
        check = {
            "contractor_id": 4,
            "company_name": "New Contractor",
            "compliance_status": "NOT_VERIFIED",
            "next_expiry_date": None,
            "expired_certs": [],
            "expiring_soon_certs": [],
        }
        alert = build_compliance_alert(check)
        assert alert["alert_required"] is False


class TestAssignmentComplianceFilter:
    """Test that the assignment module rejects EXPIRED contractors."""

    def test_expired_contractor_rejected(self):
        from lib.assignment import find_best_contractor

        contractors = [
            {
                "contractor_id": 1,
                "company_name": "Expired Gas Co",
                "status": "ACTIVE",
                "trade_disciplines": ["PLUMBING"],
                "compliance_status": "EXPIRED",
                "rating": 5,
                "average_response_hours": 1,
                "current_open_jobs": 0,
            },
        ]
        result = find_best_contractor(
            contractors=contractors,
            discipline="PLUMBING",
            job_id="SF-99",
        )
        assert result["assigned"] is False
        assert any("compliance_status=EXPIRED" in r for r in result["rejection_reasons"])

    def test_expiring_soon_contractor_still_assigned(self):
        from lib.assignment import find_best_contractor

        contractors = [
            {
                "contractor_id": 2,
                "company_name": "Expiring Soon Plumber",
                "status": "ACTIVE",
                "trade_disciplines": ["PLUMBING"],
                "compliance_status": "EXPIRING_SOON",
                "rating": 4,
                "average_response_hours": 2,
                "current_open_jobs": 1,
            },
        ]
        result = find_best_contractor(
            contractors=contractors,
            discipline="PLUMBING",
            job_id="SF-100",
        )
        assert result["assigned"] is True

    def test_compliant_contractor_assigned(self):
        from lib.assignment import find_best_contractor

        contractors = [
            {
                "contractor_id": 3,
                "company_name": "Compliant Plumber",
                "status": "ACTIVE",
                "trade_disciplines": ["PLUMBING"],
                "compliance_status": "COMPLIANT",
                "rating": 5,
                "average_response_hours": 1,
                "current_open_jobs": 0,
            },
        ]
        result = find_best_contractor(
            contractors=contractors,
            discipline="PLUMBING",
            job_id="SF-101",
        )
        assert result["assigned"] is True

    def test_no_compliance_status_still_assigned(self):
        """Contractors without compliance_status are not blocked."""
        from lib.assignment import find_best_contractor

        contractors = [
            {
                "contractor_id": 4,
                "company_name": "Legacy Plumber",
                "status": "ACTIVE",
                "trade_disciplines": ["PLUMBING"],
                "rating": 3,
                "average_response_hours": 3,
                "current_open_jobs": 2,
            },
        ]
        result = find_best_contractor(
            contractors=contractors,
            discipline="PLUMBING",
            job_id="SF-102",
        )
        assert result["assigned"] is True
