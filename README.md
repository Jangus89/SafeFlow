# SafeFlow - WhatsApp Facilities Management System

Production-grade facilities management system powered by WhatsApp, built for property managers and tenants.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────┐
│   Tenants   │────▶│  360dialog   │────▶│  Make.com   │────▶│ Airtable │
│ (WhatsApp)  │◀────│  WhatsApp    │◀────│  Workflows  │◀────│ Database │
└─────────────┘     │  Business    │     │             │     └──────────┘
                    │  API         │     │             │
                    └──────────────┘     │             │     ┌──────────┐
                                         │             │────▶│  Claude  │
                                         │             │◀────│  API     │
                                         │             │     └──────────┘
                                         │             │
                                         │             │     ┌──────────┐
                                         │             │────▶│   Xero   │
                                         │             │◀────│ Accounts │
                                         └─────────────┘     └──────────┘
```

## Tech Stack

| Component | Tool | Purpose |
|-----------|------|---------|
| Messaging | 360dialog | WhatsApp Business API provider |
| Orchestration | Make.com | Workflow automation & routing |
| Database | Airtable | Data storage & admin interface |
| Intelligence | Claude API | NLP, classification, response generation |
| Accounting | Xero | Invoicing, payments, financial tracking |

## Project Structure

```
SafeFlow-/
├── docs/                       # Architecture & operational docs
│   ├── architecture/           # System design documents
│   ├── runbooks/               # Operational procedures
│   └── api-contracts/          # API specifications
├── make-scenarios/             # Make.com scenario blueprints
│   ├── inbound/                # Incoming message handling
│   ├── outbound/               # Outgoing notifications
│   ├── escalation/             # Escalation workflows
│   └── integrations/           # Third-party integration flows
├── airtable/                   # Airtable schema & config
│   ├── schemas/                # Table definitions
│   ├── views/                  # View configurations
│   ├── automations/            # Airtable automation scripts
│   └── interfaces/             # Interface designer specs
├── prompts/                    # Claude API prompt engineering
│   ├── system/                 # System prompts
│   ├── classification/         # Intent classification prompts
│   ├── generation/             # Response generation prompts
│   └── extraction/             # Data extraction prompts
├── webhooks/                   # Webhook handlers & validation
│   ├── validators/             # Payload validation schemas
│   └── transforms/             # Data transformation maps
├── xero/                       # Xero integration config
│   ├── mappings/               # Field mapping definitions
│   └── templates/              # Invoice/quote templates
├── scripts/                    # Utility & deployment scripts
│   ├── setup/                  # Initial setup scripts
│   ├── migration/              # Data migration tools
│   └── monitoring/             # Health check scripts
├── tests/                      # Test suites
│   ├── integration/            # End-to-end flow tests
│   ├── prompts/                # Prompt regression tests
│   ├── webhooks/               # Webhook payload tests
│   └── fixtures/               # Test data fixtures
└── config/                     # Environment & app configuration
    ├── environments/           # Per-environment configs
    └── feature-flags/          # Feature flag definitions
```

## Getting Started

### Prerequisites

- 360dialog account with approved WhatsApp Business number
- Make.com account (Teams plan or higher recommended)
- Airtable account (Pro plan or higher)
- Anthropic API key
- Xero developer account

### Setup

1. Clone this repository
2. Copy `.env.example` to `.env` and configure all values
3. Import Airtable schema (see `airtable/schemas/`)
4. Import Make.com scenarios (see `make-scenarios/`)
5. Configure 360dialog webhook to point to Make.com
6. Run validation: `python scripts/setup/validate_config.py`

## Key Workflows

1. **Maintenance Request** - Tenant reports issue → classified by Claude → routed to contractor → tracked to completion
2. **Rent Inquiry** - Tenant asks about rent → Xero lookup → automated response
3. **Emergency Escalation** - Urgent issue detected → immediate notification chain → contractor dispatch
4. **Inspection Scheduling** - Automated inspection reminders → tenant confirmation → calendar sync

## Documentation

- [Architecture Decision Records](docs/architecture/decisions/)
- [API Contracts](docs/api-contracts/)
- [Operational Runbooks](docs/runbooks/)
- [Prompt Engineering Guide](prompts/README.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

Proprietary - All rights reserved.
