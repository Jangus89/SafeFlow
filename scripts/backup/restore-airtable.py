#!/usr/bin/env python3
"""Restore Airtable tables from a local backup.

Reads backup JSON files and recreates records in Airtable via the API.
Handles batch creation and rate limiting.

Usage:
    python scripts/backup/restore-airtable.py --backup-dir airtable/backups/backup_20260215_100000
    python scripts/backup/restore-airtable.py --backup-dir /path/to/backup --tables Work_Items Sites
    python scripts/backup/restore-airtable.py --backup-dir /path/to/backup --dry-run
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: requests package required. Run: pip install requests")
    sys.exit(1)


AIRTABLE_API_URL = "https://api.airtable.com/v0"
BATCH_SIZE = 10  # Airtable max 10 records per batch create
RATE_LIMIT_DELAY = 0.25


def validate_backup(backup_dir: Path) -> dict[str, Any]:
    """Validate backup directory and manifest."""
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: manifest.json not found in {backup_dir}")
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    print(f"Backup timestamp: {manifest.get('timestamp', 'unknown')}")
    print(f"Base ID: {manifest.get('base_id', 'unknown')}")
    print(f"Status: {manifest.get('status', 'unknown')}")
    print(f"Total records: {manifest.get('total_records', 0)}")
    print()

    # Validate each table file exists
    for table_name, info in manifest.get("tables", {}).items():
        table_file = backup_dir / info.get("file", f"{table_name}.json")
        if not table_file.exists():
            print(f"  WARNING: {table_file} not found")
        else:
            with open(table_file) as f:
                data = json.load(f)
            actual_count = len(data.get("records", []))
            expected_count = info.get("record_count", 0)
            status = "OK" if actual_count == expected_count else "MISMATCH"
            print(f"  [{status}] {table_name}: {actual_count} records")

    return manifest


def restore_table(
    base_id: str,
    table_name: str,
    records: list[dict[str, Any]],
    api_key: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Restore records to an Airtable table in batches."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    total = len(records)
    created = 0
    errors: list[str] = []

    for i in range(0, total, BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        # Prepare records for creation (strip id, createdTime)
        create_records = []
        for record in batch:
            fields = record.get("fields", {})
            create_records.append({"fields": fields})

        if dry_run:
            print(f"    Batch {batch_num}/{total_batches}: "
                  f"would create {len(batch)} records")
            created += len(batch)
            continue

        url = f"{AIRTABLE_API_URL}/{base_id}/{table_name}"
        payload = {"records": create_records}

        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=30
            )
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 30))
                print(f"    Rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after)
                response = requests.post(
                    url, headers=headers, json=payload, timeout=30
                )

            response.raise_for_status()
            created_batch = len(response.json().get("records", []))
            created += created_batch
            print(f"    Batch {batch_num}/{total_batches}: "
                  f"created {created_batch} records ({created}/{total})")

        except Exception as e:
            error_msg = f"Batch {batch_num}: {e}"
            errors.append(error_msg)
            print(f"    ERROR: {error_msg}")

        time.sleep(RATE_LIMIT_DELAY)

    return {"created": created, "total": total, "errors": errors}


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Restore Airtable tables from backup"
    )
    parser.add_argument(
        "--backup-dir", required=True,
        help="Path to backup directory containing manifest.json",
    )
    parser.add_argument(
        "--tables", nargs="+",
        help="Specific tables to restore (default: all)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate and report without making changes",
    )
    parser.add_argument(
        "--confirm", action="store_true",
        help="Skip confirmation prompt",
    )
    args = parser.parse_args()

    api_key = os.environ.get("AIRTABLE_API_KEY")
    base_id = os.environ.get("AIRTABLE_BASE_ID")

    if not api_key:
        print("ERROR: AIRTABLE_API_KEY environment variable not set")
        sys.exit(1)
    if not base_id:
        print("ERROR: AIRTABLE_BASE_ID environment variable not set")
        sys.exit(1)

    backup_dir = Path(args.backup_dir)

    print("SafeFlow Airtable Restore")
    print("=" * 40)
    print(f"Backup: {backup_dir}")
    print(f"Target Base: {base_id}")
    print(f"Dry run: {args.dry_run}")
    print()

    # Validate backup
    manifest = validate_backup(backup_dir)
    print()

    # Determine tables to restore
    available_tables = list(manifest.get("tables", {}).keys())
    tables_to_restore = args.tables if args.tables else available_tables

    if not args.dry_run and not args.confirm:
        print(f"This will create records in {len(tables_to_restore)} table(s).")
        print("WARNING: This does NOT delete existing records first.")
        confirm = input("Type 'RESTORE' to proceed: ")
        if confirm != "RESTORE":
            print("Restore cancelled.")
            sys.exit(0)

    # Restore each table
    total_created = 0
    all_errors: list[str] = []

    for table_name in tables_to_restore:
        print(f"\nRestoring {table_name}...")
        table_info = manifest.get("tables", {}).get(table_name, {})
        table_file = backup_dir / table_info.get("file", f"{table_name}.json")

        if not table_file.exists():
            print(f"  SKIP: file not found")
            continue

        with open(table_file) as f:
            data = json.load(f)

        records = data.get("records", [])
        if not records:
            print(f"  SKIP: no records")
            continue

        result = restore_table(base_id, table_name, records, api_key, args.dry_run)
        total_created += result["created"]
        all_errors.extend(result["errors"])

    print(f"\n{'=' * 40}")
    print(f"Restore {'simulation ' if args.dry_run else ''}complete")
    print(f"Records created: {total_created}")
    if all_errors:
        print(f"Errors: {len(all_errors)}")
        for err in all_errors:
            print(f"  - {err}")

    sys.exit(1 if all_errors else 0)


if __name__ == "__main__":
    main()
