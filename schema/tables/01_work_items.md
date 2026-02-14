# Work_Items Table — Complete Field Specification

The central table of SafeFlow. Each record represents a single job/work order reported
by a tenant (via WhatsApp) or created manually by a property manager.

---

## Identity & Reference

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 1 | `record_id` | Auto number | — | Airtable auto-incrementing ID |
| 2 | `job_reference` | Formula | `"WO-" & REPT("0", 5 - LEN(RECORD_NUMBER())) & RECORD_NUMBER()` | Human-readable reference (WO-00001, WO-00002…) |
| 3 | `title` | Single line text | Max 200 chars | Short description, LLM-extracted from tenant message (e.g. "Leaking tap in ground floor kitchen") |
| 4 | `description` | Long text | Rich text enabled | Full description of the issue. May contain LLM-summarised content from multiple WhatsApp messages |
| 5 | `category` | Single select | `PLUMBING`, `ELECTRICAL`, `HVAC`, `FIRE_SAFETY`, `STRUCTURAL`, `DOORS_WINDOWS`, `LIFTS`, `ROOFING`, `DECORATION`, `CLEANING`, `PEST_CONTROL`, `ACCESS_CONTROL`, `GENERAL`, `OTHER` | Trade category, LLM-classified from tenant description |
| 6 | `priority` | Single select | `P1_EMERGENCY` (red), `P2_URGENT` (orange), `P3_STANDARD` (yellow), `P4_PLANNED` (blue) | Priority level. P1 = health/safety risk, P2 = within 24h, P3 = within 5 working days, P4 = scheduled maintenance |

## State Machine

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 7 | `current_state` | Single select | `INTAKE`, `CLARIFICATION`, `ASSESSMENT`, `ASSIGNED_INTERNAL`, `RFQ_SENT`, `QUOTES_RECEIVED`, `QUOTE_ACCEPTED`, `IN_PROGRESS_INTERNAL`, `IN_PROGRESS_EXTERNAL`, `VERIFICATION`, `PAYMENT_PENDING`, `CLOSED` | Current position in the state machine. Colours: INTAKE (grey), CLARIFICATION (purple), ASSESSMENT (blue), ASSIGNED_* (cyan), RFQ_*/QUOTES_* (orange), IN_PROGRESS_* (yellow), VERIFICATION (teal), PAYMENT_PENDING (pink), CLOSED (green) |
| 8 | `state_started_at` | Date | Include time, GMT timezone | Timestamp when `current_state` was entered. Updated on every state transition |
| 9 | `state_history` | Long text | Plain text | JSON array of state transitions: `[{"from":"INTAKE","to":"ASSESSMENT","at":"2025-06-15T10:30:00Z","by":"rec_person_id","reason":"Auto-triaged by LLM"}]` |
| 10 | `previous_state` | Single select | Same options as `current_state` | The state before the current one. Useful for rollback logic |
| 11 | `closed_at` | Date | Include time, GMT timezone | Timestamp when state moved to CLOSED. Null while open |
| 12 | `resolution` | Single select | `COMPLETED`, `CANCELLED_DUPLICATE`, `CANCELLED_NO_ACCESS`, `CANCELLED_TENANT_WITHDREW`, `CANCELLED_NOT_LANDLORD_RESPONSIBILITY` | How the work item was resolved |

## SLA & Timing

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 13 | `sla_target_hours` | Number | Integer, no decimal | SLA target in hours based on priority. Populated by automation: P1=4, P2=24, P3=120 (5 days), P4=480 (20 days) |
| 14 | `sla_deadline` | Formula | `DATEADD({created_at}, {sla_target_hours}, 'hours')` | Calculated SLA deadline datetime |
| 15 | `is_overdue` | Formula | `IF(AND({current_state} != "CLOSED", NOW() > {sla_deadline}), TRUE(), FALSE())` | Boolean: TRUE if past SLA and not closed |
| 16 | `time_in_current_state_hours` | Formula | `ROUND(DATETIME_DIFF(NOW(), {state_started_at}, 'hours'), 1)` | Hours spent in current state (live-updating) |
| 17 | `total_resolution_hours` | Formula | `IF({closed_at}, ROUND(DATETIME_DIFF({closed_at}, {created_at}, 'hours'), 1), BLANK())` | Total hours from creation to close. Blank while open |
| 18 | `created_at` | Date | Include time, GMT timezone | When the work item was first created |

## Location & Site

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 19 | `site` | Link to another record | Links to **Sites** table | The property/building where this issue is located |
| 20 | `location_in_building` | Single line text | Max 200 chars | Specific location, e.g. "3rd floor, flat 12, bathroom" or "Roof access stairwell" |
| 21 | `floor` | Single line text | Max 20 chars | Floor number/name: "Ground", "1st", "2nd", "Basement", "Roof" |
| 22 | `area_type` | Single select | `COMMON_AREA`, `TENANT_UNIT`, `EXTERNAL`, `PLANT_ROOM`, `CAR_PARK`, `ROOF`, `STAIRWELL`, `LIFT_SHAFT`, `RECEPTION`, `OTHER` | Type of area within the building |

## People & Assignment

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 23 | `reported_by` | Link to another record | Links to **People** table | The tenant or person who reported the issue |
| 24 | `managed_by` | Link to another record | Links to **People** table | The property manager responsible for this work item |
| 25 | `assigned_to_engineer` | Link to another record | Links to **People** table | Internal engineer assigned (null if external) |
| 26 | `assigned_to_contractor` | Link to another record | Links to **Contractors** table | External contractor assigned (null if internal) |
| 27 | `assignment_type` | Single select | `INTERNAL`, `EXTERNAL`, `UNASSIGNED` | Whether assigned to in-house engineer or external contractor |
| 28 | `verified_by` | Link to another record | Links to **People** table | Supervisor who verified completion |

## LLM Processing

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 29 | `llm_extracted_summary` | Long text | Plain text | LLM-generated structured summary of the issue from WhatsApp messages |
| 30 | `llm_category_confidence` | Percent | 1 decimal place | Confidence score (0–100%) of the LLM category classification |
| 31 | `llm_priority_confidence` | Percent | 1 decimal place | Confidence score of the LLM priority classification |
| 32 | `llm_suggested_action` | Long text | Plain text | LLM recommendation: e.g. "Assign to internal plumber — standard leak repair" |
| 33 | `llm_raw_output` | Long text | Plain text | Full JSON output from LLM processing for audit/debug |
| 34 | `requires_human_review` | Checkbox | — | TRUE if LLM confidence is below threshold or edge case detected |

## Evidence & Media

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 35 | `evidence_photos` | Attachment | Allow images (jpg, png, heic) | Photos uploaded by tenant via WhatsApp or by engineer on-site |
| 36 | `evidence_videos` | Attachment | Allow video (mp4, mov) | Videos of the issue |
| 37 | `completion_photos` | Attachment | Allow images | Before/after photos taken by engineer/contractor on completion |
| 38 | `media_urls` | Long text | Plain text | JSON array of WhatsApp media URLs (raw, before download): `["https://cdn.360dialog.io/…"]` |

## Financial / Payment

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 39 | `estimated_cost` | Currency | GBP (£), 2 decimal places | Initial cost estimate (from LLM or property manager) |
| 40 | `accepted_quote_amount` | Rollup | Rollup of **Quotes** table → `total_amount` where `status = ACCEPTED`. SUM | Total value of accepted quote(s) |
| 41 | `actual_cost` | Currency | GBP (£), 2 decimal places | Final actual cost once invoiced |
| 42 | `payment_status` | Single select | `NOT_APPLICABLE`, `AWAITING_INVOICE`, `INVOICE_RECEIVED`, `APPROVED`, `PAID`, `DISPUTED` | Current payment status |
| 43 | `quotes` | Link to another record | Links to **Quotes** table | All quotes received for this work item |
| 44 | `payments` | Link to another record | Links to **Payments** table | Associated payment/invoice records |

## Communication

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 45 | `interaction_logs` | Link to another record | Links to **Interaction_Logs** table | All WhatsApp messages related to this work item |
| 46 | `pending_question` | Link to another record | Links to **Question_Bank** table | Current question being asked (during CLARIFICATION state) |
| 47 | `clarification_attempts` | Number | Integer | Count of clarification questions asked. Cap at 3 before escalating to human |
| 48 | `tenant_satisfaction_rating` | Rating | 1–5 stars | Tenant satisfaction score collected after CLOSED |
| 49 | `tenant_feedback` | Long text | Plain text | Free-text feedback from tenant after closure |

## Automation & System

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 50 | `whatsapp_thread_id` | Single line text | Max 100 chars | WhatsApp conversation thread identifier for message correlation |
| 51 | `source_channel` | Single select | `WHATSAPP`, `PORTAL`, `PHONE`, `EMAIL`, `MANUAL` | How the work item was originally reported |
| 52 | `n8n_workflow_id` | Single line text | Max 100 chars | ID of the n8n workflow execution that created/last processed this record |
| 53 | `last_automation_error` | Long text | Plain text | Last error from automation processing (null if no errors) |
| 54 | `is_recurring` | Checkbox | — | TRUE if this is a recurring/repeat issue at the same location |
| 55 | `parent_work_item` | Link to another record | Links to **Work_Items** (self-referencing) | If this is a follow-up job, links to the original work item |
| 56 | `tags` | Multiple select | `HEALTH_AND_SAFETY`, `INSURANCE_CLAIM`, `REPEAT_ISSUE`, `TENANT_ESCALATION`, `EMERGENCY_CALLOUT`, `WEEKEND_WORK`, `OUT_OF_HOURS`, `AWAITING_PARTS`, `LANDLORD_APPROVAL_NEEDED` | Freeform tags for filtering and reporting |
| 57 | `notes_internal` | Long text | Rich text enabled | Internal notes visible only to property managers and supervisors |

---

## Field Count Summary

| Category | Fields |
|----------|--------|
| Identity & Reference | 6 |
| State Machine | 6 |
| SLA & Timing | 6 |
| Location & Site | 4 |
| People & Assignment | 6 |
| LLM Processing | 6 |
| Evidence & Media | 4 |
| Financial / Payment | 6 |
| Communication | 5 |
| Automation & System | 8 |
| **Total** | **57** |
