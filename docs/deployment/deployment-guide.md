# SafeFlow Deployment Guide

## Overview

This guide walks through deploying SafeFlow from scratch. The deployment is divided into four phases with estimated times for an experienced operator. Total estimated time: **65 minutes**.

| Phase | Description | Duration |
|-------|-------------|----------|
| Phase 1 | Foundation (accounts, credentials, Airtable) | 15 min |
| Phase 2 | Make.com scenario import and configuration | 30 min |
| Phase 3 | Testing and validation | 20 min |
| Phase 4 | Go live | 5 min |

---

## Prerequisites

### Accounts Required

| Service | Plan Required | Sign-up URL |
|---------|--------------|-------------|
| **360dialog** | Partner or Direct | [360dialog.com](https://www.360dialog.com/) |
| **Make.com** | Teams or above (recommended) | [make.com](https://www.make.com/) |
| **Airtable** | Pro or above (for automations) | [airtable.com](https://airtable.com/) |
| **Anthropic** | API access (any tier) | [console.anthropic.com](https://console.anthropic.com/) |
| **Xero** | Standard or above | [xero.com/uk](https://www.xero.com/uk/) |
| **GitHub** | Free or above | [github.com](https://github.com/) |

### WhatsApp Business Verification

Before deployment, ensure your 360dialog account has:

- [ ] An approved WhatsApp Business number
- [ ] A verified Meta Business Manager account
- [ ] At least one approved message template (for outbound notifications)
- [ ] Webhook URL configuration access

### Local Tooling

| Tool | Version | Purpose |
|------|---------|---------|
| Node.js | v18+ | Integration tests and tooling |
| Python | 3.11+ | Schema validation and prompt evaluation |
| Git | 2.x+ | Version control |
| k6 | v0.50+ | Load testing |
| GitHub CLI (`gh`) | Latest | CI/CD and PR management |

### Clone the Repository

```bash
git clone https://github.com/SafeFlow/SafeFlow.git
cd SafeFlow
```

---

## Phase 1: Foundation (15 minutes)

### 1.1 Configure Environment Variables

```bash
cp config/environments/production.env.example .env
```

Open `.env` and populate all required values:

```env
# 360dialog
DIALOG_API_KEY=<your 360dialog API key>
DIALOG_API_URL=https://waba.360dialog.io
WHATSAPP_PHONE_NUMBER_ID=<your phone number ID>
WHATSAPP_BUSINESS_ACCOUNT_ID=<your business account ID>

# Airtable
AIRTABLE_API_KEY=pat<your personal access token>
AIRTABLE_BASE_ID=app<your base ID>

# Anthropic
ANTHROPIC_API_KEY=sk-ant-<your key>
CLAUDE_MODEL=claude-sonnet-4-5-20250929
CLAUDE_MAX_TOKENS=1500
CLAUDE_TEMPERATURE=0.2

# Xero
XERO_CLIENT_ID=<your client ID>
XERO_CLIENT_SECRET=<your client secret>
XERO_TENANT_ID=<your tenant ID>

# Make.com (populated after Phase 2)
MAKE_API_KEY=<your Make.com API key>
MAKE_WEBHOOK_URL_SCENARIO_A=<populated in Phase 2>
MAKE_WEBHOOK_URL_SCENARIO_B=<populated in Phase 2>
MAKE_WEBHOOK_URL_SCENARIO_C=<populated in Phase 2>
MAKE_WEBHOOK_URL_SCENARIO_D=<populated in Phase 2>
MAKE_WEBHOOK_URL_SCENARIO_E=<populated in Phase 2>
```

### 1.2 Create Airtable Base

1. Log in to Airtable and create a new base named **SafeFlow FM**.
2. Note the Base ID from the URL (format: `appXXXXXXXXXXXXXX`).
3. Create a Personal Access Token with the following scopes:
   - `data.records:read`
   - `data.records:write`
   - `schema.bases:read`
   - `schema.bases:write`
4. Update `AIRTABLE_BASE_ID` and `AIRTABLE_API_KEY` in your `.env` file.

### 1.3 Apply Airtable Schema

Create all 9 tables following the schema definitions in `airtable/schema/`:

| Order | Table | Schema File | Field Count |
|-------|-------|------------|-------------|
| 1 | Work_Items | `Work_Items.json` | 35 |
| 2 | Sites | `Sites.json` | 20 |
| 3 | People | `People.json` | 15 |
| 4 | Contractors | `Contractors.json` | 25 |
| 5 | Quotes | `Quotes.json` | 17 |
| 6 | Payments | `Payments.json` | 17 |
| 7 | Interaction_Logs | `Interaction_Logs.json` | 17 |
| 8 | Question_Bank | `Question_Bank.json` | 12 |
| 9 | Errors | `Errors.json` | 15 |

**Important**: Create tables in the order listed above, as later tables contain linked record fields referencing earlier tables.

Validate the schema after creation:

```bash
python scripts/validation/validate-airtable-schema.py
```

### 1.4 Load Seed Data

```bash
node airtable/scripts/seed-data.js
```

This loads:
- Test sites from `airtable/seed-data/sites-test.csv`
- Test contractors from `airtable/seed-data/contractors-test.csv`
- Clarification questions from `airtable/seed-data/question-bank.csv`

### 1.5 Configure Xero Integration

1. Create a Xero app at [developer.xero.com](https://developer.xero.com/).
2. Set the redirect URI to your application callback URL.
3. Authorise the app against your Xero organisation.
4. Note the `client_id`, `client_secret`, and `tenant_id`.
5. Create an expense account code in Xero for FM costs (e.g., code `300`).

---

## Phase 2: Make.com Scenario Import (30 minutes)

### 2.1 Create Make.com Organisation

1. Log in to Make.com.
2. Create a new organisation or use an existing one.
3. Create a team workspace for SafeFlow.
4. Note your Team ID and API key.

### 2.2 Create Data Stores

Before importing scenarios, create the following data store:

| Data Store Name | Key Field | Fields | Max Size |
|----------------|-----------|--------|----------|
| `DS_PROCESSED_MESSAGES` | `message_id` (Text) | `processed_at` (Date), `sender` (Text) | 5,000 records |

### 2.3 Import Scenarios

Import each scenario blueprint in order. For each scenario:

1. Go to **Scenarios** > **Create a new scenario**.
2. Click the **...** menu > **Import Blueprint**.
3. Upload the blueprint JSON file.
4. Configure all connection credentials (Airtable, 360dialog, Anthropic, Xero).

| Order | Blueprint File | Notes |
|-------|---------------|-------|
| 1 | `scenarios/scenario-a-inbound/blueprint.json` | Note the webhook URL generated -- this is `MAKE_WEBHOOK_URL_SCENARIO_A` |
| 2 | `scenarios/scenario-b-state-engine/blueprint.json` | Note the webhook URL -- `MAKE_WEBHOOK_URL_SCENARIO_B`. Configure Claude API connection. |
| 3 | Import Scenario C blueprint | Note the webhook URL -- `MAKE_WEBHOOK_URL_SCENARIO_C`. Configure 360dialog send connection. |
| 4 | `scenarios/scenario-d-sla/blueprint.json` | Configure the schedule trigger (every 15 minutes). |
| 5 | Import Scenario E blueprint | Note the webhook URL -- `MAKE_WEBHOOK_URL_SCENARIO_E`. |

### 2.4 Update Webhook URLs

After importing all scenarios, update your `.env` file with the generated webhook URLs:

```env
MAKE_WEBHOOK_URL_SCENARIO_A=https://hook.eu2.make.com/<generated_a>
MAKE_WEBHOOK_URL_SCENARIO_B=https://hook.eu2.make.com/<generated_b>
MAKE_WEBHOOK_URL_SCENARIO_C=https://hook.eu2.make.com/<generated_c>
MAKE_WEBHOOK_URL_SCENARIO_D=https://hook.eu2.make.com/<generated_d>
MAKE_WEBHOOK_URL_SCENARIO_E=https://hook.eu2.make.com/<generated_e>
```

Then update the webhook URL references within each scenario:
- Scenario A: Update the handoff URL to Scenario B and error URL to Scenario E.
- Scenario B: Update the notification URL to Scenario C and error URL to Scenario E.
- Scenario C: Update the error URL to Scenario E.
- Scenario D: Update the escalation URL to Scenario B and error URL to Scenario E.

### 2.5 Configure 360dialog Webhook

1. Log in to the 360dialog Partner Hub.
2. Navigate to your WhatsApp number configuration.
3. Set the **Webhook URL** to `MAKE_WEBHOOK_URL_SCENARIO_A`.
4. Subscribe to the `messages` webhook event.
5. Set the API key header (`D360-API-KEY`) for webhook verification.

### 2.6 Activate Scenarios

Activate each scenario in order:

1. Scenario E (Error Handler) -- activate first so error handling is available.
2. Scenario D (SLA Monitor) -- activate the scheduled trigger.
3. Scenario C (Outbound Sender).
4. Scenario B (State Engine).
5. Scenario A (Inbound Handler) -- activate last so all downstream scenarios are ready.

---

## Phase 3: Testing (20 minutes)

### 3.1 Environment Validation

```bash
bash scripts/validate-env.sh
bash scripts/health-check.sh
```

Expected output: All checks should pass (green). Address any failures before proceeding.

### 3.2 Smoke Test -- Manual WhatsApp Message

Send a WhatsApp message to your configured business number:

> "Hi, the kitchen tap in unit 4B at Meridian House is leaking badly. Can someone come and fix it please?"

**Expected behaviour** (verify within 60 seconds):

1. Message appears in Airtable `Interaction_Logs` table.
2. A new `Work_Items` record is created with:
   - `current_state`: ASSESSMENT
   - `discipline_required`: PLUMBING
   - `urgency`: STANDARD
   - `title`: Contains "tap" and "leaking" or similar
3. Tenant receives an acknowledgement WhatsApp message.

### 3.3 Emergency Flow Test

Send:

> "URGENT - strong smell of gas in the ground floor lobby. We have evacuated."

**Expected behaviour**:

1. `urgency`: EMERGENCY
2. `discipline_required`: GAS_SAFE
3. Immediate notification sent to duty supervisor.
4. Safety instructions sent to tenant (evacuate, call 0800 111 999).

### 3.4 Clarification Flow Test

Send:

> "Something is broken"

**Expected behaviour**:

1. `current_state`: CLARIFICATION
2. Tenant receives a clarification question via WhatsApp.

### 3.5 Integration Test Suite

```bash
# Install dependencies
pip install -r requirements-test.txt
cd tests/integration && npm install && cd ../..

# Run integration tests against staging
npm --prefix tests/integration test

# Run specific test suites
npm --prefix tests/integration run test:intake
npm --prefix tests/integration run test:rfq
npm --prefix tests/integration run test:sla
```

### 3.6 Load Test (Optional)

```bash
k6 run tests/load/k6-config.js --out json=k6-results/load-test.json
```

Verify thresholds pass:
- P95 response time < 5 seconds
- Error rate < 5%

---

## Phase 4: Go Live

### 4.1 Pre-Go-Live Checklist

- [ ] All 9 Airtable tables created and validated
- [ ] All 5 Make.com scenarios imported, configured, and active
- [ ] 360dialog webhook pointing to Scenario A
- [ ] Xero integration tested with a draft invoice
- [ ] Smoke tests passed (standard, emergency, clarification)
- [ ] Integration test suite passing
- [ ] Monitoring alerts configured (Slack, email, PagerDuty)
- [ ] Airtable backup schedule configured (daily)
- [ ] Team notified of go-live date and escalation contacts
- [ ] Rollback plan documented and rehearsed

### 4.2 Go Live Steps

1. **Update 360dialog webhook** to point to the production Scenario A URL (if testing was done on staging).
2. **Verify Scenario D schedule** is active (SLA monitoring every 15 minutes).
3. **Send a test message** from a real tenant device and verify end-to-end flow.
4. **Monitor** the first 30 minutes for any errors in the Errors table or Make.com execution history.
5. **Announce** go-live to tenants and property managers.

### 4.3 Post-Go-Live Monitoring

For the first 48 hours after go live, actively monitor:

| What | Where | Frequency |
|------|-------|-----------|
| Scenario execution errors | Make.com > Execution History | Every 30 minutes |
| Airtable Errors table | Airtable > Errors view | Every hour |
| SLA compliance | Airtable > Work_Items > Overdue Items view | Every 2 hours |
| WhatsApp delivery failures | Airtable > Interaction_Logs > Failed Deliveries | Every hour |
| LLM triage accuracy | Spot-check 10 recent triage results | End of day 1 |

### 4.4 Rollback Procedure

If critical issues are encountered during go live:

```bash
# Revert Make.com scenarios to previous version
bash scripts/deploy.sh rollback production

# Or manually:
# 1. Deactivate Scenario A in Make.com (stops inbound processing)
# 2. Investigate and fix the issue
# 3. Reactivate scenarios in order: E, D, C, B, A
```

---

## Environment Matrix

| Setting | Development | Staging | Production |
|---------|-------------|---------|------------|
| 360dialog number | Test number | Test number | Production number |
| Make.com workspace | Dev | Staging | Production |
| Airtable base | Dev base | Staging base | Production base |
| Claude model | claude-sonnet-4-5-20250929 | claude-sonnet-4-5-20250929 | claude-sonnet-4-5-20250929 |
| Xero organisation | Sandbox | Demo company | Live organisation |
| Log level | DEBUG | INFO | WARNING |
| SLA check interval | 5 min | 15 min | 15 min |
| Backup retention | 7 days | 14 days | 30 days |

---

## Troubleshooting

### Common Deployment Issues

| Issue | Cause | Resolution |
|-------|-------|------------|
| Webhook returns 404 | Scenario not activated | Activate the scenario in Make.com |
| Airtable 422 error on record create | Schema mismatch | Compare field names and types against schema JSON files |
| Claude API 401 | Invalid API key | Regenerate key at console.anthropic.com and update Make.com connection |
| No WhatsApp messages received | Webhook URL misconfigured | Verify URL in 360dialog Partner Hub matches Scenario A webhook |
| Xero invoice creation fails | OAuth token expired | Re-authorise the Xero connection in Make.com |
| Duplicate work items created | Deduplication data store not configured | Create the `DS_PROCESSED_MESSAGES` data store in Make.com |
| State lock not releasing | Scenario B error handler misconfigured | Verify Module 99 includes lock release step |
