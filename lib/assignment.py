"""Hardened contractor / engineer assignment logic.

Matching considers:
  1. Skill (discipline match)
  2. Availability (status=ACTIVE, emergency_available for EMERGENCY)
  3. Current open jobs count (lighter workload preferred)

Sorting is deterministic — no randomness.
When no valid contractor is found, escalates with full logging.

Usage:
    from lib.assignment import find_best_contractor

    result = find_best_contractor(
        contractors=contractor_list,
        discipline="PLUMBING",
        urgency="URGENT",
        site_postcode="SW1",
        job_id="SF-42",
    )
    if result["assigned"]:
        contractor = result["contractor"]
    else:
        escalation = result["escalation"]
"""

from datetime import datetime, timezone
from typing import Any

from lib.fallbacks import handle_contractor_match_failure
from lib.logger import get_logger
from lib.metrics import counters

log = get_logger("assignment")


def find_best_contractor(
    *,
    contractors: list[dict[str, Any]],
    discipline: str,
    urgency: str = "STANDARD",
    site_postcode: str = "",
    job_id: str = "",
    facility_id: str = "",
) -> dict[str, Any]:
    """Find the best available contractor for a job.

    Filters:
      1. status == "ACTIVE"
      2. discipline in trade_disciplines
      3. If EMERGENCY: emergency_available == True
      4. If site_postcode: coverage_postcodes overlap

    Sorting (deterministic, no randomness):
      1. Rating (descending) — higher is better
      2. Average response time (ascending) — faster is better
      3. Current open jobs (ascending) — lighter workload preferred
      4. Contractor ID (ascending) — tiebreaker for full determinism

    Returns:
      {
        "assigned": True/False,
        "contractor": {...} or None,
        "candidates_evaluated": int,
        "rejection_reasons": [...],
        "escalation": {...} or None,   # only if assigned=False
      }
    """
    log.info(
        "Contractor search started",
        job_id=job_id,
        facility_id=facility_id,
        discipline=discipline,
        urgency=urgency,
        site_postcode=site_postcode,
        total_contractors=len(contractors),
    )

    candidates: list[dict[str, Any]] = []
    rejection_reasons: list[str] = []

    for c in contractors:
        cid = c.get("contractor_id", c.get("id", "unknown"))
        name = c.get("company_name", "unknown")

        # Filter 1: Active status
        if c.get("status", "").upper() != "ACTIVE":
            rejection_reasons.append(f"{name} (#{cid}): status={c.get('status')}")
            continue

        # Filter 2: Discipline match
        trades = c.get("trade_disciplines", [])
        if isinstance(trades, str):
            trades = [t.strip() for t in trades.split(",")]
        if discipline not in trades:
            rejection_reasons.append(f"{name} (#{cid}): discipline mismatch ({trades})")
            continue

        # Filter 3: Emergency availability
        if urgency == "EMERGENCY" and not c.get("emergency_available", False):
            rejection_reasons.append(f"{name} (#{cid}): not emergency_available")
            continue

        # Filter 4: Postcode coverage (if specified)
        if site_postcode:
            coverage_raw = c.get("coverage_postcodes", "")
            if isinstance(coverage_raw, str):
                coverage = [p.strip().upper() for p in coverage_raw.split(",") if p.strip()]
            else:
                coverage = [str(p).strip().upper() for p in coverage_raw]
            if coverage:
                prefix = site_postcode.upper()
                if not any(prefix.startswith(cov) for cov in coverage):
                    rejection_reasons.append(f"{name} (#{cid}): postcode {site_postcode} not in coverage {coverage}")
                    continue

        candidates.append(c)

    log.info(
        "Contractor filtering complete",
        job_id=job_id,
        candidates=len(candidates),
        rejected=len(rejection_reasons),
    )

    if not candidates:
        log.warn(
            "No matching contractors found",
            job_id=job_id,
            facility_id=facility_id,
            discipline=discipline,
            urgency=urgency,
            rejection_reasons=rejection_reasons[:10],  # limit log size
        )
        escalation = handle_contractor_match_failure(
            job_id=job_id,
            facility_id=facility_id,
            discipline=discipline,
            urgency=urgency,
            reason=f"No active contractors match: {discipline}, {urgency}, postcode={site_postcode}",
        )
        return {
            "assigned": False,
            "contractor": None,
            "candidates_evaluated": len(contractors),
            "rejection_reasons": rejection_reasons,
            "escalation": escalation,
        }

    # Deterministic sort — NO randomness
    def _sort_key(c: dict[str, Any]) -> tuple:
        rating = -(c.get("rating", 0) or 0)              # descending
        response_time = c.get("average_response_hours", 999) or 999  # ascending
        open_jobs = c.get("current_open_jobs", 0) or 0    # ascending
        cid = c.get("contractor_id", c.get("id", 0)) or 0  # ascending tiebreaker
        return (rating, response_time, open_jobs, cid)

    candidates.sort(key=_sort_key)

    best = candidates[0]
    best_id = best.get("contractor_id", best.get("id", "unknown"))
    best_name = best.get("company_name", "unknown")

    log.info(
        "Contractor assigned",
        job_id=job_id,
        facility_id=facility_id,
        contractor_id=best_id,
        contractor_name=best_name,
        rating=best.get("rating"),
        response_hours=best.get("average_response_hours"),
        open_jobs=best.get("current_open_jobs", 0),
    )

    return {
        "assigned": True,
        "contractor": best,
        "candidates_evaluated": len(contractors),
        "rejection_reasons": rejection_reasons,
        "escalation": None,
    }
