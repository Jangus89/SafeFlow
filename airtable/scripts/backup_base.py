#!/usr/bin/env python3
"""
Airtable Base Backup Script

Creates a complete JSON backup of all tables in the Airtable base.
Designed to run on a schedule (daily via cron or Make.com) to maintain
point-in-time recovery capability.

Usage:
    python airtable/scripts/backup_base.py
    python airtable/scripts/backup_base.py --tables Work_Items,Sites
    python airtable/scripts/backup_base.py --output-dir /path/to/backups

Environment:
    AIRTABLE_PERSONAL_ACCESS_TOKEN - Airtable PAT (required)
    AIRTABLE_BASE_ID - Base to backup (required)

Output:
    Creates timestamped backup directory with one JSON file per table
    and a manifest file with metadata.

    backups/
    └── 2026-02-14T100000Z/
        ├── manifest.json
        ├── Work_Items.json
        ├── Sites.json
        ├── Contacts.json
        └── ...
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BACKUP_DIR = Path(__file__).parent.parent / "backups"
SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "schema.json"

# Airtable API rate limit: 5 requests/second
RATE_LIMIT_DELAY = 0.25  # 250ms between requests


def get_credentials() -> tuple[str, str]:
    """Get Airtable credentials from environment."""
    api_key = os.environ.get("AIRTABLE_PERSONAL_ACCESS_TOKEN") or os.environ.get("AIRTABLE_API_KEY")
    base_id = os.environ.get("AIRTABLE_BASE_ID")

    if not api_key:
        print("ERROR: Set AIRTABLE_PERSONAL_ACCESS_TOKEN environment variable", file=sys.stderr)
        sys.exit(1)
    if not base_id:
        print("ERROR: Set AIRTABLE_BASE_ID environment variable", file=sys.stderr)
        sys.exit(1)

    return api_key, base_id


def fetch_table_records(api_key: str, base_id: str, table_name: str) -> list[dict]:
    """Fetch all records from an Airtable table with pagination."""
    import requests

    records = []
    offset = None
    page = 0

    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset

        response = requests.get(
            f"https://api.airtable.com/v0/{base_id}/{table_name}",
            headers={"Authorization": f"Bearer {api_key}"},
            params=params,
            timeout=30,
        )

        if response.status_code == 429:
            # Rate limited — back off and retry
            retry_after = int(response.headers.get("Retry-After", 30))
            print(f"  Rate limited, waiting {retry_after}s...")
            time.sleep(retry_after)
            continue

        if response.status_code != 200:
            print(f"  ERROR fetching {table_name}: HTTP {response.status_code}", file=sys.stderr)
            print(f"  Response: {response.text[:500]}", file=sys.stderr)
            return records

        data = response.json()
        batch = data.get("records", [])
        records.extend(batch)
        page += 1

        offset = data.get("offset")
        if not offset:
            break

        time.sleep(RATE_LIMIT_DELAY)

    return records


def get_table_names(api_key: str, base_id: str) -> list[str]:
    """Get list of tables from Airtable metadata API."""
    import requests

    response = requests.get(
        f"https://api.airtable.com/v0/meta/bases/{base_id}/tables",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=15,
    )

    if response.status_code == 200:
        return [t["name"] for t in response.json().get("tables", [])]

    # Fallback to schema.json
    print("  Could not fetch table list from API, using schema.json")
    schema = load_schema()
    if schema:
        return [t["name"] for t in schema.get("tables", [])]

    return []


def load_schema() -> Optional[dict]:
    """Load schema.json."""
    try:
        with open(SCHEMA_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def run_backup(table_filter: Optional[list[str]] = None, output_dir: Optional[Path] = None):
    """Run a full backup of the Airtable base."""
    api_key, base_id = get_credentials()

    # Create backup directory
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    backup_path = (output_dir or BACKUP_DIR) / timestamp
    backup_path.mkdir(parents=True, exist_ok=True)

    print(f"\nAirtable Backup — {timestamp}")
    print(f"{'=' * 50}")
    print(f"Base ID: {base_id}")
    print(f"Output:  {backup_path}")

    # Get table list
    all_tables = get_table_names(api_key, base_id)
    if table_filter:
        tables = [t for t in all_tables if t in table_filter]
        skipped = set(table_filter) - set(all_tables)
        if skipped:
            print(f"\nWARNING: Tables not found: {', '.join(skipped)}")
    else:
        tables = all_tables

    print(f"\nBacking up {len(tables)} tables...\n")

    manifest = {
        "backup_timestamp": timestamp,
        "base_id": base_id,
        "schema_version": None,
        "tables": {},
        "total_records": 0,
        "duration_seconds": 0,
    }

    schema = load_schema()
    if schema:
        manifest["schema_version"] = schema.get("version")

    start_time = time.time()

    for table_name in tables:
        print(f"  Backing up: {table_name}...", end=" ", flush=True)

        records = fetch_table_records(api_key, base_id, table_name)

        # Write table backup
        table_file = backup_path / f"{table_name}.json"
        with open(table_file, "w") as f:
            json.dump({
                "table_name": table_name,
                "record_count": len(records),
                "backed_up_at": datetime.now(timezone.utc).isoformat(),
                "records": records,
            }, f, indent=2, default=str)

        manifest["tables"][table_name] = {
            "record_count": len(records),
            "file": f"{table_name}.json",
            "size_bytes": table_file.stat().st_size,
        }
        manifest["total_records"] += len(records)

        print(f"{len(records)} records")
        time.sleep(RATE_LIMIT_DELAY)

    # Write manifest
    manifest["duration_seconds"] = round(time.time() - start_time, 1)
    manifest_file = backup_path / "manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)

    # Summary
    print(f"\n{'=' * 50}")
    print(f"Backup complete!")
    print(f"  Tables: {len(tables)}")
    print(f"  Records: {manifest['total_records']}")
    print(f"  Duration: {manifest['duration_seconds']}s")
    print(f"  Location: {backup_path}")

    # Cleanup old backups (keep last 30)
    cleanup_old_backups(output_dir or BACKUP_DIR, keep=30)

    return backup_path


def cleanup_old_backups(backup_dir: Path, keep: int = 30):
    """Remove old backup directories, keeping the most recent N."""
    if not backup_dir.exists():
        return

    backups = sorted([d for d in backup_dir.iterdir() if d.is_dir()], reverse=True)

    if len(backups) <= keep:
        return

    import shutil
    for old_backup in backups[keep:]:
        print(f"  Removing old backup: {old_backup.name}")
        shutil.rmtree(old_backup)


def main():
    table_filter = None
    output_dir = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--tables" and i + 1 < len(args):
            table_filter = [t.strip() for t in args[i + 1].split(",")]
            i += 2
        elif args[i] == "--output-dir" and i + 1 < len(args):
            output_dir = Path(args[i + 1])
            i += 2
        else:
            print(f"Unknown argument: {args[i]}")
            sys.exit(1)

    try:
        import requests  # noqa: F401
    except ImportError:
        print("ERROR: requests library required: pip install requests", file=sys.stderr)
        sys.exit(2)

    run_backup(table_filter=table_filter, output_dir=output_dir)


if __name__ == "__main__":
    main()
