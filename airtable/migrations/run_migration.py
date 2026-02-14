#!/usr/bin/env python3
"""
Airtable Migration Runner

Manages schema migrations for the Airtable base. Provides:
- Migration creation from template
- Validation (pre/post checks)
- Application tracking (records in Airtable Schema_Migrations table)
- Rollback support
- Status reporting

Usage:
    python airtable/migrations/run_migration.py new "Description of change"
    python airtable/migrations/run_migration.py validate <migration_id>
    python airtable/migrations/run_migration.py apply <migration_id>
    python airtable/migrations/run_migration.py rollback <migration_id>
    python airtable/migrations/run_migration.py status
    python airtable/migrations/run_migration.py check-drift
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

MIGRATIONS_DIR = Path(__file__).parent
SCHEMA_DIR = MIGRATIONS_DIR.parent / "schema"
SCHEMA_PATH = SCHEMA_DIR / "schema.json"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def load_json(path: Path) -> Optional[dict]:
    """Load a JSON file, returning None on error."""
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"{RED}Error loading {path}: {e}{RESET}", file=sys.stderr)
        return None


def get_migration_files() -> list[Path]:
    """Get all migration files sorted by number."""
    files = sorted(MIGRATIONS_DIR.glob("[0-9]*.json"))
    return files


def get_next_migration_number() -> int:
    """Get the next migration number."""
    files = get_migration_files()
    if not files:
        return 1
    last = files[-1].stem
    match = re.match(r"^(\d+)", last)
    return int(match.group(1)) + 1 if match else 1


def get_applied_migrations_local() -> list[dict]:
    """Read applied migrations from the local tracking file."""
    tracking_path = MIGRATIONS_DIR / ".applied_migrations.json"
    if not tracking_path.exists():
        return []
    data = load_json(tracking_path)
    return data.get("applied", []) if data else []


def record_migration_local(migration_id: str, version: str, status: str, applied_by: str):
    """Record a migration application locally."""
    tracking_path = MIGRATIONS_DIR / ".applied_migrations.json"
    data = {"applied": get_applied_migrations_local()}
    data["applied"].append({
        "migration_id": migration_id,
        "version": version,
        "status": status,
        "applied_by": applied_by,
        "applied_at": datetime.now(timezone.utc).isoformat(),
    })
    with open(tracking_path, "w") as f:
        json.dump(data, f, indent=2)


def cmd_new(description: str):
    """Create a new migration file from template."""
    num = get_next_migration_number()
    slug = re.sub(r"[^a-z0-9]+", "_", description.lower()).strip("_")
    migration_id = f"{num:03d}_{slug}"
    filename = f"{migration_id}.json"

    # Determine version — bump patch from current schema version
    schema = load_json(SCHEMA_PATH)
    current_version = schema.get("version", "1.0.0") if schema else "1.0.0"
    parts = current_version.split(".")
    new_version = f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"

    # Determine dependency
    files = get_migration_files()
    depends_on = files[-1].stem if files else None

    migration = {
        "migration_id": migration_id,
        "version": new_version,
        "description": description,
        "author": os.environ.get("USER", "unknown") + "@safeflow.co.nz",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "depends_on": depends_on,
        "changes": [
            {
                "action": "add_field",
                "table": "TABLE_NAME",
                "field": {
                    "name": "field_name",
                    "field_id": "fldXXX",
                    "type": "singleLineText",
                    "description": "Description of the field"
                }
            }
        ],
        "rollback": [
            {
                "action": "remove_field",
                "table": "TABLE_NAME",
                "field_name": "field_name"
            }
        ],
        "validation": {
            "pre_checks": [
                "table_exists:TABLE_NAME"
            ],
            "post_checks": [
                "field_exists:TABLE_NAME.field_name"
            ]
        }
    }

    path = MIGRATIONS_DIR / filename
    with open(path, "w") as f:
        json.dump(migration, f, indent=2)

    print(f"{GREEN}Created migration:{RESET} {filename}")
    print(f"  Version: {current_version} -> {new_version}")
    print(f"  Depends on: {depends_on}")
    print(f"\n  Edit {path} to define your changes.")


def cmd_validate(migration_id: str):
    """Validate a migration file."""
    # Find migration file
    matches = list(MIGRATIONS_DIR.glob(f"{migration_id}*.json"))
    if not matches:
        matches = list(MIGRATIONS_DIR.glob(f"*{migration_id}*.json"))
    if not matches:
        print(f"{RED}Migration not found: {migration_id}{RESET}")
        sys.exit(1)

    migration_path = matches[0]
    migration = load_json(migration_path)
    if not migration:
        sys.exit(2)

    schema = load_json(SCHEMA_PATH)
    errors = []
    warnings = []

    print(f"\n{BOLD}Validating: {migration_path.name}{RESET}")
    print(f"  Version: {migration.get('version')}")
    print(f"  Description: {migration.get('description')}")

    # Structure validation
    for key in ["migration_id", "version", "description", "changes", "rollback"]:
        if key not in migration:
            errors.append(f"Missing required key: '{key}'")

    # Version format
    version = migration.get("version", "")
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        errors.append(f"Invalid version format: '{version}'")

    # Dependency check
    depends_on = migration.get("depends_on")
    if depends_on:
        dep_files = list(MIGRATIONS_DIR.glob(f"{depends_on}*"))
        if not dep_files:
            errors.append(f"Dependency not found: '{depends_on}'")

    # Changes validation
    valid_actions = {"add_table", "add_field", "modify_field", "remove_field",
                     "add_view", "add_select_choice", "rename_field",
                     "add_relationship", "manual"}
    for i, change in enumerate(migration.get("changes", [])):
        action = change.get("action")
        if action not in valid_actions:
            errors.append(f"changes[{i}]: Invalid action '{action}'")

        if action in ("add_field", "modify_field", "remove_field") and "table" not in change:
            errors.append(f"changes[{i}]: Missing 'table' for action '{action}'")

        # Check table exists in schema
        if schema and action in ("add_field", "modify_field", "remove_field"):
            table_name = change.get("table")
            table_names = {t["name"] for t in schema.get("tables", [])}
            if table_name and table_name not in table_names and action != "add_table":
                warnings.append(f"changes[{i}]: Table '{table_name}' not in current schema")

    # Rollback validation
    if not migration.get("rollback"):
        warnings.append("No rollback instructions defined")

    # Pre/post checks
    validation = migration.get("validation", {})
    if not validation.get("pre_checks"):
        warnings.append("No pre-checks defined")
    if not validation.get("post_checks"):
        warnings.append("No post-checks defined")

    # Report
    if errors:
        print(f"\n  {RED}ERRORS ({len(errors)}):{RESET}")
        for e in errors:
            print(f"    {RED}x{RESET} {e}")

    if warnings:
        print(f"\n  {YELLOW}WARNINGS ({len(warnings)}):{RESET}")
        for w in warnings:
            print(f"    {YELLOW}!{RESET} {w}")

    if not errors:
        print(f"\n  {GREEN}VALIDATION PASSED{RESET}")
        return True
    else:
        print(f"\n  {RED}VALIDATION FAILED{RESET}")
        return False


def cmd_apply(migration_id: str):
    """Record a migration as applied."""
    if not cmd_validate(migration_id):
        print(f"\n{RED}Cannot apply — validation failed{RESET}")
        sys.exit(1)

    matches = list(MIGRATIONS_DIR.glob(f"*{migration_id}*.json"))
    migration = load_json(matches[0])

    # Check not already applied
    applied = get_applied_migrations_local()
    applied_ids = {m["migration_id"] for m in applied}
    if migration["migration_id"] in applied_ids:
        print(f"\n{YELLOW}Migration already applied: {migration['migration_id']}{RESET}")
        sys.exit(0)

    # Check dependency applied
    depends_on = migration.get("depends_on")
    if depends_on and depends_on not in applied_ids:
        print(f"\n{RED}Dependency not yet applied: {depends_on}{RESET}")
        sys.exit(1)

    print(f"\n{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}APPLY MIGRATION: {migration['migration_id']}{RESET}")
    print(f"{CYAN}{'=' * 60}{RESET}")
    print(f"\nChanges to apply:")

    for i, change in enumerate(migration.get("changes", [])):
        action = change.get("action", "unknown")
        table = change.get("table", "N/A")
        field = change.get("field", {}).get("name", change.get("field_name", "N/A"))
        desc = change.get("description", "")
        print(f"  {i + 1}. [{action}] {table}.{field} {f'— {desc}' if desc else ''}")

    print(f"\n{YELLOW}IMPORTANT: Apply these changes manually in Airtable, then confirm.{RESET}")
    print(f"Schema reference: {SCHEMA_PATH}")

    confirm = input(f"\nHave you applied these changes in Airtable? [y/N]: ")
    if confirm.lower() != "y":
        print("Aborted.")
        sys.exit(0)

    # Record application
    applied_by = os.environ.get("USER", "unknown")
    record_migration_local(
        migration_id=migration["migration_id"],
        version=migration["version"],
        status="APPLIED",
        applied_by=applied_by,
    )

    # Update schema version
    schema = load_json(SCHEMA_PATH)
    if schema:
        schema["version"] = migration["version"]
        schema["last_updated"] = datetime.now(timezone.utc).isoformat()
        schema["updated_by"] = applied_by + "@safeflow.co.nz"
        with open(SCHEMA_PATH, "w") as f:
            json.dump(schema, f, indent=2)
        print(f"\n{GREEN}Schema version updated to {migration['version']}{RESET}")

    print(f"{GREEN}Migration recorded: {migration['migration_id']}{RESET}")
    print(f"\nNext steps:")
    print(f"  1. Update schema.json with the new field/table definitions")
    print(f"  2. Run: python airtable/schema/validate_schema.py")
    print(f"  3. Commit changes to git")


def cmd_rollback(migration_id: str):
    """Record a migration rollback."""
    matches = list(MIGRATIONS_DIR.glob(f"*{migration_id}*.json"))
    if not matches:
        print(f"{RED}Migration not found: {migration_id}{RESET}")
        sys.exit(1)

    migration = load_json(matches[0])

    print(f"\n{RED}{'=' * 60}{RESET}")
    print(f"{BOLD}ROLLBACK MIGRATION: {migration['migration_id']}{RESET}")
    print(f"{RED}{'=' * 60}{RESET}")

    rollback = migration.get("rollback", [])
    if not rollback:
        print(f"\n{YELLOW}No rollback instructions found.{RESET}")
        sys.exit(1)

    print(f"\nRollback steps:")
    for i, step in enumerate(rollback):
        if step.get("action") == "manual":
            print(f"\n  {YELLOW}MANUAL ROLLBACK REQUIRED:{RESET}")
            print(f"  {step.get('description', 'No description')}")
            for s in step.get("steps", []):
                print(f"    {s}")
        else:
            action = step.get("action", "unknown")
            table = step.get("table", "N/A")
            field = step.get("field_name", "N/A")
            print(f"  {i + 1}. [{action}] {table}.{field}")

    confirm = input(f"\nHave you completed the rollback in Airtable? [y/N]: ")
    if confirm.lower() != "y":
        print("Aborted.")
        sys.exit(0)

    record_migration_local(
        migration_id=migration["migration_id"],
        version=migration["version"],
        status="ROLLED_BACK",
        applied_by=os.environ.get("USER", "unknown"),
    )

    print(f"{GREEN}Rollback recorded: {migration['migration_id']}{RESET}")


def cmd_status():
    """Show migration status."""
    all_files = get_migration_files()
    applied = get_applied_migrations_local()
    applied_ids = {m["migration_id"]: m for m in applied}

    print(f"\n{BOLD}Migration Status{RESET}")
    print(f"{'=' * 70}")

    schema = load_json(SCHEMA_PATH)
    if schema:
        print(f"  Schema version: {schema.get('version', 'unknown')}")
        print(f"  Last updated:   {schema.get('last_updated', 'unknown')}")
    print()

    for f in all_files:
        migration = load_json(f)
        if not migration:
            continue

        mid = migration["migration_id"]
        version = migration.get("version", "?")

        if mid in applied_ids:
            record = applied_ids[mid]
            status = record.get("status", "APPLIED")
            if status == "APPLIED":
                icon = f"{GREEN}APPLIED{RESET}"
            elif status == "ROLLED_BACK":
                icon = f"{YELLOW}ROLLED_BACK{RESET}"
            else:
                icon = f"{RED}{status}{RESET}"
            when = record.get("applied_at", "")[:19]
            print(f"  [{icon}] {mid} (v{version}) — {when}")
        else:
            print(f"  [{CYAN}PENDING{RESET}] {mid} (v{version})")

    # Summary
    applied_count = sum(1 for m in applied if m.get("status") == "APPLIED")
    pending_count = len(all_files) - len(applied_ids)
    print(f"\n  {applied_count} applied, {pending_count} pending")


def cmd_check_drift():
    """Check if Airtable state matches schema.json (basic checks)."""
    schema = load_json(SCHEMA_PATH)
    if not schema:
        print(f"{RED}Cannot load schema.json{RESET}")
        sys.exit(2)

    print(f"\n{BOLD}Schema Drift Check{RESET}")
    print(f"{'=' * 60}")

    api_key = os.environ.get("AIRTABLE_PERSONAL_ACCESS_TOKEN") or os.environ.get("AIRTABLE_API_KEY")
    base_id = os.environ.get("AIRTABLE_BASE_ID")

    if not api_key or not base_id:
        print(f"\n{YELLOW}Cannot check drift — Airtable credentials not configured.{RESET}")
        print("Set AIRTABLE_PERSONAL_ACCESS_TOKEN and AIRTABLE_BASE_ID environment variables.")
        print("\nFalling back to offline schema validation...")

        # Run offline validation instead
        from validate_schema import validate_schema
        result = validate_schema(schema)
        if result.passed:
            print(f"\n{GREEN}Schema is internally consistent{RESET}")
        else:
            print(f"\n{RED}Schema has internal inconsistencies{RESET}")
        sys.exit(0 if result.passed else 1)

    try:
        import requests
    except ImportError:
        print(f"{RED}requests library required: pip install requests{RESET}")
        sys.exit(2)

    # Fetch base schema from Airtable API
    print("Fetching live schema from Airtable...")
    response = requests.get(
        f"https://api.airtable.com/v0/meta/bases/{base_id}/tables",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=15,
    )

    if response.status_code != 200:
        print(f"{RED}Airtable API error: {response.status_code}{RESET}")
        sys.exit(2)

    live_tables = {t["name"]: t for t in response.json().get("tables", [])}
    expected_tables = {t["name"]: t for t in schema.get("tables", [])}

    drift_found = False

    # Check for missing tables
    for name in expected_tables:
        if name not in live_tables:
            print(f"  {RED}MISSING TABLE:{RESET} {name} (in schema but not in Airtable)")
            drift_found = True

    # Check for extra tables
    for name in live_tables:
        if name not in expected_tables:
            print(f"  {YELLOW}EXTRA TABLE:{RESET} {name} (in Airtable but not in schema)")
            drift_found = True

    # Check fields in matching tables
    for name in expected_tables:
        if name not in live_tables:
            continue

        expected_fields = {f["name"] for f in expected_tables[name].get("fields", [])}
        live_fields = {f["name"] for f in live_tables[name].get("fields", [])}

        missing = expected_fields - live_fields
        extra = live_fields - expected_fields

        for f in missing:
            print(f"  {RED}MISSING FIELD:{RESET} {name}.{f}")
            drift_found = True
        for f in extra:
            print(f"  {YELLOW}EXTRA FIELD:{RESET} {name}.{f}")
            drift_found = True

    if not drift_found:
        print(f"\n{GREEN}No drift detected — Airtable matches schema.json{RESET}")
    else:
        print(f"\n{RED}Drift detected — schema.json and Airtable are out of sync{RESET}")
        print("Create a migration to resolve, or update schema.json to match Airtable.")

    sys.exit(1 if drift_found else 0)


def main():
    if len(sys.argv) < 2:
        print("Usage: run_migration.py <command> [args]")
        print("\nCommands:")
        print("  new <description>     Create a new migration file")
        print("  validate <id>         Validate a migration file")
        print("  apply <id>            Record a migration as applied")
        print("  rollback <id>         Record a rollback")
        print("  status                Show migration status")
        print("  check-drift           Check Airtable vs schema.json")
        sys.exit(0)

    command = sys.argv[1]

    if command == "new":
        if len(sys.argv) < 3:
            print("Usage: run_migration.py new <description>")
            sys.exit(1)
        cmd_new(" ".join(sys.argv[2:]))
    elif command == "validate":
        if len(sys.argv) < 3:
            print("Usage: run_migration.py validate <migration_id>")
            sys.exit(1)
        cmd_validate(sys.argv[2])
    elif command == "apply":
        if len(sys.argv) < 3:
            print("Usage: run_migration.py apply <migration_id>")
            sys.exit(1)
        cmd_apply(sys.argv[2])
    elif command == "rollback":
        if len(sys.argv) < 3:
            print("Usage: run_migration.py rollback <migration_id>")
            sys.exit(1)
        cmd_rollback(sys.argv[2])
    elif command == "status":
        cmd_status()
    elif command == "check-drift":
        cmd_check_drift()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
