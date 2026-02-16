"""Photo verification assessment logic for completed work items.

When a contractor marks a job as DONE and sends a photo, Claude Vision
analyses the image to determine whether the issue appears resolved.

Decision thresholds:
  - is_resolved=True AND confidence >= 85  → PAYMENT_PENDING (auto-approve)
  - is_resolved=True AND confidence 50-84  → stays VERIFICATION (PM review)
  - is_resolved=False OR confidence < 50   → IN_PROGRESS (rework)

Usage:
    from lib.verification import evaluate_vision_result, build_vision_prompt

    result = evaluate_vision_result(vision_json)
    if result["action"] == "APPROVE":
        # transition to PAYMENT_PENDING
    elif result["action"] == "REVIEW":
        # keep in VERIFICATION, alert PM
    else:
        # transition back to IN_PROGRESS
"""

import json
from typing import Any

from lib.logger import get_logger
from lib.metrics import counters

log = get_logger("verification")

AUTO_APPROVE_THRESHOLD = 85
REWORK_THRESHOLD = 50

VALID_SEVERITIES = {"None", "Low", "Medium", "High"}


def parse_vision_response(raw: str | dict[str, Any]) -> dict[str, Any] | None:
    """Parse the Claude Vision JSON response.

    Accepts either a raw JSON string or an already-parsed dict.
    Returns None if parsing fails.
    """
    if isinstance(raw, str):
        try:
            data = json.loads(raw.strip())
        except (json.JSONDecodeError, ValueError):
            log.error("Failed to parse vision response as JSON", raw_preview=raw[:200])
            return None
    elif isinstance(raw, dict):
        data = raw
    else:
        return None

    errors = validate_vision_response(data)
    if errors:
        log.warn("Vision response validation failed", errors=errors)
        return None

    return data


def validate_vision_response(data: dict[str, Any]) -> list[str]:
    """Validate the structure of a vision assessment response."""
    errors: list[str] = []

    if "is_resolved" not in data:
        errors.append("missing 'is_resolved'")
    elif not isinstance(data["is_resolved"], bool):
        errors.append("'is_resolved' must be boolean")

    if "confidence" not in data:
        errors.append("missing 'confidence'")
    elif not isinstance(data["confidence"], (int, float)):
        errors.append("'confidence' must be a number")
    elif not (0 <= data["confidence"] <= 100):
        errors.append("'confidence' must be between 0 and 100")

    if "reason" not in data:
        errors.append("missing 'reason'")
    elif not isinstance(data["reason"], str):
        errors.append("'reason' must be a string")
    elif len(data["reason"]) > 200:
        errors.append("'reason' exceeds 200 characters")

    if "severity_if_not" not in data:
        errors.append("missing 'severity_if_not'")
    elif data["severity_if_not"] not in VALID_SEVERITIES:
        errors.append(f"'severity_if_not' must be one of {VALID_SEVERITIES}")

    return errors


def evaluate_vision_result(
    vision_data: dict[str, Any] | str | None,
) -> dict[str, Any]:
    """Evaluate a Claude Vision response and determine the next action.

    Returns:
        {
            "action": "APPROVE" | "REVIEW" | "REWORK",
            "target_state": "PAYMENT_PENDING" | "VERIFICATION" | "IN_PROGRESS",
            "is_resolved": bool,
            "confidence": int,
            "reason": str,
            "severity_if_not": str,
            "parsed": bool,
        }
    """
    if vision_data is None:
        log.warn("Vision data is None — falling back to REVIEW")
        return _fallback_result("Vision assessment unavailable — requires manual review")

    parsed = parse_vision_response(vision_data)
    if parsed is None:
        counters.increment("ai_failures")
        return _fallback_result("Vision response could not be parsed — requires manual review")

    is_resolved = parsed["is_resolved"]
    confidence = int(parsed["confidence"])
    reason = parsed["reason"]
    severity = parsed["severity_if_not"]

    if is_resolved and confidence >= AUTO_APPROVE_THRESHOLD:
        action = "APPROVE"
        target_state = "PAYMENT_PENDING"
        log.info(
            "Vision auto-approved",
            confidence=confidence,
            reason=reason,
        )
    elif is_resolved and confidence >= REWORK_THRESHOLD:
        action = "REVIEW"
        target_state = "VERIFICATION"
        log.info(
            "Vision needs PM review",
            confidence=confidence,
            reason=reason,
        )
    else:
        action = "REWORK"
        target_state = "IN_PROGRESS"
        log.info(
            "Vision rework required",
            is_resolved=is_resolved,
            confidence=confidence,
            reason=reason,
            severity=severity,
        )

    return {
        "action": action,
        "target_state": target_state,
        "is_resolved": is_resolved,
        "confidence": confidence,
        "reason": reason,
        "severity_if_not": severity,
        "parsed": True,
    }


def _fallback_result(reason: str) -> dict[str, Any]:
    """Return a safe fallback when vision parsing fails."""
    return {
        "action": "REVIEW",
        "target_state": "VERIFICATION",
        "is_resolved": False,
        "confidence": 0,
        "reason": reason,
        "severity_if_not": "Medium",
        "parsed": False,
    }


def build_vision_prompt(
    *,
    job_description: str,
    discipline: str,
    urgency: str,
    work_item_id: str,
) -> str:
    """Build the text portion of the Claude Vision API user message."""
    return (
        f"Analyze this photo in context of the reported issue: {job_description}\n\n"
        f"Category: {discipline}\n"
        f"Urgency: {urgency}\n"
        f"Job Reference: {work_item_id}\n\n"
        'Does the photo provide strong evidence that the problem is now fixed? '
        'Output strict JSON only: {"is_resolved": boolean, "confidence": integer 0-100, '
        '"reason": string max 150 chars, "severity_if_not": "None|Low|Medium|High"}'
    )
