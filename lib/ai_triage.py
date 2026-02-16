"""AI Confidence & Escalation Layer + Deterministic Fallbacks.

Wraps the LLM triage call with:
  - Strict JSON schema validation of every AI response
  - Confidence-based routing (< 0.75 → supervisor queue)
  - Deterministic fallbacks when AI fails
  - Structured logging of all low-confidence events

Usage:
    from lib.ai_triage import triage_message

    result = triage_message(
        message_text="There's a leak in the kitchen",
        sender_phone="447700900123",
        site_name="Meridian House",
        has_media=False,
        api_key=os.environ["ANTHROPIC_API_KEY"],
    )
    # result is a TriageResult with .raw, .needs_review, .category, etc.
"""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

from lib.logger import get_logger
from lib.metrics import counters

log = get_logger("ai_triage")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOW_CONFIDENCE_THRESHOLD = 0.75
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 1500
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MAX_RETRIES = 3

VALID_DISCIPLINES = {
    "PLUMBING", "ELECTRICAL", "GAS_SAFE", "HVAC",
    "LIFT_ENGINEER", "FIRE_SAFETY", "GENERAL_MAINTENANCE", "SPECIALIST",
}
VALID_URGENCIES = {"EMERGENCY", "URGENT", "STANDARD", "SCHEDULED"}
VALID_ROUTING = {"INTERNAL_ENGINEER", "EXTERNAL_CONTRACTOR", "NEEDS_CLARIFICATION"}


# ---------------------------------------------------------------------------
# Strict JSON Schema
# ---------------------------------------------------------------------------

TRIAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["triage", "extraction", "routing", "clarification", "safety"],
    "properties": {
        "triage": {
            "type": "object",
            "required": ["discipline", "urgency", "confidence", "reasoning"],
            "properties": {
                "discipline": {"type": ["string", "null"]},
                "urgency": {"type": "string", "enum": list(VALID_URGENCIES)},
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "reasoning": {"type": "string", "minLength": 1},
            },
        },
        "extraction": {
            "type": "object",
            "required": ["title", "description", "location", "reported_symptoms", "has_photo", "is_recurring"],
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "location": {
                    "type": "object",
                    "required": ["building", "floor", "unit", "area"],
                },
                "reported_symptoms": {"type": "array", "items": {"type": "string"}},
                "has_photo": {"type": "boolean"},
                "is_recurring": {"type": "boolean"},
            },
        },
        "routing": {
            "type": "object",
            "required": ["decision", "reason", "required_certifications", "priority_within_queue"],
            "properties": {
                "decision": {"type": "string", "enum": list(VALID_ROUTING)},
                "reason": {"type": "string"},
                "required_certifications": {"type": "array", "items": {"type": "string"}},
                "priority_within_queue": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
            },
        },
        "clarification": {
            "type": "object",
            "required": ["needed", "questions", "missing_fields"],
        },
        "safety": {
            "type": "object",
            "required": ["immediate_danger", "safety_instructions", "emergency_services_needed", "regulatory_flags"],
        },
    },
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TriageResult:
    """Structured result from the AI triage pipeline."""
    category: str
    priority: str
    confidence_score: float
    reasoning_summary: str
    needs_review: bool
    raw: dict[str, Any]
    fallback_used: bool = False
    validation_errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Schema validation (lightweight, no external deps)
# ---------------------------------------------------------------------------

def validate_triage_response(data: dict[str, Any]) -> list[str]:
    """Validate the AI response against the strict schema.

    Returns a list of error strings.  Empty list means valid.
    """
    errors: list[str] = []

    # Top-level keys
    for key in TRIAGE_SCHEMA["required"]:
        if key not in data:
            errors.append(f"Missing required top-level key: {key}")

    if "triage" in data:
        t = data["triage"]
        if not isinstance(t, dict):
            errors.append("triage must be an object")
        else:
            for k in ["discipline", "urgency", "confidence", "reasoning"]:
                if k not in t:
                    errors.append(f"triage.{k} is required")
            if "confidence" in t:
                c = t["confidence"]
                if not isinstance(c, (int, float)) or c < 0 or c > 1:
                    errors.append(f"triage.confidence must be 0-1, got {c}")
            if "urgency" in t and t["urgency"] not in VALID_URGENCIES:
                errors.append(f"triage.urgency invalid: {t['urgency']}")
            if "discipline" in t and t["discipline"] is not None and t["discipline"] not in VALID_DISCIPLINES:
                errors.append(f"triage.discipline invalid: {t['discipline']}")
            if "reasoning" in t and (not isinstance(t["reasoning"], str) or len(t["reasoning"]) == 0):
                errors.append("triage.reasoning must be a non-empty string")

    if "extraction" in data:
        ex = data["extraction"]
        if not isinstance(ex, dict):
            errors.append("extraction must be an object")
        else:
            for k in ["title", "description", "location", "reported_symptoms", "has_photo", "is_recurring"]:
                if k not in ex:
                    errors.append(f"extraction.{k} is required")
            if "location" in ex:
                loc = ex["location"]
                if not isinstance(loc, dict):
                    errors.append("extraction.location must be an object")
                else:
                    for lk in ["building", "floor", "unit", "area"]:
                        if lk not in loc:
                            errors.append(f"extraction.location.{lk} is required")

    if "routing" in data:
        rt = data["routing"]
        if not isinstance(rt, dict):
            errors.append("routing must be an object")
        else:
            for k in ["decision", "reason", "required_certifications", "priority_within_queue"]:
                if k not in rt:
                    errors.append(f"routing.{k} is required")
            if "decision" in rt and rt["decision"] not in VALID_ROUTING:
                errors.append(f"routing.decision invalid: {rt['decision']}")

    if "clarification" in data:
        cl = data["clarification"]
        if not isinstance(cl, dict):
            errors.append("clarification must be an object")
        else:
            for k in ["needed", "questions", "missing_fields"]:
                if k not in cl:
                    errors.append(f"clarification.{k} is required")

    if "safety" in data:
        sf = data["safety"]
        if not isinstance(sf, dict):
            errors.append("safety must be an object")
        else:
            for k in ["immediate_danger", "safety_instructions", "emergency_services_needed", "regulatory_flags"]:
                if k not in sf:
                    errors.append(f"safety.{k} is required")

    return errors


# ---------------------------------------------------------------------------
# Deterministic fallback
# ---------------------------------------------------------------------------

def _build_fallback_response(
    message_text: str,
    reason: str,
) -> dict[str, Any]:
    """Build a safe deterministic fallback when AI fails."""
    return {
        "triage": {
            "discipline": "GENERAL_MAINTENANCE",
            "urgency": "STANDARD",
            "confidence": 0.0,
            "reasoning": f"AI fallback: {reason}. Defaulting to general/medium for supervisor review.",
        },
        "extraction": {
            "title": "Unclassified issue - requires manual review",
            "description": message_text[:500] if message_text else "No message text available",
            "location": {"building": None, "floor": None, "unit": None, "area": None},
            "reported_symptoms": ["unable to classify automatically"],
            "has_photo": False,
            "is_recurring": False,
            "access_requirements": None,
        },
        "routing": {
            "decision": "NEEDS_CLARIFICATION",
            "reason": f"AI fallback active: {reason}",
            "required_certifications": [],
            "priority_within_queue": "MEDIUM",
        },
        "clarification": {
            "needed": True,
            "questions": ["Could you describe the issue in more detail?"],
            "missing_fields": ["discipline", "urgency", "location"],
        },
        "safety": {
            "immediate_danger": False,
            "safety_instructions": None,
            "emergency_services_needed": False,
            "regulatory_flags": [],
        },
    }


# ---------------------------------------------------------------------------
# Core triage function
# ---------------------------------------------------------------------------

def _load_system_prompt() -> str:
    """Load the LLM system prompt from the prompts directory."""
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "llm-prompts", "intake-triage", "versions", "v2.0.0-system-prompt.txt",
    )
    try:
        with open(prompt_path) as f:
            return f.read()
    except FileNotFoundError:
        log.error("System prompt not found", path=prompt_path)
        return ""


def _call_claude(
    message_text: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """Call Claude API and return parsed JSON response."""
    system_prompt = _load_system_prompt()
    if not system_prompt:
        raise RuntimeError("System prompt file is empty or missing")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": DEFAULT_MAX_TOKENS,
        "temperature": DEFAULT_TEMPERATURE,
        "system": system_prompt,
        "messages": [{"role": "user", "content": message_text}],
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                ANTHROPIC_API_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )
            if resp.status_code == 429:
                delay = int(resp.headers.get("Retry-After", str(2 ** attempt)))
                log.warn("Claude rate limited", attempt=attempt, delay=delay)
                time.sleep(delay)
                continue
            if resp.status_code >= 500 and attempt < MAX_RETRIES:
                log.warn("Claude server error", status=resp.status_code, attempt=attempt)
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            body = resp.json()
            content_text = body["content"][0]["text"]
            return json.loads(content_text)
        except json.JSONDecodeError as exc:
            log.error("Claude returned invalid JSON", exc=exc, attempt=attempt)
            if attempt == MAX_RETRIES:
                raise
            time.sleep(2 ** attempt)
        except Exception as exc:
            log.error("Claude API call failed", exc=exc, attempt=attempt)
            if attempt == MAX_RETRIES:
                raise
            time.sleep(2 ** attempt)

    raise RuntimeError("Claude API exhausted all retries")


def triage_message(
    *,
    message_text: str,
    sender_phone: str = "",
    site_name: str = "",
    has_media: bool = False,
    api_key: str = "",
    model: str = DEFAULT_MODEL,
    job_id: str = "",
    facility_id: str = "",
    message_id: str = "",
) -> TriageResult:
    """Run AI triage on an inbound message.

    Returns a TriageResult with confidence-based routing:
      - confidence >= 0.75 → normal flow
      - confidence <  0.75 → needs_review=True, route to supervisor queue

    On AI failure, returns deterministic fallback (never raises).
    """
    log.info(
        "Triage started",
        job_id=job_id,
        facility_id=facility_id,
        message_id=message_id,
    )

    # ----- Attempt AI classification -----
    raw: dict[str, Any]
    fallback_used = False
    validation_errors: list[str] = []

    try:
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")
        raw = _call_claude(message_text, api_key, model)
    except Exception as exc:
        # DETERMINISTIC FALLBACK: AI failed entirely
        counters.increment("ai_failures")
        log.error(
            "AI triage failed, using deterministic fallback",
            exc=exc,
            job_id=job_id,
            facility_id=facility_id,
            message_id=message_id,
        )
        raw = _build_fallback_response(message_text, str(exc))
        fallback_used = True

    # ----- Validate schema strictly -----
    if not fallback_used:
        validation_errors = validate_triage_response(raw)
        if validation_errors:
            log.warn(
                "AI response failed schema validation, using fallback",
                job_id=job_id,
                validation_errors=validation_errors,
            )
            counters.increment("ai_failures")
            raw = _build_fallback_response(message_text, f"Schema validation failed: {validation_errors}")
            fallback_used = True

    # ----- Extract standardised fields -----
    triage = raw.get("triage", {})
    category = triage.get("discipline") or "GENERAL_MAINTENANCE"
    priority = triage.get("urgency") or "STANDARD"
    confidence_score = float(triage.get("confidence", 0.0))
    reasoning_summary = triage.get("reasoning", "")

    # ----- Confidence-based routing -----
    needs_review = False
    if confidence_score < LOW_CONFIDENCE_THRESHOLD:
        needs_review = True
        counters.increment("low_confidence_jobs")
        log.warn(
            "Low confidence triage — routing to supervisor queue",
            job_id=job_id,
            facility_id=facility_id,
            message_id=message_id,
            confidence_score=confidence_score,
            category=category,
            priority=priority,
        )

    if fallback_used:
        needs_review = True
        counters.increment("ai_fallback_used")

    counters.increment("total_jobs_created")

    log.info(
        "Triage complete",
        job_id=job_id,
        facility_id=facility_id,
        message_id=message_id,
        category=category,
        priority=priority,
        confidence_score=confidence_score,
        needs_review=needs_review,
        fallback_used=fallback_used,
    )

    return TriageResult(
        category=category,
        priority=priority,
        confidence_score=confidence_score,
        reasoning_summary=reasoning_summary,
        needs_review=needs_review,
        raw=raw,
        fallback_used=fallback_used,
        validation_errors=validation_errors,
    )
