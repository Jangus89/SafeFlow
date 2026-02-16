"""Contractor compliance expiry checking and alerting.

Evaluates certification expiry dates (Gas Safe, NICEIC, etc.) and
computes a compliance status for each contractor:

  - COMPLIANT:      All certs valid, earliest expiry > 30 days away
  - EXPIRING_SOON:  At least one cert expires within 30 days
  - EXPIRED:        At least one cert is past its expiry date
  - NOT_VERIFIED:   No expiry dates recorded

Assignment logic uses compliance_status to block EXPIRED contractors.
Scenario F runs daily to refresh statuses and send alerts.

Usage:
    from lib.compliance import check_contractor_compliance, get_expiring_contractors
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any

from lib.logger import get_logger

log = get_logger("compliance")

EXPIRING_SOON_DAYS = 30


def _parse_date(value: Any) -> date | None:
    """Parse a date from ISO string, datetime, or date object."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.strip()).date()
        except ValueError:
            return None
    return None


def _collect_expiry_dates(contractor: dict[str, Any]) -> list[tuple[str, date]]:
    """Return list of (cert_name, expiry_date) pairs from a contractor record."""
    pairs: list[tuple[str, date]] = []
    cert_fields = [
        ("gas_safe_expiry", "Gas Safe"),
        ("niceic_expiry", "NICEIC"),
    ]
    for field, label in cert_fields:
        d = _parse_date(contractor.get(field))
        if d is not None:
            pairs.append((label, d))
    return pairs


def check_contractor_compliance(
    contractor: dict[str, Any],
    *,
    today: date | None = None,
    expiring_soon_days: int = EXPIRING_SOON_DAYS,
) -> dict[str, Any]:
    """Evaluate a single contractor's compliance status.

    Returns:
        {
            "contractor_id": str,
            "company_name": str,
            "compliance_status": "COMPLIANT" | "EXPIRING_SOON" | "EXPIRED" | "NOT_VERIFIED",
            "next_expiry_date": str (ISO) | None,
            "expired_certs": [...],
            "expiring_soon_certs": [...],
        }
    """
    if today is None:
        today = datetime.now(timezone.utc).date()

    cid = contractor.get("contractor_id", contractor.get("id", "unknown"))
    name = contractor.get("company_name", "unknown")

    expiry_dates = _collect_expiry_dates(contractor)

    if not expiry_dates:
        return {
            "contractor_id": cid,
            "company_name": name,
            "compliance_status": "NOT_VERIFIED",
            "next_expiry_date": None,
            "expired_certs": [],
            "expiring_soon_certs": [],
        }

    threshold = today + timedelta(days=expiring_soon_days)
    expired: list[dict[str, Any]] = []
    expiring_soon: list[dict[str, Any]] = []

    for cert_name, expiry in expiry_dates:
        if expiry < today:
            expired.append({"cert": cert_name, "expiry": expiry.isoformat()})
        elif expiry <= threshold:
            expiring_soon.append({"cert": cert_name, "expiry": expiry.isoformat()})

    earliest = min(d for _, d in expiry_dates)

    if expired:
        status = "EXPIRED"
    elif expiring_soon:
        status = "EXPIRING_SOON"
    else:
        status = "COMPLIANT"

    return {
        "contractor_id": cid,
        "company_name": name,
        "compliance_status": status,
        "next_expiry_date": earliest.isoformat(),
        "expired_certs": expired,
        "expiring_soon_certs": expiring_soon,
    }


def get_expiring_contractors(
    contractors: list[dict[str, Any]],
    *,
    today: date | None = None,
    days_ahead: int = EXPIRING_SOON_DAYS,
    include_expired: bool = True,
) -> list[dict[str, Any]]:
    """Return contractors that are EXPIRING_SOON or EXPIRED.

    Only evaluates ACTIVE contractors.
    """
    results: list[dict[str, Any]] = []
    for c in contractors:
        if c.get("status", "").upper() != "ACTIVE":
            continue
        check = check_contractor_compliance(c, today=today, expiring_soon_days=days_ahead)
        if check["compliance_status"] == "EXPIRING_SOON":
            results.append(check)
        elif include_expired and check["compliance_status"] == "EXPIRED":
            results.append(check)
    return results


def build_compliance_alert(
    check_result: dict[str, Any],
) -> dict[str, Any]:
    """Build an alert payload for a contractor with compliance issues.

    Returns a structured alert suitable for WhatsApp notification
    or dashboard display.
    """
    status = check_result["compliance_status"]
    cid = check_result["contractor_id"]
    name = check_result["company_name"]

    if status == "EXPIRED":
        severity = "HIGH"
        message = (
            f"EXPIRED compliance: {name} (#{cid}) has expired certifications: "
            + ", ".join(e["cert"] + " (expired " + e["expiry"] + ")" for e in check_result["expired_certs"])
            + ". Contractor is BLOCKED from new assignments."
        )
    elif status == "EXPIRING_SOON":
        severity = "MEDIUM"
        message = (
            f"Expiring soon: {name} (#{cid}) has certifications expiring within {EXPIRING_SOON_DAYS} days: "
            + ", ".join(e["cert"] + " (expires " + e["expiry"] + ")" for e in check_result["expiring_soon_certs"])
            + ". Please request updated documents."
        )
    else:
        return {
            "alert_required": False,
            "contractor_id": cid,
            "company_name": name,
        }

    log.info(
        "Compliance alert generated",
        contractor_id=cid,
        company_name=name,
        compliance_status=status,
        severity=severity,
    )

    return {
        "alert_required": True,
        "contractor_id": cid,
        "company_name": name,
        "severity": severity,
        "compliance_status": status,
        "type": "COMPLIANCE_EXPIRY",
        "message": message,
        "next_expiry_date": check_result.get("next_expiry_date"),
        "expired_certs": check_result.get("expired_certs", []),
        "expiring_soon_certs": check_result.get("expiring_soon_certs", []),
    }
