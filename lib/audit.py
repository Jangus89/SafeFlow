"""Audit trail layer for SafeFlow state transitions.

Every state change flows through `record_transition` which writes a
structured entry to the Audit_Trail Airtable table and appends to the
work item's state_history JSON field.

Usage:
    from lib.audit import record_transition

    record_transition(
        work_item_id="SF-42",
        previous_state="INTAKE",
        new_state="ASSESSMENT",
        triggered_by="ai",
        actor_id="system",
        notes="Confidence: 0.92",
        airtable_headers=headers,
        airtable_base_url=base_url,
    )
"""

import json
import time
from datetime import datetime, timezone
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

from lib.logger import get_logger
from lib.metrics import counters

log = get_logger("audit")

# Valid triggered_by values
VALID_TRIGGERS = {"ai", "system", "user"}


def record_transition(
    *,
    work_item_id: str,
    previous_state: str | None,
    new_state: str,
    triggered_by: str,
    actor_id: str = "system",
    notes: str = "",
    airtable_headers: dict[str, str] | None = None,
    airtable_base_url: str = "",
) -> dict[str, Any]:
    """Record a state transition in the audit trail.

    Returns the audit entry dict.  If Airtable credentials are provided,
    also persists to the Audit_Trail table.
    """
    if triggered_by not in VALID_TRIGGERS:
        triggered_by = "system"

    timestamp = datetime.now(timezone.utc).isoformat()

    entry: dict[str, Any] = {
        "work_item_id": work_item_id,
        "previous_state": previous_state or "NONE",
        "new_state": new_state,
        "triggered_by": triggered_by,
        "actor_id": actor_id,
        "timestamp": timestamp,
        "notes": notes,
    }

    log.info(
        "State transition recorded",
        job_id=work_item_id,
        previous_state=entry["previous_state"],
        new_state=new_state,
        triggered_by=triggered_by,
    )

    # Persist to Airtable if credentials available
    if airtable_headers and airtable_base_url and requests is not None:
        _persist_to_airtable(entry, airtable_headers, airtable_base_url)

    return entry


def build_state_history_entry(
    *,
    from_state: str | None,
    to_state: str,
    trigger: str,
    actor_id: str = "system",
    actor_role: str = "SYSTEM",
    notes: str = "",
) -> dict[str, Any]:
    """Build a state_history JSON entry for appending to the work item."""
    return {
        "from_state": from_state or "NONE",
        "to_state": to_state,
        "trigger": trigger,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor_id": actor_id,
        "actor_role": actor_role,
        "notes": notes,
    }


def _persist_to_airtable(
    entry: dict[str, Any],
    headers: dict[str, str],
    base_url: str,
) -> None:
    """Write audit entry to the Audit_Trail Airtable table."""
    url = f"{base_url}/Audit_Trail"
    payload = {
        "fields": {
            "work_item_id": entry["work_item_id"],
            "previous_state": entry["previous_state"],
            "new_state": entry["new_state"],
            "triggered_by": entry["triggered_by"],
            "actor_id": entry["actor_id"],
            "transition_timestamp": entry["timestamp"],
            "notes": entry["notes"],
        }
    }
    for attempt in range(1, 4):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            if resp.status_code == 429:
                delay = int(resp.headers.get("Retry-After", "5"))
                log.warn("Audit trail rate limited, retrying", attempt=attempt, delay=delay)
                time.sleep(delay)
                continue
            if resp.status_code >= 500 and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return
        except Exception as exc:
            log.error(
                "Failed to persist audit trail entry",
                exc=exc,
                job_id=entry["work_item_id"],
                attempt=attempt,
            )
            if attempt < 3:
                time.sleep(2 ** attempt)
