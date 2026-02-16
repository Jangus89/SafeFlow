#!/usr/bin/env python3
"""Restore Airtable tables from a local backup.

Reads backup JSON files and recreates records in Airtable via the API.
Handles batch creation, rate limiting, retry with exponential backoff,
and optional clearing of existing records before restore.

Usage:
    python scripts/backup/restore-airtable.py --backup-dir airtable/backups/backup_20260215_100000
    python scripts/backup/restore-airtable.py --backup-dir /path/to/backup --tables Work_Items Sites
    python scripts/backup/restore-airtable.py --backup-dir /path/to/backup --dry-run
    python scripts/backup/restore-airtable.py --backup-dir /path/to/backup --clear-first
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


# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """Format log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data  # type: ignore[attr-defined]
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])
        return json.dumps(log_entry)


def setup_logging() -> logging.Logger:
    """Configure structured JSON logging."""
    logger = logging.getLogger("restore-airtable")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    return logger


logger = setup_logging()


def log_with_data(level: int, message: str, **kwargs: Any) -> None:
    """Emit a structured log entry with extra data fields."""
    record = logger.makeRecord(
        logger.name, level, "(restore)", 0, message, (), None
    )
    record.extra_data = kwargs  # type: ignore[attr-defined]
    logger.handle(record)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AIRTABLE_API_URL = "https://api.airtable.com/v0"
BATCH_SIZE = 10  # Airtable max 10 records per batch create
RATE_LIMIT_DELAY = 0.25
MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _request_with_retry(
    method: str,
    url: str,
    headers: dict[str, str],
    *,
    json_payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    context: str = "",
) -> requests.Response:
    """Execute an HTTP request with exponential backoff retry.

    Retries on 429 (rate-limit) and transient errors up to MAX_RETRIES times.
    """
    response = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.request(
                method, url, headers=headers, json=json_payload,
                params=params, timeout=30,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError:
            if response is not None and response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 30))
                log_with_data(
                    logging.WARNING, "Rate limited",
                    context=context, retry_after=retry_after, attempt=attempt,
                )
                time.sleep(retry_after)
            elif attempt < MAX_RETRIES:
                backoff = 2 ** (attempt - 1)
                status = response.status_code if response is not None else "N/A"
                log_with_data(
                    logging.WARNING, "HTTP error, retrying",
                    context=context, status=status,
                    attempt=attempt, backoff_seconds=backoff,
                )
                time.sleep(backoff)
            else:
                status = response.status_code if response is not None else "N/A"
                raise RuntimeError(
                    f"{context}: API error after {MAX_RETRIES} retries (HTTP {status})"
                )
        except requests.exceptions.RequestException as exc:
            if attempt < MAX_RETRIES:
                backoff = 2 ** (attempt - 1)
                log_with_data(
                    logging.WARNING, "Request error, retrying",
                    context=context, error=str(exc),
                    attempt=attempt, backoff_seconds=backoff,
                )
                time.sleep(backoff)
            else:
                raise RuntimeError(
                    f"{context}: request failed after {MAX_RETRIES} retries: {exc}"
                ) from exc

    raise RuntimeError(f"{context}: no response received")


def validate_backup(backup_dir: Path) -> dict[str, Any]:
    """Validate backup directory and manifest."""
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        log_with_data(logging.ERROR, "manifest.json not found", backup_dir=str(backup_dir))
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    log_with_data(
        logging.INFO, "Backup manifest loaded",
        timestamp=manifest.get("timestamp", "unknown"),
        base_id=manifest.get("base_id", "unknown"),
        status=manifest.get("status", "unknown"),
        total_records=manifest.get("total_records", 0),
    )

    # Validate each table file exists
    for table_name, info in manifest.get("tables", {}).items():
        table_file = backup_dir / info.get("file", f"{table_name}.json")
        if not table_file.exists():
            log_with_data(logging.WARNING, "Table file not found", table=table_name, file=str(table_file))
        else:
            with open(table_file) as f:
                data = json.load(f)
            actual_count = len(data.get("records", []))
            expected_count = info.get("record_count", 0)
            status = "OK" if actual_count == expected_count else "MISMATCH"
            log_with_data(
                logging.INFO, "Table file validated",
                table=table_name, status=status,
                actual_records=actual_count, expected_records=expected_count,
            )

    return manifest


def clear_table(
    base_id: str,
    table_name: str,
    api_key: str,
) -> int:
    """Delete all records from an Airtable table.

    Fetches record IDs in pages and deletes them in batches of 10.
    Returns the number of records deleted.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Collect all record IDs first
    record_ids: list[str] = []
    offset: str | None = None

    while True:
        params: dict[str, Any] = {"pageSize": 100}
        if offset:
            params["offset"] = offset

        url = f"{AIRTABLE_API_URL}/{base_id}/{table_name}"
        response = _request_with_retry(
            "GET", url, headers, params=params,
            context=f"clear {table_name} (list)",
        )
        data = response.json()
        for rec in data.get("records", []):
            rec_id = rec.get("id")
            if rec_id:
                record_ids.append(rec_id)

        offset = data.get("offset")
        if not offset:
            break
        time.sleep(RATE_LIMIT_DELAY)

    if not record_ids:
        log_with_data(logging.INFO, "Table already empty", table=table_name)
        return 0

    # Delete in batches of 10
    deleted = 0
    for i in range(0, len(record_ids), BATCH_SIZE):
        batch_ids = record_ids[i : i + BATCH_SIZE]
        url = f"{AIRTABLE_API_URL}/{base_id}/{table_name}"
        params = {f"records[]": batch_ids}
        # Airtable DELETE uses query params for record IDs
        # Build the param string manually
        query_parts = "&".join(f"records[]={rid}" for rid in batch_ids)
        full_url = f"{url}?{query_parts}"
        _request_with_retry(
            "DELETE", full_url, headers,
            context=f"clear {table_name} (delete batch)",
        )
        deleted += len(batch_ids)
        log_with_data(
            logging.INFO, "Deleted batch",
            table=table_name, deleted=deleted, total=len(record_ids),
            progress_pct=round(deleted / len(record_ids) * 100, 1),
        )
        time.sleep(RATE_LIMIT_DELAY)

    return deleted


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
    table_start = time.time()

    for i in range(0, total, BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        # Prepare records for creation (strip id, createdTime)
        create_records = []
        for record in batch:
            fields = record.get("fields", {})
            create_records.append({"fields": fields})

        progress_pct = round((i + len(batch)) / total * 100, 1)

        if dry_run:
            log_with_data(
                logging.INFO, "Dry-run batch",
                table=table_name, batch=f"{batch_num}/{total_batches}",
                records=len(batch), progress_pct=progress_pct,
            )
            created += len(batch)
            continue

        url = f"{AIRTABLE_API_URL}/{base_id}/{table_name}"
        payload = {"records": create_records}

        try:
            response = _request_with_retry(
                "POST", url, headers, json_payload=payload,
                context=f"restore {table_name} batch {batch_num}",
            )

            created_batch = len(response.json().get("records", []))
            created += created_batch
            progress_pct = round(created / total * 100, 1)
            log_with_data(
                logging.INFO, "Batch created",
                table=table_name, batch=f"{batch_num}/{total_batches}",
                batch_created=created_batch, total_created=created,
                total_records=total, progress_pct=progress_pct,
            )

        except Exception as e:
            error_msg = f"Batch {batch_num}: {e}"
            errors.append(error_msg)
            log_with_data(
                logging.ERROR, "Batch failed",
                table=table_name, batch=f"{batch_num}/{total_batches}",
                error=str(e),
            )

        time.sleep(RATE_LIMIT_DELAY)

    elapsed = round(time.time() - table_start, 3)
    return {"created": created, "total": total, "errors": errors, "duration_seconds": elapsed}


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
    parser.add_argument(
        "--clear-first", action="store_true",
        help="Delete all existing records in target tables before restoring",
    )
    args = parser.parse_args()

    api_key = os.environ.get("AIRTABLE_API_KEY")
    base_id = os.environ.get("AIRTABLE_BASE_ID")

    if not api_key:
        log_with_data(logging.ERROR, "AIRTABLE_API_KEY environment variable not set")
        sys.exit(1)
    if not base_id:
        log_with_data(logging.ERROR, "AIRTABLE_BASE_ID environment variable not set")
        sys.exit(1)

    backup_dir = Path(args.backup_dir)
    overall_start = time.time()

    log_with_data(
        logging.INFO, "SafeFlow Airtable Restore starting",
        backup_dir=str(backup_dir), target_base=base_id,
        dry_run=args.dry_run, clear_first=args.clear_first,
    )

    # Validate backup
    manifest = validate_backup(backup_dir)

    # Determine tables to restore
    available_tables = list(manifest.get("tables", {}).keys())
    tables_to_restore = args.tables if args.tables else available_tables

    if not args.dry_run and not args.confirm:
        action = "CLEAR and restore" if args.clear_first else "create"
        print(f"\nThis will {action} records in {len(tables_to_restore)} table(s).")
        if args.clear_first:
            print("WARNING: --clear-first will DELETE all existing records before restoring.")
        else:
            print("WARNING: This does NOT delete existing records first.")
        confirm = input("Type 'RESTORE' to proceed: ")
        if confirm != "RESTORE":
            log_with_data(logging.INFO, "Restore cancelled by user")
            sys.exit(0)

    # Clear tables first if requested
    if args.clear_first and not args.dry_run:
        log_with_data(logging.INFO, "Clearing existing records from target tables")
        for idx, table_name in enumerate(tables_to_restore):
            table_progress = round((idx + 1) / len(tables_to_restore) * 100, 1)
            log_with_data(
                logging.INFO, "Clearing table",
                table=table_name, progress_pct=table_progress,
            )
            deleted = clear_table(base_id, table_name, api_key)
            log_with_data(
                logging.INFO, "Table cleared",
                table=table_name, records_deleted=deleted,
            )

    # Restore each table
    total_created = 0
    all_errors: list[str] = []

    for idx, table_name in enumerate(tables_to_restore):
        table_progress = round((idx + 1) / len(tables_to_restore) * 100, 1)
        log_with_data(
            logging.INFO, "Restoring table",
            table=table_name,
            table_index=f"{idx + 1}/{len(tables_to_restore)}",
            overall_progress_pct=table_progress,
        )
        table_info = manifest.get("tables", {}).get(table_name, {})
        table_file = backup_dir / table_info.get("file", f"{table_name}.json")

        if not table_file.exists():
            log_with_data(logging.WARNING, "Table file not found, skipping", table=table_name)
            continue

        with open(table_file) as f:
            data = json.load(f)

        records = data.get("records", [])
        if not records:
            log_with_data(logging.INFO, "No records to restore, skipping", table=table_name)
            continue

        result = restore_table(base_id, table_name, records, api_key, args.dry_run)
        total_created += result["created"]
        all_errors.extend(result["errors"])

        log_with_data(
            logging.INFO, "Table restore complete",
            table=table_name, created=result["created"],
            total=result["total"], errors=len(result["errors"]),
            duration_seconds=result["duration_seconds"],
        )

    overall_elapsed = round(time.time() - overall_start, 3)

    log_with_data(
        logging.INFO,
        f"Restore {'simulation ' if args.dry_run else ''}complete",
        total_records_created=total_created,
        tables_restored=len(tables_to_restore),
        error_count=len(all_errors),
        duration_seconds=overall_elapsed,
    )

    if all_errors:
        for err in all_errors:
            log_with_data(logging.ERROR, "Restore error", detail=err)

    sys.exit(1 if all_errors else 0)


if __name__ == "__main__":
    main()
