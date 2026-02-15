# Scenario B - State Engine - Changelog

## [2.0.0] - 2026-02-15

### Added
- LLM triage via Claude API for intent classification, urgency assessment, and discipline identification
- Command processing for 11 explicit commands (DONE, ACCEPT, START, REJECT, CANCEL, HOLD, QUOTE, APPROVE, ESCALATE, CONFIRM_COMPLETE, REOPEN)
- Optimistic state locking to prevent concurrent modification of work items
- Side effects router with 11 notification and action pathways
- Xero invoice creation on CLOSED and PAYMENT_PENDING states
- State transition validator with role-based access control
- Clarification request flow with LLM-generated questions
- Interactive button messages for job assignment (Accept/Decline) and verification (Looks good/Not resolved)
- Full state history logging with timestamped append-only audit trail
- SLA deadline calculation based on urgency tier (EMERGENCY, URGENT, STANDARD, SCHEDULED)
- Support for SYSTEM role actions from Scenario D (SLA Monitor)

### Changed
- Expanded state machine from 6 states to 12 states (added ACCEPTED, ON_HOLD, VERIFICATION, PAYMENT_PENDING, ESCALATED, REOPENED)
- Enriched payload structure from Scenario A now includes person context, command data, and work item state
- Error handler releases state locks before routing to DLQ to prevent deadlocks
- Improved rejection messaging with clear explanation of why an action was not permitted

### Fixed
- Race condition when multiple messages for the same work item arrive simultaneously
- State lock not released on Airtable write failure (now uses rollback pattern)

## [1.0.0] - 2026-01-20

### Added
- Initial state engine with basic command processing
- 6-state workflow (INTAKE, ASSESSMENT, ASSIGNED, IN_PROGRESS, CLOSED, CANCELLED)
- Simple text notifications via Scenario C
- Basic Airtable persistence for work items
