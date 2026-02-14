# SafeFlow — Recommended Airtable Views

Each table should have these views configured. Views are listed by table with
filter conditions, sort order, visible fields, and grouping.

---

## Work_Items Views

### 1. Active Work (Default — Daily Operations)
- **Filter:** `current_state` is not `CLOSED`
- **Sort:** `priority` ascending (P1 first), then `created_at` ascending (oldest first)
- **Group by:** `current_state`
- **Colour:** Row colour by `priority` (P1=red, P2=orange, P3=yellow, P4=blue)
- **Visible fields:** `job_reference`, `title`, `category`, `priority`, `current_state`, `time_in_current_state_display`, `site` (lookup: site_name), `assignment_type`, `assigned_to_engineer` / `assigned_to_contractor`, `is_overdue`
- **Hidden:** LLM fields, raw data, system fields

### 2. Overdue Jobs (Escalation Board)
- **Filter:** `is_overdue` = TRUE AND `current_state` is not `CLOSED`
- **Sort:** `sla_deadline` ascending (most overdue first)
- **Group by:** `priority`
- **Colour:** Row colour by `time_in_current_state_hours` (>48h=red, 24-48h=orange, <24h=yellow)
- **Visible fields:** `job_reference`, `title`, `priority`, `current_state`, `sla_deadline`, `time_in_current_state_display`, `site`, `managed_by`, `reported_by`

### 3. By Contractor (Vendor Management)
- **Filter:** `assignment_type` = `EXTERNAL`
- **Sort:** `created_at` descending
- **Group by:** `assigned_to_contractor`
- **Visible fields:** `job_reference`, `title`, `current_state`, `category`, `accepted_quote_amount`, `actual_cost`, `payment_status`

### 4. Recently Closed (Reporting)
- **Filter:** `current_state` = `CLOSED` AND `closed_at` is within the past 30 days
- **Sort:** `closed_at` descending
- **Visible fields:** `job_reference`, `title`, `category`, `priority`, `total_resolution_hours`, `sla_status`, `actual_cost`, `tenant_satisfaction_rating`, `resolution`

### 5. Kanban Board
- **Type:** Kanban view
- **Stack by:** `current_state`
- **Card fields:** `job_reference`, `title`, `priority`, `site`, `assignment_type`
- **Card colour:** By `priority`

### 6. My Jobs (Personal — filtered by current user)
- **Filter:** `managed_by` or `assigned_to_engineer` = current user (use Airtable's "Me" filter if using Airtable Interface)
- **Sort:** `priority` ascending, `created_at` ascending
- **Group by:** `current_state`

### 7. Awaiting Quotes
- **Filter:** `current_state` IN (`RFQ_SENT`, `QUOTES_RECEIVED`)
- **Sort:** `state_started_at` ascending
- **Visible fields:** `job_reference`, `title`, `site`, `category`, `quotes` (expanded), `time_in_current_state_display`

### 8. Calendar View
- **Type:** Calendar view
- **Date field:** `sla_deadline`
- **Colour:** By `priority`
- **Filter:** `current_state` is not `CLOSED`

---

## Sites Views

### 1. Active Sites (Default)
- **Filter:** `status` = `ACTIVE`
- **Sort:** `site_name` ascending
- **Group by:** `subscription_tier`
- **Visible fields:** `site_reference`, `site_name`, `property_type`, `city`, `postcode`, `subscription_tier`, `monthly_fee`, `open_work_items_count`, `total_spend_ytd`

### 2. By Region
- **Filter:** None
- **Sort:** `city` ascending
- **Group by:** `city`
- **Visible fields:** `site_name`, `address_line_1`, `postcode`, `property_type`, `status`, `open_work_items_count`

### 3. Contract Expiring
- **Filter:** `contract_end_date` is within the next 90 days
- **Sort:** `contract_end_date` ascending
- **Visible fields:** `site_name`, `landlord_name`, `contract_start_date`, `contract_end_date`, `subscription_tier`, `monthly_fee`

### 4. Compliance Check
- **Filter:** `status` = `ACTIVE`
- **Sort:** `site_name` ascending
- **Visible fields:** `site_name`, `asbestos_register`, `epc_rating`, `listed_building_grade`, `fire_assembly_point`, `emergency_contacts`

### 5. Map View
- **Type:** Map view (if Airtable plan supports it)
- **Address field:** Combine `address_line_1`, `city`, `postcode`
- **Colour:** By `subscription_tier`

---

## People Views

### 1. All Active (Default)
- **Filter:** `status` = `ACTIVE`
- **Sort:** `full_name` ascending
- **Group by:** `roles` (first role)
- **Visible fields:** `full_name`, `roles`, `phone_whatsapp`, `email`, `primary_site`, `permission_level`

### 2. Tenants
- **Filter:** `roles` contains `TENANT` AND `status` = `ACTIVE`
- **Sort:** `full_name` ascending
- **Group by:** `primary_site`
- **Visible fields:** `full_name`, `phone_whatsapp`, `unit_number`, `primary_site`, `preferred_language`, `last_interaction_at`

### 3. Engineers
- **Filter:** `roles` contains `ENGINEER` AND `status` = `ACTIVE`
- **Sort:** `full_name` ascending
- **Visible fields:** `full_name`, `phone_whatsapp`, `trade_skills`, `certifications`, `availability_status`, `current_job_count`, `max_concurrent_jobs`

### 4. Approvers
- **Filter:** `can_approve_quotes` = TRUE
- **Sort:** `approval_limit` descending
- **Visible fields:** `full_name`, `roles`, `approval_limit`, `can_close_work_items`, `sites`

---

## Contractors Views

### 1. Approved Contractors (Default)
- **Filter:** `status` = `APPROVED`
- **Sort:** `company_name` ascending
- **Group by:** Primary trade (first in `trade_disciplines`)
- **Visible fields:** `company_name`, `trade_disciplines`, `coverage_postcodes`, `certifications`, `avg_rating`, `total_jobs_completed`, `emergency_callout`

### 2. Leaderboard (Performance)
- **Filter:** `status` = `APPROVED` AND `total_jobs_completed` > 0
- **Sort:** `avg_rating` descending
- **Visible fields:** `company_name`, `avg_rating`, `rfq_acceptance_rate`, `quote_win_rate`, `avg_response_time_hours`, `total_jobs_completed`, `total_jobs_value`

### 3. Insurance Expiring
- **Filter:** `public_liability_expiry` is within next 60 days OR `employers_liability_expiry` is within next 60 days
- **Sort:** Earliest expiry date first
- **Visible fields:** `company_name`, `public_liability_expiry`, `employers_liability_expiry`, `professional_indemnity_expiry`, `status`
- **Colour:** Row colour red if any expiry is in the past

### 4. By Trade
- **Filter:** `status` = `APPROVED`
- **Group by:** `trade_disciplines`
- **Sort:** `company_name` ascending
- **Visible fields:** `company_name`, `coverage_postcodes`, `hourly_rate`, `day_rate`, `emergency_callout`, `avg_rating`

### 5. Pending Approval
- **Filter:** `status` = `PENDING_APPROVAL`
- **Sort:** `onboarded_date` ascending (oldest pending first)
- **Visible fields:** `company_name`, `trade_disciplines`, `certifications`, `public_liability_insured`, `employers_liability_insured`

---

## Quotes Views

### 1. Pending Review (Default)
- **Filter:** `status` IN (`SUBMITTED`, `UNDER_REVIEW`, `PENDING`)
- **Sort:** `submitted_at` ascending
- **Group by:** `work_item` (lookup: job_reference)
- **Visible fields:** `quote_reference`, `contractor`, `total_amount`, `estimated_duration_hours`, `earliest_start_date`, `warranty_period_months`, `llm_value_score`, `status`

### 2. Comparison View
- **Filter:** `status` IN (`SUBMITTED`, `UNDER_REVIEW`, `PENDING`)
- **Sort:** `total_amount` ascending
- **Group by:** `work_item`
- **Visible fields:** `contractor`, `labour_cost`, `materials_cost`, `callout_charge`, `subtotal`, `vat_amount`, `total_amount`, `estimated_duration_hours`, `warranty_period_months`
- **Purpose:** Side-by-side quote comparison for the same job

### 3. Accepted Quotes
- **Filter:** `status` = `ACCEPTED`
- **Sort:** `decided_at` descending
- **Visible fields:** `quote_reference`, `work_item`, `contractor`, `total_amount`, `decided_at`, `decided_by`

### 4. Awaiting Response
- **Filter:** `status` = `REQUESTED`
- **Sort:** `requested_at` ascending
- **Visible fields:** `work_item`, `contractor`, `requested_at`, `response_time_hours`

---

## Interaction_Logs Views

### 1. Recent Messages (Default)
- **Filter:** `timestamp` is within past 7 days
- **Sort:** `timestamp` descending
- **Visible fields:** `timestamp`, `direction`, `message_type`, `message_body`, `person` (lookup: full_name), `work_item` (lookup: job_reference), `processing_status`

### 2. Unprocessed
- **Filter:** `processing_status` IN (`UNPROCESSED`, `FAILED`)
- **Sort:** `timestamp` ascending
- **Colour:** FAILED = red, UNPROCESSED = yellow
- **Visible fields:** `timestamp`, `direction`, `message_body`, `phone_number`, `processing_status`, `work_item`

### 3. By Work Item
- **Filter:** None
- **Sort:** `timestamp` ascending
- **Group by:** `work_item`
- **Purpose:** Full conversation thread for each job

### 4. Media Messages
- **Filter:** `message_type` IN (`IMAGE`, `VIDEO`, `DOCUMENT`)
- **Sort:** `timestamp` descending
- **Visible fields:** `timestamp`, `person`, `work_item`, `message_type`, `media_url`, `media_caption`

---

## Payments Views

### 1. Awaiting Action (Default)
- **Filter:** `status` IN (`DRAFT`, `AWAITING_APPROVAL`, `APPROVED`)
- **Sort:** `due_date` ascending
- **Group by:** `status`
- **Visible fields:** `payment_reference`, `work_item`, `contractor`, `gross_amount`, `status`, `due_date`, `is_overdue`

### 2. Overdue Payments
- **Filter:** `is_overdue` = TRUE
- **Sort:** `days_overdue` descending
- **Colour:** >30 days = red, 15-30 = orange, <15 = yellow
- **Visible fields:** `payment_reference`, `contractor`, `gross_amount`, `due_date`, `days_overdue`, `status`

### 3. Paid This Month
- **Filter:** `status` = `PAID` AND `paid_date` is within current month
- **Sort:** `paid_date` descending
- **Visible fields:** `payment_reference`, `work_item`, `contractor`, `net_amount`, `vat_amount`, `gross_amount`, `paid_date`, `xero_invoice_number`

### 4. By Contractor
- **Filter:** None
- **Sort:** `contractor` ascending, `due_date` descending
- **Group by:** `contractor`
- **Summary bar:** SUM of `gross_amount` per group

### 5. Xero Sync Status
- **Filter:** `status` NOT IN (`DRAFT`, `CANCELLED`)
- **Sort:** `xero_sync_at` descending
- **Visible fields:** `payment_reference`, `xero_invoice_id`, `xero_status`, `xero_sync_at`, `xero_sync_error`
- **Colour:** Red if `xero_sync_error` is not empty

---

## Errors Views

### 1. Open Errors (Default)
- **Filter:** `resolution_status` IN (`OPEN`, `INVESTIGATING`)
- **Sort:** `severity` custom order (CRITICAL first), then `occurred_at` descending
- **Colour:** By `severity`
- **Visible fields:** `error_reference`, `severity`, `scenario_name`, `error_message`, `occurred_at`, `resolution_status`, `work_item`

### 2. All Errors (Last 30 Days)
- **Filter:** `occurred_at` is within past 30 days
- **Sort:** `occurred_at` descending
- **Group by:** `scenario_name`
- **Visible fields:** `error_reference`, `severity`, `error_message`, `resolution_status`, `recurrence_count`

### 3. Recurring Issues
- **Filter:** `is_recurring` = TRUE
- **Sort:** `recurrence_count` descending
- **Visible fields:** `error_reference`, `scenario_name`, `module_name`, `error_message`, `recurrence_count`, `resolution_status`

---

## Question_Bank Views

### 1. Active Questions (Default)
- **Filter:** `is_active` = TRUE
- **Sort:** `ask_order` ascending
- **Group by:** `category_relevance`
- **Visible fields:** `question_code`, `question_text_en`, `maps_to_field`, `validation_type`, `is_required`, `whatsapp_format`

### 2. By Category
- **Filter:** `is_active` = TRUE
- **Group by:** `category_relevance`
- **Visible fields:** `question_code`, `question_text_en`, `ask_order`, `is_required`
