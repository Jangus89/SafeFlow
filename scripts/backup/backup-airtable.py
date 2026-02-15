#!/usr/bin/env python3
"""Backup all Airtable tables to local JSON files.

Exports all records from each table in the SafeFlow Airtable base,
handling pagination and rate limits. Creates timestamped backup
directories with a manifest file.

Usage:
    python scripts/backup/backup-airtable.py
    python scripts/backup/backup-airtable.py --tables Work_Items Sites
    python scripts/backup/backup-airtable.py --output-dir /path/to/backups
    python scripts/backup/backup-airtable.py --keep 30
"""

import argparse
import json
import os
import shutil
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


DEFAULT_TABLES = [
    "Work_Items", "Sites", "Contractors", "Quotes", "People",
    "Payments", "Interaction_Logs", "Question_Bank", "Errors",
]

AIRTABLE_API_URL = "https://api.airtable.com/v0"
RATE_LIMIT_DELAY = 0.25  # 250ms between requests (5 req/sec limit)
PAGE_SIZE = 100


def get_table_records(
    base_id: str,
    table_name: str,
    api_key: str,
) -> list[dict[str, Any]]:
    """Fetch all records from an Airtable table with pagination."""
    records: list[dict[str, Any]] = []
    offset = None
    page = 0

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    while True:
        page += 1
        params: dict[str, Any] = {"pageSize": PAGE_SIZE}
        if offset:
            params["offset"] = offset

        url = f"{AIRTABLE_API_URL}/{base_id}/{table_name}"

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                # Rate limited - wait and retry
                retry_after = int(response.headers.get("Retry-After", 30))
                print(f"    Rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after)
                continue
            raise RuntimeError(f"Airtable API error for {table_name}: {e}") from e

        data = response.json()
        page_records = data.get("records", [])
        records.extend(page_records)

        print(f"    Page {page}: {len(page_records)} records "
              f"(total: {len(records)})")

        offset = data.get("offset")
        if not offset:
            break

        time.sleep(RATE_LIMIT_DELAY)

    return records


def create_backup(
    tables: list[str],
    output_dir: str,
    base_id: str,
    api_key: str,
) -> dict[str, Any]:
    """Create a full backup of specified tables."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(output_dir) / f"backup_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_id": base_id,
        "tables": {},
        "status": "in_progress",
    }

    total_records = 0
    errors: list[str] = []

    for table_name in tables:
        print(f"\n  Backing up {table_name}...")
        try:
            records = get_table_records(base_id, table_name, api_key)
            total_records += len(records)

            table_file = backup_dir / f"{table_name}.json"
            with open(table_file, "w") as f:
                json.dump(
                    {"table": table_name, "record_count": len(records), "records": records},
                    f,
                    indent=2,
                )

            manifest["tables"][table_name] = {
                "record_count": len(records),
                "file": f"{table_name}.json",
                "status": "success",
            }

            time.sleep(RATE_LIMIT_DELAY)

        except Exception as e:
            error_msg = f"Failed to backup {table_name}: {e}"
            print(f"    ERROR: {error_msg}")
            errors.append(error_msg)
            manifest["tables"][table_name] = {
                "record_count": 0,
                "status": "error",
                "error": str(e),
            }

    manifest["total_records"] = total_records
    manifest["status"] = "completed" if not errors else "completed_with_errors"
    manifest["errors"] = errors

    # Write manifest
    manifest_file = backup_dir / "manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)

    return {
        "backup_dir": str(backup_dir),
        "total_records": total_records,
        "tables_backed_up": len(tables) - len(errors),
        "errors": errors,
    }


def cleanup_old_backups(output_dir: str, keep: int) -> int:
    """Remove old backups, keeping the most recent N."""
    backup_path = Path(output_dir)
    if not backup_path.exists():
        return 0

    backups = sorted(
        [d for d in backup_path.iterdir() if d.is_dir() and d.name.startswith("backup_")],
        key=lambda d: d.name,
        reverse=True,
    )

    removed = 0
    for old_backup in backups[keep:]:
        shutil.rmtree(old_backup)
        removed += 1
        print(f"  Removed old backup: {old_backup.name}")

    return removed


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Backup Airtable tables to local JSON files"
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        default=DEFAULT_TABLES,
        help=f"Tables to backup (default: all {len(DEFAULT_TABLES)} tables)",
    )
    parser.add_argument(
        "--output-dir",
        default="airtable/backups",
        help="Output directory for backups (default: airtable/backups)",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=30,
        help="Number of backups to keep (default: 30)",
    )
    args = parser.parse_args()

    # Check environment variables
    api_key = os.environ.get("AIRTABLE_API_KEY")
    base_id = os.environ.get("AIRTABLE_BASE_ID")

    if not api_key:
        print("ERROR: AIRTABLE_API_KEY environment variable not set")
        sys.exit(1)
    if not base_id:
        print("ERROR: AIRTABLE_BASE_ID environment variable not set")
        sys.exit(1)

    print("SafeFlow Airtable Backup")
    print("=" * 40)
    print(f"Base ID: {base_id}")
    print(f"Tables:  {', '.join(args.tables)}")
    print(f"Output:  {args.output_dir}")

    # Run backup
    result = create_backup(args.tables, args.output_dir, base_id, api_key)

    print(f"\n{'=' * 40}")
    print(f"Backup complete: {result['backup_dir']}")
    print(f"Tables: {result['tables_backed_up']}/{len(args.tables)}")
    print(f"Total records: {result['total_records']}")

    if result["errors"]:
        print(f"Errors: {len(result['errors'])}")
        for err in result["errors"]:
            print(f"  - {err}")

    # Cleanup old backups
    removed = cleanup_old_backups(args.output_dir, args.keep)
    if removed > 0:
        print(f"Cleaned up {removed} old backup(s)")

    sys.exit(1 if result["errors"] else 0)


if __name__ == "__main__":
    main()
