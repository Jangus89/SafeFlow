# Scenario D - SLA Monitor - Changelog

## [1.0.0] - 2026-02-15

### Added
- Scheduled trigger running every 15 minutes (Europe/London timezone)
- Four-tier SLA definitions (EMERGENCY, URGENT, STANDARD, SCHEDULED) aligned with UK FM standards
- Three-level escalation chain with progressively senior notification recipients
- State-specific nudge logic for CLARIFICATION, ASSESSMENT, ASSIGNED, IN_PROGRESS, VERIFICATION, PAYMENT_PENDING, and ESCALATED states
- Auto-cancel for CLARIFICATION timeout (48 hours with no response)
- Auto-close for VERIFICATION timeout (72 hours with no response, deemed accepted)
- Auto-reassignment at escalation level 3, selecting the engineer with the lightest workload and matching discipline
- Escalation level tracking and update on Work_Items table
- State transitions routed through Scenario B (State Engine) for consistency and audit trail
- Notifications dispatched via Scenario C (Outbound Sender)
- Escalation event logging to Interaction_Logs table
- Global error handler routing to Scenario E (DLQ)
- Exclusion of state-locked, CLOSED, and CANCELLED items from processing
