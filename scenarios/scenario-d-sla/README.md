# Scenario D - SLA Monitor

## Purpose

Scenario D is the scheduled SLA monitoring and escalation engine for the SafeFlow system. It runs every 15 minutes to identify overdue or at-risk work items, applies state-specific nudge logic, escalates breached SLAs through a three-level escalation chain, triggers auto-cancel and auto-close transitions, and dispatches notifications via Scenario C.

This scenario is critical for ensuring that UK commercial property facilities management obligations are met within contractually agreed timeframes. SLA definitions follow UK FM standards with four urgency tiers: EMERGENCY, URGENT, STANDARD, and SCHEDULED.

## SLA Definitions

| Urgency | Response Time | Resolution Time | Escalation Intervals | Examples |
|---------|--------------|-----------------|---------------------|----------|
| EMERGENCY | 15 minutes | 4 hours | 15m, 30m, 60m | Life safety, flooding, gas leak, fire, security breach |
| URGENT | 1 hour | 24 hours | 1h, 2h, 4h | No heating, no hot water, lift failure, major leak |
| STANDARD | 4 hours | 72 hours | 4h, 8h, 24h | General repairs, minor plumbing, electrical faults |
| SCHEDULED | 24 hours | 14 days | 24h, 48h, 72h | Planned maintenance, inspections, cosmetic repairs |

## Escalation Levels

| Level | Trigger | Action | Recipients |
|-------|---------|--------|------------|
| 1 | First escalation interval breached | Nudge assignee | Assigned engineer/contractor |
| 2 | Second escalation interval breached | Escalate to supervisor | Assignee + supervisor + property manager |
| 3 | Third escalation interval breached | Critical alert + auto-reassign | All of the above + senior management |
| 3+ | Beyond third interval | Critical alert to all stakeholders | All stakeholders including directors |

## Module Flow

```
[1] Schedule Trigger (every 15 minutes, Europe/London)
 |
 v
[2] Search Overdue Work Items
 |  Airtable query: is_overdue = TRUE or approaching SLA deadline
 |  Excludes CLOSED, CANCELLED, and state-locked items
 |
 v
[3] Filter - Has Results
 |  Stop silently if no overdue items found
 |
 v
[4] Iterator - Process Each Item
 |
 v
[5] Calculate Overdue Metrics
 |  Minutes overdue, required escalation level,
 |  whether escalation increment needed
 |
 v
[6] Filter - Needs Action
 |  Skip items already processed at current level
 |
 v
[7] Router - State-Specific Nudge Logic
 |  7a: CLARIFICATION    --> [8]  Nudge reporter / auto-cancel (48h)
 |  7b: ASSESSMENT       --> [9]  Alert supervisor
 |  7c: ASSIGNED          --> [10] Nudge assignee / auto-reassign (2x SLA)
 |  7d: IN_PROGRESS       --> [11] Check in with assignee
 |  7e: VERIFICATION      --> [12] Remind verifier / auto-close (72h)
 |  7f: PAYMENT_PENDING   --> [13] Flag finance team
 |  7g: ESCALATED         --> [14] Further escalation levels
 |  7h: Other             --> [15] Default alert to supervisor
 |
 v
[16] Merge Action Outputs
 |
 v
[17] Escalation Level Router
 |  17a: Level 0->1  --> [18] Nudge assignee
 |  17b: Level 1->2  --> [19] Notify supervisor + PM
 |  17c: Level 2->3  --> [20] Senior management + auto-reassign
 |  17d: Level 3+    --> [21] Critical alert all stakeholders
 |
 v
[22] Update Work Item - Escalation Fields
 |
 v
[23] Router - State Transition Required
 |  23a: Escalate (level 2+)          --> [24] via Scenario B
 |  23b: Auto-cancel (CLARIFICATION)  --> [25] via Scenario B
 |  23c: Auto-close (VERIFICATION)    --> [26] via Scenario B
 |  23d: No transition needed         --> [28] Skip to notifications
 |
 v
[24-26] State Transitions via Scenario B
 |
 v
[27] Auto-Reassignment Search (level 3 only)
 |
 v
[28] Send Notifications via Scenario C
 |
 v
[29] Log Escalation in Interaction_Logs

[99] Global Error Handler
     Route to Scenario E (DLQ)
```

## State-Specific Nudge Logic

### CLARIFICATION Overdue
- **First breach**: Send reminder to the reporter asking for the missing information
- **48+ hours**: Auto-cancel the work item via Scenario B with a notification to the reporter

### ASSESSMENT Overdue
- Alert the site supervisor or property manager for manual triage

### ASSIGNED Overdue
- **First breach**: Nudge the assigned engineer or contractor
- **2x SLA resolution time**: Trigger auto-reassignment to an available engineer with the required discipline

### IN_PROGRESS Overdue
- Send a check-in message to the assignee
- Notify the property manager

### VERIFICATION Overdue
- **First breach**: Remind the tenant/verifier to confirm completion
- **72+ hours**: Auto-close the work item as accepted (deemed satisfactory)

### PAYMENT_PENDING Overdue
- Flag to the finance team for attention

### ESCALATED
- Apply further escalation levels, notifying increasingly senior stakeholders

## Auto-Transitions

| Trigger | From State | To State | Threshold | Via |
|---------|-----------|----------|-----------|-----|
| Clarification timeout | CLARIFICATION | CANCELLED | 48 hours no response | Scenario B (CANCEL command) |
| Verification timeout | VERIFICATION | CLOSED | 72 hours no response | Scenario B (DONE command) |
| Level 2+ escalation | Any active | ESCALATED | Based on urgency tier | Scenario B (ESCALATE command) |

All auto-transitions are executed via Scenario B (State Engine) to ensure state locking, validation, and audit trail consistency.

## Auto-Reassignment

At escalation level 3, the SLA Monitor searches for an available engineer with:
1. Matching discipline for the work item
2. Active status
3. Current workload below maximum capacity

The search prioritises the engineer with the lightest workload. If no discipline match is found, it falls back to any available engineer.

## Configuration Requirements

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AIRTABLE_BASE_ID` | Airtable base identifier | `appXXXXXXXXXX` |
| `AIRTABLE_API_KEY` | Airtable personal access token | `pat...` |
| `MAKE_WEBHOOK_URL_SCENARIO_B` | State Engine webhook URL | `https://hook.eu1.make.com/...` |
| `MAKE_WEBHOOK_URL_SCENARIO_C` | Outbound Sender webhook URL | `https://hook.eu1.make.com/...` |
| `MAKE_WEBHOOK_URL_SCENARIO_E` | Error Handler / DLQ webhook URL | `https://hook.eu1.make.com/...` |

### Airtable Tables Required

- **Work_Items** - Must include fields: `work_item_id`, `title`, `current_state`, `urgency`, `sla_due_at`, `escalation_level`, `assigned_engineer_id`, `contractor_id`, `reported_by`, `site_id`, `discipline_required`, `state_started_at`, `time_in_current_state`, `is_overdue`, `state_locked`, `priority_score`, `created_at`, `updated_at`, `state_history`, `blocked_reason`
- **People** - Must include fields: `role`, `is_active`, `disciplines`, `current_workload`, `max_workload`
- **Sites** - Must include fields: `property_manager_id`, `supervisor_id`
- **Interaction_Logs** - Must include fields: `work_item_id`, `direction`, `channel`, `message_type`, `message_content`, `delivery_status`, `created_at`, `scenario_execution_id`

### Airtable Formula Fields

The following formula fields should be configured on the Work_Items table:

| Field | Type | Formula |
|-------|------|---------|
| `is_overdue` | Formula (Checkbox) | `IF(AND({sla_due_at} != BLANK(), {current_state} != "CLOSED", {current_state} != "CANCELLED"), {sla_due_at} < NOW(), FALSE())` |
| `time_in_current_state` | Formula (Number) | `IF({state_started_at} != BLANK(), DATETIME_DIFF(NOW(), {state_started_at}, 'minutes'), 0)` |

## Testing

### Using Test Payloads

Test payload files in the `test-payloads/` directory represent the Airtable records that would be returned by Module 2. To test the full scenario, insert matching records into the Work_Items table and trigger the scheduled run manually in Make.com.

```bash
# The test payloads document expected behaviour for various overdue scenarios:

# Emergency overdue item - should escalate immediately
cat test-payloads/overdue-emergency.json

# Clarification timeout - should auto-cancel after 48h
cat test-payloads/overdue-clarification-timeout.json

# Level 2 escalation - should notify supervisor and PM
cat test-payloads/escalation-level-2.json

# No overdue items - scenario should exit silently
cat test-payloads/no-overdue-items.json

# Multiple overdue items - should process each independently
cat test-payloads/multiple-overdue.json
```

### Validation Checklist

- [ ] Schedule trigger fires every 15 minutes in Europe/London timezone
- [ ] Overdue items are correctly identified by Airtable filter
- [ ] State-locked items are excluded from processing
- [ ] CLOSED and CANCELLED items are excluded from processing
- [ ] Escalation level is correctly calculated based on urgency tier
- [ ] Items already at the current escalation level are skipped
- [ ] CLARIFICATION items are auto-cancelled after 48 hours
- [ ] VERIFICATION items are auto-closed after 72 hours
- [ ] Auto-transitions use Scenario B (State Engine) for consistency
- [ ] Level 2+ escalation triggers transition to ESCALATED state
- [ ] Level 3 escalation triggers auto-reassignment search
- [ ] Notifications are sent via Scenario C
- [ ] Escalation events are logged to Interaction_Logs
- [ ] No overdue items results in silent completion
- [ ] Errors are routed to Scenario E with full context

## Error Handling Strategy

### Per-Module Error Handling

| Module | Error Strategy | Rationale |
|--------|---------------|-----------|
| Search Overdue (2) | Route to error handler | Cannot proceed without data |
| Update Escalation (22) | Route to error handler | Must record escalation level |
| State Transitions (24-26) | Route to error handler | Critical state changes |
| Notifications (28) | Route to error handler | Non-critical but should log failure |
| Log Escalation (29) | Ignore | Audit log failure should not block escalation |
| All others | Global Error Handler (99) | Catch-all |

## Operations Notes

### Operations Estimate

| Metric | Value |
|--------|-------|
| Operations per run (no overdue) | 2 |
| Operations per run (5 overdue items) | ~50 |
| Daily average | ~200 |
| Monthly estimate | ~6,000 |

### Performance Considerations

- The scenario processes up to 100 overdue items per run (max_records limit on the Airtable query)
- Each item requires 4-6 Airtable operations (read, update, log) plus webhook calls
- Emergency periods with many overdue items may spike to 200+ operations per run
- The iterator processes items sequentially to avoid Airtable rate limiting
- State transitions via Scenario B are fire-and-forget (async webhook calls)

### Stale Lock Detection

The SLA Monitor also serves as a safety net for stale state locks. If a work item's `state_locked_at` timestamp is older than 5 minutes, the lock is considered stale (indicating a failed execution that did not clean up). Stale locks are excluded from the overdue query by the `state_locked != TRUE()` filter, but a separate maintenance task should periodically release them.
