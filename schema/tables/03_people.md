# People Table — Complete Field Specification

All human users of the system: tenants, property managers, engineers, contractors' contacts,
and supervisors. WhatsApp phone number is the primary identifier.

---

## Identity

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 1 | `person_id` | Auto number | — | Auto-incrementing ID |
| 2 | `full_name` | Single line text | Max 200 chars | Full name, e.g. "James Whitfield" |
| 3 | `first_name` | Single line text | Max 100 chars | First name |
| 4 | `last_name` | Single line text | Max 100 chars | Last name |
| 5 | `email` | Email | — | Email address (optional for tenants) |
| 6 | `phone_whatsapp` | Phone number | +44 format | Primary WhatsApp number — **the unique identifier** for matching inbound messages |
| 7 | `phone_secondary` | Phone number | +44 format | Secondary/office phone (optional) |
| 8 | `status` | Single select | `ACTIVE`, `INACTIVE`, `BLOCKED` | Whether this person can interact with the system |

## Roles & Permissions

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 9 | `roles` | Multiple select | `TENANT`, `PROPERTY_MANAGER`, `ENGINEER`, `CONTRACTOR_CONTACT`, `SUPERVISOR`, `ADMIN` | A person can hold multiple roles (e.g. PROPERTY_MANAGER + SUPERVISOR) |
| 10 | `permission_level` | Single select | `BASIC`, `STANDARD`, `ELEVATED`, `ADMIN` | Overall permission tier. BASIC=can report, STANDARD=can manage, ELEVATED=can approve, ADMIN=full access |
| 11 | `can_approve_quotes` | Checkbox | — | TRUE if this person can accept/reject contractor quotes |
| 12 | `approval_limit` | Currency | GBP (£), 2 decimal places | Maximum quote value this person can approve without escalation (e.g. £5,000.00) |
| 13 | `can_close_work_items` | Checkbox | — | TRUE if this person can move work items to CLOSED |
| 14 | `can_create_work_items` | Checkbox | — | TRUE if this person can manually create work items (not just via WhatsApp) |

## Site Assignments

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 15 | `sites` | Link to another record | Links to **Sites** table | Sites this person is associated with |
| 16 | `primary_site` | Link to another record | Links to **Sites** table | The main site (for tenants — where they live/work) |
| 17 | `unit_number` | Single line text | Max 50 chars | Tenant's unit/flat/suite number within the site |

## Engineer-Specific

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 18 | `trade_skills` | Multiple select | `PLUMBING`, `ELECTRICAL`, `HVAC`, `GENERAL_MAINTENANCE`, `CARPENTRY`, `PAINTING`, `LOCKSMITH`, `FIRE_SYSTEMS`, `LIFTS`, `ROOFING` | Skills/trades for internal engineers |
| 19 | `certifications` | Multiple select | `GAS_SAFE`, `NICEIC`, `OFTEC`, `F_GAS`, `CSCS`, `IPAF`, `PASMA`, `FIRST_AID`, `ASBESTOS_AWARENESS`, `CONFINED_SPACES` | Professional certifications held |
| 20 | `max_concurrent_jobs` | Number | Integer | Maximum jobs this engineer can handle simultaneously |
| 21 | `current_job_count` | Count | Count of linked **Work_Items** where `assigned_to_engineer = this` AND `current_state` IN (ASSIGNED_INTERNAL, IN_PROGRESS_INTERNAL) | How many active jobs assigned |
| 22 | `availability_status` | Single select | `AVAILABLE`, `BUSY`, `ON_LEAVE`, `OFF_SICK` | Current availability |

## Contractor Link

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 23 | `contractor_company` | Link to another record | Links to **Contractors** table | If role is CONTRACTOR_CONTACT, links to their company |

## Communication Preferences

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 24 | `preferred_language` | Single select | `en`, `es`, `pl`, `pt`, `ro`, `ur`, `bn` | Preferred language for WhatsApp messages |
| 25 | `whatsapp_opted_in` | Checkbox | — | TRUE if they've opted in to WhatsApp communications |
| 26 | `opt_in_date` | Date | DD/MM/YYYY | Date they opted in (for GDPR compliance) |
| 27 | `last_interaction_at` | Date | Include time, GMT timezone | Last time this person sent or received a WhatsApp message |

## Relationships

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 28 | `reported_work_items` | Link to another record | Links to **Work_Items** (via `reported_by`) | Work items this person reported |
| 29 | `managed_work_items` | Link to another record | Links to **Work_Items** (via `managed_by`) | Work items this person manages |
| 30 | `assigned_work_items` | Link to another record | Links to **Work_Items** (via `assigned_to_engineer`) | Work items assigned to this engineer |
| 31 | `interaction_logs` | Link to another record | Links to **Interaction_Logs** | All message history for this person |

## System

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 32 | `created_at` | Date | Include time, GMT timezone | When this person record was created |
| 33 | `notes` | Long text | Plain text | Internal notes about this person |
| 34 | `gdpr_data_request_date` | Date | DD/MM/YYYY | Date of last GDPR subject access request (if any) |

---

## Field Count: 34
