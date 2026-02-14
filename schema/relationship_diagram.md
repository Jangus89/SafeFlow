# SafeFlow — Entity Relationship Diagram

```mermaid
erDiagram
    Work_Items ||--o{ Quotes : "receives quotes"
    Work_Items ||--o{ Payments : "has payments"
    Work_Items ||--o{ Interaction_Logs : "has messages"
    Work_Items }o--|| Sites : "located at"
    Work_Items }o--o| People : "reported_by"
    Work_Items }o--o| People : "managed_by"
    Work_Items }o--o| People : "assigned_to_engineer"
    Work_Items }o--o| People : "verified_by"
    Work_Items }o--o| Contractors : "assigned_to_contractor"
    Work_Items }o--o| Question_Bank : "pending_question"
    Work_Items }o--o| Work_Items : "parent_work_item (self-ref)"
    Work_Items ||--o{ Errors : "related errors"

    Sites ||--o{ Work_Items : "has work items"
    Sites }o--o{ People : "has people"
    Sites }o--o{ Contractors : "preferred contractors"

    People ||--o{ Interaction_Logs : "has messages"
    People }o--o| Contractors : "works for (contractor_company)"

    Contractors ||--o{ Quotes : "submits quotes"
    Contractors ||--o{ Payments : "receives payments"

    Quotes }o--o| People : "submitted_by"
    Quotes }o--o| People : "decided_by"

    Payments }o--o| People : "approved_by"
    Payments }o--o| Sites : "cost allocated to"

    Interaction_Logs }o--o| Sites : "related to site"

    Errors }o--o| Work_Items : "related work item"
    Errors }o--o| People : "related person"
    Errors }o--o| Errors : "related errors (self-ref)"

    Work_Items {
        auto_number record_id PK
        formula job_reference "WO-00001"
        text title
        long_text description
        single_select current_state "12 states"
        single_select priority "P1-P4"
        single_select category "14 categories"
        date created_at
        date state_started_at
        single_select assignment_type "INTERNAL/EXTERNAL"
        currency estimated_cost "GBP"
        currency actual_cost "GBP"
        formula is_overdue "boolean"
        formula sla_deadline
    }

    Sites {
        auto_number site_id PK
        formula site_reference "SITE-0001"
        text site_name
        text address_line_1
        text city
        text postcode "UK format"
        single_select property_type "8 types"
        single_select subscription_tier "3 tiers"
        currency monthly_fee "GBP"
        phone whatsapp_intake_number "+44"
        single_select status "ACTIVE etc"
    }

    People {
        auto_number person_id PK
        text full_name
        phone phone_whatsapp "+44 (primary key)"
        email email
        multiple_select roles "6 roles"
        single_select permission_level "4 levels"
        currency approval_limit "GBP"
        checkbox can_approve_quotes
        single_select preferred_language "7 langs"
        single_select availability_status
    }

    Contractors {
        auto_number contractor_id PK
        text company_name
        text company_number "Companies House"
        text vat_number
        single_select status "4 statuses"
        multiple_select trade_disciplines "17 trades"
        multiple_select certifications "12 certs"
        checkbox public_liability_insured
        currency public_liability_amount "GBP"
        date public_liability_expiry
        formula avg_rating "1-5 stars"
        number payment_terms_days
    }

    Quotes {
        auto_number quote_id PK
        formula quote_reference "QT-00001"
        single_select status "8 statuses"
        currency labour_cost "GBP"
        currency materials_cost "GBP"
        currency callout_charge "GBP"
        formula subtotal "GBP"
        percent vat_rate "20%"
        formula total_amount "GBP"
        number estimated_duration_hours
        date expiry_date
    }

    Interaction_Logs {
        auto_number log_id PK
        date timestamp
        single_select direction "IN/OUT"
        single_select message_type "13 types"
        long_text message_body
        text whatsapp_message_id "wamid"
        single_select processing_status "5 statuses"
        single_select llm_intent "11 intents"
    }

    Payments {
        auto_number payment_id PK
        formula payment_reference "INV-00001"
        single_select invoice_type "4 types"
        currency net_amount "GBP"
        currency vat_amount "GBP"
        formula gross_amount "GBP"
        single_select status "9 statuses"
        date due_date
        date paid_date
        text xero_invoice_id
        formula is_overdue "boolean"
    }

    Question_Bank {
        auto_number question_id PK
        text question_code "Q_LOCATION etc"
        long_text question_text_en
        long_text question_text_es
        long_text question_text_pl
        single_select whatsapp_format "3 formats"
        text maps_to_field
        single_select validation_type "8 types"
        checkbox is_required
    }

    Errors {
        auto_number error_id PK
        formula error_reference "ERR-00001"
        date occurred_at
        single_select severity "5 levels"
        single_select scenario_name "14 scenarios"
        text module_name
        long_text error_message
        single_select resolution_status "5 statuses"
        checkbox is_recurring
        number recurrence_count
    }
```

---

## Relationship Summary Table

| From Table | Field | To Table | Cardinality | Description |
|-----------|-------|----------|-------------|-------------|
| Work_Items | `site` | Sites | Many-to-One | Each job is at one site; a site has many jobs |
| Work_Items | `reported_by` | People | Many-to-One | Each job reported by one person |
| Work_Items | `managed_by` | People | Many-to-One | Each job managed by one PM |
| Work_Items | `assigned_to_engineer` | People | Many-to-One | Internal assignment |
| Work_Items | `assigned_to_contractor` | Contractors | Many-to-One | External assignment |
| Work_Items | `verified_by` | People | Many-to-One | Completion verification |
| Work_Items | `quotes` | Quotes | One-to-Many | A job can have multiple quotes |
| Work_Items | `payments` | Payments | One-to-Many | A job can have multiple payments |
| Work_Items | `interaction_logs` | Interaction_Logs | One-to-Many | All messages for a job |
| Work_Items | `pending_question` | Question_Bank | Many-to-One | Current clarification question |
| Work_Items | `parent_work_item` | Work_Items | Many-to-One | Self-referencing for follow-ups |
| Sites | `people` | People | Many-to-Many | People assigned to sites |
| Sites | `preferred_contractors` | Contractors | Many-to-Many | Pre-approved contractors per site |
| People | `contractor_company` | Contractors | Many-to-One | Contractor contacts linked to company |
| Quotes | `contractor` | Contractors | Many-to-One | Who submitted the quote |
| Quotes | `submitted_by` | People | Many-to-One | Individual who submitted |
| Quotes | `decided_by` | People | Many-to-One | Who accepted/rejected |
| Payments | `contractor` | Contractors | Many-to-One | Who is being paid |
| Payments | `approved_by` | People | Many-to-One | Who approved payment |
| Payments | `site` | Sites | Many-to-One | Cost allocation |
| Interaction_Logs | `person` | People | Many-to-One | Who sent/received |
| Interaction_Logs | `site` | Sites | Many-to-One | Which site's intake number |
| Errors | `work_item` | Work_Items | Many-to-One | Related job |
| Errors | `person` | People | Many-to-One | Related person |
| Errors | `related_errors` | Errors | Many-to-Many | Self-referencing duplicates |
