# Question_Bank Table — Complete Field Specification

Pre-defined questions used during the CLARIFICATION state. When the LLM determines
information is missing, it selects questions from this bank to ask the tenant via WhatsApp.

---

## Identity

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 1 | `question_id` | Auto number | — | Auto-incrementing ID |
| 2 | `question_code` | Single line text | Max 30 chars | Unique code, e.g. "Q_LOCATION", "Q_URGENCY", "Q_ACCESS" |

## Question Content

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 3 | `question_text_en` | Long text | Plain text | Question in English, e.g. "Where exactly in the building is the problem? Please include the floor, room, and area." |
| 4 | `question_text_es` | Long text | Plain text | Question in Spanish |
| 5 | `question_text_pl` | Long text | Plain text | Question in Polish |
| 6 | `whatsapp_format` | Single select | `TEXT`, `INTERACTIVE_BUTTONS`, `INTERACTIVE_LIST` | How this question is sent via WhatsApp |
| 7 | `button_options` | Long text | Plain text | JSON for interactive buttons: `[{"id":"opt_1","title":"Yes"},{"id":"opt_2","title":"No"}]` |
| 8 | `list_options` | Long text | Plain text | JSON for interactive list: `[{"id":"floor_g","title":"Ground floor","description":"Street level"}]` |

## Mapping

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 9 | `maps_to_field` | Single line text | Max 100 chars | Which Work_Items field this answer populates, e.g. "location_in_building", "category", "floor" |
| 10 | `category_relevance` | Multiple select | `PLUMBING`, `ELECTRICAL`, `HVAC`, `FIRE_SAFETY`, `STRUCTURAL`, `DOORS_WINDOWS`, `LIFTS`, `ROOFING`, `DECORATION`, `CLEANING`, `PEST_CONTROL`, `ACCESS_CONTROL`, `GENERAL`, `ALL` | Which job categories this question is relevant to |
| 11 | `required_for_states` | Multiple select | `INTAKE`, `CLARIFICATION`, `ASSESSMENT` | Which states require this question to be answered |
| 12 | `ask_order` | Number | Integer | Order in which to ask (1 = first, 2 = second, etc.) |

## Validation

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 13 | `is_required` | Checkbox | — | TRUE if this question must be answered before proceeding |
| 14 | `validation_type` | Single select | `FREE_TEXT`, `SINGLE_CHOICE`, `MULTIPLE_CHOICE`, `PHOTO_REQUIRED`, `YES_NO`, `NUMERIC`, `POSTCODE`, `PHONE_NUMBER` | Expected answer format |
| 15 | `validation_regex` | Single line text | Max 200 chars | Regex for validating the response (optional) |
| 16 | `max_retries` | Number | Integer, default 2 | How many times to re-ask if the answer is invalid |
| 17 | `fallback_action` | Single select | `ESCALATE_TO_HUMAN`, `SKIP`, `USE_DEFAULT` | What to do if max retries exceeded |
| 18 | `default_value` | Single line text | Max 200 chars | Default value if fallback_action = USE_DEFAULT |

## System

| # | Field Name | Type | Configuration | Description |
|---|-----------|------|---------------|-------------|
| 19 | `is_active` | Checkbox | — | TRUE if this question is currently in use |
| 20 | `created_at` | Date | Include time, GMT timezone | When this question was created |
| 21 | `notes` | Long text | Plain text | Notes about when/why to use this question |

---

## Field Count: 21
