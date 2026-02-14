# Interaction_Logs Table — Complete Field Specification

Every WhatsApp message (inbound and outbound) is logged here. This is the audit trail
for all communication between the system and its users.

---

## Identity

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 1 | `log_id` | Auto number | — | Auto-incrementing ID |
| 2 | `timestamp` | Date | Include time, GMT timezone | When the message was sent/received |

## Message Details

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 3 | `direction` | Single select | `INBOUND` (green), `OUTBOUND` (blue) | Whether this message was received from or sent to a user |
| 4 | `message_type` | Single select | `TEXT`, `IMAGE`, `VIDEO`, `AUDIO`, `DOCUMENT`, `LOCATION`, `CONTACT`, `STICKER`, `TEMPLATE`, `INTERACTIVE`, `BUTTON_REPLY`, `LIST_REPLY`, `REACTION` | WhatsApp message type |
| 5 | `message_body` | Long text | Plain text | Text content of the message |
| 6 | `media_url` | URL | — | URL of media attachment (photo, video, document) — hosted on 360dialog CDN |
| 7 | `media_mime_type` | Single line text | Max 50 chars | MIME type, e.g. "image/jpeg", "video/mp4", "application/pdf" |
| 8 | `media_caption` | Single line text | Max 500 chars | Caption attached to media message |

## WhatsApp Metadata

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 9 | `whatsapp_message_id` | Single line text | Max 100 chars | WhatsApp's unique message ID (wamid.xxxxx) |
| 10 | `whatsapp_status` | Single select | `SENT`, `DELIVERED`, `READ`, `FAILED`, `DELETED` | Delivery status of outbound messages |
| 11 | `whatsapp_error_code` | Number | Integer | WhatsApp error code if delivery failed |
| 12 | `whatsapp_error_message` | Single line text | Max 500 chars | Error message if delivery failed |
| 13 | `template_name` | Single line text | Max 100 chars | For OUTBOUND template messages: name of the template used |
| 14 | `template_language` | Single line text | Max 10 chars | Template language code: "en", "es", "pl" |

## Links

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 15 | `person` | Link to another record | Links to **People** table | The person who sent/received this message |
| 16 | `phone_number` | Phone number | +44 format | The WhatsApp phone number (for quick lookup before person is matched) |
| 17 | `work_item` | Link to another record | Links to **Work_Items** table | The work item this message relates to (may be null for initial intake) |
| 18 | `site` | Link to another record | Links to **Sites** table | The site this message relates to (derived from the intake number called) |

## Processing

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 19 | `processing_status` | Single select | `UNPROCESSED` (red), `PROCESSING` (yellow), `PROCESSED` (green), `FAILED` (dark red), `IGNORED` (grey) | Whether this message has been handled by the automation |
| 20 | `processed_at` | Date | Include time, GMT timezone | When the message was processed |
| 21 | `processing_action` | Single line text | Max 200 chars | What action was taken, e.g. "Created WO-00123", "Updated state to IN_PROGRESS" |
| 22 | `n8n_execution_id` | Single line text | Max 100 chars | n8n workflow execution ID that processed this message |

## Raw Data

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 23 | `raw_payload` | Long text | Plain text | Full JSON payload from 360dialog webhook (for debugging) |
| 24 | `llm_intent` | Single select | `REPORT_ISSUE`, `PROVIDE_INFO`, `ASK_QUESTION`, `CONFIRM`, `REJECT`, `SEND_PHOTO`, `REQUEST_UPDATE`, `COMPLAINT`, `GREETING`, `SPAM`, `UNKNOWN` | LLM-classified intent of inbound message |
| 25 | `llm_sentiment` | Single select | `POSITIVE`, `NEUTRAL`, `NEGATIVE`, `ANGRY`, `URGENT` | LLM-detected sentiment |
| 26 | `llm_extracted_data` | Long text | Plain text | JSON of structured data extracted by LLM: `{"issue":"leak","location":"kitchen","urgency":"high"}` |

---

## Field Count: 26
