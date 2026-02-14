# Sites Table — Complete Field Specification

Each record represents a single commercial property/building managed through SafeFlow.
Sites are the top-level entity — all work items, people, and contractors relate back to a site.

---

## Identity

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 1 | `site_id` | Auto number | — | Auto-incrementing ID |
| 2 | `site_reference` | Formula | `"SITE-" & REPT("0", 4 - LEN(RECORD_NUMBER())) & RECORD_NUMBER()` | Human-readable ref (SITE-0001) |
| 3 | `site_name` | Single line text | Max 200 chars | Property name, e.g. "Meridian House" or "The Chambers, Fleet Street" |
| 4 | `status` | Single select | `ACTIVE`, `ONBOARDING`, `SUSPENDED`, `OFFBOARDED` | Whether the site is actively managed |

## UK Address

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 5 | `address_line_1` | Single line text | Max 200 chars | Building number/name and street, e.g. "14-16 Fleet Street" |
| 6 | `address_line_2` | Single line text | Max 200 chars | Secondary address line (optional) |
| 7 | `city` | Single line text | Max 100 chars | City/town, e.g. "London", "Manchester", "Birmingham" |
| 8 | `county` | Single line text | Max 100 chars | County (optional), e.g. "Greater London", "West Midlands" |
| 9 | `postcode` | Single line text | Max 10 chars | UK postcode, e.g. "EC4A 2AB" |
| 10 | `country` | Single line text | Default: "United Kingdom" | Always "United Kingdom" |
| 11 | `what3words` | Single line text | Max 100 chars | what3words address for precise location (optional) |
| 12 | `latitude` | Number | 6 decimal places | GPS latitude for mapping |
| 13 | `longitude` | Number | 6 decimal places | GPS longitude for mapping |

## Property Details

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 14 | `property_type` | Single select | `OFFICE`, `RETAIL`, `RESIDENTIAL`, `INDUSTRIAL`, `MIXED_USE`, `HEALTHCARE`, `EDUCATION`, `HOSPITALITY` | Type of commercial property |
| 15 | `total_units` | Number | Integer | Total number of lettable units/suites |
| 16 | `total_floors` | Number | Integer | Number of floors including basement |
| 17 | `total_sqft` | Number | Integer | Total square footage |
| 18 | `year_built` | Number | Integer, 4 digits | Year the building was constructed |
| 19 | `epc_rating` | Single select | `A`, `B`, `C`, `D`, `E`, `F`, `G` | Energy Performance Certificate rating |
| 20 | `listed_building_grade` | Single select | `NONE`, `GRADE_I`, `GRADE_II_STAR`, `GRADE_II` | Heritage listing status |

## WhatsApp Configuration

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 21 | `whatsapp_intake_number` | Phone number | +44 format | The WhatsApp number tenants message to report issues at this site |
| 22 | `whatsapp_number_id` | Single line text | Max 50 chars | 360dialog phone number ID for API calls |
| 23 | `welcome_message_template` | Single line text | Max 100 chars | Name of the WhatsApp message template for first-contact tenants |

## Subscription & Billing

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 24 | `subscription_tier` | Single select | `ESSENTIAL`, `PROFESSIONAL`, `ENTERPRISE` | SafeFlow subscription level |
| 25 | `monthly_fee` | Currency | GBP (£), 2 decimal places | Monthly subscription fee |
| 26 | `contract_start_date` | Date | DD/MM/YYYY | When the management contract started |
| 27 | `contract_end_date` | Date | DD/MM/YYYY | When the management contract expires |
| 28 | `billing_contact_email` | Email | — | Email for invoicing |
| 29 | `xero_contact_id` | Single line text | Max 100 chars | Xero accounting contact ID for this site's landlord/owner |

## Relationships

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 30 | `work_items` | Link to another record | Links to **Work_Items** table | All work orders at this site |
| 31 | `people` | Link to another record | Links to **People** table (via junction) | All people associated with this site (tenants, managers, engineers) |
| 32 | `preferred_contractors` | Link to another record | Links to **Contractors** table | Pre-approved contractors for this site |
| 33 | `landlord_name` | Single line text | Max 200 chars | Landlord or building owner name/company |
| 34 | `managing_agent` | Single line text | Max 200 chars | Managing agent company name (if different from PM) |

## Operational

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 35 | `access_instructions` | Long text | Rich text enabled | How to access the building (key codes, security desk, etc.) |
| 36 | `emergency_contacts` | Long text | Plain text | JSON: `[{"name":"John","role":"Building Manager","phone":"+447700900001"}]` |
| 37 | `opening_hours` | Single line text | Max 200 chars | Standard opening hours, e.g. "Mon-Fri 08:00-18:00, Sat 09:00-13:00" |
| 38 | `out_of_hours_procedure` | Long text | Plain text | What to do for emergency callouts outside opening hours |
| 39 | `fire_assembly_point` | Single line text | Max 200 chars | Fire assembly point description |
| 40 | `asbestos_register` | Checkbox | — | TRUE if an asbestos register is on file |
| 41 | `notes` | Long text | Rich text enabled | General notes about the site |

## Metrics (Rollups)

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 42 | `open_work_items_count` | Count | Count of linked **Work_Items** where `current_state != CLOSED` | Number of currently open jobs |
| 43 | `total_work_items_count` | Count | Count of all linked **Work_Items** | Total jobs ever raised |
| 44 | `total_spend_ytd` | Rollup | Rollup of **Work_Items** → `actual_cost`, SUM, filtered to current year | Year-to-date spend on works |
| 45 | `avg_resolution_hours` | Rollup | Rollup of **Work_Items** → `total_resolution_hours`, AVERAGE | Average time to resolve jobs |

---

## Field Count: 45
