# Scenario C - Outbound Message Sender

## Purpose

Scenario C is the outbound messaging gateway for the SafeFlow system. It receives notification requests from Scenario B (State Engine) and Scenario D (SLA Monitor), resolves recipient details, deduplicates recent messages, and dispatches WhatsApp messages via the 360dialog Cloud API.

All outbound communication -- whether a job confirmation to a tenant, an assignment notification to a contractor, or an escalation alert to a property manager -- flows through this scenario. This centralised approach ensures consistent message formatting, delivery tracking, rate limit compliance, and a complete audit trail in Airtable.

## Message Types Supported

| Type | Use Case | WhatsApp Window |
|------|----------|----------------|
| `template` | Pre-approved HSM messages (job created, escalation alerts) | Outside 24-hour window |
| `text` | Free-text status updates, clarification questions | Inside 24-hour window only |
| `interactive` | Button replies (accept/reject, verify/reopen) | Inside 24-hour window only |

## Module Flow

```
[1] Webhook - Outbound Request
 |  From Scenario B / D
 |  Validates X-Source-Scenario header
 |
 v
[2] Load Recipient Details
 |  Airtable People lookup by person_id
 |  Skipped if phone already provided
 |
 v
[3] Validate Recipient
 |  Check: valid phone number + active user
 |  Reject invalid recipients to DLQ
 |
 v
[4] Resolve Recipient Fields
 |  Consolidate phone, name, language
 |
 v
[5] Dedupe Check - Recent Messages
 |  Search DS_OUTBOUND_DEDUPE for matching key
 |  Key = phone + work_item_id + notification_type
 |
 v
[6] Filter - Skip Duplicates
 |  Stop if identical notification sent in last 5 minutes
 |
 v
[7] Record Dedupe Key
 |  Add to data store with 5-minute TTL
 |
 v
[8] Message Type Router
 |         |              |
 v         v              v
[9]      [10]           [11]
Template  Text         Interactive
Message   Message      Message
 |         |              |
 +----+----+----+---------+
      |
      v
[12] Create Interaction Log
 |   Log outbound message to Airtable
 |
 v
[14] Process Additional Recipients
     Re-invoke self for each extra recipient

[13] Error Handler - Send Failure (attached to modules 9, 10, 11)
     Classify error, retry logic, route to DLQ

[99] Global Error Handler (attached to all modules)
     Route to Scenario E (DLQ)
```

## Deduplication

Outbound deduplication prevents the same notification being sent to the same recipient multiple times within a short window. This protects against:

- Make.com webhook retries causing duplicate sends
- Multiple upstream scenarios triggering the same notification concurrently
- Rapid state transitions generating overlapping notifications

### Dedupe Key Format

```
{phone}_{work_item_id}_{notification_type}
```

Example: `447700900123_1042_JOB_CREATED`

### TTL

The dedupe window is 5 minutes. Records older than 5 minutes are eligible for cleanup.

## Recipient Resolution

When Scenario B or D sends a notification request, the recipient may be identified by `person_id` only (with `phone` and `name` left empty). This scenario resolves the full recipient details from the Airtable People table.

If the phone number is already provided in the request (e.g., for tenant notifications where the phone is known from the inbound message), the People table lookup is skipped to reduce Airtable API usage.

## Additional Recipients

Some notifications need to reach multiple people (e.g., cancellation notices to reporter, assignee, and property manager). The `additional_recipients` array in the request payload triggers a self-referencing webhook call for each extra recipient, ensuring each message is independently deduplicated, logged, and error-handled.

## WhatsApp Template Messages

Template messages (HSMs) are pre-approved by Meta and required for messaging outside the 24-hour conversation window. The following templates must be registered in the 360dialog Partner Hub:

| Template Name | Category | Parameters |
|--------------|----------|------------|
| `job_created_confirmation` | UTILITY | recipient_name, work_item_id, title, urgency |
| `job_accepted_notification` | UTILITY | work_item_id, title, contractor_name |
| `escalation_alert` | UTILITY | work_item_id, title, urgency, reason |
| `clarification_reminder` | UTILITY | recipient_name, work_item_id, title |
| `clarification_auto_cancel` | UTILITY | recipient_name, work_item_id, title |
| `verification_reminder` | UTILITY | recipient_name, work_item_id, title |
| `verification_auto_close` | UTILITY | recipient_name, work_item_id, title |
| `escalation_level_1_nudge` | UTILITY | work_item_id, title, urgency, minutes_overdue |
| `escalation_level_2_supervisor` | UTILITY | work_item_id, title, urgency, minutes_overdue, current_assignee |
| `escalation_level_3_critical` | UTILITY | work_item_id, title, urgency, minutes_overdue, current_assignee |

## Configuration Requirements

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `MAKE_WEBHOOK_URL_SCENARIO_C` | This scenario's webhook URL | `https://hook.eu1.make.com/...` |
| `MAKE_WEBHOOK_URL_SCENARIO_E` | Error Handler / DLQ webhook URL | `https://hook.eu1.make.com/...` |
| `360DIALOG_API_KEY` | 360dialog API key | `your-api-key` |
| `AIRTABLE_BASE_ID` | Airtable base identifier | `appXXXXXXXXXX` |
| `AIRTABLE_API_KEY` | Airtable personal access token | `pat...` |
| `DS_OUTBOUND_DEDUPE` | Make.com data store ID for outbound deduplication | `ds_654321` |

### Make.com Data Store

Create a data store named `DS_OUTBOUND_DEDUPE` with the following structure:

| Field | Type | Description |
|-------|------|-------------|
| `dedupe_key` | Text (key) | Composite key: phone_workItemId_notificationType |
| `sent_at` | Date | When the message was sent |
| `recipient` | Text | Recipient phone number |

Set the data store size limit to accommodate approximately 500 records (sufficient for the 5-minute TTL window at expected volumes).

### Airtable Tables Required

- **People** - Must include fields: `first_name`, `last_name`, `whatsapp_number`, `role`, `is_active`, `preferred_language`
- **Interaction_Logs** - Must include fields: `work_item_id`, `person_id`, `direction`, `channel`, `message_type`, `message_content`, `whatsapp_message_id`, `delivery_status`, `created_at`, `scenario_execution_id`, `notification_type`

## Testing

### Using Test Payloads

Test payload files are provided in the `test-payloads/` directory:

```bash
# Test a template message (job created confirmation)
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_C" \
  -H "Content-Type: application/json" \
  -H "X-Source-Scenario: scenario-b-state-engine" \
  -d @test-payloads/template-job-created.json

# Test a text status update
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_C" \
  -H "Content-Type: application/json" \
  -H "X-Source-Scenario: scenario-b-state-engine" \
  -d @test-payloads/text-status-update.json

# Test an interactive completion confirmation
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_C" \
  -H "Content-Type: application/json" \
  -H "X-Source-Scenario: scenario-b-state-engine" \
  -d @test-payloads/interactive-completion-confirm.json

# Test invalid payload (missing recipient)
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_C" \
  -H "Content-Type: application/json" \
  -H "X-Source-Scenario: scenario-b-state-engine" \
  -d @test-payloads/invalid-missing-recipient.json

# Test rate-limited response handling
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_C" \
  -H "Content-Type: application/json" \
  -H "X-Source-Scenario: scenario-b-state-engine" \
  -d @test-payloads/edge-rate-limited.json
```

### Validation Checklist

- [ ] Template message sends successfully via 360dialog API
- [ ] Text message sends successfully within 24-hour window
- [ ] Interactive message with buttons sends successfully
- [ ] Recipient is resolved from People table when phone not provided
- [ ] Invalid recipient (inactive or missing phone) is rejected to DLQ
- [ ] Duplicate notification within 5 minutes is filtered
- [ ] Interaction log created for every outbound message
- [ ] Failed send is logged with FAILED delivery status
- [ ] Additional recipients each receive their own message
- [ ] Rate-limited responses trigger retry with exponential backoff
- [ ] All errors route to Scenario E with full context

## Error Handling Strategy

### Per-Module Error Handling

| Module | Error Strategy | Rationale |
|--------|---------------|-----------|
| Load Recipient (2) | Route to error handler | Cannot send without recipient |
| Dedupe Check (5) | Ignore errors, continue | Better to duplicate than miss |
| Template Send (9) | Route to send error handler (13) | Classify and retry |
| Text Send (10) | Route to send error handler (13) | Classify and retry |
| Interactive Send (11) | Route to send error handler (13) | Classify and retry |
| Interaction Log (12) | Ignore | Message already sent; non-critical |
| All others | Global Error Handler (99) | Catch-all |

### Send Error Classification

| Error Type | Severity | Retry | Action |
|-----------|----------|-------|--------|
| 429 Rate Limited | LOW | Yes (60s delay) | Queue for retry |
| 500-503 Server Error | HIGH | Yes (30s delay) | Queue for retry |
| 404 Template Not Found | MEDIUM | No | Alert operations team |
| Session Expired (24h) | MEDIUM | No | Suggest template fallback |
| Invalid Phone Number | MEDIUM | No | Flag in DLQ |

## Operations Notes

### Operations Estimate

| Metric | Value |
|--------|-------|
| Operations per message | 6 |
| Average daily messages | 50 outbound |
| Daily operations | 300 |
| Monthly operations | ~9,000 |

### Rate Limits

- **360dialog**: 250 messages/second. Well within limits at current volumes.
- **Airtable**: 5 requests/second per base. This scenario makes 1-2 Airtable calls per message (recipient lookup + interaction log).
- **Make.com webhooks**: Queued automatically, no hard limit.

### 24-Hour Conversation Window

WhatsApp enforces a 24-hour conversation window. Free-text and interactive messages can only be sent within 24 hours of the recipient's last inbound message. Outside this window, only pre-approved template messages are permitted.

The State Engine (Scenario B) is responsible for selecting the correct message type. Scenario C does not enforce the window rule but will receive and log the 360dialog error if a session message is sent outside the window.

### Cost Estimate

At current volumes (50 outbound messages/day):
- Template messages (utility category): ~$0.035 per conversation
- Session messages (within window): no additional cost
- Monthly estimated cost: ~$30-50 depending on conversation mix
