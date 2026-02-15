# Scenario E - Error Handler / Dead Letter Queue

## Purpose

Scenario E is the centralised error handler and dead letter queue (DLQ) for the SafeFlow system. Every unhandled error from Scenarios A (Inbound), B (State Engine), C (Outbound), and D (SLA Monitor) is forwarded here for classification, persistence, alerting, and retry management.

This scenario ensures that no error is silently lost. Every failure is recorded in Airtable, classified by severity, and routed to the appropriate alerting channel. Retryable errors are queued with exponential backoff, and a daily digest summarises all errors for the operations team.

## Severity Levels

| Severity | Description | Alert Channel | Examples |
|----------|-------------|---------------|----------|
| CRITICAL | Immediate attention required. Data corruption risk or complete scenario failure. | Slack + Email | State Engine runtime error, data store corruption |
| HIGH | Service degradation. Upstream API failures, persistent errors. | Slack | 360dialog API down, Airtable 5xx errors, Xero connection failure |
| MEDIUM | Individual message/record failure. Invalid data, recipient issues. | Daily digest | Invalid recipient, malformed payload, state lock conflict |
| LOW | Transient issues. Rate limits, temporary network errors. | Log only | 360dialog rate limit, temporary network timeout |

## Module Flow

### Real-Time Error Intake (Webhook)

```
[1] Webhook - Error Intake
 |  Receives error payloads from all scenarios
 |
 v
[2] Parse Error Details
 |  Normalise, enrich, generate error_id
 |
 v
[3] Severity Classifier
 |  Confirm/override severity based on error context
 |
 v
[4] Create Error Record
 |  Persist to Airtable Errors table
 |
 v
[5] Severity Router
 |        |           |           |
 v        v           v           v
[6]      [7]        Skip        Skip
CRITICAL  HIGH      MEDIUM      LOW
Slack    Slack      (logged)    (logged)
 |
 v
[8] Email (CRITICAL only)
 |
 v
[9] Auto-Retry Router
 |           |
 v           v
[10]        [14]
Calculate   Return ACK
Retry       (no retry)
 |
 v
[11] Queue Retry
 |
 v
[12] Check Retry Exhaustion
 |           |
 v           v
[13]        [14]
Alert       Return ACK
Exhausted

[14] Return Acknowledgement (HTTP 200)

[99] Global Error Handler
     NEVER calls own webhook (anti-recursion guard)
```

### Daily Digest (Scheduled)

```
[50] Schedule Trigger (08:00 Europe/London)
 |
 v
[51] Search Errors (last 24 hours, unresolved)
 |
 v
[52] Aggregate Stats
 |
 v
[53] Send Slack Summary (#safeflow-ops)
 |
 v
[54] Send Email Summary
```

## Severity Classification Rules

The Severity Classifier (Module 3) applies these rules in order:

1. **State Engine runtime/data error** -> CRITICAL (regardless of upstream severity)
2. **State lock conflict** -> MEDIUM (will auto-retry)
3. **HTTP 429 (rate limit)** -> LOW (transient, will auto-retry)
4. **HTTP 5xx (server error)** -> HIGH (upstream service issue)
5. **Invalid recipient** -> MEDIUM (data quality issue)
6. **All others** -> Use severity provided by the source scenario

## Retry Policy

### Exponential Backoff

Retryable errors are queued with exponential backoff:

| Retry | Delay | Cumulative |
|-------|-------|-----------|
| 1st | 60 seconds | 1 minute |
| 2nd | 120 seconds | 3 minutes |
| 3rd | 240 seconds | 7 minutes |

After the 3rd retry, the error is marked as `RETRY_EXHAUSTED` and a Slack alert is sent for manual intervention.

### Retryable Error Types

| Error Type | Source | Default Delay |
|-----------|--------|--------------|
| Rate limit (429) | 360dialog, Airtable | 60 seconds |
| Server error (5xx) | Any upstream API | 30 seconds |
| State lock conflict | Scenario B | 60 seconds |
| Connection timeout | Any upstream API | 30 seconds |

### Non-Retryable Error Types

| Error Type | Source | Action |
|-----------|--------|--------|
| Invalid recipient | Scenario C | Needs manual review |
| Malformed payload | Scenario A | Needs manual review |
| Template not found | Scenario C | Needs template registration |
| Session expired (24h) | Scenario C | Needs template fallback |
| Data validation error | Any | Needs data fix |

## Anti-Recursion Guard

The global error handler in this scenario (Module 99) **never** calls `MAKE_WEBHOOK_URL_SCENARIO_E`. If this scenario itself fails, the error is logged only to Make.com's execution history. This prevents infinite recursion loops.

## Configuration Requirements

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `MAKE_WEBHOOK_URL_SCENARIO_E` | This scenario's webhook URL | `https://hook.eu1.make.com/...` |
| `AIRTABLE_BASE_ID` | Airtable base identifier | `appXXXXXXXXXX` |
| `AIRTABLE_API_KEY` | Airtable personal access token | `pat...` |
| `SLACK_WEBHOOK_URL` | Slack webhook for #safeflow-alerts | `https://hooks.slack.com/services/...` |
| `SLACK_WEBHOOK_URL_OPS` | Slack webhook for #safeflow-ops (digest) | `https://hooks.slack.com/services/...` |
| `OPS_EMAIL_ADDRESS` | Operations team email | `ops@example.com` |
| `OPS_EMAIL_FROM` | From address for alert emails | `safeflow-alerts@example.com` |

### Airtable Tables Required

- **Errors** - Dedicated error tracking table

### Airtable Field Requirements (Errors)

| Field | Type | Description |
|-------|------|-------------|
| `error_id` | Single Line Text | Unique error identifier (YYYYMMDD-HHmmss-execId) |
| `scenario` | Single Select | Source scenario identifier |
| `error_type` | Single Line Text | Error type/class |
| `error_message` | Long Text | Full error message |
| `error_status_code` | Number | HTTP status code (if applicable) |
| `module_id` | Number | Source module ID |
| `module_name` | Single Line Text | Source module name |
| `severity` | Single Select | CRITICAL, HIGH, MEDIUM, LOW |
| `severity_reason` | Single Line Text | Explanation of severity classification |
| `payload` | Long Text | Original payload (stringified) |
| `source_execution_id` | Single Line Text | Make.com execution ID of the failing scenario |
| `dlq_execution_id` | Single Line Text | Make.com execution ID of this DLQ run |
| `status` | Single Select | PENDING_RETRY, NEEDS_REVIEW, RETRY_EXHAUSTED, RESOLVED |
| `retry_eligible` | Checkbox | Whether the error can be retried |
| `retry_count` | Number | Number of retry attempts |
| `retry_next_at` | Date/Time | Scheduled time for next retry |
| `retry_delay_seconds` | Number | Current retry delay |
| `context` | Long Text | Additional error context |
| `resolved` | Checkbox | Whether the error has been resolved |
| `resolved_at` | Date/Time | When the error was resolved |
| `resolved_by` | Single Line Text | Who resolved the error |
| `resolution_notes` | Long Text | Notes on how the error was resolved |
| `created_at` | Date/Time | When the error was received |
| `updated_at` | Date/Time | Last modification timestamp |

## Testing

### Using Test Payloads

Test payload files are provided in the `test-payloads/` directory:

```bash
# Test a critical scenario failure (should trigger Slack + email)
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_E" \
  -H "Content-Type: application/json" \
  -d @test-payloads/critical-scenario-failure.json

# Test a high-severity API timeout (should trigger Slack)
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_E" \
  -H "Content-Type: application/json" \
  -d @test-payloads/high-api-timeout.json

# Test a medium-severity validation error (should log only)
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_E" \
  -H "Content-Type: application/json" \
  -d @test-payloads/medium-validation-error.json

# Test a low-severity rate limit warning (should log only)
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_E" \
  -H "Content-Type: application/json" \
  -d @test-payloads/low-rate-limit-warning.json

# Test retry exhaustion (should trigger exhaustion alert)
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_E" \
  -H "Content-Type: application/json" \
  -d @test-payloads/retry-exhausted.json
```

### Validation Checklist

- [ ] CRITICAL error triggers Slack alert to #safeflow-alerts
- [ ] CRITICAL error triggers email to operations team
- [ ] HIGH error triggers Slack alert only
- [ ] MEDIUM error is logged to Airtable without alert
- [ ] LOW error is logged to Airtable without alert
- [ ] Error record is created in Airtable Errors table
- [ ] Retryable error is queued with correct exponential backoff delay
- [ ] Retry exhaustion triggers Slack alert
- [ ] Non-retryable error is marked as NEEDS_REVIEW
- [ ] Daily digest includes correct error counts by severity
- [ ] Daily digest includes correct error counts by scenario
- [ ] Anti-recursion guard prevents infinite loops
- [ ] HTTP 200 is returned to the calling scenario

## Error Handling Strategy

### Critical Design Decision

This scenario **must not** call itself when it encounters an error. The global error handler (Module 99) returns HTTP 200 with a diagnostic message and relies on Make.com's built-in execution logging for error visibility.

### Per-Module Error Handling

| Module | Error Strategy | Rationale |
|--------|---------------|-----------|
| Create Error Record (4) | Ignore | Continue to alerting even if Airtable write fails |
| Slack Critical (6) | Ignore | Continue to email if Slack fails |
| Slack High (7) | Ignore | Error is still in Airtable |
| Email (8) | Ignore | Error is still in Airtable and Slack |
| Queue Retry (11) | Ignore | Error is still recorded |
| Retry Exhausted Alert (13) | Ignore | Error is still in Airtable |
| Daily Digest Slack (53) | Ignore | Do not create recursive errors |
| Daily Digest Email (54) | Ignore | Do not create recursive errors |
| All others | Global Error Handler (99) | Anti-recursion: return 200 only |

## Operations Notes

### Operations Estimate

| Metric | Value |
|--------|-------|
| Operations per error | 5 |
| Average daily errors | ~10 |
| Daily error operations | ~50 |
| Daily digest operations | 4 |
| Monthly estimate | ~1,620 |

### Slack Channels

- **#safeflow-alerts**: Real-time CRITICAL and HIGH alerts. Monitor during business hours.
- **#safeflow-ops**: Daily digest at 08:00. Review each morning.

### Error Resolution Workflow

1. Error appears in Slack or daily digest
2. Investigate using the error_id and source_execution_id
3. Review the original payload stored in the Airtable error record
4. Fix the root cause (data issue, configuration, upstream service)
5. Mark the error as resolved in Airtable with resolution notes
6. If the original payload needs reprocessing, manually replay it through the source scenario's webhook
