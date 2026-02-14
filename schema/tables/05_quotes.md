# Quotes Table — Complete Field Specification

Each record is a single quote from a contractor in response to an RFQ (Request for Quotation).
A Work_Item can have multiple quotes from different contractors.

---

## Identity

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 1 | `quote_id` | Auto number | — | Auto-incrementing ID |
| 2 | `quote_reference` | Formula | `"QT-" & REPT("0", 5 - LEN(RECORD_NUMBER())) & RECORD_NUMBER()` | Human-readable ref (QT-00001) |

## Links

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 3 | `work_item` | Link to another record | Links to **Work_Items** table | The job this quote is for |
| 4 | `contractor` | Link to another record | Links to **Contractors** table | The contractor who submitted this quote |
| 5 | `submitted_by` | Link to another record | Links to **People** table | The individual who submitted the quote |

## Quote Status

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 6 | `status` | Single select | `REQUESTED` (grey), `PENDING` (yellow), `SUBMITTED` (blue), `UNDER_REVIEW` (orange), `ACCEPTED` (green), `REJECTED` (red), `EXPIRED` (dark grey), `WITHDRAWN` (light grey) | Current status of this quote |
| 7 | `requested_at` | Date | Include time, GMT timezone | When the RFQ was sent to this contractor |
| 8 | `submitted_at` | Date | Include time, GMT timezone | When the contractor submitted their quote |
| 9 | `decided_at` | Date | Include time, GMT timezone | When the quote was accepted/rejected |
| 10 | `decided_by` | Link to another record | Links to **People** table | Person who accepted/rejected the quote |
| 11 | `expiry_date` | Date | DD/MM/YYYY | Quote validity expiry date |
| 12 | `response_time_hours` | Formula | `IF({submitted_at}, ROUND(DATETIME_DIFF({submitted_at}, {requested_at}, 'hours'), 1), BLANK())` | Hours between RFQ sent and quote received |

## Financials

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 13 | `labour_cost` | Currency | GBP (£), 2 decimal places | Labour component of the quote |
| 14 | `materials_cost` | Currency | GBP (£), 2 decimal places | Materials/parts component |
| 15 | `callout_charge` | Currency | GBP (£), 2 decimal places | Callout/attendance fee (if applicable) |
| 16 | `subtotal` | Formula | `{labour_cost} + {materials_cost} + {callout_charge}` | Sum before VAT |
| 17 | `vat_rate` | Percent | Default 20% | VAT rate (standard 20%, may be 0% or 5% for some works) |
| 18 | `vat_amount` | Formula | `{subtotal} * {vat_rate}` | Calculated VAT amount |
| 19 | `total_amount` | Formula | `{subtotal} + {vat_amount}` | Total including VAT |
| 20 | `estimated_duration_hours` | Number | 1 decimal place | Estimated time to complete the work |
| 21 | `payment_terms` | Single line text | Max 50 chars | E.g. "Net 30", "50% upfront, 50% on completion" |

## Quote Details

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 22 | `scope_of_work` | Long text | Rich text enabled | Detailed description of what the quote covers |
| 23 | `exclusions` | Long text | Plain text | What is explicitly NOT included in this quote |
| 24 | `earliest_start_date` | Date | DD/MM/YYYY | Earliest date the contractor can start |
| 25 | `estimated_completion_date` | Date | DD/MM/YYYY | Expected completion date |
| 26 | `warranty_period_months` | Number | Integer | Warranty/guarantee period offered |
| 27 | `quote_document` | Attachment | Allow PDF, images | Uploaded formal quote document |

## LLM Analysis

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 28 | `llm_analysis` | Long text | Plain text | LLM comparison/analysis of this quote vs others and market rates |
| 29 | `llm_value_score` | Number | 1-10, 1 decimal place | LLM-assessed value-for-money score |
| 30 | `llm_flags` | Long text | Plain text | Any concerns flagged by LLM (e.g. "price 40% above market rate", "no warranty offered") |

## Communication

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 31 | `rejection_reason` | Long text | Plain text | Why the quote was rejected (for contractor feedback) |
| 32 | `notes` | Long text | Plain text | Internal notes about this quote |

---

## Field Count: 32
