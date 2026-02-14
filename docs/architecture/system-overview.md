# System Architecture Overview

## Design Principles

1. **Separation of Concerns** - Each tool handles one domain well
2. **Event-Driven** - All workflows triggered by events, not polling
3. **Idempotent Operations** - Safe to retry any operation
4. **Graceful Degradation** - System remains functional when components fail
5. **Audit Trail** - Every action logged and traceable

## Component Responsibilities

### 360dialog (WhatsApp Business API)
- **Role**: Message transport layer
- **Responsibilities**:
  - Receive inbound WhatsApp messages
  - Deliver outbound messages (text, templates, media)
  - Handle message status callbacks (sent, delivered, read)
  - Manage WhatsApp template approvals
- **SLA**: 99.9% uptime, <2s message delivery

### Make.com (Workflow Orchestration)
- **Role**: Central nervous system
- **Responsibilities**:
  - Route inbound messages to correct processing pipeline
  - Orchestrate multi-step workflows
  - Handle error recovery and retries
  - Manage state transitions
  - Rate limit outbound API calls
- **Key Scenarios**:
  - `inbound-message-router` - Entry point for all messages
  - `maintenance-request-flow` - Full maintenance lifecycle
  - `escalation-handler` - Time-based escalation chains
  - `xero-sync` - Financial data synchronization

### Airtable (Database & Admin UI)
- **Role**: System of record + admin interface
- **Responsibilities**:
  - Store all tenant, property, and request data
  - Provide admin interface for property managers
  - Trigger automations on data changes
  - Generate reports and dashboards
- **Tables**: See `airtable/schemas/` for full definitions

### Claude API (Intelligence Layer)
- **Role**: Natural language understanding and generation
- **Responsibilities**:
  - Classify inbound message intent
  - Extract structured data from free-text messages
  - Generate contextual responses
  - Detect urgency and sentiment
  - Handle multilingual support
- **Constraints**: Temperature 0.3 for consistency, structured output enforced

### Xero (Financial Integration)
- **Role**: Accounting system of record
- **Responsibilities**:
  - Invoice generation for maintenance work
  - Payment tracking and reconciliation
  - Tenant account balance lookups
  - Contractor payment management

## Data Flow

### Inbound Message Flow
```
1. Tenant sends WhatsApp message
2. 360dialog webhook → Make.com inbound scenario
3. Make.com extracts message metadata (sender, timestamp, type)
4. Lookup tenant in Airtable by phone number
5. If unknown tenant → new tenant registration flow
6. Send message + context to Claude API for classification
7. Claude returns: {intent, urgency, entities, suggested_response}
8. Route to appropriate workflow based on intent
9. Execute workflow (create record, lookup data, etc.)
10. Generate response via Claude with context
11. Send response via 360dialog
12. Log interaction in Airtable
```

### Escalation Flow
```
1. Airtable automation checks for overdue requests (scheduled)
2. Trigger Make.com escalation scenario
3. Calculate escalation level based on:
   - Time since creation
   - Urgency level
   - Number of previous escalations
4. Notify appropriate person via WhatsApp
5. Update escalation record in Airtable
6. If max escalations reached → notify management
```

## Error Handling Strategy

| Error Type | Handling | Recovery |
|-----------|----------|----------|
| 360dialog API down | Queue messages in Make.com | Retry with exponential backoff |
| Claude API timeout | Fallback to template responses | Retry once, then use fallback |
| Airtable rate limit | Batch operations, queue writes | Exponential backoff, max 5 retries |
| Xero API error | Log error, notify admin | Manual intervention for financial ops |
| Invalid message format | Log and ignore | No retry needed |
| Unknown tenant | Start registration flow | Automatic |

## Security Model

- All API keys stored in Make.com/Airtable encrypted fields
- Webhook endpoints validated via signature verification
- Tenant data access scoped by property manager
- PII handling compliant with Privacy Act 2020 (NZ)
- Message content not logged in plain text in monitoring systems
- Regular API key rotation schedule (90 days)

## Rate Limits & Quotas

| Service | Limit | Our Budget |
|---------|-------|------------|
| 360dialog | 80 messages/second | 30 msg/s max |
| Make.com | 10,000 operations/month (Teams) | ~8,000 ops/month |
| Airtable | 5 requests/second | 3 req/s max |
| Claude API | Tier-dependent | Monitored per-request |
| Xero | 60 calls/minute | 30 calls/min max |
