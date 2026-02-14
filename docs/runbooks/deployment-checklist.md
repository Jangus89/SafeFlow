# Deployment Checklist

## Initial Deployment

### Phase 1: Foundation Setup

- [ ] **Airtable Base**
  - [ ] Create base from schema (`airtable/schemas/base-schema.json`)
  - [ ] Create all tables with correct field types
  - [ ] Set up linked record relationships
  - [ ] Create all defined views
  - [ ] Add sample data for testing
  - [ ] Set up field permissions (hide Key Safe Code from most users)
  - [ ] Note Base ID → update `.env`

- [ ] **360dialog WhatsApp**
  - [ ] Register WhatsApp Business number
  - [ ] Get API key from 360dialog hub
  - [ ] Submit WhatsApp message templates for approval
  - [ ] Wait for template approval (24-72 hours)
  - [ ] Note API key → update `.env`

- [ ] **Anthropic (Claude API)**
  - [ ] Create API key at console.anthropic.com
  - [ ] Set up billing
  - [ ] Note API key → update `.env`
  - [ ] Run prompt tests: `pytest tests/prompts/ -v`

- [ ] **Xero**
  - [ ] Create Xero app at developer.xero.com
  - [ ] Configure OAuth 2.0 redirect URIs
  - [ ] Set up required account codes
  - [ ] Create tracking categories (Property, Category)
  - [ ] Complete OAuth flow and store tokens
  - [ ] Note credentials → update `.env`

### Phase 2: Make.com Setup

- [ ] **Connections**
  - [ ] Create Airtable connection (use Personal Access Token)
  - [ ] Create HTTP connection for 360dialog
  - [ ] Create HTTP connection for Claude API
  - [ ] Create Xero connection (OAuth)
  - [ ] Name all connections with `sf-` prefix

- [ ] **Import Scenarios**
  - [ ] Import `inbound-message-router.json`
  - [ ] Import `maintenance-request-flow.json`
  - [ ] Import `escalation-handler.json`
  - [ ] Import `outbound-notification.json`
  - [ ] Import `xero-sync.json`
  - [ ] Update all connection references
  - [ ] Update all environment variables

- [ ] **Webhook Configuration**
  - [ ] Copy inbound webhook URL from Make.com
  - [ ] Configure 360dialog webhook to point to Make.com URL
  - [ ] Set webhook verify token

- [ ] **Airtable Automations**
  - [ ] Create status change automation (use `airtable/automations/status-change-notification.js`)
  - [ ] Configure automation trigger and input variables
  - [ ] Update webhook URL in automation script
  - [ ] Test automation with status change

### Phase 3: Testing

- [ ] **Unit Tests**
  - [ ] Run webhook validation: `pytest tests/webhooks/ -v`
  - [ ] Run prompt structure tests: `pytest tests/prompts/ -v -m "not live"`

- [ ] **Integration Tests (use test phone number)**
  - [ ] Send text message → verify classification
  - [ ] Send maintenance request → verify Airtable record created
  - [ ] Send image → verify media downloaded and attached
  - [ ] Reply to button → verify routing works
  - [ ] Send emergency message → verify escalation triggered
  - [ ] Verify fallback response when Claude is unavailable
  - [ ] Test duplicate request detection

- [ ] **Escalation Tests**
  - [ ] Create overdue request in Airtable
  - [ ] Wait for escalation scenario to run
  - [ ] Verify escalation notification sent
  - [ ] Verify Escalation Log record created

- [ ] **Xero Tests** (if enabled)
  - [ ] Complete a maintenance request with cost
  - [ ] Wait for xero-sync to run
  - [ ] Verify draft invoice created in Xero
  - [ ] Verify Airtable record updated with invoice ID

### Phase 4: Go Live

- [ ] Switch all scenarios from test to live mode
- [ ] Enable scheduled scenarios (escalation, xero-sync)
- [ ] Monitor first 24 hours closely
- [ ] Check Error Log hourly for first day
- [ ] Verify first real tenant message processed correctly
- [ ] Run health check: `python scripts/monitoring/health_check.py`

## Configuration Update Deployment

For changes to prompts, scenarios, or configuration:

1. [ ] Document change in relevant changelog
2. [ ] Run affected test suite
3. [ ] Deploy to Make.com (update scenario modules)
4. [ ] Test with sample message
5. [ ] Monitor Error Log for 1 hour
6. [ ] Commit configuration change to this repository
