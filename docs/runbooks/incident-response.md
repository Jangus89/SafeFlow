# Incident Response Runbook

## Severity Levels

| Level | Description | Response Time | Examples |
|-------|------------|---------------|----------|
| SEV-1 | System down, no messages processing | 15 min | Make.com scenario disabled, webhook down |
| SEV-2 | Degraded, partial functionality | 1 hour | Claude API errors, Airtable rate limited |
| SEV-3 | Minor issue, workaround available | 4 hours | Template not sending, wrong classification |
| SEV-4 | Cosmetic / non-urgent | Next business day | Typo in response, minor UI issue |

## SEV-1: System Down

### Symptoms
- Tenants not receiving responses to messages
- Make.com showing scenario errors or paused
- Webhook URL returning errors

### Diagnosis Steps

1. **Check Make.com Dashboard**
   - Login → Scenarios → Check "safeflow-inbound-message-router"
   - Is the scenario active? (green circle)
   - Check execution history for recent errors
   - Check operations usage (may have hit limit)

2. **Check 360dialog**
   - Login to 360dialog hub
   - Check webhook configuration is pointing to correct Make.com URL
   - Check API key status

3. **Check Airtable**
   - Open Error Log table → "Unresolved Errors" view
   - Look for patterns in recent errors
   - Check if base is responding (try loading any table)

### Resolution Steps

1. **Make.com scenario paused/errored:**
   - Review error details in execution log
   - Fix the configuration issue
   - Re-enable the scenario
   - Send test message to verify

2. **Webhook URL changed:**
   - Copy new webhook URL from Make.com
   - Update in 360dialog webhook config
   - Verify with test webhook

3. **Operations limit reached:**
   - Upgrade plan or wait for reset
   - Disable non-critical scenarios (xero-sync, escalation) to preserve budget
   - Enable critical scenarios first (inbound-router)

4. **API key expired/revoked:**
   - Generate new key in respective service
   - Update in Make.com connections
   - Test all scenarios that use that connection

### Post-Incident

- Log incident in Error Log table with resolution
- Review queued messages that weren't processed
- Process any backlog manually if needed
- Update this runbook with new findings

---

## SEV-2: Claude API Errors

### Symptoms
- Tenants receiving fallback responses instead of intelligent replies
- Classification confidence dropping
- "Sorry, I'm having trouble processing..." messages in logs

### Diagnosis

1. Check Anthropic status page: https://status.anthropic.com
2. Check Error Log for Claude-specific errors
3. Verify API key is valid and has sufficient quota
4. Check if model name in config matches available models

### Resolution

1. **API rate limited:** Reduce request volume, check rate limit settings
2. **API key issue:** Rotate key in Anthropic console → update in Make.com
3. **Model unavailable:** Switch to fallback model in config
4. **Timeout:** Increase timeout in Make.com HTTP module (default 40s → 60s)

---

## SEV-2: Airtable Rate Limited

### Symptoms
- 429 errors in Make.com execution logs
- Data not being written to Airtable
- Delayed responses to tenants

### Resolution

1. Check which scenarios are consuming the most operations
2. Add delays between Airtable modules in Make.com (200ms minimum)
3. Batch operations where possible
4. Consider if any scenarios can run less frequently

---

## Scheduled Maintenance

### Monthly Tasks
- [ ] Review Error Log and resolve/close old entries
- [ ] Check Make.com operations usage trend
- [ ] Review Claude classification accuracy (Low Confidence view)
- [ ] Verify Xero sync is creating correct invoices
- [ ] Test emergency escalation flow end-to-end
- [ ] Rotate API keys if due (90-day cycle)
- [ ] Review and archive resolved maintenance requests older than 90 days

### Quarterly Tasks
- [ ] Review and update prompt templates based on classification data
- [ ] Audit WhatsApp template approval status
- [ ] Test disaster recovery (scenario reimport from blueprints)
- [ ] Review Airtable row counts and archive if approaching limits
- [ ] Update this runbook with lessons learned
