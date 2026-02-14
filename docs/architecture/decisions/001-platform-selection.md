# ADR-001: Platform Selection

## Status
Accepted

## Date
2025-02-14

## Context
We need a facilities management system that property managers can operate without engineering support. The system must handle WhatsApp communication with tenants, manage maintenance requests, and integrate with accounting.

## Decision
We chose a no-code/low-code stack:
- **360dialog** over Twilio for WhatsApp (better pricing for WABA, native template management)
- **Make.com** over Zapier/n8n (superior error handling, visual debugging, data transformation)
- **Airtable** over PostgreSQL/Supabase (non-technical admin UI, built-in views/interfaces)
- **Claude API** over OpenAI (superior instruction following, structured output, safety)
- **Xero** over QuickBooks (NZ/AU market standard, better API)

## Consequences

### Positive
- Property managers can modify workflows without developers
- Visual debugging in Make.com reduces incident resolution time
- Airtable provides immediate admin interface
- Lower total cost of ownership for small-medium operations

### Negative
- Make.com operation limits require careful workflow optimization
- Airtable has row limits (125k on Pro) requiring archival strategy
- No traditional CI/CD — testing relies on scenario validation
- Vendor lock-in risk across multiple platforms

### Mitigations
- Document all configurations as code in this repository
- Build export/migration tooling for each platform
- Monitor operation counts and implement efficiency improvements
- Maintain API contract documentation for future platform swaps
