#!/usr/bin/env python3
"""
Airtable Schema Validator

Validates the schema.json definition for internal consistency, enforces
naming conventions, checks relationship integrity, and ensures Airtable
platform constraints are respected.

Usage:
    python airtable/schema/validate_schema.py
    python airtable/schema/validate_schema.py --strict   # Fail on warnings too
    python airtable/schema/validate_schema.py --json     # Machine-readable output

Exit codes:
    0 - All validations passed
    1 - Errors found
    2 - Schema file not found or invalid JSON
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).parent / "schema.json"

# Airtable platform limits
AIRTABLE_LIMITS = {
    "max_tables_per_base": 250,
    "max_fields_per_table": 500,
    "max_characters_field_name": 255,
    "max_characters_table_name": 255,
    "max_select_choices": 100,
    "max_rows_pro_plan": 125000,
    "max_views_per_table": 100,
}

# Valid Airtable field types
VALID_FIELD_TYPES = {
    "singleLineText", "multilineText", "email", "url", "phoneNumber",
    "number", "currency", "percent", "rating", "checkbox",
    "singleSelect", "multipleSelects",
    "date", "dateTime",
    "multipleRecordLinks", "lookup", "rollup", "count",
    "formula", "autonumber",
    "multipleAttachments",
    "barcode", "button", "richText",
    "duration", "lastModifiedTime", "createdTime", "lastModifiedBy", "createdBy",
}


class SchemaValidationResult:
    def __init__(self):
        self.errors: list[dict] = []
        self.warnings: list[dict] = []
        self.info: list[dict] = []

    def error(self, location: str, message: str):
        self.errors.append({"level": "error", "location": location, "message": message})

    def warning(self, location: str, message: str):
        self.warnings.append({"level": "warning", "location": location, "message": message})

    def add_info(self, location: str, message: str):
        self.info.append({"level": "info", "location": location, "message": message})

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
        }


def load_schema(path: Path) -> dict | None:
    """Load and parse the schema JSON file."""
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Schema file not found: {path}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in schema: {e}", file=sys.stderr)
        return None


def validate_top_level(schema: dict, result: SchemaValidationResult):
    """Validate top-level schema structure."""
    required_keys = ["version", "base_name", "tables"]
    for key in required_keys:
        if key not in schema:
            result.error("schema", f"Missing required top-level key: '{key}'")

    if "version" in schema:
        if not re.match(r"^\d+\.\d+\.\d+$", schema["version"]):
            result.error("schema.version", f"Version must be semver format: {schema['version']}")

    if "tables" in schema:
        if not isinstance(schema["tables"], list):
            result.error("schema.tables", "Tables must be an array")
        elif len(schema["tables"]) > AIRTABLE_LIMITS["max_tables_per_base"]:
            result.error("schema.tables", f"Too many tables: {len(schema['tables'])} > {AIRTABLE_LIMITS['max_tables_per_base']}")
        else:
            result.add_info("schema.tables", f"{len(schema['tables'])} tables defined")


def validate_table(table: dict, table_index: int, all_table_names: set, result: SchemaValidationResult):
    """Validate a single table definition."""
    loc = f"tables[{table_index}]"
    name = table.get("name", f"<unnamed-{table_index}>")
    loc = f"tables.{name}"

    # Required fields
    for key in ["name", "table_id", "fields"]:
        if key not in table:
            result.error(loc, f"Missing required key: '{key}'")

    # Name conventions
    if "name" in table:
        if len(table["name"]) > AIRTABLE_LIMITS["max_characters_table_name"]:
            result.error(loc, f"Table name too long: {len(table['name'])} chars")

    # Table ID format
    if "table_id" in table:
        if not table["table_id"].startswith("tbl"):
            result.warning(f"{loc}.table_id", "Table IDs should start with 'tbl'")

    # Primary field must reference an existing field
    if "primary_field" in table and "fields" in table:
        field_names = {f["name"] for f in table["fields"]}
        if table["primary_field"] not in field_names:
            result.error(loc, f"Primary field '{table['primary_field']}' not found in fields")

    # Field count limits
    if "fields" in table:
        if len(table["fields"]) > AIRTABLE_LIMITS["max_fields_per_table"]:
            result.error(loc, f"Too many fields: {len(table['fields'])} > {AIRTABLE_LIMITS['max_fields_per_table']}")
        result.add_info(loc, f"{len(table['fields'])} fields defined")

    # View count limits
    if "views" in table:
        if len(table["views"]) > AIRTABLE_LIMITS["max_views_per_table"]:
            result.error(loc, f"Too many views: {len(table['views'])} > {AIRTABLE_LIMITS['max_views_per_table']}")


def validate_field(field: dict, table_name: str, field_index: int, all_table_ids: set, result: SchemaValidationResult):
    """Validate a single field definition."""
    name = field.get("name", f"<unnamed-{field_index}>")
    loc = f"tables.{table_name}.fields.{name}"

    # Required keys
    for key in ["name", "type"]:
        if key not in field:
            result.error(loc, f"Missing required key: '{key}'")
            return

    # Field type validity
    if field["type"] not in VALID_FIELD_TYPES:
        result.error(loc, f"Invalid field type: '{field['type']}'")

    # Field ID format
    if "field_id" in field:
        if not field["field_id"].startswith("fld"):
            result.warning(f"{loc}.field_id", "Field IDs should start with 'fld'")

    # Name length
    if len(field["name"]) > AIRTABLE_LIMITS["max_characters_field_name"]:
        result.error(loc, f"Field name too long: {len(field['name'])} chars")

    # Select field validation
    if field["type"] in ("singleSelect", "multipleSelects"):
        options = field.get("options", {})
        choices = options.get("choices", [])
        if not choices:
            result.warning(loc, "Select field has no choices defined")
        elif len(choices) > AIRTABLE_LIMITS["max_select_choices"]:
            result.error(loc, f"Too many select choices: {len(choices)} > {AIRTABLE_LIMITS['max_select_choices']}")

    # Link field validation
    if field["type"] == "multipleRecordLinks":
        options = field.get("options", {})
        linked_table = options.get("linkedTableId")
        if not linked_table:
            result.error(loc, "Link field missing 'linkedTableId' in options")
        elif linked_table not in all_table_ids:
            result.error(loc, f"Link field references unknown table: '{linked_table}'")

    # Formula field validation
    if field["type"] == "formula":
        options = field.get("options", {})
        if "formula" not in options:
            result.error(loc, "Formula field missing 'formula' in options")

    # Validation rules check (our custom extension)
    if "validation" in field:
        v = field["validation"]
        if "regex" in v:
            try:
                re.compile(v["regex"])
            except re.error as e:
                result.error(loc, f"Invalid regex in validation: {e}")


def validate_relationships(schema: dict, result: SchemaValidationResult):
    """Validate relationship definitions."""
    relationships = schema.get("relationships", [])
    if not isinstance(relationships, list):
        result.error("relationships", "Relationships must be an array")
        return

    table_names = {t["name"] for t in schema.get("tables", [])}

    for i, rel in enumerate(relationships):
        loc = f"relationships[{i}]"
        for key in ["from", "to", "type"]:
            if key not in rel:
                result.error(loc, f"Missing required key: '{key}'")

        if rel.get("type") not in ("one-to-many", "many-to-one", "many-to-many"):
            result.warning(loc, f"Unusual relationship type: '{rel.get('type')}'")

    result.add_info("relationships", f"{len(relationships)} relationships defined")


def validate_state_machine(schema: dict, result: SchemaValidationResult):
    """Validate state machine definition."""
    sm = schema.get("state_machine")
    if not sm:
        result.warning("state_machine", "No state machine defined")
        return

    loc = "state_machine"
    for key in ["table", "field", "initial_state", "terminal_states", "transitions"]:
        if key not in sm:
            result.error(loc, f"Missing required key: '{key}'")

    if "transitions" in sm:
        all_states = set()
        for t in sm["transitions"]:
            all_states.add(t.get("from", ""))
            for to_state in t.get("to", []):
                all_states.add(to_state)

        # Check initial state reachable
        if sm.get("initial_state") not in all_states:
            result.error(loc, f"Initial state '{sm.get('initial_state')}' not in transitions")

        # Check terminal states reachable
        for ts in sm.get("terminal_states", []):
            if ts not in all_states:
                result.error(loc, f"Terminal state '{ts}' not reachable from any transition")

        # Check for orphan states (no incoming transitions)
        from_states = {t["from"] for t in sm["transitions"]}
        to_states = set()
        for t in sm["transitions"]:
            to_states.update(t.get("to", []))

        orphans = from_states - to_states - {sm.get("initial_state")}
        for orphan in orphans:
            result.warning(loc, f"State '{orphan}' has outgoing transitions but no incoming transitions")

        result.add_info(loc, f"{len(sm['transitions'])} transitions, {len(all_states)} states")


def validate_unique_constraints(schema: dict, result: SchemaValidationResult):
    """Validate that declared unique fields exist."""
    constraints = schema.get("constraints", {})
    unique_fields = constraints.get("unique_fields", [])

    table_field_map = {}
    for table in schema.get("tables", []):
        for field in table.get("fields", []):
            key = f"{table['name']}.{field['name']}"
            table_field_map[key] = field

    for uf in unique_fields:
        if uf not in table_field_map:
            result.error(f"constraints.unique_fields", f"Unique field '{uf}' does not exist in schema")
        else:
            result.add_info("constraints.unique_fields", f"Unique constraint on '{uf}'")


def validate_schema(schema: dict, strict: bool = False) -> SchemaValidationResult:
    """Run all validations on the schema."""
    result = SchemaValidationResult()

    # Top-level
    validate_top_level(schema, result)
    if result.errors:
        return result

    # Collect table metadata
    tables = schema.get("tables", [])
    all_table_names = {t.get("name") for t in tables}
    all_table_ids = {t.get("table_id") for t in tables}

    # Check for duplicate table names
    seen_names = set()
    for t in tables:
        name = t.get("name")
        if name in seen_names:
            result.error(f"tables.{name}", f"Duplicate table name: '{name}'")
        seen_names.add(name)

    # Check for duplicate table IDs
    seen_ids = set()
    for t in tables:
        tid = t.get("table_id")
        if tid in seen_ids:
            result.error(f"tables.{t.get('name')}", f"Duplicate table_id: '{tid}'")
        seen_ids.add(tid)

    # Validate each table and its fields
    for i, table in enumerate(tables):
        validate_table(table, i, all_table_names, result)

        field_names_in_table = set()
        for j, field in enumerate(table.get("fields", [])):
            # Check for duplicate field names within table
            fname = field.get("name")
            if fname in field_names_in_table:
                result.error(f"tables.{table.get('name')}.fields.{fname}", "Duplicate field name in table")
            field_names_in_table.add(fname)

            validate_field(field, table.get("name", ""), j, all_table_ids, result)

    # Relationships
    validate_relationships(schema, result)

    # State machine
    validate_state_machine(schema, result)

    # Unique constraints
    validate_unique_constraints(schema, result)

    return result


def main():
    strict = "--strict" in sys.argv
    output_json = "--json" in sys.argv

    schema = load_schema(SCHEMA_PATH)
    if schema is None:
        sys.exit(2)

    result = validate_schema(schema, strict=strict)

    if output_json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        # Header
        print("=" * 60)
        print("  Airtable Schema Validation")
        print(f"  Schema: {SCHEMA_PATH.name}")
        print(f"  Version: {schema.get('version', 'unknown')}")
        print("=" * 60)

        # Errors
        if result.errors:
            print(f"\n\033[91mERRORS ({len(result.errors)}):\033[0m")
            for e in result.errors:
                print(f"  \033[91m✗\033[0m [{e['location']}] {e['message']}")

        # Warnings
        if result.warnings:
            print(f"\n\033[93mWARNINGS ({len(result.warnings)}):\033[0m")
            for w in result.warnings:
                print(f"  \033[93m!\033[0m [{w['location']}] {w['message']}")

        # Info
        if result.info:
            print(f"\n\033[92mINFO:\033[0m")
            for i in result.info:
                print(f"  \033[92m✓\033[0m [{i['location']}] {i['message']}")

        # Summary
        print("\n" + "-" * 60)
        if result.passed:
            print(f"\033[92mPASSED\033[0m — {len(result.errors)} errors, {len(result.warnings)} warnings")
        else:
            print(f"\033[91mFAILED\033[0m — {len(result.errors)} errors, {len(result.warnings)} warnings")

    exit_code = 0
    if result.errors:
        exit_code = 1
    elif strict and result.warnings:
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
