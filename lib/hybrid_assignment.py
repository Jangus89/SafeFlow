"""Hybrid assignment logic — internal engineers vs external contractors.

During ASSESSMENT, the system first evaluates whether a job is suitable
for an internal engineer (simpler, lower cost, standard trades). If so,
it attempts to match from the Engineers table. If no internal match or
the job is complex/specialist, it falls through to external contractor
assignment.

Internal engineers can escalate to RFQ by sending the "RFQ" command,
which notifies the property manager for approval.

Usage:
    from lib.hybrid_assignment import (
        evaluate_internal_suitability,
        find_best_engineer,
        build_rfq_escalation,
    )
"""

from typing import Any

from lib.logger import get_logger
from lib.metrics import counters

log = get_logger("hybrid_assignment")

# Disciplines where internal engineers are typically available
INTERNAL_DISCIPLINES = {
    "PLUMBING",
    "ELECTRICAL",
    "GENERAL_MAINTENANCE",
    "HVAC",
    "FIRE_SAFETY",
    "GAS_SAFE",
}

# If estimated cost exceeds this, prefer external contractor
DEFAULT_COST_THRESHOLD = 500.0

# Urgencies where internal is preferred (faster response)
INTERNAL_PREFERRED_URGENCIES = {"EMERGENCY", "URGENT"}


def evaluate_internal_suitability(
    *,
    category: str,
    urgency: str,
    estimated_cost: float | None = None,
    cost_threshold: float = DEFAULT_COST_THRESHOLD,
) -> dict[str, Any]:
    """Evaluate whether a job should be assigned to an internal engineer.

    This is the deterministic fallback used when the LLM decision is
    unavailable. The LLM-based decision (module 11d in Scenario B) takes
    precedence when available.

    Returns:
        {
            "use_internal": bool,
            "reason": str,
        }
    """
    discipline = category.upper().strip()

    # Rule 1: Discipline must be one we have internal capability for
    if discipline not in INTERNAL_DISCIPLINES:
        return {
            "use_internal": False,
            "reason": f"Discipline {discipline} requires specialist external contractor",
        }

    # Rule 2: Emergency/Urgent jobs prefer internal (faster mobilisation)
    if urgency.upper() in INTERNAL_PREFERRED_URGENCIES:
        return {
            "use_internal": True,
            "reason": f"{urgency} job — internal engineer preferred for faster response",
        }

    # Rule 3: If cost exceeds threshold, prefer external
    if estimated_cost is not None and estimated_cost > cost_threshold:
        return {
            "use_internal": False,
            "reason": f"Estimated cost £{estimated_cost:.0f} exceeds internal threshold £{cost_threshold:.0f}",
        }

    # Rule 4: Standard jobs in supported disciplines → internal
    return {
        "use_internal": True,
        "reason": f"Standard {discipline} job suitable for internal engineer",
    }


def parse_llm_assignment_decision(raw: str | dict[str, Any]) -> dict[str, Any] | None:
    """Parse the LLM's internal/external assignment decision.

    Expected JSON: {"use_internal": bool, "reason": str}
    Returns None if parsing fails.
    """
    import json

    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, str):
        try:
            data = json.loads(raw.strip())
        except (json.JSONDecodeError, ValueError):
            log.warn("Failed to parse LLM assignment decision", raw_preview=raw[:200])
            return None
    else:
        return None

    if "use_internal" not in data or not isinstance(data["use_internal"], bool):
        log.warn("LLM assignment decision missing 'use_internal' boolean")
        return None

    if "reason" not in data or not isinstance(data["reason"], str):
        log.warn("LLM assignment decision missing 'reason' string")
        return None

    return data


def find_best_engineer(
    *,
    engineers: list[dict[str, Any]],
    discipline: str,
    job_id: str = "",
) -> dict[str, Any]:
    """Find the best available internal engineer for a job.

    Filters:
      1. status == "AVAILABLE" or "ON_JOB" with capacity
      2. discipline in trade_disciplines
      3. current_open_jobs < max_concurrent_jobs

    Sorting (deterministic):
      1. Rating (descending)
      2. Current open jobs (ascending)
      3. Engineer ID (ascending tiebreaker)

    Returns:
        {
            "matched": True/False,
            "engineer": {...} or None,
            "candidates_evaluated": int,
            "rejection_reasons": [...],
        }
    """
    log.info(
        "Engineer search started",
        job_id=job_id,
        discipline=discipline,
        total_engineers=len(engineers),
    )

    candidates: list[dict[str, Any]] = []
    rejection_reasons: list[str] = []

    for e in engineers:
        eid = e.get("engineer_id", e.get("id", "unknown"))
        name = e.get("name", "unknown")

        # Filter 1: Available status
        status = e.get("status", "").upper()
        if status not in ("AVAILABLE", "ON_JOB"):
            rejection_reasons.append(f"{name} (#{eid}): status={status}")
            continue

        # Filter 2: Discipline match
        trades = e.get("trade_disciplines", [])
        if isinstance(trades, str):
            trades = [t.strip() for t in trades.split(",")]
        if discipline not in trades:
            rejection_reasons.append(f"{name} (#{eid}): discipline mismatch ({trades})")
            continue

        # Filter 3: Capacity check
        current = e.get("current_open_jobs", 0) or 0
        max_jobs = e.get("max_concurrent_jobs", 5) or 5
        if current >= max_jobs:
            rejection_reasons.append(f"{name} (#{eid}): at capacity ({current}/{max_jobs})")
            continue

        candidates.append(e)

    log.info(
        "Engineer filtering complete",
        job_id=job_id,
        candidates=len(candidates),
        rejected=len(rejection_reasons),
    )

    if not candidates:
        log.info(
            "No matching internal engineers — will fall through to external",
            job_id=job_id,
            discipline=discipline,
        )
        return {
            "matched": False,
            "engineer": None,
            "candidates_evaluated": len(engineers),
            "rejection_reasons": rejection_reasons,
        }

    # Deterministic sort
    def _sort_key(e: dict[str, Any]) -> tuple:
        rating = -(e.get("rating", 0) or 0)
        open_jobs = e.get("current_open_jobs", 0) or 0
        eid = e.get("engineer_id", e.get("id", 0)) or 0
        return (rating, open_jobs, eid)

    candidates.sort(key=_sort_key)

    best = candidates[0]
    best_id = best.get("engineer_id", best.get("id", "unknown"))
    best_name = best.get("name", "unknown")

    log.info(
        "Internal engineer matched",
        job_id=job_id,
        engineer_id=best_id,
        engineer_name=best_name,
        rating=best.get("rating"),
        open_jobs=best.get("current_open_jobs", 0),
    )

    return {
        "matched": True,
        "engineer": best,
        "candidates_evaluated": len(engineers),
        "rejection_reasons": rejection_reasons,
    }


def build_rfq_escalation(
    *,
    job_id: str,
    engineer_id: str,
    engineer_name: str,
    rfq_reason: str,
    job_title: str = "",
    job_category: str = "",
) -> dict[str, Any]:
    """Build an RFQ escalation payload for the property manager.

    Called when an internal engineer sends the RFQ command, indicating
    the job needs external quotes (too complex, specialist tools, etc.).

    Returns a payload suitable for creating an Escalations record and
    notifying the PM via Scenario C.
    """
    log.info(
        "RFQ escalation triggered",
        job_id=job_id,
        engineer_id=engineer_id,
        engineer_name=engineer_name,
        rfq_reason=rfq_reason,
    )

    counters.increment("rfq_escalations")

    return {
        "escalation_type": "RFQ",
        "work_item_id": job_id,
        "triggered_by": "engineer",
        "reason": f"Internal engineer {engineer_name} (#{engineer_id}) requests external quotes: {rfq_reason}",
        "rfq_reason": rfq_reason,
        "status": "OPEN",
        "target_state": "RFQ_PENDING",
        "notification": {
            "message": (
                f"RFQ Request for Job {job_id}"
                + (f" ({job_title})" if job_title else "")
                + f"\n\nEngineer {engineer_name} has requested external quotes."
                + f"\nReason: {rfq_reason}"
                + (f"\nCategory: {job_category}" if job_category else "")
                + "\n\nPlease approve or reject this RFQ request."
            ),
            "severity": "MEDIUM",
        },
    }
