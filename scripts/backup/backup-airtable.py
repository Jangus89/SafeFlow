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
    python scripts/backup/backup-airtable.py --verify
"""

import argparse
import fcntl
import json
import logging
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
    logger = logging.getLogger("backup-airtable")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    return logger


logger = setup_logging()


def log_with_data(level: int, message: str, **kwargs: Any) -> None:
    """Emit a structured log entry with extra data fields."""
    record = logger.makeRecord(
        logger.name, level, "(backup)", 0, message, (), None
    )
    record.extra_data = kwargs  # type: ignore[attr-defined]
    logger.handle(record)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TABLES = [
    "Work_Items", "Sites", "Contractors", "Quotes", "People",
    "Payments", "Interaction_Logs", "Question_Bank", "Errors",
]

AIRTABLE_API_URL = "https://api.airtable.com/v0"
RATE_LIMIT_DELAY = 0.25  # 250ms between requests (5 req/sec limit)
PAGE_SIZE = 100
MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# File lock helpers
# ---------------------------------------------------------------------------

LOCK_FILE_PATH = "/tmp/safeflow_backup_airtable.lock"


def acquire_lock() -> 'int':
    """Acquire an exclusive file lock to prevent concurrent runs.

    Returns the file descriptor so the caller can release it.
    """
    fd = os.open(LOCK_FILE_PATH, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        log_with_data(logging.ERROR, "Another backup process is already running")
        sys.exit(1)
    return fd


def release_lock(fd: int) -> None:
    """Release the file lock."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

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

        # Retry with exponential backoff for ALL HTTP errors
        response = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.get(url, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                break  # success
            except requests.exceptions.HTTPError:
                if response is not None and response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 30))
                    log_with_data(
                        logging.WARNING, "Rate limited",
                        table=table_name, retry_after=retry_after, attempt=attempt,
                    )
                    time.sleep(retry_after)
                elif attempt < MAX_RETRIES:
                    backoff = 2 ** (attempt - 1)
                    status = response.status_code if response is not None else "N/A"
                    log_with_data(
                        logging.WARNING, "HTTP error, retrying",
                        table=table_name, status=status,
                        attempt=attempt, backoff_seconds=backoff,
                    )
                    time.sleep(backoff)
                else:
                    status = response.status_code if response is not None else "N/A"
                    raise RuntimeError(
                        f"Airtable API error for {table_name} after {MAX_RETRIES} "
                        f"retries (HTTP {status})"
                    )
            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES:
                    backoff = 2 ** (attempt - 1)
                    log_with_data(
                        logging.WARNING, "Request error, retrying",
                        table=table_name, error=str(e),
                        attempt=attempt, backoff_seconds=backoff,
                    )
                    time.sleep(backoff)
                else:
                    raise RuntimeError(
                        f"Airtable request failed for {table_name} after "
                        f"{MAX_RETRIES} retries: {e}"
                    ) from e

        if response is None:
            raise RuntimeError(f"No response received for {table_name}")

        data = response.json()
        page_records = data.get("records", [])
        records.extend(page_records)

        log_with_data(
            logging.INFO, "Page fetched",
            table=table_name, page=page,
            page_records=len(page_records), total_records=len(records),
        )

        offset = data.get("offset")
        if not offset:
            break

        time.sleep(RATE_LIMIT_DELAY)

    return records


def verify_table_file(table_file: Path, expected_count: int, table_name: str) -> bool:
    """Re-read a written JSON file and verify the record count matches."""
    try:
        with open(table_file, "r") as f:
            data = json.load(f)
        actual_count = len(data.get("records", []))
        if actual_count != expected_count:
            log_with_data(
                logging.ERROR, "Verification failed: record count mismatch",
                table=table_name, expected=expected_count, actual=actual_count,
                file=str(table_file),
            )
            return False
        log_with_data(
            logging.INFO, "Verification passed",
            table=table_name, record_count=actual_count, file=str(table_file),
        )
        return True
    except Exception as e:
        log_with_data(
            logging.ERROR, "Verification failed: could not read file",
            table=table_name, file=str(table_file), error=str(e),
        )
        return False


def create_backup(
    tables: list[str],
    output_dir: str,
    base_id: str,
    api_key: str,
    verify: bool = False,
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
        log_with_data(logging.INFO, "Starting table backup", table=table_name)
        table_start = time.time()
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

            table_elapsed = round(time.time() - table_start, 3)

            # Optional verification
            verified = True
            if verify:
                verified = verify_table_file(table_file, len(records), table_name)

            manifest["tables"][table_name] = {
                "record_count": len(records),
                "file": f"{table_name}.json",
                "status": "success" if verified else "verification_failed",
                "duration_seconds": table_elapsed,
            }

            if not verified:
                error_msg = f"Verification failed for {table_name}"
                errors.append(error_msg)

            log_with_data(
                logging.INFO, "Table backup complete",
                table=table_name, records=len(records),
                duration_seconds=table_elapsed, verified=verified if verify else "skipped",
            )

            time.sleep(RATE_LIMIT_DELAY)

        except Exception as e:
            table_elapsed = round(time.time() - table_start, 3)
            error_msg = f"Failed to backup {table_name}: {e}"
            log_with_data(
                logging.ERROR, "Table backup failed",
                table=table_name, error=str(e), duration_seconds=table_elapsed,
            )
            errors.append(error_msg)
            manifest["tables"][table_name] = {
                "record_count": 0,
                "status": "error",
                "error": str(e),
                "duration_seconds": table_elapsed,
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
        log_with_data(logging.INFO, "Removed old backup", backup=old_backup.name)

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
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Re-read each exported JSON file after writing and validate record counts match",
    )
    args = parser.parse_args()

    # Check environment variables
    api_key = os.environ.get("AIRTABLE_API_KEY")
    base_id = os.environ.get("AIRTABLE_BASE_ID")

    if not api_key:
        log_with_data(logging.ERROR, "AIRTABLE_API_KEY environment variable not set")
        sys.exit(1)
    if not base_id:
        log_with_data(logging.ERROR, "AIRTABLE_BASE_ID environment variable not set")
        sys.exit(1)

    # Acquire file lock to prevent concurrent runs
    lock_fd = acquire_lock()

    try:
        overall_start = time.time()

        log_with_data(
            logging.INFO, "SafeFlow Airtable Backup starting",
            base_id=base_id, tables=args.tables,
            output_dir=args.output_dir, verify=args.verify,
        )

        # Run backup
        result = create_backup(
            args.tables, args.output_dir, base_id, api_key, verify=args.verify,
        )

        overall_elapsed = round(time.time() - overall_start, 3)

        log_with_data(
            logging.INFO, "Backup complete",
            backup_dir=result["backup_dir"],
            tables_backed_up=result["tables_backed_up"],
            total_tables=len(args.tables),
            total_records=result["total_records"],
            error_count=len(result["errors"]),
            duration_seconds=overall_elapsed,
        )

        if result["errors"]:
            for err in result["errors"]:
                log_with_data(logging.ERROR, "Backup error", detail=err)

        # Cleanup old backups
        removed = cleanup_old_backups(args.output_dir, args.keep)
        if removed > 0:
            log_with_data(logging.INFO, "Old backups cleaned up", removed=removed)

        sys.exit(1 if result["errors"] else 0)

    finally:
        release_lock(lock_fd)


if __name__ == "__main__":
    main()
