# Intake Triage Prompt - Changelog

All notable changes to the intake triage prompt are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [2.0.0] - 2026-02-14

### Added
- Complete 8-discipline classification system
- 4-tier urgency classification with UK-specific criteria
- Structured location extraction with UK floor conventions
- Safety assessment module with emergency service instructions
- Clarification question generation
- Confidence scoring framework
- 5 comprehensive worked examples
- Edge case handling (spam, greetings, abuse, foreign language, photo-only)
- Regulatory flags (Gas Safe, Asbestos, NICEIC)
- Multi-issue detection and prioritisation

### Changed
- Restructured output JSON for richer data extraction
- Improved routing logic with certification requirements
- Enhanced UK terminology and formatting

### Breaking Changes
- Output JSON schema completely redesigned from v1.x
- Discipline categories expanded from 5 to 8
- Routing decisions now include certification requirements

## [1.0.0] - 2026-01-15

### Added
- Initial intake triage prompt
- Basic 5-category classification
- Simple urgency assessment
- Text-only output format
