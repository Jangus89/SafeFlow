# Airtable Schema Migrations

## Why Migrations?

Airtable has no native migration system. Schema changes are manual, error-prone, and undocumented. This migration system provides:

1. **Version control** — Every schema change is a numbered migration file
2. **Audit trail** — Who changed what, when, and why
3. **Rollback instructions** — Every migration includes reversal steps
4. **Validation** — Pre/post migration checks prevent broken schemas
5. **Reproducibility** — New environments can be built from migration history

## How It Works

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Developer   │────▶│  Migration   │────▶│  Airtable    │
│  writes      │     │  runner      │     │  (manual or  │
│  migration   │     │  validates   │     │   API apply) │
│  file        │     │  and tracks  │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ Schema_       │
                     │ Migrations   │
                     │ table in     │
                     │ Airtable     │
                     └──────────────┘
```

1. Developer creates a migration file in `airtable/migrations/`
2. Migration runner (`run_migration.py`) validates the migration
3. Changes are applied manually in Airtable (or via API for supported operations)
4. Runner records the migration in the `Schema_Migrations` Airtable table
5. `schema.json` is updated to reflect the new state

## Migration File Format

```
airtable/migrations/
├── 001_initial_schema.json           # Applied
├── 002_add_sla_fields.json           # Applied
├── 003_add_contractor_insurance.json  # Pending
└── ...
```

Each migration file:

```json
{
  "migration_id": "003_add_contractor_insurance",
  "version": "1.2.0",
  "description": "Add insurance tracking fields to Contractors table",
  "author": "developer@company.com",
  "created_at": "2026-02-14T12:00:00Z",
  "depends_on": "002_add_sla_fields",

  "changes": [
    {
      "action": "add_field",
      "table": "Contractors",
      "field": {
        "name": "insurance_provider",
        "type": "singleLineText",
        "description": "Name of insurance provider"
      }
    }
  ],

  "rollback": [
    {
      "action": "remove_field",
      "table": "Contractors",
      "field_name": "insurance_provider"
    }
  ],

  "validation": {
    "pre_checks": ["table_exists:Contractors"],
    "post_checks": ["field_exists:Contractors.insurance_provider"]
  }
}
```

## Creating a Migration

```bash
# Generate a new migration file from template
python airtable/migrations/run_migration.py new "Add insurance tracking fields"

# Validate migration before applying
python airtable/migrations/run_migration.py validate 003_add_contractor_insurance

# Apply migration (records in Airtable, updates schema.json)
python airtable/migrations/run_migration.py apply 003_add_contractor_insurance

# Check migration status
python airtable/migrations/run_migration.py status

# Rollback a migration
python airtable/migrations/run_migration.py rollback 003_add_contractor_insurance
```

## Migration Actions

| Action | Description | API Support |
|--------|-------------|-------------|
| `add_table` | Create a new table | Yes (Airtable API) |
| `add_field` | Add field to existing table | Yes (Airtable API) |
| `modify_field` | Change field options | Partial (some types) |
| `remove_field` | Delete a field | Yes (Airtable API) |
| `add_view` | Create a view | No (manual) |
| `add_select_choice` | Add option to select field | Yes (Airtable API) |
| `rename_field` | Rename a field | Yes (Airtable API) |
| `add_relationship` | Create linked record field | Yes (Airtable API) |

## Rules

1. **Never modify a migration that has been applied** — create a new one instead
2. **Always include rollback instructions** — even if rollback is manual
3. **One logical change per migration** — keep migrations atomic
4. **Test in development base first** — never apply untested migrations to production
5. **Update schema.json after applying** — keep the source of truth in sync
