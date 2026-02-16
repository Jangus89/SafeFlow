"""Tests for the AI triage confidence & escalation layer."""

import sys
from pathlib import Path

# Ensure lib is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.ai_triage import (
    LOW_CONFIDENCE_THRESHOLD,
    TriageResult,
    _build_fallback_response,
    validate_triage_response,
)
from lib.metrics import counters


class TestValidateTriageResponse:
    """Strict JSON schema validation."""

    def _valid_response(self):
        return {
            "triage": {
                "discipline": "PLUMBING",
                "urgency": "STANDARD",
                "confidence": 0.92,
                "reasoning": "Dripping tap, standard plumbing issue.",
            },
            "extraction": {
                "title": "Dripping tap",
                "description": "Tenant reports dripping tap in kitchen.",
                "location": {"building": None, "floor": "ground", "unit": "4B", "area": "kitchen"},
                "reported_symptoms": ["dripping tap"],
                "has_photo": False,
                "is_recurring": False,
            },
            "routing": {
                "decision": "INTERNAL_ENGINEER",
                "reason": "Standard plumbing issue.",
                "required_certifications": [],
                "priority_within_queue": "LOW",
            },
            "clarification": {
                "needed": False,
                "questions": [],
                "missing_fields": [],
            },
            "safety": {
                "immediate_danger": False,
                "safety_instructions": None,
                "emergency_services_needed": False,
                "regulatory_flags": [],
            },
        }

    def test_valid_response_passes(self):
        errors = validate_triage_response(self._valid_response())
        assert errors == []

    def test_missing_top_level_key(self):
        data = self._valid_response()
        del data["safety"]
        errors = validate_triage_response(data)
        assert any("safety" in e for e in errors)

    def test_invalid_urgency(self):
        data = self._valid_response()
        data["triage"]["urgency"] = "CRITICAL"
        errors = validate_triage_response(data)
        assert any("urgency" in e for e in errors)

    def test_invalid_confidence(self):
        data = self._valid_response()
        data["triage"]["confidence"] = 1.5
        errors = validate_triage_response(data)
        assert any("confidence" in e for e in errors)

    def test_invalid_discipline(self):
        data = self._valid_response()
        data["triage"]["discipline"] = "MAGIC"
        errors = validate_triage_response(data)
        assert any("discipline" in e for e in errors)

    def test_null_discipline_is_valid(self):
        data = self._valid_response()
        data["triage"]["discipline"] = None
        errors = validate_triage_response(data)
        assert errors == []

    def test_empty_reasoning_fails(self):
        data = self._valid_response()
        data["triage"]["reasoning"] = ""
        errors = validate_triage_response(data)
        assert any("reasoning" in e for e in errors)

    def test_missing_location_subfield(self):
        data = self._valid_response()
        del data["extraction"]["location"]["area"]
        errors = validate_triage_response(data)
        assert any("area" in e for e in errors)

    def test_invalid_routing_decision(self):
        data = self._valid_response()
        data["routing"]["decision"] = "SELF_SERVICE"
        errors = validate_triage_response(data)
        assert any("decision" in e for e in errors)


class TestDeterministicFallback:
    """AI failure fallback always returns safe defaults."""

    def test_fallback_has_required_fields(self):
        fb = _build_fallback_response("test message", "API timeout")
        errors = validate_triage_response(fb)
        assert errors == [], f"Fallback failed validation: {errors}"

    def test_fallback_category_is_general(self):
        fb = _build_fallback_response("test", "error")
        assert fb["triage"]["discipline"] == "GENERAL_MAINTENANCE"

    def test_fallback_priority_is_standard(self):
        fb = _build_fallback_response("test", "error")
        assert fb["triage"]["urgency"] == "STANDARD"

    def test_fallback_confidence_is_zero(self):
        fb = _build_fallback_response("test", "error")
        assert fb["triage"]["confidence"] == 0.0

    def test_fallback_needs_clarification(self):
        fb = _build_fallback_response("test", "error")
        assert fb["routing"]["decision"] == "NEEDS_CLARIFICATION"
        assert fb["clarification"]["needed"] is True


class TestConfidenceThreshold:
    """Confidence-based routing logic."""

    def test_threshold_is_075(self):
        assert LOW_CONFIDENCE_THRESHOLD == 0.75

    def test_low_confidence_triggers_review(self):
        # Simulate what triage_message does for low confidence
        confidence = 0.55
        needs_review = confidence < LOW_CONFIDENCE_THRESHOLD
        assert needs_review is True

    def test_high_confidence_no_review(self):
        confidence = 0.88
        needs_review = confidence < LOW_CONFIDENCE_THRESHOLD
        assert needs_review is False

    def test_boundary_075_no_review(self):
        confidence = 0.75
        needs_review = confidence < LOW_CONFIDENCE_THRESHOLD
        assert needs_review is False

    def test_boundary_074_triggers_review(self):
        confidence = 0.74
        needs_review = confidence < LOW_CONFIDENCE_THRESHOLD
        assert needs_review is True
