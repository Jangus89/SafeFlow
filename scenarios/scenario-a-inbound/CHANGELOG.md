# Scenario A - Inbound Handler - Changelog

## [2.0.0] - 2026-02-15

### Added
- Command extraction (done, accept, start, reject, cancel, hold, quote, approve)
- Job ID detection from message text (SF-XXXX format)
- Auto-registration for unknown WhatsApp senders
- Button reply processing for interactive messages
- Media ID extraction for images, documents, and audio

### Changed
- Enhanced message parsing to handle all WhatsApp message types
- Improved deduplication with 72-hour TTL data store
- Enriched handoff payload to Scenario B with person details, command data, and work item context

### Fixed
- Duplicate message processing when 360dialog retries webhook delivery

## [1.0.0] - 2026-01-15

### Added
- Initial inbound message handler
- Basic webhook receipt from 360dialog
- Text message parsing
- Simple forwarding to processing scenario
