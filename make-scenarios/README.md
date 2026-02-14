# Make.com Scenarios

## Overview

All Make.com scenarios are documented as JSON blueprints in this directory. These blueprints serve as:
1. **Version-controlled documentation** of workflow logic
2. **Import templates** for scenario recreation
3. **Review artifacts** for workflow changes

## Scenario Index

| Scenario | Trigger | Purpose | Est. Operations/Run |
|----------|---------|---------|-------------------|
| `inbound-message-router` | Webhook (360dialog) | Route incoming WhatsApp messages | 5-12 |
| `maintenance-request-flow` | Called by router | Full maintenance request lifecycle | 8-15 |
| `escalation-handler` | Scheduled (15 min) | Check and escalate overdue requests | 3-8 |
| `outbound-notification` | Webhook (Airtable) | Send proactive notifications | 3-5 |
| `xero-sync` | Scheduled (hourly) | Sync financial data with Xero | 5-20 |
| `tenant-registration` | Called by router | Register new tenants | 4-6 |

## Import Instructions

1. Open Make.com → Scenarios → Create New
2. Click the three dots menu → Import Blueprint
3. Paste the JSON from the relevant `.json` file
4. Update connection references to your Make.com connections
5. Update webhook URLs if needed
6. Activate the scenario

## Naming Conventions

- Scenario names: `safeflow-{domain}-{action}` (e.g., `safeflow-maintenance-create`)
- Webhook names: `sf-webhook-{purpose}` (e.g., `sf-webhook-inbound`)
- Connection names: `sf-{service}` (e.g., `sf-airtable`, `sf-360dialog`)

## Operation Budget

Monthly budget: ~8,000 operations (of 10,000 Teams plan limit)

| Scenario | Estimated Monthly Ops | Priority |
|----------|--------------------|----------|
| Inbound Router | 3,000 | Critical |
| Maintenance Flow | 2,000 | Critical |
| Escalation | 1,500 | High |
| Notifications | 800 | Medium |
| Xero Sync | 500 | Medium |
| Registration | 200 | Low |
