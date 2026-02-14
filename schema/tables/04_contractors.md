# Contractors Table — Complete Field Specification

External contractor/vendor companies. Each contractor can have multiple contacts (linked via People table).
Contractors bid on RFQs and are assigned to external work items.

---

## Identity

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 1 | `contractor_id` | Auto number | — | Auto-incrementing ID |
| 2 | `company_name` | Single line text | Max 200 chars | Registered company name, e.g. "Aquaflow Plumbing Ltd" |
| 3 | `trading_name` | Single line text | Max 200 chars | Trading as name if different from registered |
| 4 | `company_number` | Single line text | Max 20 chars | Companies House registration number |
| 5 | `vat_number` | Single line text | Max 20 chars | VAT registration number (if VAT registered) |
| 6 | `status` | Single select | `APPROVED`, `PENDING_APPROVAL`, `SUSPENDED`, `BLACKLISTED` | Vetting status |

## Contact Details

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 7 | `primary_phone` | Phone number | +44 format | Main office/business phone |
| 8 | `whatsapp_phone` | Phone number | +44 format | WhatsApp number for receiving RFQs and job updates |
| 9 | `email` | Email | — | Primary business email |
| 10 | `website` | URL | — | Company website |
| 11 | `address` | Long text | Plain text | Registered business address |
| 12 | `postcode` | Single line text | Max 10 chars | Business postcode |
| 13 | `contacts` | Link to another record | Links to **People** table (where role = CONTRACTOR_CONTACT) | Individual contacts at this company |

## Trade & Coverage

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 14 | `trade_disciplines` | Multiple select | `PLUMBING`, `ELECTRICAL`, `HVAC`, `FIRE_SAFETY`, `STRUCTURAL`, `DOORS_WINDOWS`, `LIFTS`, `ROOFING`, `DECORATION`, `CLEANING`, `PEST_CONTROL`, `ACCESS_CONTROL`, `GAS`, `DRAINAGE`, `GLAZING`, `FLOORING`, `GENERAL_BUILDING` | Trades this contractor covers |
| 15 | `coverage_postcodes` | Long text | Plain text | Comma-separated postcode prefixes: "SW, SE, EC, WC, W, E, N, NW" or specific: "SW1, SW3, SW7" |
| 16 | `max_travel_radius_miles` | Number | Integer | Maximum distance willing to travel from base |
| 17 | `preferred_sites` | Link to another record | Links to **Sites** table | Sites where this contractor is pre-approved |
| 18 | `emergency_callout` | Checkbox | — | TRUE if available for out-of-hours/emergency work |
| 19 | `emergency_callout_rate` | Currency | GBP (£), 2 decimal places | Emergency callout charge |

## Certifications & Compliance

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 20 | `certifications` | Multiple select | `GAS_SAFE`, `NICEIC`, `NAPIT`, `OFTEC`, `F_GAS`, `CSCS`, `CHAS`, `SAFE_CONTRACTOR`, `CONSTRUCTIONLINE`, `ISO_9001`, `ISO_14001`, `ISO_45001` | Professional certifications and accreditations |
| 21 | `gas_safe_number` | Single line text | Max 20 chars | Gas Safe Register number (if applicable) |
| 22 | `niceic_number` | Single line text | Max 20 chars | NICEIC registration number (if applicable) |
| 23 | `certification_expiry_dates` | Long text | Plain text | JSON: `{"GAS_SAFE":"2026-03-15","NICEIC":"2025-12-01"}` |

## Insurance

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 24 | `public_liability_insured` | Checkbox | — | TRUE if has public liability insurance |
| 25 | `public_liability_amount` | Currency | GBP (£), 0 decimal places | Cover amount, e.g. £5,000,000 |
| 26 | `public_liability_expiry` | Date | DD/MM/YYYY | Policy expiry date |
| 27 | `employers_liability_insured` | Checkbox | — | TRUE if has employer's liability insurance |
| 28 | `employers_liability_expiry` | Date | DD/MM/YYYY | Policy expiry date |
| 29 | `professional_indemnity_insured` | Checkbox | — | TRUE if has professional indemnity insurance |
| 30 | `professional_indemnity_expiry` | Date | DD/MM/YYYY | Policy expiry date |
| 31 | `insurance_documents` | Attachment | Allow PDF | Uploaded insurance certificates |

## Performance Metrics

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 32 | `avg_response_time_hours` | Formula | Average of `DATETIME_DIFF(quote.submitted_at, quote.requested_at)` across linked Quotes | Average time to respond to RFQs |
| 33 | `rfq_acceptance_rate` | Formula | `COUNT(quotes WHERE status != DECLINED) / COUNT(all quotes) * 100` | Percentage of RFQs they respond to |
| 34 | `quote_win_rate` | Formula | `COUNT(quotes WHERE status = ACCEPTED) / COUNT(quotes WHERE status IN (ACCEPTED, REJECTED)) * 100` | Percentage of submitted quotes that are accepted |
| 35 | `avg_rating` | Rollup | Average of **Work_Items** → `tenant_satisfaction_rating` where `assigned_to_contractor = this` | Average tenant satisfaction score |
| 36 | `total_jobs_completed` | Count | Count of linked **Work_Items** where `current_state = CLOSED` | Total completed jobs |
| 37 | `total_jobs_value` | Rollup | SUM of **Work_Items** → `actual_cost` where `assigned_to_contractor = this` | Total value of completed works |

## Financial

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 38 | `payment_terms_days` | Number | Integer | Standard payment terms (e.g. 30 = Net 30) |
| 39 | `bank_sort_code` | Single line text | Max 8 chars | UK sort code (xx-xx-xx format) |
| 40 | `bank_account_number` | Single line text | Max 10 chars | UK bank account number |
| 41 | `xero_contact_id` | Single line text | Max 100 chars | Xero accounting contact ID |
| 42 | `day_rate` | Currency | GBP (£), 2 decimal places | Standard day rate (if applicable) |
| 43 | `hourly_rate` | Currency | GBP (£), 2 decimal places | Standard hourly rate (if applicable) |

## Relationships

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 44 | `quotes` | Link to another record | Links to **Quotes** table | All quotes submitted by this contractor |
| 45 | `work_items` | Link to another record | Links to **Work_Items** table | All work items assigned to this contractor |
| 46 | `payments` | Link to another record | Links to **Payments** table | All payments made to this contractor |

## System

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 47 | `onboarded_date` | Date | DD/MM/YYYY | When this contractor was approved |
| 48 | `last_review_date` | Date | DD/MM/YYYY | Last performance review date |
| 49 | `next_review_date` | Date | DD/MM/YYYY | Next scheduled review |
| 50 | `notes` | Long text | Rich text enabled | Internal notes about this contractor |

---

## Field Count: 50
