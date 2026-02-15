# Migration 001: Initial Schema

**Version:** 1.0.0
**Date:** 15/02/2026
**Author:** SafeFlow Team
**Depends on:** none

## Description

Creates the initial 9-table Airtable base for the SafeFlow WhatsApp facilities management system.
This is the foundation migration that establishes all tables, fields, views, and relationships.

## Pre-checks

- [ ] Airtable base exists and is empty (no existing tables)
- [ ] Airtable API key has schema write permissions
- [ ] Base ID matches target environment

## Changes

### Tables Added

| Table Name | Table ID | Field Count | Description |
|-----------|----------|-------------|-------------|
| Work_Items | tblWorkItems | 35 | Core work order tracking with state machine |
| Sites | tblSites | 20 | UK commercial property definitions |
| Contractors | tblContractors | 25 | External contractor registry with certifications |
| Quotes | tblQuotes | 17 | RFQ responses and cost tracking |
| People | tblPeople | 15 | All system users (tenants, engineers, supervisors) |
| Payments | tblPayments | 17 | Invoice and payment tracking (Xero integration) |
| Interaction_Logs | tblInteractionLogs | 17 | WhatsApp message history |
| Question_Bank | tblQuestionBank | 12 | Clarification questions (multilingual) |
| Errors | tblErrors | 15 | System error logging and tracking |

### Key Relationships

| From Table | Field | To Table | Type |
|-----------|-------|----------|------|
| Work_Items | site_id | Sites | Many-to-One |
| Work_Items | reported_by | People | Many-to-One |
| Work_Items | assigned_engineer_id | People | Many-to-One |
| Work_Items | contractor_id | Contractors | Many-to-One |
| Quotes | work_item_id | Work_Items | Many-to-One |
| Quotes | contractor_id | Contractors | Many-to-One |
| Payments | work_item_id | Work_Items | Many-to-One |
| Payments | quote_id | Quotes | Many-to-One |
| Payments | contractor_id | Contractors | Many-to-One |
| Payments | approved_by | People | Many-to-One |
| Interaction_Logs | work_item_id | Work_Items | Many-to-One |
| Interaction_Logs | person_id | People | Many-to-One |
| Sites | primary_contact | People | Many-to-One |
| Sites | property_manager | People | Many-to-One |

### State Machine Configuration

12 states: INTAKE, CLARIFICATION, ASSESSMENT, ASSIGNED, IN_PROGRESS, VERIFICATION,
PAYMENT_PENDING, CLOSED, ESCALATED, ON_HOLD, CANCELLED, REOPENED

18 transitions defined with side effects.

### SLA Definitions

| Urgency | Response | Resolution | Escalation Intervals |
|---------|----------|------------|---------------------|
| EMERGENCY | 15 min | 4 hours | 15, 30, 60 min |
| URGENT | 1 hour | 24 hours | 60, 120, 240 min |
| STANDARD | 4 hours | 72 hours | 4, 8, 24 hours |
| SCHEDULED | 24 hours | 2 weeks | 24, 48, 72 hours |

## Apply Instructions

1. Create each table in order (Work_Items first, then referencing tables)
2. Add all fields to each table
3. Configure select field choices
4. Set up linked record relationships
5. Create views with filters and sorts
6. Load seed data from `airtable/seed-data/`

```bash
# Validate schema before applying
python scripts/validation/validate-airtable-schema.py

# Apply via Airtable Web API (manual steps in Airtable UI)
# Or use the Airtable metadata API if available on your plan
```

## Rollback Instructions

1. This is the initial migration - rollback means deleting the entire base
2. Confirm no production data exists before rolling back
3. Delete all tables in reverse order (Errors first, Work_Items last)
4. Or delete the entire Airtable base and recreate empty

## Post-checks

- [ ] All 9 tables created successfully
- [ ] All relationships link correctly (test by creating a sample record)
- [ ] All formula fields calculate correctly
- [ ] All views display with correct filters
- [ ] Select field choices match schema definition
- [ ] Seed data loads without errors
- [ ] State machine transitions work (test: create Work_Item, change state)

## Notes

- Individual table schemas are in `airtable/schema/[TableName].json`
- Complete schema is in `airtable/schema/schema.json`
- This migration should only be applied to a new, empty base
- Allow 30-60 minutes for manual setup via Airtable UI
