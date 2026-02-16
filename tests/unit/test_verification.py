"""Tests for the photo verification assessment module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib.verification import (
    AUTO_APPROVE_THRESHOLD,
    REWORK_THRESHOLD,
    build_vision_prompt,
    evaluate_vision_result,
    parse_vision_response,
    validate_vision_response,
)


class TestValidateVisionResponse:
    def test_valid_response(self):
        data = {
            "is_resolved": True,
            "confidence": 92,
            "reason": "New pipe fitted, floor dry",
            "severity_if_not": "None",
        }
        assert validate_vision_response(data) == []

    def test_missing_is_resolved(self):
        data = {"confidence": 80, "reason": "ok", "severity_if_not": "None"}
        errors = validate_vision_response(data)
        assert any("is_resolved" in e for e in errors)

    def test_is_resolved_not_boolean(self):
        data = {"is_resolved": "yes", "confidence": 80, "reason": "ok", "severity_if_not": "None"}
        errors = validate_vision_response(data)
        assert any("boolean" in e for e in errors)

    def test_missing_confidence(self):
        data = {"is_resolved": True, "reason": "ok", "severity_if_not": "None"}
        errors = validate_vision_response(data)
        assert any("confidence" in e for e in errors)

    def test_confidence_out_of_range(self):
        data = {"is_resolved": True, "confidence": 150, "reason": "ok", "severity_if_not": "None"}
        errors = validate_vision_response(data)
        assert any("between 0 and 100" in e for e in errors)

    def test_negative_confidence(self):
        data = {"is_resolved": True, "confidence": -5, "reason": "ok", "severity_if_not": "None"}
        errors = validate_vision_response(data)
        assert any("between 0 and 100" in e for e in errors)

    def test_missing_reason(self):
        data = {"is_resolved": True, "confidence": 80, "severity_if_not": "None"}
        errors = validate_vision_response(data)
        assert any("reason" in e for e in errors)

    def test_reason_too_long(self):
        data = {"is_resolved": True, "confidence": 80, "reason": "x" * 201, "severity_if_not": "None"}
        errors = validate_vision_response(data)
        assert any("200 characters" in e for e in errors)

    def test_invalid_severity(self):
        data = {"is_resolved": False, "confidence": 30, "reason": "not fixed", "severity_if_not": "Critical"}
        errors = validate_vision_response(data)
        assert any("severity_if_not" in e for e in errors)

    def test_missing_severity(self):
        data = {"is_resolved": False, "confidence": 30, "reason": "not fixed"}
        errors = validate_vision_response(data)
        assert any("severity_if_not" in e for e in errors)


class TestParseVisionResponse:
    def test_parse_valid_json_string(self):
        raw = '{"is_resolved": true, "confidence": 90, "reason": "Fixed", "severity_if_not": "None"}'
        result = parse_vision_response(raw)
        assert result is not None
        assert result["is_resolved"] is True
        assert result["confidence"] == 90

    def test_parse_dict(self):
        data = {"is_resolved": False, "confidence": 20, "reason": "Still leaking", "severity_if_not": "High"}
        result = parse_vision_response(data)
        assert result is not None
        assert result["is_resolved"] is False

    def test_parse_invalid_json_string(self):
        result = parse_vision_response("not json at all")
        assert result is None

    def test_parse_none(self):
        result = parse_vision_response(None)
        assert result is None

    def test_parse_invalid_structure(self):
        result = parse_vision_response({"foo": "bar"})
        assert result is None

    def test_parse_json_with_whitespace(self):
        raw = '  \n{"is_resolved": true, "confidence": 88, "reason": "Looks good", "severity_if_not": "None"}\n  '
        result = parse_vision_response(raw)
        assert result is not None


class TestEvaluateVisionResult:
    def test_auto_approve_high_confidence(self):
        data = {"is_resolved": True, "confidence": 95, "reason": "Clear fix", "severity_if_not": "None"}
        result = evaluate_vision_result(data)
        assert result["action"] == "APPROVE"
        assert result["target_state"] == "PAYMENT_PENDING"
        assert result["parsed"] is True

    def test_auto_approve_at_threshold(self):
        data = {"is_resolved": True, "confidence": 85, "reason": "Fixed", "severity_if_not": "None"}
        result = evaluate_vision_result(data)
        assert result["action"] == "APPROVE"
        assert result["target_state"] == "PAYMENT_PENDING"

    def test_review_moderate_confidence(self):
        data = {"is_resolved": True, "confidence": 70, "reason": "Probably fixed", "severity_if_not": "Low"}
        result = evaluate_vision_result(data)
        assert result["action"] == "REVIEW"
        assert result["target_state"] == "VERIFICATION"

    def test_review_at_lower_boundary(self):
        data = {"is_resolved": True, "confidence": 50, "reason": "Ambiguous", "severity_if_not": "Low"}
        result = evaluate_vision_result(data)
        assert result["action"] == "REVIEW"
        assert result["target_state"] == "VERIFICATION"

    def test_rework_low_confidence(self):
        data = {"is_resolved": True, "confidence": 40, "reason": "Unclear photo", "severity_if_not": "Medium"}
        result = evaluate_vision_result(data)
        assert result["action"] == "REWORK"
        assert result["target_state"] == "IN_PROGRESS"

    def test_rework_not_resolved(self):
        data = {"is_resolved": False, "confidence": 90, "reason": "Crack still visible", "severity_if_not": "Medium"}
        result = evaluate_vision_result(data)
        assert result["action"] == "REWORK"
        assert result["target_state"] == "IN_PROGRESS"

    def test_rework_not_resolved_low_confidence(self):
        data = {"is_resolved": False, "confidence": 20, "reason": "Unrelated photo", "severity_if_not": "High"}
        result = evaluate_vision_result(data)
        assert result["action"] == "REWORK"
        assert result["target_state"] == "IN_PROGRESS"

    def test_none_input_falls_back_to_review(self):
        result = evaluate_vision_result(None)
        assert result["action"] == "REVIEW"
        assert result["target_state"] == "VERIFICATION"
        assert result["parsed"] is False

    def test_invalid_json_falls_back_to_review(self):
        result = evaluate_vision_result("garbage data")
        assert result["action"] == "REVIEW"
        assert result["target_state"] == "VERIFICATION"
        assert result["parsed"] is False

    def test_result_includes_all_fields(self):
        data = {"is_resolved": True, "confidence": 92, "reason": "New pipe visible", "severity_if_not": "None"}
        result = evaluate_vision_result(data)
        assert "action" in result
        assert "target_state" in result
        assert "is_resolved" in result
        assert "confidence" in result
        assert "reason" in result
        assert "severity_if_not" in result
        assert "parsed" in result

    def test_confidence_boundary_84_is_review(self):
        data = {"is_resolved": True, "confidence": 84, "reason": "Almost sure", "severity_if_not": "Low"}
        result = evaluate_vision_result(data)
        assert result["action"] == "REVIEW"

    def test_confidence_boundary_49_is_rework(self):
        data = {"is_resolved": True, "confidence": 49, "reason": "Uncertain", "severity_if_not": "Medium"}
        result = evaluate_vision_result(data)
        assert result["action"] == "REWORK"


class TestBuildVisionPrompt:
    def test_prompt_contains_all_fields(self):
        prompt = build_vision_prompt(
            job_description="Leaking pipe under kitchen sink",
            discipline="PLUMBING",
            urgency="URGENT",
            work_item_id="SF-1042",
        )
        assert "Leaking pipe under kitchen sink" in prompt
        assert "PLUMBING" in prompt
        assert "URGENT" in prompt
        assert "SF-1042" in prompt
        assert "is_resolved" in prompt
        assert "confidence" in prompt
        assert "severity_if_not" in prompt

    def test_prompt_requests_json_output(self):
        prompt = build_vision_prompt(
            job_description="Broken window",
            discipline="GLAZING",
            urgency="STANDARD",
            work_item_id="SF-500",
        )
        assert "strict JSON only" in prompt


class TestThresholdConstants:
    def test_auto_approve_threshold_is_85(self):
        assert AUTO_APPROVE_THRESHOLD == 85

    def test_rework_threshold_is_50(self):
        assert REWORK_THRESHOLD == 50

    def test_approve_threshold_greater_than_rework(self):
        assert AUTO_APPROVE_THRESHOLD > REWORK_THRESHOLD
