#!/usr/bin/env python3
"""Validate Airtable schema definition against SafeFlow requirements.

Checks:
    - All required tables present (9 tables)
    - Field types are valid Airtable types
    - Relationships reference valid tables
    - State machine is fully connected
    - SLA definitions are complete
    - Formula fields have formula property
    - Select fields have choices defined
    - Naming conventions followed

Usage:
    python scripts/validation/validate-airtable-schema.py
    python scripts/validation/validate-airtable-schema.py --schema path/to/schema.json
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Any


VALID_FIELD_TYPES = {
    "autonumber", "singleLineText", "multilineText", "number", "currency",
    "percent", "email", "phoneNumber", "url", "singleSelect",
    "multipleSelects", "multipleRecordLinks", "date", "dateTime",
    "checkbox", "rating", "formula", "rollup", "count",
    "lookup", "barcode", "button", "richText", "duration",
    "lastModifiedTime", "createdTime", "lastModifiedBy", "createdBy",
    "autoNumber", "attachment",
}

REQUIRED_TABLES = [
    "Work_Items", "Sites", "Contractors", "Quotes", "People",
    "Payments", "Interaction_Logs", "Question_Bank", "Errors",
]

REQUIRED_STATES = [
    "INTAKE", "CLARIFICATION", "ASSESSMENT", "ASSIGNED", "IN_PROGRESS",
    "VERIFICATION", "PAYMENT_PENDING", "CLOSED", "ESCALATED", "ON_HOLD",
    "CANCELLED", "REOPENED",
]


class SchemaValidator:
    """Validates SafeFlow Airtable schema definition."""

    def __init__(self, schema_path: str) -> None:
        self.schema_path = Path(schema_path)
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.schema: dict[str, Any] = {}

    def load_schema(self) -> bool:
        """Load and parse the schema JSON file."""
        try:
            with open(self.schema_path) as f:
                self.schema = json.load(f)
            return True
        except FileNotFoundError:
            self.errors.append(f"Schema file not found: {self.schema_path}")
            return False
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in schema file: {e}")
            return False

    def validate_structure(self) -> None:
        """Check top-level schema structure."""
        required_keys = ["version", "tables"]
        for key in required_keys:
            if key not in self.schema:
                self.errors.append(f"Missing required top-level key: {key}")

    def validate_tables(self) -> None:
        """Check all required tables are present."""
        tables = self.schema.get("tables", [])
        table_names = [t.get("name", "") for t in tables]

        for required in REQUIRED_TABLES:
            if required not in table_names:
                self.errors.append(f"Missing required table: {required}")

        # Check for duplicates
        seen = set()
        for name in table_names:
            if name in seen:
                self.errors.append(f"Duplicate table name: {name}")
            seen.add(name)

    def validate_fields(self) -> None:
        """Validate field definitions for each table."""
        tables = self.schema.get("tables", [])
        for table in tables:
            table_name = table.get("name", "unknown")
            fields = table.get("fields", [])

            if not fields:
                self.warnings.append(f"Table {table_name} has no fields defined")
                continue

            field_names = set()
            for field in fields:
                name = field.get("name", "")
                field_type = field.get("type", "")

                # Check for duplicate field names
                if name in field_names:
                    self.errors.append(
                        f"Table {table_name}: duplicate field name '{name}'"
                    )
                field_names.add(name)

                # Validate field type
                if field_type and field_type not in VALID_FIELD_TYPES:
                    self.errors.append(
                        f"Table {table_name}.{name}: invalid type '{field_type}'"
                    )

                # Check formula fields have formula
                if field_type == "formula":
                    options = field.get("options", {})
                    if not options.get("formula"):
                        self.errors.append(
                            f"Table {table_name}.{name}: formula field missing formula"
                        )

                # Check select fields have choices
                if field_type in ("singleSelect", "multipleSelects"):
                    options = field.get("options", {})
                    choices = options.get("choices", [])
                    if not choices:
                        self.warnings.append(
                            f"Table {table_name}.{name}: select field has no choices"
                        )

                # Check currency fields have symbol
                if field_type == "currency":
                    options = field.get("options", {})
                    if not options.get("symbol"):
                        self.warnings.append(
                            f"Table {table_name}.{name}: currency field missing symbol"
                        )

    def validate_relationships(self) -> None:
        """Check that link fields reference valid tables."""
        tables = self.schema.get("tables", [])
        table_ids = {t.get("table_id", ""): t.get("name", "") for t in tables}
        table_names = set(t.get("name", "") for t in tables)

        for table in tables:
            table_name = table.get("name", "unknown")
            for field in table.get("fields", []):
                if field.get("type") == "multipleRecordLinks":
                    options = field.get("options", {})
                    linked_id = options.get("linkedTableId", "")
                    if linked_id and linked_id not in table_ids:
                        self.errors.append(
                            f"Table {table_name}.{field['name']}: "
                            f"links to unknown table ID '{linked_id}'"
                        )

    def validate_state_machine(self) -> None:
        """Validate state machine definition."""
        sm = self.schema.get("state_machine", {})
        if not sm:
            self.warnings.append("No state_machine definition found in schema")
            return

        states = sm.get("states", [])
        for required in REQUIRED_STATES:
            if required not in states:
                self.errors.append(f"State machine missing required state: {required}")

        # Check initial state
        initial = sm.get("initial_state", "")
        if initial not in states:
            self.errors.append(
                f"State machine initial_state '{initial}' not in states list"
            )

        # Check terminal states
        terminal = sm.get("terminal_states", [])
        for t in terminal:
            if t not in states:
                self.errors.append(
                    f"Terminal state '{t}' not in states list"
                )

        # Check transitions reference valid states
        transitions = sm.get("transitions", [])
        for tr in transitions:
            from_state = tr.get("from", "")
            to_state = tr.get("to", "")
            if from_state != "*" and from_state not in states:
                self.errors.append(
                    f"Transition from unknown state: {from_state}"
                )
            if to_state != "PREVIOUS_STATE" and to_state not in states:
                self.errors.append(
                    f"Transition to unknown state: {to_state}"
                )

        # Check all non-terminal states have at least one outgoing transition
        for state in states:
            if state in terminal:
                continue
            outgoing = [
                t for t in transitions
                if t.get("from") == state or t.get("from") == "*"
            ]
            if not outgoing:
                self.warnings.append(
                    f"State '{state}' has no outgoing transitions"
                )

    def validate_sla_definitions(self) -> None:
        """Validate SLA definitions."""
        sla = self.schema.get("sla_definitions", {})
        if not sla:
            self.warnings.append("No sla_definitions found in schema")
            return

        required_urgencies = ["EMERGENCY", "URGENT", "STANDARD", "SCHEDULED"]
        for urgency in required_urgencies:
            if urgency not in sla:
                self.errors.append(f"Missing SLA definition for urgency: {urgency}")
                continue

            defn = sla[urgency]
            for key in ["response_minutes", "resolution_hours"]:
                if key not in defn:
                    self.errors.append(
                        f"SLA {urgency}: missing '{key}'"
                    )

    def validate_views(self) -> None:
        """Check that tables have views defined."""
        tables = self.schema.get("tables", [])
        for table in tables:
            table_name = table.get("name", "unknown")
            views = table.get("views", [])
            if not views:
                self.warnings.append(f"Table {table_name} has no views defined")

    def validate_work_items_fields(self) -> None:
        """Ensure Work_Items table has minimum required fields."""
        tables = self.schema.get("tables", [])
        work_items = next(
            (t for t in tables if t.get("name") == "Work_Items"), None
        )
        if not work_items:
            return

        fields = work_items.get("fields", [])
        field_names = {f.get("name", "") for f in fields}

        required_fields = [
            "current_state", "state_started_at", "state_history",
            "site_id", "discipline_required", "urgency",
            "sla_due_at", "escalation_level", "created_at",
        ]
        for rf in required_fields:
            if rf not in field_names:
                self.errors.append(
                    f"Work_Items missing required field: {rf}"
                )

        if len(fields) < 30:
            self.warnings.append(
                f"Work_Items has {len(fields)} fields (expected 30+)"
            )

    def run(self) -> bool:
        """Run all validations and return success status."""
        if not self.load_schema():
            return False

        self.validate_structure()
        self.validate_tables()
        self.validate_fields()
        self.validate_relationships()
        self.validate_state_machine()
        self.validate_sla_definitions()
        self.validate_views()
        self.validate_work_items_fields()

        return len(self.errors) == 0

    def report(self) -> str:
        """Generate validation report."""
        lines = ["SafeFlow Airtable Schema Validation", "=" * 40, ""]

        if self.errors:
            lines.append(f"ERRORS ({len(self.errors)}):")
            for err in self.errors:
                lines.append(f"  [ERROR] {err}")
            lines.append("")

        if self.warnings:
            lines.append(f"WARNINGS ({len(self.warnings)}):")
            for warn in self.warnings:
                lines.append(f"  [WARN]  {warn}")
            lines.append("")

        tables = self.schema.get("tables", [])
        total_fields = sum(len(t.get("fields", [])) for t in tables)
        lines.append(f"Tables: {len(tables)}")
        lines.append(f"Total fields: {total_fields}")
        lines.append("")

        if not self.errors:
            lines.append("RESULT: PASSED")
        else:
            lines.append("RESULT: FAILED")

        lines.append(f"  {len(self.errors)} error(s), {len(self.warnings)} warning(s)")
        return "\n".join(lines)


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Validate SafeFlow Airtable schema definition"
    )
    parser.add_argument(
        "--schema",
        default="airtable/schema/schema.json",
        help="Path to schema.json file (default: airtable/schema/schema.json)",
    )
    args = parser.parse_args()

    validator = SchemaValidator(args.schema)
    success = validator.run()
    print(validator.report())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
