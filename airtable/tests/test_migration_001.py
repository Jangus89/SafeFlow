#!/usr/bin/env python3
"""Tests for Airtable schema migration 001 (initial schema).

Validates the schema.json file contains all required tables, fields,
state machine configuration, and SLA definitions.

Usage:
    pytest airtable/tests/test_migration_001.py -v
"""

import json
from pathlib import Path

import pytest

SCHEMA_PATH = Path("airtable/schema/schema.json")

REQUIRED_TABLES = [
    "Work_Items", "Sites", "Contractors", "Quotes", "People",
    "Payments", "Interaction_Logs", "Question_Bank", "Errors",
]

REQUIRED_STATES = [
    "INTAKE", "CLARIFICATION", "ASSESSMENT", "ASSIGNED", "IN_PROGRESS",
    "VERIFICATION", "PAYMENT_PENDING", "CLOSED", "ESCALATED", "ON_HOLD",
    "CANCELLED", "REOPENED",
]

VALID_FIELD_TYPES = {
    "autonumber", "singleLineText", "multilineText", "number", "currency",
    "percent", "email", "phoneNumber", "url", "singleSelect",
    "multipleSelects", "multipleRecordLinks", "date", "dateTime",
    "checkbox", "rating", "formula", "rollup", "count",
    "lookup", "barcode", "button", "richText", "duration",
    "lastModifiedTime", "createdTime", "lastModifiedBy", "createdBy",
    "autoNumber", "attachment",
}


@pytest.fixture
def schema():
    """Load the main schema file."""
    with open(SCHEMA_PATH) as f:
        return json.load(f)


@pytest.fixture
def tables(schema):
    """Extract tables from schema."""
    return {t["name"]: t for t in schema.get("tables", [])}


class TestSchemaStructure:
    """Test top-level schema structure."""

    def test_schema_file_exists(self):
        assert SCHEMA_PATH.exists(), f"Schema file not found: {SCHEMA_PATH}"

    def test_schema_is_valid_json(self):
        with open(SCHEMA_PATH) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_schema_has_version(self, schema):
        assert "version" in schema

    def test_schema_has_tables(self, schema):
        assert "tables" in schema
        assert len(schema["tables"]) > 0


class TestRequiredTables:
    """Test all 9 required tables are present."""

    def test_all_nine_tables_present(self, tables):
        assert len(tables) >= 9, f"Expected 9+ tables, found {len(tables)}"

    @pytest.mark.parametrize("table_name", REQUIRED_TABLES)
    def test_required_table_exists(self, tables, table_name):
        assert table_name in tables, f"Missing required table: {table_name}"

    def test_no_duplicate_table_names(self, schema):
        names = [t["name"] for t in schema["tables"]]
        assert len(names) == len(set(names)), "Duplicate table names found"

    def test_tables_have_table_ids(self, schema):
        for table in schema["tables"]:
            assert "table_id" in table, f"Table {table['name']} missing table_id"


class TestWorkItemsTable:
    """Test Work_Items table has all required fields."""

    def test_work_items_has_30_plus_fields(self, tables):
        fields = tables["Work_Items"].get("fields", [])
        assert len(fields) >= 30, (
            f"Work_Items has {len(fields)} fields, expected 30+"
        )

    def test_work_items_has_state_field(self, tables):
        field_names = {f["name"] for f in tables["Work_Items"]["fields"]}
        assert "current_state" in field_names

    def test_work_items_has_sla_fields(self, tables):
        field_names = {f["name"] for f in tables["Work_Items"]["fields"]}
        assert "sla_due_at" in field_names
        assert "escalation_level" in field_names

    def test_work_items_has_llm_fields(self, tables):
        field_names = {f["name"] for f in tables["Work_Items"]["fields"]}
        assert "llm_extracted_data" in field_names or "llm_confidence" in field_names

    def test_work_items_has_assignment_fields(self, tables):
        field_names = {f["name"] for f in tables["Work_Items"]["fields"]}
        assert "site_id" in field_names
        assert "discipline_required" in field_names
        assert "urgency" in field_names

    def test_work_items_has_formula_fields(self, tables):
        formula_fields = [
            f for f in tables["Work_Items"]["fields"]
            if f.get("type") == "formula"
        ]
        assert len(formula_fields) >= 2, "Work_Items should have formula fields"

    def test_work_items_has_views(self, tables):
        views = tables["Work_Items"].get("views", [])
        assert len(views) >= 3, "Work_Items should have multiple views"


class TestFieldTypes:
    """Test field type validity across all tables."""

    def test_all_field_types_valid(self, schema):
        invalid = []
        for table in schema["tables"]:
            for field in table.get("fields", []):
                ft = field.get("type", "")
                if ft and ft not in VALID_FIELD_TYPES:
                    invalid.append(f"{table['name']}.{field['name']}: {ft}")
        assert not invalid, f"Invalid field types: {invalid}"

    def test_formula_fields_have_formulas(self, schema):
        missing = []
        for table in schema["tables"]:
            for field in table.get("fields", []):
                if field.get("type") == "formula":
                    options = field.get("options", {})
                    if not options.get("formula"):
                        missing.append(f"{table['name']}.{field['name']}")
        assert not missing, f"Formula fields missing formula: {missing}"

    def test_select_fields_have_choices(self, schema):
        missing = []
        for table in schema["tables"]:
            for field in table.get("fields", []):
                if field.get("type") in ("singleSelect", "multipleSelects"):
                    options = field.get("options", {})
                    if not options.get("choices"):
                        missing.append(f"{table['name']}.{field['name']}")
        assert not missing, f"Select fields missing choices: {missing}"

    def test_currency_fields_use_gbp(self, schema):
        for table in schema["tables"]:
            for field in table.get("fields", []):
                if field.get("type") == "currency":
                    symbol = field.get("options", {}).get("symbol", "")
                    assert symbol == "£", (
                        f"{table['name']}.{field['name']}: "
                        f"expected £, got {symbol}"
                    )


class TestRelationships:
    """Test linked record fields reference valid tables."""

    def test_link_fields_reference_valid_tables(self, schema):
        table_ids = {t["table_id"] for t in schema["tables"]}
        invalid = []
        for table in schema["tables"]:
            for field in table.get("fields", []):
                if field.get("type") == "multipleRecordLinks":
                    linked = field.get("options", {}).get("linkedTableId", "")
                    if linked and linked not in table_ids:
                        invalid.append(
                            f"{table['name']}.{field['name']} -> {linked}"
                        )
        assert not invalid, f"Invalid link targets: {invalid}"


class TestStateMachine:
    """Test state machine definition."""

    def test_state_machine_exists(self, schema):
        assert "state_machine" in schema

    def test_all_twelve_states_present(self, schema):
        states = schema["state_machine"].get("states", [])
        assert len(states) >= 12, f"Expected 12+ states, found {len(states)}"
        for state in REQUIRED_STATES:
            assert state in states, f"Missing state: {state}"

    def test_initial_state_is_intake(self, schema):
        assert schema["state_machine"].get("initial_state") == "INTAKE"

    def test_terminal_states_defined(self, schema):
        terminal = schema["state_machine"].get("terminal_states", [])
        assert "CLOSED" in terminal
        assert "CANCELLED" in terminal

    def test_transitions_exist(self, schema):
        transitions = schema["state_machine"].get("transitions", [])
        assert len(transitions) >= 10, (
            f"Expected 10+ transitions, found {len(transitions)}"
        )

    def test_transitions_reference_valid_states(self, schema):
        states = set(schema["state_machine"]["states"])
        transitions = schema["state_machine"]["transitions"]
        invalid = []
        for t in transitions:
            if t["from"] != "*" and t["from"] not in states:
                invalid.append(f"from: {t['from']}")
            if t["to"] != "PREVIOUS_STATE" and t["to"] not in states:
                invalid.append(f"to: {t['to']}")
        assert not invalid, f"Invalid transition states: {invalid}"

    def test_all_transitions_have_triggers(self, schema):
        transitions = schema["state_machine"]["transitions"]
        for t in transitions:
            assert "trigger" in t, f"Transition {t['from']} -> {t['to']} missing trigger"


class TestSLADefinitions:
    """Test SLA definitions."""

    def test_sla_definitions_exist(self, schema):
        assert "sla_definitions" in schema

    @pytest.mark.parametrize("urgency", ["EMERGENCY", "URGENT", "STANDARD", "SCHEDULED"])
    def test_sla_urgency_defined(self, schema, urgency):
        sla = schema["sla_definitions"]
        assert urgency in sla, f"Missing SLA for {urgency}"

    def test_emergency_sla_is_strictest(self, schema):
        sla = schema["sla_definitions"]
        assert sla["EMERGENCY"]["response_minutes"] <= 15
        assert sla["EMERGENCY"]["resolution_hours"] <= 4

    def test_sla_has_required_fields(self, schema):
        for urgency, defn in schema["sla_definitions"].items():
            assert "response_minutes" in defn, f"{urgency}: missing response_minutes"
            assert "resolution_hours" in defn, f"{urgency}: missing resolution_hours"


class TestIndividualTableFiles:
    """Test individual table JSON files exist and are valid."""

    @pytest.mark.parametrize("table_name", REQUIRED_TABLES)
    def test_individual_table_file_exists(self, table_name):
        path = Path(f"airtable/schema/{table_name}.json")
        assert path.exists(), f"Individual table file missing: {path}"

    @pytest.mark.parametrize("table_name", REQUIRED_TABLES)
    def test_individual_table_file_valid_json(self, table_name):
        path = Path(f"airtable/schema/{table_name}.json")
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            assert "fields" in data, f"{table_name}.json missing fields"
