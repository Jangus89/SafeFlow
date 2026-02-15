# Property Manager User Guide

## Introduction

This guide is for property managers using SafeFlow to oversee facilities management across their commercial property portfolio. SafeFlow automates the intake, triage, and tracking of maintenance requests received via WhatsApp, giving you real-time visibility and control through Airtable dashboards.

As a property manager, you do not need to interact with WhatsApp directly for day-to-day operations. Your primary interface is the Airtable base, where you can monitor work items, approve quotes, handle escalations, and review SLA compliance. You will receive WhatsApp notifications for items requiring your attention.

---

## Dashboard Overview

### Accessing Your Dashboard

1. Log in to Airtable at [airtable.com](https://airtable.com/).
2. Open the **SafeFlow FM** base.
3. Navigate to the **Work_Items** table.

### Key Views

| View | Purpose | When to Use |
|------|---------|-------------|
| **Kanban Board** | Visual overview of all active work items grouped by state | Daily check -- see at a glance what is in each stage |
| **Active Work** | Grid view of all non-closed/non-cancelled items, sorted by priority | Working through the queue, reviewing status |
| **Overdue Items** | Items that have breached their SLA deadline | Priority review -- these need immediate attention |
| **Emergency Queue** | Emergency-urgency items still in active states | Real-time monitoring during incidents |
| **By Engineer** | Work items grouped by assigned engineer | Workload balancing and capacity planning |
| **RFQ Pipeline** | Items routed to external contractors | Managing the quoting and contractor selection process |
| **All Work Items** | Complete unfiltered list | Searching, reporting, auditing |

### Understanding the Kanban Board

The Kanban board shows work items as cards, grouped into columns by their current state:

| Column | What It Means | Your Action |
|--------|--------------|-------------|
| **INTAKE** | Just received, being processed by AI | No action needed -- automated |
| **CLARIFICATION** | AI needs more detail from the tenant | Monitor -- system sends follow-up questions automatically |
| **ASSESSMENT** | Triaged and ready for assignment | Review if manual assignment needed |
| **ASSIGNED** | Contractor/engineer notified, awaiting acceptance | Monitor -- escalates automatically after 24 hours |
| **IN_PROGRESS** | Work underway | Monitor for SLA compliance |
| **VERIFICATION** | Work reported complete, awaiting tenant confirmation | Review if tenant disputes |
| **PAYMENT_PENDING** | Tenant confirmed, invoice being processed | Approve invoice if required |
| **ON_HOLD** | Paused -- awaiting approval, parts, or access | **Action needed** -- review and approve or cancel |
| **ESCALATED** | Requires your intervention | **Action needed** -- resolve the escalation |
| **CLOSED** | Complete and paid | No action needed |
| **CANCELLED** | Cancelled by tenant or manager | No action needed |
| **REOPENED** | Previously closed, issue has recurred | Review -- may indicate quality issue with contractor |

---

## Monitoring Work Items

### Daily Monitoring Routine

Recommended daily checks (10-15 minutes):

1. **Kanban Board**: Quick visual scan for any build-up in a single column (indicates a bottleneck).
2. **Overdue Items view**: Address any SLA breaches immediately.
3. **Emergency Queue**: Ensure no emergencies are stuck.
4. **Escalated items**: Review and resolve any escalations.
5. **ON_HOLD items**: Review items awaiting your approval.

### Key Fields to Monitor

| Field | What to Look For |
|-------|-----------------|
| `current_state` | Items stuck in one state for too long |
| `urgency` | EMERGENCY items should progress rapidly |
| `is_overdue` | True indicates SLA breach -- requires attention |
| `time_in_current_state` | High values indicate stalled items |
| `priority_score` | Higher scores need attention first |
| `escalation_level` | Values above 0 indicate escalation history |

### Setting Up Notifications

Airtable supports email notifications for record changes. Configure alerts for:

1. New ESCALATED items (any work item entering ESCALATED state).
2. SLA breaches (is_overdue changing to true).
3. High-value quotes submitted (quote total_cost above your threshold).

---

## Handling Escalations

Escalated items require your direct intervention. Common escalation reasons:

### No Contractor Available

**What happened**: The system could not find a suitable contractor for the required trade discipline and postcode area.

**Actions**:
1. Open the work item and review the `discipline_required` and site location.
2. Check the Contractors table for active contractors with the matching trade.
3. Either:
   - Manually assign a contractor you know can cover the area.
   - Contact a new contractor and onboard them (see the Contractor Guide).
   - Re-categorise the work item if the discipline was misidentified.
4. Move the work item back to ASSESSMENT to re-enter the assignment flow.

### SLA Breach

**What happened**: The work item exceeded its SLA resolution deadline.

**Actions**:
1. Check the `urgency` level and `sla_due_at` timestamp.
2. Contact the assigned contractor/engineer for a status update.
3. Either:
   - Extend the SLA if there is a legitimate reason (parts on order, access issues).
   - Reassign to a different contractor if the current one is unresponsive.
   - Escalate to your own manager if the issue is systemic.
4. Return the item to ASSESSMENT for re-assignment, or update the state manually.

### Tenant Dispute

**What happened**: The tenant has rejected the completed work or raised a dispute about quality.

**Actions**:
1. Review the `completion_notes` and `completion_evidence_url` (photo).
2. Contact the tenant for details about their concerns.
3. Contact the contractor for their perspective.
4. Either:
   - Return to IN_PROGRESS if remedial work is needed.
   - Close the item if the dispute is resolved.
   - Cancel and create a new work item if a different contractor is needed.

### Contractor Non-Response

**What happened**: An assigned contractor did not respond within 24 hours.

**Actions**:
1. Contact the contractor directly (phone/email) to confirm availability.
2. If unavailable, return the item to ASSESSMENT for re-assignment.
3. Consider adjusting the contractor's rating in the Contractors table.

---

## Approving Quotes

When work is routed to external contractors, the RFQ process generates quotes that may require your approval.

### Reviewing Quotes

1. Navigate to the **Quotes** table.
2. Open the **Pending Review** view to see submitted quotes awaiting your decision.
3. For each quote, review:
   - `labour_cost` and `materials_cost` (both excluding VAT)
   - `total_inc_vat` (total including 20% VAT)
   - `scope_of_work` (what is included)
   - `exclusions` (what is not included)
   - `lead_time_days` (how long the work will take)
   - `valid_until` (expiry date of the quote)

### Comparing Quotes

1. Open the **Comparison View** to see all quotes for the same work item side by side.
2. Quotes are grouped by work item and sorted by total cost (lowest first).
3. Consider:
   - Is the cheapest quote genuinely like-for-like with others?
   - Does the contractor have the required certifications?
   - What is the contractor's rating and track record?
   - Is the lead time acceptable given the SLA?

### Accepting or Rejecting Quotes

To **accept** a quote:
1. Change the quote `status` to **ACCEPTED**.
2. The system will automatically:
   - Update the work item with the quoted amount.
   - Notify the contractor of acceptance.
   - Move the work item to ASSIGNED.

To **reject** a quote:
1. Change the quote `status` to **REJECTED**.
2. Add a note in the `notes` field explaining the reason.
3. The contractor will be notified.

---

## SLA Compliance Reports

### Understanding SLA Tiers

| Urgency | Response SLA | Resolution SLA | Escalation Intervals |
|---------|-------------|----------------|---------------------|
| EMERGENCY | 15 minutes | 4 hours | 15 min, 30 min, 60 min |
| URGENT | 1 hour | 24 hours | 1 hr, 2 hr, 4 hr |
| STANDARD | 4 hours | 72 hours | 4 hr, 8 hr, 24 hr |
| SCHEDULED | 24 hours | 2 weeks | 24 hr, 48 hr, 72 hr |

### Generating SLA Reports

Use the **Overdue Items** view to see current SLA breaches.

For historical reporting:
1. Switch to the **All Work Items** view.
2. Filter by date range using `created_at`.
3. Group by `urgency` to see distribution.
4. Export to CSV for spreadsheet analysis.

Key metrics to track:

| Metric | How to Calculate | Target |
|--------|-----------------|--------|
| SLA compliance rate | (Items resolved within SLA / Total items) x 100 | >90% |
| Average resolution time | Average of (closed_at - created_at) by urgency | Below SLA target |
| First response time | Average of (first outbound message - created_at) | Below response SLA |
| Escalation rate | (Escalated items / Total items) x 100 | <10% |
| Reopened rate | (Reopened items / Closed items) x 100 | <5% |

---

## WhatsApp Commands for Property Managers

As a property manager, you can also interact with SafeFlow via WhatsApp using these commands:

| Command | Usage | Example |
|---------|-------|---------|
| `APPROVE SF-1234` | Approve a work item or quote | "APPROVE SF-1234" |
| `CANCEL SF-1234` | Cancel a work item | "CANCEL SF-1234 Duplicate request" |
| `HOLD SF-1234` | Put a work item on hold | "HOLD SF-1234 Awaiting budget approval" |
| `ESCALATE SF-1234` | Manually escalate a work item | "ESCALATE SF-1234 Contractor not responding" |

---

## Tips for Effective Management

1. **Check the Kanban board daily** -- a 5-minute visual scan catches bottlenecks early.
2. **Resolve escalations promptly** -- escalated items block the workflow and affect SLA compliance.
3. **Review contractor ratings quarterly** -- low-rated contractors increase rework and escalation rates.
4. **Monitor the Errors table weekly** -- recurring errors may indicate configuration issues.
5. **Keep contractor records current** -- expired certifications (Gas Safe, NICEIC) will prevent assignment.
6. **Use the Comparison View for quotes** -- always compare at least 2 quotes for non-emergency work.
7. **Set up Airtable email notifications** -- get alerted to escalations without checking the dashboard constantly.
