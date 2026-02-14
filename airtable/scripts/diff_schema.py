#!/usr/bin/env python3
"""
Airtable Schema Diff Tool

Compares two schema versions and reports differences. Used for:
- Reviewing changes before migration
- Detecting drift between environments
- Generating migration files from schema changes

Usage:
    python airtable/scripts/diff_schema.py <old_schema.json> <new_schema.json>
    python airtable/scripts/diff_schema.py --live  # Compare schema.json vs live Airtable
    python airtable/scripts/diff_schema.py --json   # Machine-readable output
"""

import json
import sys
from pathlib import Path
from typing import Any, Optional

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def load_json(path: str) -> Optional[dict]:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading {path}: {e}", file=sys.stderr)
        return None


class SchemaDiff:
    def __init__(self):
        self.added_tables: list[str] = []
        self.removed_tables: list[str] = []
        self.added_fields: list[dict] = []
        self.removed_fields: list[dict] = []
        self.modified_fields: list[dict] = []
        self.added_views: list[dict] = []
        self.removed_views: list[dict] = []
        self.version_change: Optional[tuple[str, str]] = None

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added_tables or self.removed_tables
            or self.added_fields or self.removed_fields
            or self.modified_fields
            or self.added_views or self.removed_views
            or self.version_change
        )

    def to_dict(self) -> dict:
        return {
            "has_changes": self.has_changes,
            "version_change": self.version_change,
            "summary": {
                "tables_added": len(self.added_tables),
                "tables_removed": len(self.removed_tables),
                "fields_added": len(self.added_fields),
                "fields_removed": len(self.removed_fields),
                "fields_modified": len(self.modified_fields),
                "views_added": len(self.added_views),
                "views_removed": len(self.removed_views),
            },
            "added_tables": self.added_tables,
            "removed_tables": self.removed_tables,
            "added_fields": self.added_fields,
            "removed_fields": self.removed_fields,
            "modified_fields": self.modified_fields,
            "added_views": self.added_views,
            "removed_views": self.removed_views,
        }

    def to_migration_changes(self) -> list[dict]:
        """Generate migration change entries from this diff."""
        changes = []

        for table in self.added_tables:
            changes.append({"action": "add_table", "table": table})

        for table in self.removed_tables:
            changes.append({"action": "remove_table", "table": table})

        for field in self.added_fields:
            changes.append({
                "action": "add_field",
                "table": field["table"],
                "field": field["field"],
            })

        for field in self.removed_fields:
            changes.append({
                "action": "remove_field",
                "table": field["table"],
                "field_name": field["field_name"],
            })

        for field in self.modified_fields:
            changes.append({
                "action": "modify_field",
                "table": field["table"],
                "field_name": field["field_name"],
                "changes": field["changes"],
            })

        return changes


def diff_schemas(old: dict, new: dict) -> SchemaDiff:
    """Compare two schema definitions and return differences."""
    diff = SchemaDiff()

    # Version change
    old_version = old.get("version")
    new_version = new.get("version")
    if old_version != new_version:
        diff.version_change = (old_version, new_version)

    # Index tables by name
    old_tables = {t["name"]: t for t in old.get("tables", [])}
    new_tables = {t["name"]: t for t in new.get("tables", [])}

    # Added/removed tables
    diff.added_tables = [n for n in new_tables if n not in old_tables]
    diff.removed_tables = [n for n in old_tables if n not in new_tables]

    # Compare fields in tables that exist in both
    common_tables = set(old_tables.keys()) & set(new_tables.keys())

    for table_name in common_tables:
        old_fields = {f["name"]: f for f in old_tables[table_name].get("fields", [])}
        new_fields = {f["name"]: f for f in new_tables[table_name].get("fields", [])}

        # Added fields
        for fname in new_fields:
            if fname not in old_fields:
                diff.added_fields.append({
                    "table": table_name,
                    "field_name": fname,
                    "field": new_fields[fname],
                })

        # Removed fields
        for fname in old_fields:
            if fname not in new_fields:
                diff.removed_fields.append({
                    "table": table_name,
                    "field_name": fname,
                })

        # Modified fields
        for fname in old_fields:
            if fname in new_fields:
                old_f = old_fields[fname]
                new_f = new_fields[fname]

                changes = {}
                for key in set(list(old_f.keys()) + list(new_f.keys())):
                    if key in ("field_id",):  # skip ID comparisons
                        continue
                    old_val = old_f.get(key)
                    new_val = new_f.get(key)
                    if old_val != new_val:
                        changes[key] = {"old": old_val, "new": new_val}

                if changes:
                    diff.modified_fields.append({
                        "table": table_name,
                        "field_name": fname,
                        "changes": changes,
                    })

        # Views
        old_views = {v["name"]: v for v in old_tables[table_name].get("views", [])}
        new_views = {v["name"]: v for v in new_tables[table_name].get("views", [])}

        for vname in new_views:
            if vname not in old_views:
                diff.added_views.append({"table": table_name, "view_name": vname})

        for vname in old_views:
            if vname not in new_views:
                diff.removed_views.append({"table": table_name, "view_name": vname})

    return diff


def print_diff(diff: SchemaDiff):
    """Pretty-print the schema diff."""
    if not diff.has_changes:
        print(f"\n{GREEN}No differences found.{RESET}")
        return

    print(f"\n{BOLD}Schema Diff{RESET}")
    print("=" * 60)

    if diff.version_change:
        old, new = diff.version_change
        print(f"\n  Version: {old} -> {new}")

    if diff.added_tables:
        print(f"\n  {GREEN}Tables Added ({len(diff.added_tables)}):{RESET}")
        for t in diff.added_tables:
            print(f"    {GREEN}+ {t}{RESET}")

    if diff.removed_tables:
        print(f"\n  {RED}Tables Removed ({len(diff.removed_tables)}):{RESET}")
        for t in diff.removed_tables:
            print(f"    {RED}- {t}{RESET}")

    if diff.added_fields:
        print(f"\n  {GREEN}Fields Added ({len(diff.added_fields)}):{RESET}")
        for f in diff.added_fields:
            ftype = f["field"].get("type", "?")
            print(f"    {GREEN}+ {f['table']}.{f['field_name']}{RESET} ({ftype})")

    if diff.removed_fields:
        print(f"\n  {RED}Fields Removed ({len(diff.removed_fields)}):{RESET}")
        for f in diff.removed_fields:
            print(f"    {RED}- {f['table']}.{f['field_name']}{RESET}")

    if diff.modified_fields:
        print(f"\n  {YELLOW}Fields Modified ({len(diff.modified_fields)}):{RESET}")
        for f in diff.modified_fields:
            print(f"    {YELLOW}~ {f['table']}.{f['field_name']}{RESET}")
            for key, change in f["changes"].items():
                old_val = json.dumps(change["old"], default=str) if change["old"] is not None else "null"
                new_val = json.dumps(change["new"], default=str) if change["new"] is not None else "null"
                # Truncate long values
                if len(old_val) > 60:
                    old_val = old_val[:57] + "..."
                if len(new_val) > 60:
                    new_val = new_val[:57] + "..."
                print(f"      {key}: {old_val} -> {new_val}")

    if diff.added_views:
        print(f"\n  {GREEN}Views Added ({len(diff.added_views)}):{RESET}")
        for v in diff.added_views:
            print(f"    {GREEN}+ {v['table']}.{v['view_name']}{RESET}")

    if diff.removed_views:
        print(f"\n  {RED}Views Removed ({len(diff.removed_views)}):{RESET}")
        for v in diff.removed_views:
            print(f"    {RED}- {v['table']}.{v['view_name']}{RESET}")

    # Summary
    print(f"\n{'=' * 60}")
    total = (len(diff.added_tables) + len(diff.removed_tables)
             + len(diff.added_fields) + len(diff.removed_fields)
             + len(diff.modified_fields))
    print(f"  Total changes: {total}")


def main():
    output_json = "--json" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if len(args) == 2:
        old = load_json(args[0])
        new = load_json(args[1])
    elif "--live" in sys.argv:
        print("Live diff not yet implemented — provide two schema files.")
        sys.exit(1)
    else:
        print("Usage: diff_schema.py <old_schema.json> <new_schema.json>")
        print("       diff_schema.py --live")
        sys.exit(1)

    if not old or not new:
        sys.exit(2)

    diff = diff_schemas(old, new)

    if output_json:
        print(json.dumps(diff.to_dict(), indent=2, default=str))
    else:
        print_diff(diff)

    sys.exit(0 if not diff.has_changes else 1)


if __name__ == "__main__":
    main()
