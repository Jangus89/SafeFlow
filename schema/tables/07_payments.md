# Payments Table — Complete Field Specification

Tracks invoices and payments for completed work. Integrates with Xero accounting.
Each record represents a single invoice/payment event.

---

## Identity

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 1 | `payment_id` | Auto number | — | Auto-incrementing ID |
| 2 | `payment_reference` | Formula | `"INV-" & REPT("0", 5 - LEN(RECORD_NUMBER())) & RECORD_NUMBER()` | Internal reference (INV-00001) |

## Links

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 3 | `work_item` | Link to another record | Links to **Work_Items** table | The job this payment relates to |
| 4 | `contractor` | Link to another record | Links to **Contractors** table | The contractor being paid |
| 5 | `site` | Link to another record | Links to **Sites** table | The site (for cost allocation) |
| 6 | `approved_by` | Link to another record | Links to **People** table | Person who approved this payment |

## Invoice Details

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 7 | `invoice_type` | Single select | `CONTRACTOR_INVOICE`, `INTERNAL_COST`, `RECHARGE_TO_TENANT`, `EMERGENCY_CALLOUT` | Type of invoice |
| 8 | `contractor_invoice_number` | Single line text | Max 50 chars | The contractor's own invoice number |
| 9 | `contractor_invoice_date` | Date | DD/MM/YYYY | Date on the contractor's invoice |
| 10 | `invoice_document` | Attachment | Allow PDF, images | Scanned/uploaded invoice document |

## Amounts

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 11 | `net_amount` | Currency | GBP (£), 2 decimal places | Invoice amount before VAT |
| 12 | `vat_amount` | Currency | GBP (£), 2 decimal places | VAT amount |
| 13 | `gross_amount` | Formula | `{net_amount} + {vat_amount}` | Total including VAT |
| 14 | `retention_amount` | Currency | GBP (£), 2 decimal places | Amount held in retention (if applicable) |
| 15 | `amount_payable` | Formula | `{gross_amount} - {retention_amount}` | Net amount to pay now |
| 16 | `currency` | Single line text | Default: "GBP" | Always GBP |

## Payment Status

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 17 | `status` | Single select | `DRAFT` (grey), `AWAITING_APPROVAL` (yellow), `APPROVED` (blue), `SUBMITTED_TO_XERO` (purple), `PAID` (green), `PARTIALLY_PAID` (orange), `OVERDUE` (red), `DISPUTED` (dark red), `CANCELLED` (dark grey) | Current payment status |
| 18 | `due_date` | Date | DD/MM/YYYY | Payment due date (calculated from invoice date + payment terms) |
| 19 | `paid_date` | Date | DD/MM/YYYY | Date payment was actually made |
| 20 | `paid_amount` | Currency | GBP (£), 2 decimal places | Amount actually paid (may differ from amount_payable for partial payments) |
| 21 | `is_overdue` | Formula | `IF(AND({status} != "PAID", {status} != "CANCELLED", NOW() > {due_date}), TRUE(), FALSE())` | TRUE if past due date and not yet paid |
| 22 | `days_overdue` | Formula | `IF({is_overdue}, DATETIME_DIFF(NOW(), {due_date}, 'days'), 0)` | Number of days past due |

## Xero Integration

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 23 | `xero_invoice_id` | Single line text | Max 100 chars | Xero invoice UUID |
| 24 | `xero_invoice_number` | Single line text | Max 50 chars | Xero-generated invoice number |
| 25 | `xero_status` | Single line text | Max 50 chars | Status in Xero: DRAFT, SUBMITTED, AUTHORISED, PAID, VOIDED |
| 26 | `xero_sync_at` | Date | Include time, GMT timezone | Last time this record was synced with Xero |
| 27 | `xero_sync_error` | Long text | Plain text | Error message if Xero sync failed |
| 28 | `xero_account_code` | Single line text | Max 20 chars | Xero nominal account code for cost allocation |
| 29 | `xero_tracking_category` | Single line text | Max 100 chars | Xero tracking category (typically site name) |

## System

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 30 | `created_at` | Date | Include time, GMT timezone | When this payment record was created |
| 31 | `notes` | Long text | Plain text | Internal notes about this payment |

---

## Field Count: 31
