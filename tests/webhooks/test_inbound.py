"""Tests for WhatsApp webhook payload validation."""

import json

import jsonschema
import pytest


class TestWhatsAppWebhookValidation:
    """Validate inbound webhook payloads against the JSON schema."""

    def test_valid_text_message(self, whatsapp_webhook_schema, sample_text_message):
        """Valid text message payload should pass validation."""
        jsonschema.validate(sample_text_message, whatsapp_webhook_schema)

    def test_valid_image_message(self, whatsapp_webhook_schema, sample_image_message):
        """Valid image message payload should pass validation."""
        jsonschema.validate(sample_image_message, whatsapp_webhook_schema)

    def test_valid_interactive_reply(
        self, whatsapp_webhook_schema, sample_interactive_reply
    ):
        """Valid interactive reply payload should pass validation."""
        jsonschema.validate(sample_interactive_reply, whatsapp_webhook_schema)

    def test_missing_object_field(self, whatsapp_webhook_schema):
        """Payload missing 'object' field should fail validation."""
        invalid_payload = {"entry": []}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_payload, whatsapp_webhook_schema)

    def test_wrong_object_value(self, whatsapp_webhook_schema):
        """Payload with wrong 'object' value should fail validation."""
        invalid_payload = {"object": "instagram", "entry": [{"id": "test", "changes": []}]}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_payload, whatsapp_webhook_schema)

    def test_empty_entry_array(self, whatsapp_webhook_schema):
        """Payload with empty entry array should fail validation."""
        invalid_payload = {"object": "whatsapp_business_account", "entry": []}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_payload, whatsapp_webhook_schema)

    def test_invalid_phone_format(self, whatsapp_webhook_schema):
        """Phone number with letters should fail validation."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WABA_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "6421000000",
                                    "phone_number_id": "PHONE_ID",
                                },
                                "contacts": [
                                    {
                                        "profile": {"name": "Test"},
                                        "wa_id": "invalid_phone",
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, whatsapp_webhook_schema)

    def test_valid_message_types(self, whatsapp_webhook_schema, sample_text_message):
        """All supported message types should pass validation."""
        valid_types = [
            "text", "image", "document", "audio", "video",
            "location", "contacts", "interactive", "button",
            "sticker", "reaction",
        ]
        for msg_type in valid_types:
            payload = json.loads(json.dumps(sample_text_message))
            payload["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = msg_type
            # Should not raise
            jsonschema.validate(payload, whatsapp_webhook_schema)

    def test_invalid_message_type(self, whatsapp_webhook_schema, sample_text_message):
        """Unsupported message type should fail validation."""
        payload = json.loads(json.dumps(sample_text_message))
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = "carrier_pigeon"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, whatsapp_webhook_schema)


class TestStatusWebhook:
    """Validate status update webhook payloads."""

    def test_valid_status_update(self, whatsapp_webhook_schema):
        """Valid status update payload should pass validation."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WABA_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "6421000000",
                                    "phone_number_id": "PHONE_ID",
                                },
                                "statuses": [
                                    {
                                        "id": "wamid.STATUS123",
                                        "status": "delivered",
                                        "timestamp": "1707900000",
                                        "recipient_id": "64211234567",
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        jsonschema.validate(payload, whatsapp_webhook_schema)
