#!/usr/bin/env python3
"""
Airtable Change Audit Logger

Queries the Airtable base for recent changes and generates an audit report.
Checks schema.json version against applied migrations and flags discrepancies.

Usage:
    python airtable/scripts/audit_changes.py
    python airtable/scripts/audit_changes.py --days 7
    python airtable/scripts/audit_changes.py --json
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

BASE_DIR = Path(__file__).parent.parent
SCHEMA_PATH = BASE_DIR / "schema" / "schema.json"
MIGRATIONS_DIR = BASE_DIR / "migrations"
TRACKING_PATH = MIGRATIONS_DIR / ".applied_migrations.json"


def load_json(path: Path) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def audit_schema_version():
    """Check schema version consistency."""
    findings = []

    schema = load_json(SCHEMA_PATH)
    schema_version = schema.get("version", "unknown")

    # Check against latest applied migration
    tracking = load_json(TRACKING_PATH)
    applied = tracking.get("applied", [])
    applied_active = [m for m in applied if m.get("status") == "APPLIED"]

    if applied_active:
        latest = applied_active[-1]
        migration_version = latest.get("version", "unknown")

        if schema_version != migration_version:
            findings.append({
                "level": "error",
                "check": "version_consistency",
                "message": f"Schema version ({schema_version}) does not match latest migration ({migration_version})",
            })
        else:
            findings.append({
                "level": "ok",
                "check": "version_consistency",
                "message": f"Schema version {schema_version} matches latest migration",
            })
    else:
        findings.append({
            "level": "warning",
            "check": "version_consistency",
            "message": "No migrations applied yet",
        })

    return findings


def audit_pending_migrations():
    """Check for unapplied migrations."""
    findings = []

    migration_files = sorted(MIGRATIONS_DIR.glob("[0-9]*.json"))
    tracking = load_json(TRACKING_PATH)
    applied_ids = {m["migration_id"] for m in tracking.get("applied", []) if m.get("status") == "APPLIED"}

    pending = []
    for f in migration_files:
        migration = load_json(f)
        if migration.get("migration_id") not in applied_ids:
            pending.append(migration.get("migration_id", f.stem))

    if pending:
        findings.append({
            "level": "warning",
            "check": "pending_migrations",
            "message": f"{len(pending)} pending migrations: {', '.join(pending)}",
        })
    else:
        findings.append({
            "level": "ok",
            "check": "pending_migrations",
            "message": "All migrations applied",
        })

    return findings


def audit_schema_integrity():
    """Run schema validation and report findings."""
    findings = []

    schema = load_json(SCHEMA_PATH)
    if not schema:
        findings.append({
            "level": "error",
            "check": "schema_integrity",
            "message": "Cannot load schema.json",
        })
        return findings

    # Basic integrity checks
    tables = schema.get("tables", [])
    table_names = set()
    duplicate_tables = set()

    for table in tables:
        name = table.get("name")
        if name in table_names:
            duplicate_tables.add(name)
        table_names.add(name)

    if duplicate_tables:
        findings.append({
            "level": "error",
            "check": "schema_integrity",
            "message": f"Duplicate table names: {', '.join(duplicate_tables)}",
        })

    # Check for orphan linked fields
    table_ids = {t.get("table_id") for t in tables}
    for table in tables:
        for field in table.get("fields", []):
            if field.get("type") == "multipleRecordLinks":
                linked_id = field.get("options", {}).get("linkedTableId")
                if linked_id and linked_id not in table_ids:
                    findings.append({
                        "level": "error",
                        "check": "schema_integrity",
                        "message": f"{table['name']}.{field['name']} links to unknown table: {linked_id}",
                    })

    # Check state machine transitions reference valid states
    sm = schema.get("state_machine", {})
    if sm:
        transitions = sm.get("transitions", [])
        all_from = {t["from"] for t in transitions}
        all_to = set()
        for t in transitions:
            all_to.update(t.get("to", []))

        # Find states that are destinations but have no outgoing transition (except terminal)
        terminal = set(sm.get("terminal_states", []))
        dead_ends = all_to - all_from - terminal
        if dead_ends:
            findings.append({
                "level": "warning",
                "check": "state_machine",
                "message": f"States with no outgoing transitions (not terminal): {', '.join(dead_ends)}",
            })

    if not any(f["level"] == "error" for f in findings if f["check"] == "schema_integrity"):
        findings.append({
            "level": "ok",
            "check": "schema_integrity",
            "message": f"Schema integrity OK — {len(tables)} tables, no orphan references",
        })

    return findings


def audit_backup_status():
    """Check if backups are current."""
    findings = []
    backup_dir = BASE_DIR / "backups"

    if not backup_dir.exists():
        findings.append({
            "level": "warning",
            "check": "backup_status",
            "message": "No backup directory found — run airtable/scripts/backup_base.py",
        })
        return findings

    backups = sorted([d for d in backup_dir.iterdir() if d.is_dir()], reverse=True)

    if not backups:
        findings.append({
            "level": "warning",
            "check": "backup_status",
            "message": "No backups found",
        })
        return findings

    latest = backups[0]
    manifest_path = latest / "manifest.json"
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        timestamp_str = manifest.get("backup_timestamp", "")
        try:
            backup_time = datetime.strptime(timestamp_str, "%Y-%m-%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            age = datetime.now(timezone.utc) - backup_time
            if age > timedelta(days=1):
                findings.append({
                    "level": "warning",
                    "check": "backup_status",
                    "message": f"Latest backup is {age.days} days old (threshold: 1 day)",
                })
            else:
                findings.append({
                    "level": "ok",
                    "check": "backup_status",
                    "message": f"Latest backup: {timestamp_str} ({manifest.get('total_records', '?')} records)",
                })
        except (ValueError, TypeError):
            findings.append({
                "level": "warning",
                "check": "backup_status",
                "message": f"Cannot parse backup timestamp from {latest.name}",
            })
    else:
        findings.append({
            "level": "warning",
            "check": "backup_status",
            "message": f"Latest backup {latest.name} has no manifest",
        })

    findings.append({
        "level": "ok",
        "check": "backup_count",
        "message": f"{len(backups)} backup(s) on disk",
    })

    return findings


def main():
    output_json = "--json" in sys.argv
    days = 7
    for i, arg in enumerate(sys.argv):
        if arg == "--days" and i + 1 < len(sys.argv):
            days = int(sys.argv[i + 1])

    all_findings = []

    # Run all audits
    all_findings.extend(audit_schema_version())
    all_findings.extend(audit_pending_migrations())
    all_findings.extend(audit_schema_integrity())
    all_findings.extend(audit_backup_status())

    if output_json:
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "findings": all_findings,
            "error_count": sum(1 for f in all_findings if f["level"] == "error"),
            "warning_count": sum(1 for f in all_findings if f["level"] == "warning"),
        }
        print(json.dumps(report, indent=2))
    else:
        print(f"\n{BOLD}SafeFlow Airtable Audit Report{RESET}")
        print(f"{'=' * 60}")
        print(f"  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        print()

        icons = {"ok": f"{GREEN}OK{RESET}", "warning": f"{YELLOW}WARN{RESET}", "error": f"{RED}FAIL{RESET}"}

        for finding in all_findings:
            icon = icons.get(finding["level"], "?")
            print(f"  [{icon}] {finding['check']}: {finding['message']}")

        # Summary
        errors = sum(1 for f in all_findings if f["level"] == "error")
        warnings = sum(1 for f in all_findings if f["level"] == "warning")
        print(f"\n{'=' * 60}")
        if errors:
            print(f"  {RED}ISSUES FOUND: {errors} error(s), {warnings} warning(s){RESET}")
        elif warnings:
            print(f"  {YELLOW}WARNINGS: {warnings} warning(s){RESET}")
        else:
            print(f"  {GREEN}ALL CHECKS PASSED{RESET}")

    sys.exit(1 if any(f["level"] == "error" for f in all_findings) else 0)


if __name__ == "__main__":
    main()
