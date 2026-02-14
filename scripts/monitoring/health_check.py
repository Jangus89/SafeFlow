#!/usr/bin/env python3
"""
SafeFlow Health Check Script

Checks the health of all integrated services and reports status.
Designed to be run as a scheduled job (cron) or monitoring check.

Usage:
    python scripts/monitoring/health_check.py
    python scripts/monitoring/health_check.py --json  # Machine-readable output

Exit codes:
    0 - All services healthy
    1 - One or more services degraded
    2 - Critical failure
"""

import json
import os
import sys
import time
from datetime import datetime


def check_whatsapp_api():
    """Check 360dialog WhatsApp API connectivity."""
    try:
        import requests

        api_url = os.environ.get("WHATSAPP_API_URL", "https://waba.360dialog.io/v1")
        api_key = os.environ.get("WHATSAPP_API_KEY")

        if not api_key:
            return {"status": "unknown", "message": "API key not configured"}

        response = requests.get(
            f"{api_url}/configs/webhook",
            headers={"D360-API-KEY": api_key},
            timeout=10,
        )

        if response.status_code == 200:
            return {"status": "healthy", "message": "API responding", "latency_ms": response.elapsed.microseconds // 1000}
        else:
            return {"status": "degraded", "message": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


def check_airtable_api():
    """Check Airtable API connectivity."""
    try:
        import requests

        api_key = os.environ.get("AIRTABLE_PERSONAL_ACCESS_TOKEN") or os.environ.get("AIRTABLE_API_KEY")
        base_id = os.environ.get("AIRTABLE_BASE_ID")

        if not api_key or not base_id:
            return {"status": "unknown", "message": "Credentials not configured"}

        response = requests.get(
            f"https://api.airtable.com/v0/{base_id}/Error%20Log?maxRecords=1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )

        if response.status_code == 200:
            return {"status": "healthy", "message": "API responding", "latency_ms": response.elapsed.microseconds // 1000}
        elif response.status_code == 429:
            return {"status": "degraded", "message": "Rate limited"}
        else:
            return {"status": "unhealthy", "message": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


def check_anthropic_api():
    """Check Claude API connectivity."""
    try:
        import requests

        api_key = os.environ.get("ANTHROPIC_API_KEY")

        if not api_key:
            return {"status": "unknown", "message": "API key not configured"}

        # Minimal API call to verify connectivity
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "ping"}],
            },
            timeout=15,
        )

        if response.status_code == 200:
            return {"status": "healthy", "message": "API responding", "latency_ms": response.elapsed.microseconds // 1000}
        elif response.status_code == 429:
            return {"status": "degraded", "message": "Rate limited"}
        elif response.status_code == 401:
            return {"status": "unhealthy", "message": "Invalid API key"}
        else:
            return {"status": "degraded", "message": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


def check_xero_api():
    """Check Xero API connectivity (token validity)."""
    try:
        import requests

        tenant_id = os.environ.get("XERO_TENANT_ID")

        if not tenant_id:
            return {"status": "unknown", "message": "Xero not configured"}

        # Xero requires OAuth — just check if tenant ID is set
        # Full connectivity check requires valid OAuth token
        return {"status": "unknown", "message": "OAuth token check not implemented — verify manually"}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


def check_error_log():
    """Check recent error rate in Airtable Error Log."""
    try:
        import requests

        api_key = os.environ.get("AIRTABLE_PERSONAL_ACCESS_TOKEN") or os.environ.get("AIRTABLE_API_KEY")
        base_id = os.environ.get("AIRTABLE_BASE_ID")

        if not api_key or not base_id:
            return {"status": "unknown", "message": "Cannot check error log"}

        response = requests.get(
            f"https://api.airtable.com/v0/{base_id}/Error%20Log",
            headers={"Authorization": f"Bearer {api_key}"},
            params={
                "filterByFormula": "AND({Resolved} != TRUE(), IS_AFTER({Timestamp}, DATEADD(NOW(), -1, 'hours')))",
                "maxRecords": 100,
            },
            timeout=10,
        )

        if response.status_code == 200:
            records = response.json().get("records", [])
            count = len(records)
            if count == 0:
                return {"status": "healthy", "message": "No recent errors"}
            elif count < 5:
                return {"status": "degraded", "message": f"{count} unresolved errors in last hour"}
            else:
                return {"status": "unhealthy", "message": f"{count} unresolved errors in last hour"}
        else:
            return {"status": "unknown", "message": f"Cannot query error log: HTTP {response.status_code}"}
    except Exception as e:
        return {"status": "unknown", "message": str(e)}


def main():
    """Run all health checks and report."""
    output_json = "--json" in sys.argv

    checks = {
        "whatsapp_api": check_whatsapp_api,
        "airtable_api": check_airtable_api,
        "anthropic_api": check_anthropic_api,
        "xero_api": check_xero_api,
        "error_log": check_error_log,
    }

    results = {}
    overall_status = "healthy"

    for name, check_fn in checks.items():
        results[name] = check_fn()

        if results[name]["status"] == "unhealthy":
            overall_status = "unhealthy"
        elif results[name]["status"] == "degraded" and overall_status == "healthy":
            overall_status = "degraded"

    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "overall_status": overall_status,
        "checks": results,
    }

    if output_json:
        print(json.dumps(report, indent=2))
    else:
        print(f"\nSafeFlow Health Check — {report['timestamp']}")
        print(f"Overall: {overall_status.upper()}\n")

        status_icons = {"healthy": "●", "degraded": "◐", "unhealthy": "○", "unknown": "?"}

        for name, result in results.items():
            icon = status_icons.get(result["status"], "?")
            print(f"  {icon} {name}: {result['status']} — {result['message']}")

        print()

    # Exit code
    if overall_status == "unhealthy":
        return 2
    elif overall_status == "degraded":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
