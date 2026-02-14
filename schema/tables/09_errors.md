# Errors Table — Complete Field Specification

System error log. Every automation failure, webhook error, or processing exception
is logged here for debugging and resolution tracking.

---

## Identity

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 1 | `error_id` | Auto number | — | Auto-incrementing ID |
| 2 | `error_reference` | Formula | `"ERR-" & REPT("0", 5 - LEN(RECORD_NUMBER())) & RECORD_NUMBER()` | Human-readable ref (ERR-00001) |
| 3 | `occurred_at` | Date | Include time, GMT timezone | When the error occurred |

## Error Details

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 4 | `severity` | Single select | `CRITICAL` (red), `HIGH` (orange), `MEDIUM` (yellow), `LOW` (blue), `INFO` (grey) | Error severity level |
| 5 | `scenario_name` | Single select | `WEBHOOK_INTAKE`, `STATE_TRANSITION`, `LLM_PROCESSING`, `RFQ_SEND`, `QUOTE_PROCESSING`, `PAYMENT_SYNC`, `WHATSAPP_SEND`, `WHATSAPP_RECEIVE`, `XERO_SYNC`, `AIRTABLE_WRITE`, `MEDIA_DOWNLOAD`, `TEMPLATE_SEND`, `SCHEDULED_TASK`, `OTHER` | Which business scenario/workflow was running |
| 6 | `module_name` | Single line text | Max 100 chars | Technical module/node that failed, e.g. "n8n.whatsapp_webhook", "n8n.airtable_update" |
| 7 | `error_message` | Long text | Plain text | The error message |
| 8 | `stack_trace` | Long text | Plain text | Full stack trace (if available) |
| 9 | `error_code` | Single line text | Max 50 chars | Error code if applicable, e.g. "WHATSAPP_131049", "XERO_VALIDATION" |

## Context

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 10 | `work_item` | Link to another record | Links to **Work_Items** table | Related work item (if applicable) |
| 11 | `person` | Link to another record | Links to **People** table | Related person (if applicable) |
| 12 | `payload` | Long text | Plain text | The input data/payload that caused the error (JSON) |
| 13 | `n8n_execution_id` | Single line text | Max 100 chars | n8n execution ID for the failed workflow |
| 14 | `n8n_workflow_name` | Single line text | Max 200 chars | Name of the n8n workflow that failed |

## Resolution

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 15 | `resolution_status` | Single select | `OPEN` (red), `INVESTIGATING` (yellow), `RESOLVED` (green), `WONT_FIX` (grey), `DUPLICATE` (light grey) | Whether this error has been addressed |
| 16 | `resolved_at` | Date | Include time, GMT timezone | When the error was resolved |
| 17 | `resolved_by` | Single line text | Max 100 chars | Person/system that resolved it |
| 18 | `resolution_notes` | Long text | Plain text | How the error was fixed |
| 19 | `is_recurring` | Checkbox | — | TRUE if this error has occurred before |
| 20 | `recurrence_count` | Number | Integer | How many times this same error has occurred |
| 21 | `related_errors` | Link to another record | Links to **Errors** table (self-referencing) | Related/duplicate error records |

---

## Field Count: 21
