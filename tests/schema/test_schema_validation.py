"""Tests for Airtable schema validation.

Validates that schema.json is internally consistent and passes
all validation rules without requiring Airtable API access.

Run with: pytest tests/schema/test_schema_validation.py -v
"""

import json
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).parent.parent.parent
SCHEMA_PATH = ROOT_DIR / "airtable" / "schema" / "schema.json"
META_SCHEMA_PATH = ROOT_DIR / "airtable" / "schema" / "meta-schema.json"
MIGRATIONS_DIR = ROOT_DIR / "airtable" / "migrations"

# Add schema dir to path for importing validator
sys.path.insert(0, str(ROOT_DIR / "airtable" / "schema"))


@pytest.fixture
def schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


@pytest.fixture
def meta_schema():
    with open(META_SCHEMA_PATH) as f:
        return json.load(f)


class TestSchemaStructure:
    """Validate the schema file itself is well-formed."""

    def test_schema_file_exists(self):
        assert SCHEMA_PATH.exists(), "schema.json not found"

    def test_schema_is_valid_json(self):
        with open(SCHEMA_PATH) as f:
            json.load(f)  # Should not raise

    def test_schema_has_version(self, schema):
        assert "version" in schema
        parts = schema["version"].split(".")
        assert len(parts) == 3, "Version must be semver (X.Y.Z)"

    def test_schema_has_tables(self, schema):
        assert "tables" in schema
        assert isinstance(schema["tables"], list)
        assert len(schema["tables"]) > 0

    def test_meta_schema_validates_schema(self, schema, meta_schema):
        """schema.json should pass validation against meta-schema.json."""
        import jsonschema
        jsonschema.validate(schema, meta_schema)


class TestTableDefinitions:
    """Validate each table definition."""

    def test_all_tables_have_required_keys(self, schema):
        for table in schema["tables"]:
            assert "name" in table, f"Table missing 'name'"
            assert "table_id" in table, f"Table {table.get('name')} missing 'table_id'"
            assert "fields" in table, f"Table {table.get('name')} missing 'fields'"

    def test_no_duplicate_table_names(self, schema):
        names = [t["name"] for t in schema["tables"]]
        assert len(names) == len(set(names)), f"Duplicate table names: {[n for n in names if names.count(n) > 1]}"

    def test_no_duplicate_table_ids(self, schema):
        ids = [t["table_id"] for t in schema["tables"]]
        assert len(ids) == len(set(ids)), f"Duplicate table IDs"

    def test_table_ids_follow_convention(self, schema):
        for table in schema["tables"]:
            assert table["table_id"].startswith("tbl"), (
                f"Table {table['name']}: table_id '{table['table_id']}' should start with 'tbl'"
            )

    def test_primary_field_exists_in_fields(self, schema):
        for table in schema["tables"]:
            if "primary_field" in table:
                field_names = {f["name"] for f in table["fields"]}
                assert table["primary_field"] in field_names, (
                    f"Table {table['name']}: primary_field '{table['primary_field']}' not in fields"
                )

    def test_required_tables_exist(self, schema):
        """Core system tables must exist."""
        table_names = {t["name"] for t in schema["tables"]}
        required = {"Work_Items", "Sites", "Contacts", "Contractors",
                     "Team_Members", "Interaction_Log", "Error_Log"}
        missing = required - table_names
        assert not missing, f"Missing required tables: {missing}"


class TestFieldDefinitions:
    """Validate field definitions across all tables."""

    def test_all_fields_have_name_and_type(self, schema):
        for table in schema["tables"]:
            for field in table["fields"]:
                assert "name" in field, f"{table['name']}: field missing 'name'"
                assert "type" in field, f"{table['name']}.{field.get('name')}: missing 'type'"

    def test_no_duplicate_field_names_per_table(self, schema):
        for table in schema["tables"]:
            names = [f["name"] for f in table["fields"]]
            dupes = [n for n in names if names.count(n) > 1]
            assert not dupes, f"{table['name']}: duplicate field names: {set(dupes)}"

    def test_field_types_are_valid(self, schema):
        valid_types = {
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
        for table in schema["tables"]:
            for field in table["fields"]:
                assert field["type"] in valid_types, (
                    f"{table['name']}.{field['name']}: invalid type '{field['type']}'"
                )

    def test_field_ids_follow_convention(self, schema):
        for table in schema["tables"]:
            for field in table["fields"]:
                if "field_id" in field:
                    assert field["field_id"].startswith("fld"), (
                        f"{table['name']}.{field['name']}: field_id '{field['field_id']}' should start with 'fld'"
                    )

    def test_select_fields_have_choices(self, schema):
        for table in schema["tables"]:
            for field in table["fields"]:
                if field["type"] in ("singleSelect", "multipleSelects"):
                    options = field.get("options", {})
                    choices = options.get("choices", [])
                    assert len(choices) > 0, (
                        f"{table['name']}.{field['name']}: select field has no choices"
                    )

    def test_formula_fields_have_formula(self, schema):
        for table in schema["tables"]:
            for field in table["fields"]:
                if field["type"] == "formula":
                    options = field.get("options", {})
                    assert "formula" in options, (
                        f"{table['name']}.{field['name']}: formula field missing 'formula' in options"
                    )


class TestRelationships:
    """Validate link fields reference valid tables."""

    def test_link_fields_reference_valid_tables(self, schema):
        table_ids = {t["table_id"] for t in schema["tables"]}
        for table in schema["tables"]:
            for field in table["fields"]:
                if field["type"] == "multipleRecordLinks":
                    linked_id = field.get("options", {}).get("linkedTableId")
                    assert linked_id in table_ids, (
                        f"{table['name']}.{field['name']}: links to unknown table '{linked_id}'"
                    )

    def test_relationships_array_is_valid(self, schema):
        relationships = schema.get("relationships", [])
        assert isinstance(relationships, list)
        for rel in relationships:
            assert "from" in rel, f"Relationship missing 'from'"
            assert "to" in rel, f"Relationship missing 'to'"
            assert "type" in rel, f"Relationship missing 'type'"


class TestStateMachine:
    """Validate state machine definition."""

    def test_state_machine_exists(self, schema):
        assert "state_machine" in schema

    def test_initial_state_is_valid(self, schema):
        sm = schema["state_machine"]
        transitions = sm["transitions"]
        all_states = set()
        for t in transitions:
            all_states.add(t["from"])
            all_states.update(t["to"])

        assert sm["initial_state"] in all_states

    def test_terminal_states_reachable(self, schema):
        sm = schema["state_machine"]
        all_to = set()
        for t in sm["transitions"]:
            all_to.update(t["to"])

        for ts in sm["terminal_states"]:
            assert ts in all_to, f"Terminal state '{ts}' not reachable"

    def test_no_transitions_from_terminal_to_nonterminal(self, schema):
        sm = schema["state_machine"]
        terminal = set(sm["terminal_states"])

        for t in sm["transitions"]:
            if t["from"] in terminal:
                non_terminal_targets = set(t["to"]) - terminal
                assert not non_terminal_targets, (
                    f"Terminal state '{t['from']}' has transitions to non-terminal: {non_terminal_targets}"
                )

    def test_work_items_states_match_field_choices(self, schema):
        """State machine states should match Work_Items.current_state choices."""
        sm = schema["state_machine"]
        sm_states = set()
        for t in sm["transitions"]:
            sm_states.add(t["from"])
            sm_states.update(t["to"])

        # Find Work_Items.current_state field
        work_items = next(t for t in schema["tables"] if t["name"] == "Work_Items")
        state_field = next(f for f in work_items["fields"] if f["name"] == "current_state")
        choices = {c["name"] for c in state_field["options"]["choices"]}

        missing_in_choices = sm_states - choices
        assert not missing_in_choices, (
            f"States in state_machine not in field choices: {missing_in_choices}"
        )


class TestConstraints:
    """Validate declared constraints."""

    def test_unique_fields_exist(self, schema):
        constraints = schema.get("constraints", {})
        unique_fields = constraints.get("unique_fields", [])

        all_fields = set()
        for table in schema["tables"]:
            for field in table["fields"]:
                all_fields.add(f"{table['name']}.{field['name']}")

        for uf in unique_fields:
            assert uf in all_fields, f"Unique field '{uf}' does not exist in schema"

    def test_sensitive_fields_exist(self, schema):
        constraints = schema.get("constraints", {})
        sensitive = constraints.get("sensitive_fields", [])

        all_fields = set()
        for table in schema["tables"]:
            for field in table["fields"]:
                all_fields.add(f"{table['name']}.{field['name']}")

        for sf in sensitive:
            assert sf in all_fields, f"Sensitive field '{sf}' does not exist in schema"


class TestMigrations:
    """Validate migration files."""

    def test_migration_files_are_valid_json(self):
        for path in MIGRATIONS_DIR.glob("[0-9]*.json"):
            with open(path) as f:
                data = json.load(f)
            assert "migration_id" in data, f"{path.name}: missing 'migration_id'"
            assert "version" in data, f"{path.name}: missing 'version'"
            assert "changes" in data, f"{path.name}: missing 'changes'"

    def test_migration_ids_are_sequential(self):
        files = sorted(MIGRATIONS_DIR.glob("[0-9]*.json"))
        for i, path in enumerate(files):
            expected_prefix = f"{i + 1:03d}_"
            assert path.name.startswith(expected_prefix), (
                f"Migration {path.name} should start with '{expected_prefix}'"
            )

    def test_migrations_have_rollback(self):
        for path in MIGRATIONS_DIR.glob("[0-9]*.json"):
            with open(path) as f:
                data = json.load(f)
            assert "rollback" in data and data["rollback"], (
                f"{path.name}: missing rollback instructions"
            )
