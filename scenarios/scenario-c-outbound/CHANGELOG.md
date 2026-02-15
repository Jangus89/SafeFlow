# Scenario C - Outbound Message Sender - Changelog

## [1.0.0] - 2026-02-15

### Added
- Webhook trigger receiving outbound requests from Scenario B and Scenario D
- Recipient resolution from Airtable People table by person_id
- Recipient validation (active user with valid WhatsApp number)
- Outbound deduplication with 5-minute TTL data store (DS_OUTBOUND_DEDUPE)
- Message type router supporting template, text, and interactive messages
- 360dialog Cloud API integration for all three message types
- Interaction log creation for every outbound message (OUTBOUND direction)
- Error handler with send failure classification (rate limit, server error, template not found, session expired)
- Automatic retry with exponential backoff for 429 and 5xx errors
- Additional recipients processing via self-referencing webhook calls
- Global error handler routing to Scenario E (DLQ)
- Ten pre-approved WhatsApp template message definitions
