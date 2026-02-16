"""SLA Breach Simulation Protection.

Provides:
  - SLA countdown checking for all active work items
  - Automatic escalation when thresholds are crossed
  - Escalation state logging
  - Alert notification trigger payloads

Designed to be called by Scenario D (every 15 min) or as standalone
check against Airtable.

Usage:
    from lib.sla import check_sla_breach, SLA_TIERS

    result = check_sla_breach(
        work_item_id="SF-42",
        urgency="URGENT",
        sla_due_at="2026-02-16T14:00:00Z",
        current_state="IN_PROGRESS",
        escalation_level=0,
    )
    if result["breached"]:
        # trigger escalation
"""

from datetime import datetime, timezone
from typing import Any

from lib.audit import record_transition
from lib.logger import get_logger
from lib.metrics import counters

log = get_logger("sla")

# ---------------------------------------------------------------------------
# SLA Tier definitions
# ---------------------------------------------------------------------------

SLA_TIERS: dict[str, dict[str, Any]] = {
    "EMERGENCY": {
        "response_minutes": 15,
        "resolution_hours": 4,
        "escalation_intervals_minutes": [15, 30, 60],
    },
    "URGENT": {
        "response_minutes": 60,
        "resolution_hours": 24,
        "escalation_intervals_minutes": [60, 120, 240],
    },
    "STANDARD": {
        "response_minutes": 240,
        "resolution_hours": 72,
        "escalation_intervals_minutes": [240, 480, 1440],
    },
    "SCHEDULED": {
        "response_minutes": 1440,
        "resolution_hours": 336,  # 2 weeks
        "escalation_intervals_minutes": [1440, 2880, 4320],
    },
}

# Terminal states — SLA does not apply
TERMINAL_STATES = {"CLOSED", "CANCELLED"}


def check_sla_breach(
    *,
    work_item_id: str,
    urgency: str,
    sla_due_at: str | None,
    current_state: str,
    escalation_level: int = 0,
    facility_id: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Check whether a work item has breached its SLA.

    Returns a dict with:
      - breached: bool
      - minutes_overdue: float (0 if not breached)
      - new_escalation_level: int
      - escalation_required: bool (True if level should increase)
      - alert: dict | None (notification payload if escalation needed)
    """
    now = now or datetime.now(timezone.utc)

    result: dict[str, Any] = {
        "work_item_id": work_item_id,
        "breached": False,
        "minutes_overdue": 0.0,
        "new_escalation_level": escalation_level,
        "escalation_required": False,
        "alert": None,
    }

    # Terminal states — nothing to check
    if current_state in TERMINAL_STATES:
        return result

    # No SLA set — flag it (should not happen in production)
    if not sla_due_at:
        log.warn(
            "Work item has no SLA deadline set",
            job_id=work_item_id,
            facility_id=facility_id,
            current_state=current_state,
        )
        return result

    # Parse deadline
    try:
        deadline = datetime.fromisoformat(sla_due_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        log.error(
            "Invalid sla_due_at format",
            job_id=work_item_id,
            sla_due_at=sla_due_at,
        )
        return result

    # Calculate overdue
    if now <= deadline:
        return result

    minutes_overdue = (now - deadline).total_seconds() / 60
    result["breached"] = True
    result["minutes_overdue"] = round(minutes_overdue, 1)

    # Determine required escalation level
    tier = SLA_TIERS.get(urgency, SLA_TIERS["STANDARD"])
    intervals = tier["escalation_intervals_minutes"]
    new_level = 0
    for i, threshold in enumerate(intervals):
        if minutes_overdue >= threshold:
            new_level = i + 1
    # Beyond defined intervals → level 3+
    if new_level > len(intervals):
        new_level = len(intervals)

    result["new_escalation_level"] = new_level

    if new_level > escalation_level:
        result["escalation_required"] = True
        counters.increment("sla_breaches")
        counters.increment("escalations_triggered")

        severity = "CRITICAL" if urgency == "EMERGENCY" or new_level >= 3 else "HIGH"

        log.error(
            "SLA breach detected — escalating",
            job_id=work_item_id,
            facility_id=facility_id,
            urgency=urgency,
            current_state=current_state,
            minutes_overdue=result["minutes_overdue"],
            previous_level=escalation_level,
            new_level=new_level,
            severity=severity,
        )

        result["alert"] = {
            "type": "SLA_BREACH",
            "severity": severity,
            "work_item_id": work_item_id,
            "urgency": urgency,
            "current_state": current_state,
            "minutes_overdue": result["minutes_overdue"],
            "escalation_level": new_level,
            "message": (
                f"SLA BREACH: Job {work_item_id} ({urgency}) is "
                f"{result['minutes_overdue']:.0f} minutes overdue. "
                f"Escalating to level {new_level}."
            ),
            "timestamp": now.isoformat(),
        }

        # Record the escalation in the audit trail
        record_transition(
            work_item_id=work_item_id,
            previous_state=current_state,
            new_state=f"ESCALATED_L{new_level}",
            triggered_by="system",
            actor_id="sla_monitor",
            notes=f"SLA breached by {result['minutes_overdue']:.0f} min. Level {escalation_level} → {new_level}.",
        )

    return result


def calculate_sla_deadline(
    urgency: str,
    created_at: datetime | None = None,
) -> str:
    """Calculate the SLA deadline for a given urgency tier.

    Returns ISO 8601 datetime string.
    """
    created_at = created_at or datetime.now(timezone.utc)
    tier = SLA_TIERS.get(urgency, SLA_TIERS["STANDARD"])
    from datetime import timedelta
    deadline = created_at + timedelta(hours=tier["resolution_hours"])
    return deadline.isoformat()
