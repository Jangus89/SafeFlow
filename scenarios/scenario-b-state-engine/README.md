# Scenario B - State Engine

## Purpose

Scenario B is the core business logic engine of the SafeFlow system. It implements a 12-state work order machine for UK commercial property facilities management. Every inbound message processed by Scenario A is forwarded here for intent classification, state transition validation, and side effect execution.

The State Engine receives enriched payloads from Scenario A (inbound messages) and Scenario D (SLA escalations), determines the appropriate action, validates and persists state transitions, and hands off to Scenario C (outbound sender) for notifications.

## 12-State Work Order Machine

```
               +----------+
               |  INTAKE   |
               +-----+----+
                     |
            +--------+--------+
            |                 |
    +-------v------+   +------v-------+
    | CLARIFICATION |   |  ASSESSMENT  |
    +-------+------+   +------+-------+
            |                 |
            +---------+-------+
                      |
               +------v------+
               |   ASSIGNED   |
               +------+------+
                      |
               +------v------+
               |   ACCEPTED   |
               +------+------+
                      |
            +---------+---------+
            |                   |
     +------v------+    +------v------+
     | IN_PROGRESS  |    |  ON_HOLD    |
     +------+------+    +------+------+
            |                   |
            +--------+--------+
                     |
              +------v-------+
              | VERIFICATION  |
              +------+-------+
                     |
           +---------+---------+
           |                   |
    +------v--------+  +------v------+
    |PAYMENT_PENDING|  |   CLOSED    |
    +------+--------+  +-------------+
           |
    +------v------+
    |   CLOSED    |       +----------+
    +-------------+       | CANCELLED |
                          +----------+
         +----------+        (from most states)
         | ESCALATED |
         +----------+
         (from most active states)
```

## Module Flow

```
[1] Webhook - Receive from Scenario A / D
 |  Validates X-Source-Scenario header
 |
 v
[2] Load Work Item + Person + Site
 |  Three parallel Airtable lookups for full context
 |
 v
[3] Lock Check
 |  Reject if state_locked = true (concurrent modification guard)
 |
 v
[4] Intent Router
 |  Routes by intent type:
 |    4a: Command (DONE, ACCEPT, START, REJECT, etc.)  --> [6]
 |    4b: New Issue (no existing work item)             --> [5]
 |    4c: Clarification Response                        --> [5]
 |    4d: Media Attachment                              --> [5]
 |    4e: RFQ / Quote Submission                        --> [5]
 |    4f: General Follow-up                             --> [5]
 |
 v
[5] LLM Triage - Claude API                       [6] Command Processing
 |  POST to api.anthropic.com/v1/messages           |  Map command to target
 |  System prompt: intake-triage                    |  state, validate roles,
 |  Returns: intent, urgency, discipline,           |  extract quote amounts
 |  title, recommended_state, confidence            |
 |                                                  |
 +-------------------+-----------------------------+
                     |
              +------v-------+
              [7] State Transition Validator
              |  Validate: source state permits target state
              |  Validate: person role is authorised
              |  Prepare: transition reason, urgency, title
              |
              v
       +------+------+
       [8] Validation Router
       |         |
       v         v
  [9] Lock   [13] Rejection
  (passed)   (failed - notify user via Scenario C)
       |
       v
  [10] Persist State Change
  |   Airtable upsert: create or update Work_Item
  |   Set state, SLA deadlines, append history
  |   Release lock on completion
  |
  v
  [11] Update Interaction Log
  |   Mark LLM processed, store intent + confidence
  |
  v
  [12] Side Effects Router
       Routes to appropriate notification/action:
       12a: New Issue Created     --> [14] Notify tenant, begin assignment
       12b: Clarification Needed  --> [15] Ask tenant for detail
       12c: Job Assigned          --> [16] Notify contractor with buttons
       12d: Job Accepted          --> [17] Notify tenant
       12e: Work Started          --> [18] Notify tenant
       12f: Verification Required --> [19] Ask tenant to verify
       12g: Closed + Invoice      --> [20] Notify tenant, Xero invoice
       12h: Cancelled             --> [21] Notify all parties
       12i: Escalated             --> [22] Alert management
       12j: On Hold               --> [23] Notify stakeholders
       12k: Payment Pending       --> [24] Create Xero invoice

  [99] Global Error Handler (attached to all modules)
       Release state lock, route to Scenario E (DLQ)
```

## State Transition Rules

### Commands and Permitted Transitions

| Command | From States | To State | Permitted Roles |
|---------|-------------|----------|-----------------|
| `DONE` | IN_PROGRESS | VERIFICATION | Contractor, Engineer |
| `ACCEPT` | ASSIGNED | ACCEPTED | Contractor, Engineer |
| `START` | ACCEPTED | IN_PROGRESS | Contractor, Engineer |
| `REJECT` | ASSIGNED | ASSIGNED | Contractor, Engineer |
| `CANCEL` | INTAKE, CLARIFICATION, ASSESSMENT, ASSIGNED, ACCEPTED, ON_HOLD | CANCELLED | Tenant, Manager, Admin, System |
| `HOLD` | IN_PROGRESS, ACCEPTED | ON_HOLD | Manager, Admin, Contractor, Engineer |
| `QUOTE` | ASSIGNED, ACCEPTED | ASSESSMENT | Contractor |
| `APPROVE` | ASSESSMENT, VERIFICATION | ASSIGNED / CLOSED | Manager, Admin |
| `ESCALATE` | INTAKE, CLARIFICATION, ASSESSMENT, ASSIGNED, ACCEPTED, IN_PROGRESS, ON_HOLD | ESCALATED | Manager, Admin, System |
| `CONFIRM_COMPLETE` | VERIFICATION | CLOSED | Tenant, Manager, Admin |
| `REOPEN` | CLOSED | REOPENED | Tenant, Manager, Admin |

### LLM-Driven Transitions

| Scenario | From | To | Condition |
|----------|------|-----|-----------|
| New issue, sufficient detail | NEW | ASSESSMENT | LLM `has_sufficient_detail = true` |
| New issue, vague | NEW | CLARIFICATION | LLM `has_sufficient_detail = false` |
| Clarification response, now clear | CLARIFICATION | ASSESSMENT | LLM re-evaluates `has_sufficient_detail = true` |
| Clarification response, still vague | CLARIFICATION | CLARIFICATION | LLM `has_sufficient_detail = false` (second request sent) |

### System Auto-Transitions (via Scenario D)

| Trigger | From | To | Timing |
|---------|------|----|--------|
| Clarification timeout | CLARIFICATION | CANCELLED | 48 hours with no response |
| Verification timeout | VERIFICATION | CLOSED | 72 hours with no response |
| SLA breach L2+ | Any active | ESCALATED | Based on urgency tier |

## Concurrency Control

The State Engine uses an optimistic locking pattern to prevent race conditions:

1. **Lock Check (Module 3)**: Before processing, verify `state_locked = false` on the work item. If locked, reject the execution and send to DLQ for retry.
2. **Acquire Lock (Module 9)**: Set `state_locked = true`, `state_locked_by = executionId`, `state_locked_at = now`.
3. **Persist + Unlock (Module 10)**: Update the state and set `state_locked = false` in the same Airtable update.
4. **Error Rollback**: If any step fails after lock acquisition, the global error handler releases the lock before routing to DLQ.

Lock TTL: If a lock is held for more than 5 minutes (indicating a failed execution that did not clean up), Scenario D's scheduled runs will detect and release stale locks.

## LLM Triage Configuration

### Model

The default model is `claude-sonnet-4-20250514`. This is configured via the `LLM_MODEL_ID` environment variable. Sonnet provides a good balance of speed (< 2 seconds) and accuracy for triage tasks.

### System Prompt

The system prompt instructs the LLM to:
- Classify intent (NEW_ISSUE, CLARIFICATION_RESPONSE, STATUS_ENQUIRY, QUOTE_SUBMISSION, MEDIA_EVIDENCE, FOLLOW_UP, UNKNOWN)
- Assess urgency using UK FM standards (EMERGENCY, URGENT, STANDARD, SCHEDULED)
- Identify trade discipline (PLUMBING, ELECTRICAL, HVAC, etc.)
- Extract location details from message text
- Determine if sufficient detail exists for job creation
- Generate a clarification question if detail is insufficient
- Return a confidence score (0.0 to 1.0)

### Cost Estimate

At approximately 500 tokens input + 300 tokens output per triage call:
- Per call: ~$0.003 (Sonnet pricing)
- Daily (50 messages, ~30 needing triage): ~$0.09
- Monthly: ~$2.70

## Xero Integration

The State Engine creates purchase invoices in Xero when work items reach CLOSED or PAYMENT_PENDING state and a contractor is assigned. Invoices are created as DRAFT status in GBP with:
- Reference: SF-{work_item_id}
- Line item: Job title and description
- Amount: From the contractor's submitted quote
- Due date: 30 days from creation
- Tax type: OUTPUT2 (standard UK VAT)

## Configuration Requirements

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `MAKE_WEBHOOK_URL_SCENARIO_B` | This scenario's webhook URL | `https://hook.eu1.make.com/...` |
| `MAKE_WEBHOOK_URL_SCENARIO_C` | Outbound Sender webhook URL | `https://hook.eu1.make.com/...` |
| `MAKE_WEBHOOK_URL_SCENARIO_E` | Error Handler / DLQ webhook URL | `https://hook.eu1.make.com/...` |
| `AIRTABLE_BASE_ID` | Airtable base identifier | `appXXXXXXXXXX` |
| `AIRTABLE_API_KEY` | Airtable personal access token | `pat...` |
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-...` |
| `LLM_MODEL_ID` | Claude model ID | `claude-sonnet-4-20250514` |
| `XERO_API_BASE_URL` | Xero API base URL | `https://api.xero.com` |
| `XERO_ACCESS_TOKEN` | Xero OAuth2 access token | `eyJ...` |
| `XERO_TENANT_ID` | Xero organisation ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `XERO_EXPENSE_ACCOUNT_CODE` | Xero expense account code | `300` |

### Airtable Tables Required

- **Work_Items** - Full work order record with state machine fields
- **People** - Person details including role, site, disciplines
- **Sites** - Site configuration including managers and preferred contractors
- **Interaction_Logs** - Updated with LLM processing results

### Airtable Field Requirements (Work_Items)

| Field | Type | Description |
|-------|------|-------------|
| `work_item_id` | Auto Number | Unique job reference (SF-XXXX) |
| `title` | Single Line Text | Concise issue title |
| `description` | Long Text | Detailed issue description |
| `current_state` | Single Select | Current state in the 12-state machine |
| `previous_state` | Single Line Text | State before last transition |
| `urgency` | Single Select | EMERGENCY, URGENT, STANDARD, SCHEDULED |
| `discipline_required` | Single Select | Required trade discipline |
| `reported_by` | Link to People | Person who reported the issue |
| `assigned_engineer_id` | Link to People | Assigned engineer/contractor |
| `contractor_id` | Link to People | Contractor company contact |
| `site_id` | Link to Sites | Site where issue is located |
| `sla_due_at` | Date/Time | SLA resolution deadline |
| `sla_response_due_at` | Date/Time | SLA response deadline |
| `escalation_level` | Number | Current escalation level (0-3+) |
| `state_locked` | Checkbox | Concurrency lock flag |
| `state_locked_by` | Single Line Text | Execution ID holding the lock |
| `state_locked_at` | Date/Time | When the lock was acquired |
| `state_started_at` | Date/Time | When the current state began |
| `state_history` | Long Text | Append-only state transition log |
| `quote_amount` | Currency | Contractor's quoted amount |
| `invoice_id` | Single Line Text | Xero invoice ID |
| `invoice_number` | Single Line Text | Xero invoice number |
| `priority_score` | Number | Calculated priority for SLA ordering |
| `blocked_reason` | Single Line Text | Reason if ON_HOLD |
| `is_overdue` | Formula/Checkbox | Whether SLA is breached |
| `time_in_current_state` | Formula | Minutes in current state |
| `created_at` | Date/Time | Record creation timestamp |
| `updated_at` | Date/Time | Last modification timestamp |

## Testing

### Using Test Payloads

Test payload files are provided in the `test-payloads/` directory:

```bash
# Test a new clear issue (should create work item in ASSESSMENT)
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_B" \
  -H "Content-Type: application/json" \
  -H "X-Source-Scenario: scenario-a-inbound" \
  -d @test-payloads/new-issue-clear.json

# Test a vague issue (should create work item in CLARIFICATION)
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_B" \
  -H "Content-Type: application/json" \
  -H "X-Source-Scenario: scenario-a-inbound" \
  -d @test-payloads/new-issue-vague.json

# Test DONE command (should transition IN_PROGRESS -> VERIFICATION)
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_B" \
  -H "Content-Type: application/json" \
  -H "X-Source-Scenario: scenario-a-inbound" \
  -d @test-payloads/command-done.json

# Test ACCEPT command (should transition ASSIGNED -> ACCEPTED)
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_B" \
  -H "Content-Type: application/json" \
  -H "X-Source-Scenario: scenario-a-inbound" \
  -d @test-payloads/command-accept.json

# Test clarification response (should transition CLARIFICATION -> ASSESSMENT)
curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_B" \
  -H "Content-Type: application/json" \
  -H "X-Source-Scenario: scenario-a-inbound" \
  -d @test-payloads/clarification-response.json
```

### Validation Checklist

- [ ] New issue with clear detail creates Work_Item in ASSESSMENT state
- [ ] New issue with vague detail creates Work_Item in CLARIFICATION state
- [ ] Clarification response with sufficient detail transitions to ASSESSMENT
- [ ] DONE command from contractor transitions IN_PROGRESS to VERIFICATION
- [ ] ACCEPT command from contractor transitions ASSIGNED to ACCEPTED
- [ ] Invalid command for current state returns rejection message
- [ ] Unpermitted role receives rejection message
- [ ] State lock prevents concurrent modification
- [ ] State lock is released on error
- [ ] LLM triage result is stored on Interaction_Log
- [ ] Xero invoice is created on CLOSED state with contractor
- [ ] Side effect notifications are sent via Scenario C
- [ ] Errors are routed to Scenario E with full context

## Error Handling Strategy

### Per-Module Error Handling

| Module | Error Strategy | Rationale |
|--------|---------------|-----------|
| Load Context (2) | Route to error handler | Cannot proceed without context |
| LLM Triage (5) | Route to error handler, 2 retries | Critical for triage accuracy |
| Acquire Lock (9) | Route to error handler | Cannot proceed without lock |
| Persist State (10) | Rollback lock, then error handler | Must release lock on failure |
| Update Interaction Log (11) | Ignore | Non-critical; do not block transition |
| Xero Invoice (24) | Route to error handler | Financial; requires manual follow-up |
| All others | Global Error Handler (99) | Catch-all |

### Global Error Handler (Module 99)

1. **Release Lock**: If the work item is locked, release it to prevent deadlocks
2. **Forward to DLQ**: Send full error context and payload to Scenario E
3. **Return HTTP 200**: Acknowledge receipt to upstream caller

## Operations Notes

### Operations Estimate

| Metric | Value |
|--------|-------|
| Operations per message | 12 |
| Average daily messages | 50 |
| Daily operations | 600 |
| Monthly operations | ~18,000 |

### Rate Limits

- **Anthropic**: 4,000 requests/minute (Tier 2). Not a concern at current volumes.
- **Airtable**: 5 requests/second per base. This scenario makes 4-6 Airtable calls per message (lookups + lock + persist + log update). At sustained rates above 1 message/second, rate limiting may occur.
- **Xero**: 60 requests/minute. Invoice creation only occurs on state closure, so well within limits.
- **Make.com webhooks**: Queued automatically, no hard limit.

### Performance Considerations

- The LLM triage call (Module 5) is the primary latency contributor at 2-3 seconds. This is bypassed for explicit commands.
- Airtable operations are parallelised where possible (Module 2 performs three lookups).
- State locking adds minimal overhead (one extra Airtable update) but is essential for data integrity.
