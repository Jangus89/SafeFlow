# SafeFlow Incident Response Runbook

## Severity Levels

| Severity | Definition | Response Time | Resolution Target | Notification |
|----------|-----------|---------------|-------------------|--------------|
| **P0 -- Critical** | Complete system outage. No messages processed. Tenants cannot report issues. | **15 minutes** | **1 hour** | PagerDuty + Slack + Email + Phone call to on-call |
| **P1 -- High** | Major degradation. Messages processing but with significant delays (>5 min) or data loss. Emergency routing broken. | **30 minutes** | **4 hours** | PagerDuty + Slack + Email |
| **P2 -- Medium** | Partial degradation. Non-critical feature broken (e.g., notifications delayed, SLA monitoring paused). Core intake and triage functional. | **2 hours** | **24 hours** | Slack + Email |
| **P3 -- Low** | Minor issue. Cosmetic errors, non-blocking edge cases, logging gaps. No tenant impact. | **Next business day** | **1 week** | Slack |

---

## Incident Response Procedure

### 1. Detection

Incidents may be detected via:

- **Automated alerts**: PagerDuty, Slack #safeflow-alerts, email alerts (see `monitoring/alerts/alert-rules.json`)
- **Make.com execution failures**: Visible in the Make.com execution history dashboard
- **Airtable Errors table**: Manual review of recent error records
- **Tenant reports**: Tenants reporting that messages are not being acknowledged
- **Property manager reports**: Managers noticing work items not progressing
- **Monitoring dashboards**: Operations dashboard showing anomalies

### 2. Assessment

Upon detection, the on-call responder must:

1. **Acknowledge** the alert within the response time SLA.
2. **Assess severity** using the table above.
3. **Create a GitHub issue** using the incident template (`.github/ISSUE_TEMPLATE/incident.md`).
4. **Notify stakeholders** via the appropriate channels.
5. **Begin investigation** using the common incidents guide below.

### 3. Investigation

Follow the relevant common incident playbook (see below). General investigation steps:

1. Check Make.com execution history for the relevant scenario(s).
2. Check the Airtable Errors table for recent entries.
3. Check 360dialog webhook delivery logs.
4. Check Anthropic API status page.
5. Check Airtable API status page.
6. Check Xero API status page.

### 4. Resolution

1. Implement the fix (see rollback procedures if needed).
2. Verify the fix by sending a test message through the full pipeline.
3. Monitor for 15 minutes to confirm stability.
4. Update the GitHub issue with resolution details.

### 5. Communication

| Audience | When | Channel | What |
|----------|------|---------|------|
| Operations team | Immediately on detection | Slack #safeflow-alerts | Incident declared, severity, who is investigating |
| Property managers | If P0/P1 lasting >30 min | Email / WhatsApp | Service disruption notice with estimated resolution |
| Tenants | If P0 lasting >1 hour | WhatsApp broadcast | Apology + alternative contact method |
| Operations team | On resolution | Slack #safeflow-alerts | Incident resolved, root cause summary |
| All stakeholders | Within 48 hours | Email | Post-incident review document |

---

## Common Incidents

### CI-01: Make.com Scenario A Not Processing Inbound Messages

**Severity**: P0

**Symptoms**:
- No new Interaction_Logs appearing in Airtable
- No new Work_Items being created
- 360dialog webhook returning non-200 responses
- Tenants reporting no acknowledgement

**Investigation steps**:

1. Check Scenario A status in Make.com:
   - Is the scenario active? (It may have been deactivated due to repeated errors.)
   - Are there queued webhook events?
   - What does the execution history show?

2. Check 360dialog webhook configuration:
   - Is the webhook URL correct?
   - Is the D360-API-KEY header configured?
   - Check 360dialog Partner Hub for webhook delivery logs.

3. Check Make.com plan limits:
   - Has the operations quota been exhausted for the current billing period?

**Resolution**:

```
Option A: Reactivate scenario
  1. Go to Make.com > Scenarios > Scenario A
  2. Review the error that caused deactivation
  3. Fix the root cause (e.g., expired credential)
  4. Reactivate the scenario
  5. Process any queued webhooks

Option B: Webhook URL changed
  1. Copy the current Scenario A webhook URL from Make.com
  2. Update the 360dialog Partner Hub webhook configuration
  3. Test with a curl command:
     curl -X POST "$MAKE_WEBHOOK_URL_SCENARIO_A" \
       -H "Content-Type: application/json" \
       -H "D360-API-KEY: $DIALOG_API_KEY" \
       -d @scenarios/scenario-a-inbound/test-payloads/valid-text-message.json

Option C: Plan limit reached
  1. Upgrade the Make.com plan immediately
  2. Or wait for the billing period to reset (check dashboard for reset date)
```

---

### CI-02: Claude API Triage Failures

**Severity**: P1

**Symptoms**:
- Work_Items created but stuck in INTAKE state
- LLM confidence showing as 0 or null
- Errors table showing Anthropic API errors (401, 429, 500)
- Scenario B execution failures at Module 5

**Investigation steps**:

1. Check the Anthropic API status page: [status.anthropic.com](https://status.anthropic.com/)
2. Check the API key validity: Is the key still active in the Anthropic console?
3. Check rate limits: Are we hitting the 50 req/min Tier 1 limit?
4. Check the error message in the Errors table or Make.com execution log.

**Resolution**:

```
401 Unauthorized:
  1. Regenerate the API key at console.anthropic.com
  2. Update the Anthropic connection in Make.com Scenario B
  3. Test with a manual execution

429 Rate Limited:
  1. Check current usage in Anthropic console
  2. If sustained, increase the retry delay in Scenario B Module 5
  3. Consider upgrading to Tier 2 (4,000 req/min)

500/502/503 Service Error:
  1. Check status.anthropic.com for outage information
  2. Wait for service recovery
  3. Process queued items by replaying DLQ entries
```

---

### CI-03: Airtable Rate Limiting

**Severity**: P2

**Symptoms**:
- Intermittent 429 errors in execution logs
- Slow work item creation (>10 seconds)
- Some messages processed, others failing
- Errors table showing "RATE_LIMIT_EXCEEDED"

**Investigation steps**:

1. Check the error frequency in the Errors table.
2. Check if there is an unusual spike in inbound message volume.
3. Check if another integration is consuming Airtable API capacity.

**Resolution**:

```
1. Verify Make.com retry with backoff is configured (should be by default)
2. If sustained, add artificial delays between Airtable calls:
   - Add a 250ms sleep module between consecutive Airtable operations
3. Check for runaway automations in Airtable that may be consuming quota
4. If persistent, contact Airtable support about rate limit increase
5. Long-term: Consider splitting high-volume tables to separate bases
```

---

### CI-04: WhatsApp Delivery Failures

**Severity**: P2

**Symptoms**:
- Outbound messages not reaching tenants
- Interaction_Logs showing `delivery_status` = FAILED
- Scenario C execution failures
- 360dialog API returning 4xx errors

**Investigation steps**:

1. Check the 360dialog Partner Hub for account status.
2. Check if the WhatsApp number has been flagged or rate-limited by Meta.
3. Check message template approval status (templates may have been rejected).
4. Check if the recipient numbers are valid and have active WhatsApp accounts.

**Resolution**:

```
Template rejected:
  1. Review rejection reason in Meta Business Manager
  2. Modify template and resubmit for approval
  3. Update Scenario C to use the approved template

Number quality rating low:
  1. Check Meta Business Manager quality rating
  2. Reduce message volume temporarily
  3. Ensure messages are expected (no spam complaints)
  4. Wait for quality rating to recover (typically 7 days)

API key expired:
  1. Regenerate API key in 360dialog Partner Hub
  2. Update the 360dialog connection in Make.com Scenarios A and C
```

---

### CI-05: Xero Invoice Creation Failures

**Severity**: P2

**Symptoms**:
- Work_Items reaching CLOSED but no Xero invoice created
- Errors table showing Xero API errors
- Missing `invoice_id` on closed Work_Items

**Investigation steps**:

1. Check Xero API status page.
2. Check OAuth token status in Make.com connection.
3. Check the Xero organisation for any account-level issues.
4. Check the expense account code is valid.

**Resolution**:

```
OAuth token expired:
  1. Go to Make.com > Connections
  2. Find the Xero connection
  3. Re-authorise the connection (OAuth flow)
  4. Test with a manual invoice creation

Invalid account code:
  1. Log in to Xero
  2. Verify the expense account code exists (e.g., code 300)
  3. Update XERO_EXPENSE_ACCOUNT_CODE in environment config

Missing contractor Xero contact:
  1. Check the contractor record in Airtable for xero_contact_id
  2. If missing, create the contact in Xero and update Airtable
```

---

### CI-06: State Lock Deadlock

**Severity**: P1

**Symptoms**:
- Work_Items stuck with `state_locked` = true
- No state transitions occurring for affected items
- Scenario B rejecting processing attempts for locked items

**Investigation steps**:

1. Query Work_Items for records where `state_locked` = true.
2. Check `state_locked_at` -- if older than 5 minutes, the lock is stale.
3. Check if Scenario D is running (it should auto-release stale locks).

**Resolution**:

```
Immediate (manual):
  1. Identify locked records in Airtable Work_Items table
  2. For each locked record:
     a. Verify no active Make.com execution is processing it
     b. Set state_locked = false
     c. Clear state_locked_by and state_locked_at
  3. The next processing attempt will proceed normally

Systematic:
  1. Check Scenario D is active and running on schedule
  2. Verify Scenario D includes the stale lock detection module
  3. Check Scenario B Module 99 (error handler) includes lock release
```

---

### CI-07: SLA Monitoring Not Running

**Severity**: P2

**Symptoms**:
- Emergency work items not escalating despite SLA breaches
- Scenario D not appearing in recent execution history
- `escalation_level` remaining at 0 for overdue items

**Investigation steps**:

1. Check Scenario D status in Make.com -- is it active?
2. Check the schedule trigger configuration (should be every 15 minutes).
3. Check for execution errors in Scenario D history.

**Resolution**:

```
1. Reactivate Scenario D if deactivated
2. Verify the schedule trigger is set to every 15 minutes
3. Manually trigger one execution to verify it works
4. Check any overdue items and manually escalate if necessary:
   - Update current_state to ESCALATED
   - Increment escalation_level
   - Add entry to state_history
```

---

## Rollback Procedures

### Rollback Make.com Scenarios

```bash
# Full rollback to previous version
bash scripts/deploy.sh rollback production

# Manual rollback steps:
# 1. Deactivate Scenario A (stops inbound processing)
# 2. For each scenario (A-E):
#    a. Open the scenario in Make.com
#    b. Click ... > Version History
#    c. Restore the previous version
# 3. Reactivate scenarios in order: E, D, C, B, A
```

### Rollback Airtable Schema Changes

```bash
# Restore from backup
python scripts/backup/restore-airtable.py \
  --backup-dir airtable/backups/2026-02-14_120000 \
  --dry-run

# If dry run looks correct, execute the restore
python scripts/backup/restore-airtable.py \
  --backup-dir airtable/backups/2026-02-14_120000 \
  --confirm
```

### Emergency: Disable All Processing

If a critical issue requires stopping all message processing immediately:

1. **Deactivate Scenario A** in Make.com. This stops all inbound message processing. Messages will queue at the 360dialog webhook level.
2. Investigate and resolve the issue.
3. Reactivate Scenario A. Queued messages will be processed in order.

**Note**: 360dialog webhooks have a retry window. Messages received during the outage will be retried and processed once Scenario A is reactivated, provided the outage is less than 72 hours.

---

## Post-Incident Review Template

After every P0 or P1 incident (and optionally for P2), complete this template within 48 hours.

### Incident Summary

| Field | Value |
|-------|-------|
| **Incident ID** | INC-YYYY-NNN |
| **Severity** | P0 / P1 / P2 / P3 |
| **Date/Time detected** | DD/MM/YYYY HH:MM (Europe/London) |
| **Date/Time resolved** | DD/MM/YYYY HH:MM (Europe/London) |
| **Duration** | X hours Y minutes |
| **Impact** | Description of tenant/user impact |
| **Responders** | Names of people involved |

### Timeline

| Time | Event |
|------|-------|
| HH:MM | Alert triggered / Issue detected |
| HH:MM | On-call acknowledged |
| HH:MM | Investigation began |
| HH:MM | Root cause identified |
| HH:MM | Fix deployed |
| HH:MM | Monitoring confirmed resolution |
| HH:MM | Incident closed |

### Root Cause Analysis

_Describe the root cause in detail. What failed and why?_

### Contributing Factors

_List any factors that contributed to the incident occurring or lasting longer than necessary._

### What Went Well

_List things that worked well during the response._

### What Could Be Improved

_List areas for improvement._

### Action Items

| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| _Preventive action 1_ | _Name_ | _DD/MM/YYYY_ | Open |
| _Preventive action 2_ | _Name_ | _DD/MM/YYYY_ | Open |
| _Detection improvement_ | _Name_ | _DD/MM/YYYY_ | Open |

### Metrics

| Metric | Value |
|--------|-------|
| Time to detect | X minutes |
| Time to acknowledge | X minutes |
| Time to resolve | X hours Y minutes |
| Messages affected | N |
| Work items affected | N |
| Tenant-facing impact duration | X hours Y minutes |

---

## Escalation Contacts

| Role | Contact Method | When to Escalate |
|------|---------------|------------------|
| On-call engineer | PagerDuty rotation | Automated (all P0, P1) |
| Engineering lead | Slack DM + phone | P0 not resolved in 30 min |
| Operations manager | Phone | P0 not resolved in 1 hour |
| Account manager | Email + phone | P0 lasting >2 hours with tenant impact |

---

## Useful Links

| Resource | URL |
|----------|-----|
| Make.com dashboard | https://eu2.make.com/ |
| Airtable base | https://airtable.com/appXXXXXXXXXXXXXX |
| 360dialog Partner Hub | https://hub.360dialog.com/ |
| Anthropic console | https://console.anthropic.com/ |
| Anthropic status | https://status.anthropic.com/ |
| Xero developer | https://developer.xero.com/ |
| GitHub repository | https://github.com/SafeFlow/SafeFlow |
| Slack channel | #safeflow-alerts |
| PagerDuty service | SafeFlow Production |
