# ADR-003: Conversation Context Management

## Status
Accepted

## Date
2025-02-14

## Context
WhatsApp conversations are stateful — tenants expect the system to remember context within a conversation. We need a strategy for maintaining conversation state without a traditional backend.

## Decision
Implement conversation context via Airtable with a sliding window approach:

### Context Storage
- **Conversations table**: One record per active conversation
- **Messages table**: Individual messages linked to conversations
- **Context window**: Last 10 messages included in Claude API calls

### State Machine
```
IDLE → ACTIVE (on inbound message)
ACTIVE → AWAITING_INPUT (when system asks a question)
AWAITING_INPUT → ACTIVE (on tenant response)
ACTIVE → RESOLVED (on resolution confirmation)
ACTIVE → ESCALATED (on escalation trigger)
ACTIVE → IDLE (after 24h inactivity)
```

### Context Assembly (for Claude API)
```json
{
  "tenant": { "name", "property", "history_summary" },
  "active_requests": [ { "id", "status", "summary" } ],
  "recent_messages": [ { "role", "content", "timestamp" } ],
  "current_state": "AWAITING_INPUT"
}
```

## Consequences
- Claude receives sufficient context for coherent multi-turn conversations
- 10-message window limits token usage while maintaining coherence
- State machine prevents invalid transitions
- Conversation records enable analytics and quality review
- 24h auto-close prevents stale conversations from accumulating
