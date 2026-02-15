# Scenario E - Error Handler / Dead Letter Queue - Changelog

## [1.0.0] - 2026-02-15

### Added
- Webhook-triggered error intake from all SafeFlow scenarios (A, B, C, D)
- Error parsing and normalisation with generated error_id
- Four-level severity classification (CRITICAL, HIGH, MEDIUM, LOW) with context-aware overrides
- Airtable Errors table persistence for all errors
- Slack alerts to #safeflow-alerts for CRITICAL and HIGH severity errors
- Email alerts to operations team for CRITICAL severity errors
- Auto-retry with exponential backoff (60s base, 3 max retries, doubling delay)
- Retry exhaustion detection and alerting
- Anti-recursion guard in global error handler (never calls own webhook)
- Daily error digest at 08:00 Europe/London with summary statistics
- Digest delivered to #safeflow-ops Slack channel and operations team email
- Error record lifecycle management (PENDING_RETRY, NEEDS_REVIEW, RETRY_EXHAUSTED, RESOLVED)
