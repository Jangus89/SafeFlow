# Changelog

All notable changes to the SafeFlow WhatsApp Facilities Management System are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-02-15

### Added
- Complete 9-table Airtable schema with 160+ fields
- 12-state work order lifecycle state machine
- 5 Make.com scenario blueprints (Inbound, State Engine, Outbound, SLA Monitor, Error Handler)
- LLM intake triage prompt v2.0.0 with 8 trade disciplines
- 200 test cases for intake triage prompt
- Quote analysis LLM prompt v1.0.0
- Automated evaluation pipeline for LLM prompts
- A/B testing framework with statistical significance testing
- Airtable schema validation scripts
- Make.com scenario validation scripts
- Deployment and rollback scripts
- Airtable backup and restore scripts
- Integration test suite
- k6 load test configuration
- 5 GitHub Actions CI/CD workflows
- Comprehensive documentation (architecture, deployment, runbooks, user guides)
- Monitoring dashboards and alert rules
- Seed data for testing
- Airtable migration framework

### Architecture
- WhatsApp via 360dialog Business API
- Make.com for workflow orchestration (5 scenarios)
- Airtable for data persistence (9 tables)
- Claude API for intelligent triage and analysis
- Xero integration for accounting and invoicing
- UK commercial property focus with GBP, UK dates, UK terminology

## [1.0.0] - 2026-01-15

### Added
- Initial repository structure
- Basic inbound message handling
- Simple 5-category classification
- Prototype Airtable schema
