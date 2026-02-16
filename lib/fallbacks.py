"""Deterministic fallback handlers for SafeFlow.

Covers three failure domains:
  1. AI classification failure  → handled in ai_triage.py
  2. Contractor matching failure → escalate + alert
  3. WhatsApp media parsing failure → continue without media

No silent failures.  Every fallback is logged and counted.

Usage:
    from lib.fallbacks import handle_contractor_match_failure, handle_media_parse_failure
"""

from datetime import datetime, timezone
from typing import Any

from lib.logger import get_logger
from lib.metrics import counters

log = get_logger("fallbacks")


def handle_contractor_match_failure(
    *,
    job_id: str,
    facility_id: str = "",
    discipline: str = "",
    urgency: str = "",
    reason: str = "No matching contractor found",
) -> dict[str, Any]:
    """Handle failure to find a valid contractor.

    Actions:
      1. Log the failure with full context
      2. Increment counter
      3. Return an escalation payload for the supervisor queue

    Returns a dict suitable for feeding into Scenario B escalation.
    """
    counters.increment("contractor_unassigned_events")

    log.error(
        "Contractor matching failed — escalating to supervisor",
        job_id=job_id,
        facility_id=facility_id,
        discipline=discipline,
        urgency=urgency,
        reason=reason,
    )

    return {
        "action": "ESCALATE",
        "reason": reason,
        "job_id": job_id,
        "facility_id": facility_id,
        "discipline": discipline,
        "urgency": urgency,
        "needs_review": True,
        "alert": {
            "type": "CONTRACTOR_UNAVAILABLE",
            "severity": "HIGH",
            "message": f"No contractor available for {discipline} ({urgency}) on job {job_id}. Requires manual assignment.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


def handle_media_parse_failure(
    *,
    job_id: str,
    facility_id: str = "",
    message_id: str = "",
    media_id: str = "",
    error: str = "",
) -> dict[str, Any]:
    """Handle WhatsApp media parsing failure.

    Actions:
      1. Log the media error
      2. Increment counter
      3. Return a payload that allows the flow to continue WITHOUT media

    The job is created without media.  The flow is NOT blocked.
    """
    counters.increment("media_parse_failures")

    log.warn(
        "Media parsing failed — continuing without media",
        job_id=job_id,
        facility_id=facility_id,
        message_id=message_id,
        media_id=media_id,
        error=error,
    )

    return {
        "media_available": False,
        "media_url": None,
        "media_error": error,
        "job_id": job_id,
        "message_id": message_id,
        "continue_flow": True,
    }
