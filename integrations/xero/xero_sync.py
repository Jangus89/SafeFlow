#!/usr/bin/env python3
"""Synchronise SafeFlow accepted quotes and payments to Xero.

Queries Airtable for accepted quotes with PENDING payment records,
creates or updates corresponding Xero invoices, and updates Airtable
with the Xero invoice ID and sync status.

Usage:
    python integrations/xero/xero_sync.py
    python integrations/xero/xero_sync.py --dry-run
    python integrations/xero/xero_sync.py --limit 5
    python integrations/xero/xero_sync.py --work-item SF-1042
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: requests package required. Run: pip install requests")
    sys.exit(1)

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from xero_client import XeroApiError, XeroClient, XeroTokenError


# ─── Centralised Structured Logging (via lib.logger) ───────────────────────

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib.logger import get_logger as _get_safeflow_logger  # noqa: E402

logger = logging.getLogger("safeflow.xero.sync")
_sf_log = _get_safeflow_logger("xero.sync")


# ─── Airtable Client ────────────────────────────────────────────────────────

AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "")
AIRTABLE_BASE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}"
AIRTABLE_HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    "Content-Type": "application/json",
}

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0


def airtable_request(
    method: str,
    table: str,
    record_id: str = "",
    params: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Make an Airtable API request with retry logic."""
    path = f"{AIRTABLE_BASE_URL}/{table}"
    if record_id:
        path += f"/{record_id}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.request(
                method, path, headers=AIRTABLE_HEADERS,
                params=params, json=json_body, timeout=30,
            )
            if response.status_code == 429:
                delay = int(response.headers.get("Retry-After", "5"))
                logger.warning("Airtable rate limit hit, waiting %ds", delay)
                time.sleep(delay)
                continue
            if response.status_code >= 500 and attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning("Airtable %d error, retrying in %.1fs", response.status_code, delay)
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as e:
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning("Connection error, retrying in %.1fs: %s", delay, e)
                time.sleep(delay)
                continue
            raise

    return {}


def find_pending_payments() -> list[dict[str, Any]]:
    """Find payment records in PENDING status that need Xero sync."""
    result = airtable_request(
        "GET", "Payments",
        params={
            "filterByFormula": "AND({status} = 'PENDING', {xero_invoice_id} = '')",
            "maxRecords": "100",
        },
    )
    return result.get("records", [])


def get_record(table: str, record_id: str) -> dict[str, Any]:
    """Get a single Airtable record by ID."""
    return airtable_request("GET", table, record_id=record_id)


def update_payment_xero_status(
    payment_id: str,
    xero_invoice_id: str,
    sync_status: str,
    error_message: str = "",
) -> None:
    """Update a payment record with Xero sync information."""
    fields: dict[str, Any] = {
        "xero_invoice_id": xero_invoice_id,
        "xero_sync_status": sync_status,
        "xero_synced_at": datetime.now(timezone.utc).isoformat(),
    }
    if error_message:
        fields["xero_sync_error"] = error_message[:1000]

    airtable_request("PATCH", "Payments", record_id=payment_id, json_body={"fields": fields})


# ─── Sync Logic ──────────────────────────────────────────────────────────────


def sync_payment_to_xero(
    payment: dict[str, Any],
    xero: XeroClient,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Sync a single payment record to Xero.

    Returns:
        Dict with sync result: {success, payment_id, xero_invoice_id, error}
    """
    payment_id = payment["id"]
    fields = payment.get("fields", {})

    result: dict[str, Any] = {
        "payment_id": payment_id,
        "success": False,
        "xero_invoice_id": "",
        "error": "",
    }

    try:
        # Get linked work item
        work_item_ids = fields.get("work_item_id", [])
        if not work_item_ids:
            result["error"] = "No work_item_id linked to payment"
            return result

        work_item = get_record("Work_Items", work_item_ids[0])
        wi_fields = work_item.get("fields", {})

        # Get linked quote
        quote_ids = fields.get("quote_id", [])
        quote_fields: dict[str, Any] = {}
        if quote_ids:
            quote = get_record("Quotes", quote_ids[0])
            quote_fields = quote.get("fields", {})

        # Get linked contractor
        contractor_ids = fields.get("contractor_id", []) or quote_fields.get("contractor_id", [])
        contractor_fields: dict[str, Any] = {}
        if contractor_ids:
            contractor = get_record("Contractors", contractor_ids[0])
            contractor_fields = contractor.get("fields", {})

        if not contractor_fields:
            result["error"] = "No contractor linked to payment or quote"
            return result

        # Build reference for duplicate check
        sf_ref = wi_fields.get("work_item_id", work_item_ids[0])

        if dry_run:
            labour = quote_fields.get("labour_cost", 0)
            materials = quote_fields.get("materials_cost", 0)
            logger.info(
                "[DRY RUN] Would create invoice for SF-%s: £%.2f + £%.2f materials = £%.2f + VAT",
                sf_ref, labour, materials, labour + materials,
            )
            result["success"] = True
            result["xero_invoice_id"] = "DRY_RUN"
            return result

        # Check for existing invoice (idempotency)
        existing = xero.find_invoice_by_reference(f"SF-{sf_ref}")
        if existing:
            logger.info("Invoice already exists for SF-%s, updating payment record", sf_ref)
            update_payment_xero_status(payment_id, existing["InvoiceID"], "SYNCED")
            result["success"] = True
            result["xero_invoice_id"] = existing["InvoiceID"]
            return result

        # Create invoice
        invoice = xero.create_invoice_from_quote(wi_fields, quote_fields, contractor_fields)

        # Update Airtable payment record
        update_payment_xero_status(payment_id, invoice["InvoiceID"], "SYNCED")

        result["success"] = True
        result["xero_invoice_id"] = invoice["InvoiceID"]

    except XeroApiError as e:
        result["error"] = str(e)
        logger.error("Xero API error syncing payment %s: %s", payment_id, e)
        if not dry_run:
            update_payment_xero_status(payment_id, "", "FAILED", str(e))

    except XeroTokenError as e:
        result["error"] = str(e)
        logger.error("Xero token error: %s", e)

    except Exception as e:
        result["error"] = str(e)
        logger.error("Unexpected error syncing payment %s: %s", payment_id, e)
        if not dry_run:
            update_payment_xero_status(payment_id, "", "FAILED", str(e))

    return result


# ─── CLI ─────────────────────────────────────────────────────────────────────


def main() -> None:
    """Entry point for Xero sync."""
    parser = argparse.ArgumentParser(description="Sync SafeFlow payments to Xero")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--limit", type=int, default=0, help="Max payments to sync (0 = all)")
    parser.add_argument("--work-item", type=str, help="Sync a specific work item by ID")
    parser.add_argument("--json", action="store_true", dest="output_json", help="Output results as JSON")
    args = parser.parse_args()

    # Validate environment
    missing_vars = []
    for var in ["AIRTABLE_API_KEY", "AIRTABLE_BASE_ID", "XERO_CLIENT_ID", "XERO_CLIENT_SECRET", "XERO_TENANT_ID"]:
        if not os.environ.get(var):
            missing_vars.append(var)
    if missing_vars:
        logger.error("Missing required environment variables: %s", ", ".join(missing_vars))
        sys.exit(1)

    print("SafeFlow → Xero Payment Sync")
    if args.dry_run:
        print("  Mode: DRY RUN (no changes will be made)")
    print()

    # Initialise Xero client
    try:
        xero = XeroClient()
    except XeroTokenError as e:
        logger.error("Failed to initialise Xero client: %s", e)
        sys.exit(1)

    # Find pending payments
    if args.work_item:
        payments = airtable_request(
            "GET", "Payments",
            params={
                "filterByFormula": f"AND({{status}} = 'PENDING', SEARCH(\"{args.work_item}\", ARRAYJOIN({{work_item_id}}, \",\")))",
                "maxRecords": "10",
            },
        ).get("records", [])
    else:
        payments = find_pending_payments()

    if args.limit > 0:
        payments = payments[:args.limit]

    print(f"Found {len(payments)} pending payment(s) to sync")
    print()

    if not payments:
        print("Nothing to sync.")
        return

    # Sync each payment
    results: list[dict[str, Any]] = []
    success_count = 0
    fail_count = 0

    for i, payment in enumerate(payments):
        print(f"  [{i + 1}/{len(payments)}] Payment {payment['id']}...", end=" ")

        result = sync_payment_to_xero(payment, xero, dry_run=args.dry_run)
        results.append(result)

        if result["success"]:
            success_count += 1
            print(f"OK (invoice: {result['xero_invoice_id']})")
        else:
            fail_count += 1
            print(f"FAILED: {result['error']}")

        time.sleep(0.5)  # Rate limit buffer

    # Summary
    print()
    print("=" * 50)
    print(f"Synced: {success_count}  Failed: {fail_count}  Total: {len(payments)}")

    if args.output_json:
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": args.dry_run,
            "total": len(payments),
            "success": success_count,
            "failed": fail_count,
            "results": results,
        }
        print(json.dumps(report, indent=2))

    sys.exit(1 if fail_count > 0 else 0)


if __name__ == "__main__":
    main()
