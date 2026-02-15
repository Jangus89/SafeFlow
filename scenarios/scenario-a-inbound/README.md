# Scenario A - Inbound Message Handler

## Purpose

Scenario A is the front door of the SafeFlow system. It receives all inbound WhatsApp messages from tenants, contractors, and property managers via the 360dialog webhook, normalises the payload, deduplicates messages, logs every interaction to Airtable, and hands off an enriched payload to Scenario B (State Engine) for business logic processing.

This scenario is designed for UK commercial property facilities management. All messages arrive through a single WhatsApp Business Account managed via 360dialog's Cloud API.

## Module Flow

```
[1] Webhook - 360dialog Inbound
 |
 v
[2] Parse Message
 |  Extract sender_phone, sender_name, message_id, message_type,
 |  message_text, media_id, timestamp, button info
 |
 v
[3] Dedupe Check
 |  Search DS_PROCESSED_MESSAGES data store for message_id
 |
 v
[4] Filter - Skip Duplicates
 |  Stop execution if message already processed
 |
 v
[5] Record Message ID
 |  Add message_id to data store with 72-hour TTL
 |
 v
[6] Lookup Person
 |  Search Airtable People table by whatsapp_number
 |
 v
[7] Router - Known vs Unknown Person
 |              |
 |              v
 |         [8] Create Person Record
 |              (auto-register as TENANT)
 |              |
 v              v
[9] Extract Command
 |  Detect commands: done, accept, start, reject,
 |  cancel, hold, quote, approve
 |  Extract SF-XXXX job references from text
 |
 v
[10] Find Active Work Item
 |   Search Airtable Work_Items by job reference or person
 |
 v
[11] Create Interaction Log
 |   Log inbound message to Interaction_Logs table
 |
 v
[12] Handoff to Scenario B
     POST enriched payload to State Engine webhook

[99] Global Error Handler (attached to all modules)
     Routes errors to Scenario E (DLQ)
     Always returns HTTP 200 to 360dialog
```

## Message Types Handled

| Type | Payload Fields Used | Notes |
|------|-------------------|-------|
| `text` | `text.body` | Standard text messages |
| `image` | `image.id`, `image.caption` | Photos of issues, receipts |
| `document` | `document.id` | PDFs, invoices |
| `audio` | `audio.id` | Voice notes |
| `video` | `video.id` | Video of issues |
| `interactive` | `button_reply.id`, `button_reply.title` | Template button responses |
| `interactive` | `list_reply.id`, `list_reply.title` | Template list selections |

## Commands Recognised

Commands are extracted from either interactive button replies (by button ID) or from the first word of text messages (case-insensitive):

| Command | Typical Usage | Roles |
|---------|--------------|-------|
| `DONE` | Contractor marks work complete | Contractor |
| `ACCEPT` | Contractor accepts a job | Contractor |
| `START` | Contractor signals work started | Contractor |
| `REJECT` | Contractor declines a job | Contractor |
| `CANCEL` | Tenant or manager cancels a request | Tenant, Manager |
| `HOLD` | Manager puts work item on hold | Manager |
| `QUOTE` | Contractor submits a quote | Contractor |
| `APPROVE` | Manager approves a quote or work | Manager |

Job references in the format `SF-12345` are automatically extracted from message text.

## Configuration Requirements

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `MAKE_WEBHOOK_URL_SCENARIO_A` | This scenario's webhook URL | `https://hook.eu1.make.com/abc123...` |
| `MAKE_WEBHOOK_URL_SCENARIO_B` | State Engine webhook URL | `https://hook.eu1.make.com/def456...` |
| `MAKE_WEBHOOK_URL_SCENARIO_E` | Error Handler / DLQ webhook URL | `https://hook.eu1.make.com/ghi789...` |
| `360DIALOG_API_KEY` | 360dialog API key | `your-api-key` |
| `AIRTABLE_BASE_ID` | Airtable base identifier | `appXXXXXXXXXX` |
| `AIRTABLE_API_KEY` | Airtable personal access token | `pat...` |
| `DS_PROCESSED_MESSAGES` | Make.com data store ID for deduplication | `ds_123456` |

### Make.com Data Store

Create a data store named `DS_PROCESSED_MESSAGES` with the following structure:

| Field | Type | Description |
|-------|------|-------------|
| `message_id` | Text (key) | WhatsApp message ID |
| `processed_at` | Date | When the message was processed |
| `sender` | Text | Sender phone number |

Set the data store size limit to accommodate 72 hours of messages (approximately 3,600 records at 50 messages/day).

### Airtable Tables Required

- **People** - Must include fields: `whatsapp_number`, `first_name`, `role`, `site_id`, `is_active`, `created_at`, `last_interaction_at`
- **Work_Items** - Must include fields: `work_item_id`, `reported_by`, `current_state`, `created_at`
- **Interaction_Logs** - Must include fields: `work_item_id`, `person_id`, `direction`, `channel`, `message_type`, `message_content`, `whatsapp_message_id`, `media_url`, `llm_processed`, `delivery_status`, `created_at`, `scenario_execution_id`

### 360dialog Webhook Setup

1. In the 360dialog Partner Hub, set the webhook URL to `MAKE_WEBHOOK_URL_SCENARIO_A`.
2. Subscribe to the `messages` webhook event.
3. Set the API key header (`D360-API-KEY`) for webhook verification.

## Testing

### Using Test Payloads

Test payload files are provided in the `test-payloads/` directory:

```bash
# Test a standard text message
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_A" \
  -H "Content-Type: application/json" \
  -H "D360-API-KEY: $360DIALOG_API_KEY" \
  -d @test-payloads/valid-text-message.json

# Test an image message with caption
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_A" \
  -H "Content-Type: application/json" \
  -H "D360-API-KEY: $360DIALOG_API_KEY" \
  -d @test-payloads/valid-image-message.json

# Test a button reply
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_A" \
  -H "Content-Type: application/json" \
  -H "D360-API-KEY: $360DIALOG_API_KEY" \
  -d @test-payloads/valid-button-reply.json

# Test malformed payload (should trigger error handler)
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_A" \
  -H "Content-Type: application/json" \
  -d @test-payloads/invalid-malformed.json

# Test duplicate message (send twice, second should be filtered)
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_A" \
  -H "Content-Type: application/json" \
  -H "D360-API-KEY: $360DIALOG_API_KEY" \
  -d @test-payloads/edge-duplicate-message.json
```

### Validation Checklist

- [ ] Standard text message creates an Interaction_Log and triggers Scenario B
- [ ] Image message stores media_url correctly in Interaction_Log
- [ ] Button reply extracts the correct command (button ID)
- [ ] Duplicate message is filtered on second delivery
- [ ] Unknown sender is auto-registered as TENANT in People table
- [ ] Known person lookup returns correct person_id and role
- [ ] Job reference SF-XXXX is extracted from message text
- [ ] Error handler sends to Scenario E and returns HTTP 200
- [ ] Handoff payload to Scenario B contains all required fields

## Error Handling Strategy

### Per-Module Error Handling

| Module | Error Strategy | Rationale |
|--------|---------------|-----------|
| Dedupe Check (3) | Ignore errors, continue | Better to process a duplicate than drop a message |
| Lookup Person (6) | Route to Router (7) | Empty result triggers new person creation |
| All others | Global Error Handler (99) | Catch-all for unexpected failures |

### Global Error Handler (Module 99)

The global error handler performs two actions:

1. **Forward to DLQ**: Sends the full error context and original payload to Scenario E (Dead Letter Queue) via webhook for later investigation and replay.
2. **Return HTTP 200**: Always responds with `200 OK` to the 360dialog webhook to prevent automatic retries that would compound the error.

### Error Payload Structure

```json
{
  "scenario": "SCENARIO_A_INBOUND",
  "error_type": "RuntimeError",
  "error_message": "Airtable rate limit exceeded",
  "module_id": 11,
  "module_name": "Create Interaction Log",
  "payload": "<original webhook payload as string>",
  "execution_id": "exec_abc123",
  "timestamp": "2026-02-14T10:30:00.000Z"
}
```

## Operations Notes

### Operations Estimate

| Metric | Value |
|--------|-------|
| Operations per message | 8 |
| Average daily messages | 50 |
| Daily operations | 400 |
| Monthly operations | ~12,000 |

### Rate Limits

- **360dialog**: 250 messages/second (unlikely to be a bottleneck for inbound)
- **Airtable**: 5 requests/second per base. This scenario makes 3-4 Airtable calls per message. At sustained inbound rates above 1 message/second, Airtable rate limiting may occur. Make.com's automatic retry with backoff handles this.
- **Make.com webhooks**: Queued automatically, no hard limit.

### Deduplication TTL

The `DS_PROCESSED_MESSAGES` data store retains message IDs for 72 hours. This window is wide enough to handle 360dialog's retry behaviour (retries occur within minutes) while keeping the data store size manageable. Records older than 72 hours are eligible for cleanup.

### Monitoring Recommendations

1. **Error rate**: Alert if more than 5% of executions hit the error handler in a 1-hour window.
2. **Latency**: Monitor end-to-end execution time. Target is under 2 seconds per message.
3. **Data store size**: Monitor `DS_PROCESSED_MESSAGES` size. If it approaches the plan limit, reduce TTL or increase plan.
4. **Airtable rate errors**: Track HTTP 429 responses from Airtable. If frequent, consider batching or upgrading the Airtable plan.
5. **Handoff failures**: Monitor HTTP responses from Scenario B webhook. Non-200 responses indicate downstream issues.

### Scaling Considerations

- The scenario is stateless and can handle concurrent executions (Make.com queues webhook triggers).
- For very high volume (100+ messages/minute sustained), consider splitting the Airtable writes into a separate scenario triggered via an intermediate webhook to parallelise I/O.
- The deduplication data store is the primary shared state; ensure the Make.com plan supports the required data store size.
