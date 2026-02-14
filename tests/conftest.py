"""Shared test configuration and fixtures for SafeFlow test suite."""

import json
import os
from pathlib import Path

import pytest

# Project root
ROOT_DIR = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures"
PROMPTS_DIR = ROOT_DIR / "prompts"
SCHEMAS_DIR = ROOT_DIR / "webhooks" / "validators"


@pytest.fixture
def project_root():
    return ROOT_DIR


@pytest.fixture
def whatsapp_webhook_schema():
    """Load the WhatsApp webhook validation schema."""
    schema_path = SCHEMAS_DIR / "whatsapp-webhook-schema.json"
    with open(schema_path) as f:
        return json.load(f)


@pytest.fixture
def sample_text_message():
    """Sample inbound text message from 360dialog."""
    return {
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
                                    "profile": {"name": "Test Tenant"},
                                    "wa_id": "64211234567",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "64211234567",
                                    "id": "wamid.TEST123",
                                    "timestamp": "1707900000",
                                    "type": "text",
                                    "text": {
                                        "body": "The kitchen tap is leaking"
                                    },
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


@pytest.fixture
def sample_image_message():
    """Sample inbound image message."""
    return {
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
                                    "profile": {"name": "Test Tenant"},
                                    "wa_id": "64211234567",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "64211234567",
                                    "id": "wamid.TEST456",
                                    "timestamp": "1707900000",
                                    "type": "image",
                                    "image": {
                                        "id": "MEDIA_ID_123",
                                        "mime_type": "image/jpeg",
                                        "sha256": "abc123",
                                        "caption": "Water damage in bathroom",
                                    },
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


@pytest.fixture
def sample_interactive_reply():
    """Sample interactive button reply."""
    return {
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
                                    "profile": {"name": "Test Tenant"},
                                    "wa_id": "64211234567",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "64211234567",
                                    "id": "wamid.TEST789",
                                    "timestamp": "1707900000",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {
                                            "id": "resolve_MR-20250214-1234",
                                            "title": "Looks correct",
                                        },
                                    },
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


@pytest.fixture
def classification_test_cases():
    """Test cases for intent classification prompt."""
    return [
        {
            "input": "The kitchen tap is leaking",
            "expected_intent": "maintenance_request",
            "expected_urgency": "medium",
            "expected_category": "plumbing",
        },
        {
            "input": "I can smell gas in my apartment",
            "expected_intent": "emergency",
            "expected_urgency": "emergency",
        },
        {
            "input": "When is my rent due this month?",
            "expected_intent": "rent_inquiry",
            "expected_urgency": "low",
        },
        {
            "input": "Hi",
            "expected_intent": "greeting",
            "expected_urgency": "low",
        },
        {
            "input": "The issue from ref MR-20250210-1234 is still not fixed",
            "expected_intent": "maintenance_update",
            "expected_urgency": "high",
        },
        {
            "input": "The power outlet in the bedroom is sparking",
            "expected_intent": "maintenance_request",
            "expected_urgency": "high",
        },
        {
            "input": "There are cockroaches in the kitchen again",
            "expected_intent": "maintenance_request",
            "expected_urgency": "medium",
            "expected_category": "pest",
        },
        {
            "input": "Your maintenance team did a great job fixing the shower, thanks!",
            "expected_intent": "feedback",
            "expected_urgency": "low",
        },
        {
            "input": "How do I end my lease early?",
            "expected_intent": "general_inquiry",
            "expected_urgency": "low",
        },
        {
            "input": "Water is flooding into my lounge from a burst pipe!",
            "expected_intent": "emergency",
            "expected_urgency": "emergency",
        },
    ]
