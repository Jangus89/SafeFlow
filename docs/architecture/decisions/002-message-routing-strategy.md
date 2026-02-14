# ADR-002: Message Routing Strategy

## Status
Accepted

## Date
2025-02-14

## Context
Inbound WhatsApp messages need to be classified and routed to the correct workflow. We need to decide where classification happens and how routing is structured.

## Decision
Use a two-stage routing approach:
1. **Stage 1 (Make.com)**: Structural routing based on message type (text, image, location, interactive reply)
2. **Stage 2 (Claude API)**: Semantic routing based on message content and conversation context

### Routing Rules (Stage 1)
```
message_type == "interactive" → handle_button_reply
message_type == "image"       → maintenance_with_photo
message_type == "location"    → location_based_request
message_type == "text"        → claude_classification
```

### Classification Schema (Stage 2)
Claude classifies text messages into:
- `maintenance_request` - Report a problem
- `maintenance_update` - Update on existing request
- `rent_inquiry` - Questions about rent/payments
- `general_inquiry` - General questions
- `emergency` - Urgent safety/health issues
- `feedback` - Complaints or compliments
- `unknown` - Cannot classify

## Consequences
- Two-stage approach reduces Claude API calls (non-text messages skip LLM)
- Deterministic routing for structured inputs (button replies, locations)
- Claude handles ambiguous natural language classification
- Classification results cached in Airtable for analytics and prompt improvement
