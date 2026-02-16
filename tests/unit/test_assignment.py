"""Tests for the hardened contractor assignment logic."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.assignment import find_best_contractor
from lib.metrics import counters


def _make_contractor(**overrides):
    base = {
        "contractor_id": 1,
        "company_name": "Test Co",
        "status": "ACTIVE",
        "trade_disciplines": ["PLUMBING"],
        "emergency_available": True,
        "coverage_postcodes": "SW,EC,SE",
        "rating": 4,
        "average_response_hours": 2,
        "current_open_jobs": 3,
    }
    base.update(overrides)
    return base


class TestFilterLogic:
    def test_inactive_contractor_rejected(self):
        contractors = [_make_contractor(status="SUSPENDED")]
        result = find_best_contractor(
            contractors=contractors, discipline="PLUMBING", job_id="SF-1"
        )
        assert result["assigned"] is False
        assert "SUSPENDED" in result["rejection_reasons"][0]

    def test_discipline_mismatch_rejected(self):
        contractors = [_make_contractor(trade_disciplines=["ELECTRICAL"])]
        result = find_best_contractor(
            contractors=contractors, discipline="PLUMBING", job_id="SF-1"
        )
        assert result["assigned"] is False

    def test_emergency_not_available_rejected(self):
        contractors = [_make_contractor(emergency_available=False)]
        result = find_best_contractor(
            contractors=contractors, discipline="PLUMBING", urgency="EMERGENCY", job_id="SF-1"
        )
        assert result["assigned"] is False

    def test_postcode_mismatch_rejected(self):
        contractors = [_make_contractor(coverage_postcodes="W1,NW")]
        result = find_best_contractor(
            contractors=contractors, discipline="PLUMBING",
            site_postcode="SW1A", job_id="SF-1"
        )
        assert result["assigned"] is False

    def test_matching_contractor_assigned(self):
        contractors = [_make_contractor()]
        result = find_best_contractor(
            contractors=contractors, discipline="PLUMBING",
            site_postcode="SW1A", job_id="SF-1"
        )
        assert result["assigned"] is True
        assert result["contractor"]["company_name"] == "Test Co"


class TestDeterministicSorting:
    def test_higher_rating_preferred(self):
        contractors = [
            _make_contractor(contractor_id=1, rating=3, company_name="Low Rating"),
            _make_contractor(contractor_id=2, rating=5, company_name="High Rating"),
        ]
        result = find_best_contractor(
            contractors=contractors, discipline="PLUMBING", job_id="SF-1"
        )
        assert result["contractor"]["company_name"] == "High Rating"

    def test_faster_response_preferred_on_tie(self):
        contractors = [
            _make_contractor(contractor_id=1, rating=4, average_response_hours=5, company_name="Slow"),
            _make_contractor(contractor_id=2, rating=4, average_response_hours=1, company_name="Fast"),
        ]
        result = find_best_contractor(
            contractors=contractors, discipline="PLUMBING", job_id="SF-1"
        )
        assert result["contractor"]["company_name"] == "Fast"

    def test_lighter_workload_preferred(self):
        contractors = [
            _make_contractor(contractor_id=1, rating=4, average_response_hours=2, current_open_jobs=10, company_name="Busy"),
            _make_contractor(contractor_id=2, rating=4, average_response_hours=2, current_open_jobs=1, company_name="Free"),
        ]
        result = find_best_contractor(
            contractors=contractors, discipline="PLUMBING", job_id="SF-1"
        )
        assert result["contractor"]["company_name"] == "Free"

    def test_deterministic_tiebreaker_by_id(self):
        contractors = [
            _make_contractor(contractor_id=99, rating=4, average_response_hours=2, current_open_jobs=1, company_name="Higher ID"),
            _make_contractor(contractor_id=1, rating=4, average_response_hours=2, current_open_jobs=1, company_name="Lower ID"),
        ]
        result = find_best_contractor(
            contractors=contractors, discipline="PLUMBING", job_id="SF-1"
        )
        assert result["contractor"]["company_name"] == "Lower ID"

    def test_no_randomness_in_results(self):
        contractors = [
            _make_contractor(contractor_id=i, rating=4, average_response_hours=2, current_open_jobs=1)
            for i in range(20)
        ]
        results = [
            find_best_contractor(contractors=contractors, discipline="PLUMBING", job_id="SF-1")["contractor"]["contractor_id"]
            for _ in range(10)
        ]
        assert len(set(results)) == 1, "Assignment must be deterministic"


class TestEscalationOnNoMatch:
    def test_no_contractors_escalates(self):
        result = find_best_contractor(
            contractors=[], discipline="PLUMBING", job_id="SF-1"
        )
        assert result["assigned"] is False
        assert result["escalation"] is not None
        assert result["escalation"]["action"] == "ESCALATE"

    def test_escalation_includes_alert(self):
        result = find_best_contractor(
            contractors=[], discipline="PLUMBING", urgency="EMERGENCY", job_id="SF-1"
        )
        assert result["escalation"]["alert"]["severity"] == "HIGH"
        assert "CONTRACTOR_UNAVAILABLE" in result["escalation"]["alert"]["type"]
