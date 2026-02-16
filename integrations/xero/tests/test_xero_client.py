#!/usr/bin/env python3
"""Unit tests for Xero API client.

Tests OAuth2 token management, invoice creation, retry logic,
and error handling using mocked HTTP calls.

Usage:
    python -m pytest integrations/xero/tests/test_xero_client.py -v
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from xero_client import (
    MAX_RETRIES,
    XERO_API_BASE,
    XERO_AUTH_URL,
    XeroApiError,
    XeroClient,
    XeroTokenError,
)


class TestXeroTokenManagement(unittest.TestCase):
    """Tests for OAuth2 token lifecycle."""

    def setUp(self) -> None:
        self.token_dir = tempfile.mkdtemp()
        self.token_file = Path(self.token_dir) / ".xero-tokens.json"
        self.env_patch = patch.dict(os.environ, {
            "XERO_CLIENT_ID": "test_client_id",
            "XERO_CLIENT_SECRET": "test_client_secret",
            "XERO_TENANT_ID": "test_tenant_id",
        })
        self.env_patch.start()

    def tearDown(self) -> None:
        self.env_patch.stop()
        if self.token_file.exists():
            self.token_file.unlink()

    def test_load_tokens_from_file(self) -> None:
        """Should load stored tokens from JSON file."""
        token_data = {
            "access_token": "test_access",
            "refresh_token": "test_refresh",
            "expires_at": time.time() + 3600,
        }
        with open(self.token_file, "w") as f:
            json.dump(token_data, f)

        client = XeroClient(token_file=self.token_file)
        self.assertEqual(client._access_token, "test_access")
        self.assertEqual(client._refresh_token, "test_refresh")

    def test_save_tokens_to_file(self) -> None:
        """Should persist tokens to file with restricted permissions."""
        client = XeroClient(token_file=self.token_file)
        client._access_token = "new_access"
        client._refresh_token = "new_refresh"
        client._token_expires_at = time.time() + 3600
        client._save_tokens()

        self.assertTrue(self.token_file.exists())
        with open(self.token_file) as f:
            data = json.load(f)
        self.assertEqual(data["access_token"], "new_access")
        self.assertEqual(data["refresh_token"], "new_refresh")

    def test_token_is_valid(self) -> None:
        """Should correctly validate token expiry with 60s buffer."""
        client = XeroClient(token_file=self.token_file)

        # Token with plenty of time
        client._access_token = "valid"
        client._token_expires_at = time.time() + 3600
        self.assertTrue(client._token_is_valid())

        # Token about to expire (within 60s buffer)
        client._token_expires_at = time.time() + 30
        self.assertFalse(client._token_is_valid())

        # Expired token
        client._token_expires_at = time.time() - 100
        self.assertFalse(client._token_is_valid())

        # No token at all
        client._access_token = ""
        self.assertFalse(client._token_is_valid())

    @patch("xero_client.requests.post")
    def test_refresh_access_token(self, mock_post: MagicMock) -> None:
        """Should refresh token and save to file."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "access_token": "refreshed_access",
            "refresh_token": "refreshed_refresh",
            "expires_in": 1800,
        }
        mock_post.return_value = mock_response

        client = XeroClient(token_file=self.token_file)
        client._refresh_token = "old_refresh"
        client.refresh_access_token()

        self.assertEqual(client._access_token, "refreshed_access")
        self.assertEqual(client._refresh_token, "refreshed_refresh")

        # Verify the POST was called with correct params
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        self.assertIn("grant_type", call_kwargs.kwargs.get("data", call_kwargs[1].get("data", {})))

    def test_refresh_without_refresh_token_raises(self) -> None:
        """Should raise XeroTokenError if no refresh token is available."""
        client = XeroClient(token_file=self.token_file)
        client._refresh_token = ""

        with self.assertRaises(XeroTokenError):
            client.refresh_access_token()

    def test_missing_env_vars_raises(self) -> None:
        """Should raise XeroTokenError if required env vars are missing."""
        with patch.dict(os.environ, {"XERO_CLIENT_ID": "", "XERO_CLIENT_SECRET": ""}, clear=False):
            with self.assertRaises(XeroTokenError):
                XeroClient(client_id="", client_secret="", token_file=self.token_file)


class TestXeroInvoiceCreation(unittest.TestCase):
    """Tests for invoice creation payload mapping."""

    def setUp(self) -> None:
        self.token_dir = tempfile.mkdtemp()
        self.token_file = Path(self.token_dir) / ".xero-tokens.json"

        # Write valid tokens
        token_data = {
            "access_token": "test_access",
            "refresh_token": "test_refresh",
            "expires_at": time.time() + 3600,
        }
        with open(self.token_file, "w") as f:
            json.dump(token_data, f)

        self.env_patch = patch.dict(os.environ, {
            "XERO_CLIENT_ID": "test_client_id",
            "XERO_CLIENT_SECRET": "test_client_secret",
            "XERO_TENANT_ID": "test_tenant_id",
        })
        self.env_patch.start()

    def tearDown(self) -> None:
        self.env_patch.stop()

    @patch("xero_client.requests.request")
    def test_create_invoice_maps_fields_correctly(self, mock_request: MagicMock) -> None:
        """Should map work item, quote, and contractor fields to Xero invoice."""
        # Mock: find contact (none found), create contact, find invoice (none), create invoice
        mock_responses = [
            # find_contact_by_name
            MagicMock(status_code=200, json=MagicMock(return_value={"Contacts": []})),
            # create_contact
            MagicMock(status_code=200, json=MagicMock(return_value={
                "Contacts": [{"ContactID": "xero-contact-123", "Name": "TestCo"}]
            })),
            # find_invoice_by_reference
            MagicMock(status_code=200, json=MagicMock(return_value={"Invoices": []})),
            # create_invoice
            MagicMock(status_code=200, json=MagicMock(return_value={
                "Invoices": [{
                    "InvoiceID": "xero-inv-456",
                    "Reference": "SF-WI-001",
                    "Status": "AUTHORISED",
                    "Total": 570.00,
                }]
            })),
        ]
        mock_request.side_effect = mock_responses

        client = XeroClient(token_file=self.token_file)
        client._last_request_time = 0  # Skip rate limiting in tests

        work_item = {
            "work_item_id": "WI-001",
            "title": "Replace faulty stop valve",
        }
        quote = {
            "labour_cost": 350.00,
            "materials_cost": 125.50,
        }
        contractor = {
            "company_name": "TestCo Plumbing",
            "email": "info@testco.com",
            "phone": "+447700900123",
        }

        invoice = client.create_invoice_from_quote(work_item, quote, contractor)

        self.assertEqual(invoice["InvoiceID"], "xero-inv-456")
        self.assertEqual(invoice["Reference"], "SF-WI-001")

        # Verify the create_invoice call had correct line items
        create_call = mock_request.call_args_list[3]
        body = create_call.kwargs.get("json", create_call[1].get("json", {}))
        line_items = body["Invoices"][0]["LineItems"]

        self.assertEqual(len(line_items), 2)
        self.assertEqual(line_items[0]["UnitAmount"], 350.00)
        self.assertIn("Labour", line_items[0]["Description"])
        self.assertEqual(line_items[1]["UnitAmount"], 125.50)
        self.assertIn("Materials", line_items[1]["Description"])

    @patch("xero_client.requests.request")
    def test_create_invoice_skips_zero_cost_line_items(self, mock_request: MagicMock) -> None:
        """Should not include line items with zero cost."""
        mock_responses = [
            MagicMock(status_code=200, json=MagicMock(return_value={"Contacts": [{"ContactID": "c1", "Name": "Co"}]})),
            MagicMock(status_code=200, json=MagicMock(return_value={"Invoices": []})),
            MagicMock(status_code=200, json=MagicMock(return_value={
                "Invoices": [{"InvoiceID": "inv-1", "Reference": "SF-WI-002", "Status": "AUTHORISED"}]
            })),
        ]
        mock_request.side_effect = mock_responses

        client = XeroClient(token_file=self.token_file)
        client._last_request_time = 0

        invoice = client.create_invoice_from_quote(
            {"work_item_id": "WI-002", "title": "Labour only job"},
            {"labour_cost": 200.00, "materials_cost": 0},
            {"company_name": "Co"},
        )

        create_call = mock_request.call_args_list[2]
        body = create_call.kwargs.get("json", create_call[1].get("json", {}))
        line_items = body["Invoices"][0]["LineItems"]
        self.assertEqual(len(line_items), 1)

    @patch("xero_client.requests.request")
    def test_create_invoice_no_line_items_raises(self, mock_request: MagicMock) -> None:
        """Should raise error when both costs are zero."""
        mock_responses = [
            MagicMock(status_code=200, json=MagicMock(return_value={"Contacts": [{"ContactID": "c1", "Name": "Co"}]})),
            MagicMock(status_code=200, json=MagicMock(return_value={"Invoices": []})),
        ]
        mock_request.side_effect = mock_responses

        client = XeroClient(token_file=self.token_file)
        client._last_request_time = 0

        with self.assertRaises(XeroApiError):
            client.create_invoice_from_quote(
                {"work_item_id": "WI-003", "title": "Empty"},
                {"labour_cost": 0, "materials_cost": 0},
                {"company_name": "Co"},
            )

    @patch("xero_client.requests.request")
    def test_duplicate_invoice_returns_existing(self, mock_request: MagicMock) -> None:
        """Should return existing invoice if reference already exists."""
        existing_invoice = {"InvoiceID": "existing-inv", "Reference": "SF-WI-004", "Status": "AUTHORISED"}
        mock_responses = [
            MagicMock(status_code=200, json=MagicMock(return_value={"Contacts": [{"ContactID": "c1", "Name": "Co"}]})),
            MagicMock(status_code=200, json=MagicMock(return_value={"Invoices": [existing_invoice]})),
        ]
        mock_request.side_effect = mock_responses

        client = XeroClient(token_file=self.token_file)
        client._last_request_time = 0

        invoice = client.create_invoice_from_quote(
            {"work_item_id": "WI-004", "title": "Dup test"},
            {"labour_cost": 100, "materials_cost": 50},
            {"company_name": "Co"},
        )

        self.assertEqual(invoice["InvoiceID"], "existing-inv")
        # Should NOT have made a POST to create a new invoice
        self.assertEqual(mock_request.call_count, 2)


class TestXeroRetryLogic(unittest.TestCase):
    """Tests for retry and error handling."""

    def setUp(self) -> None:
        self.token_dir = tempfile.mkdtemp()
        self.token_file = Path(self.token_dir) / ".xero-tokens.json"

        token_data = {
            "access_token": "test_access",
            "refresh_token": "test_refresh",
            "expires_at": time.time() + 3600,
        }
        with open(self.token_file, "w") as f:
            json.dump(token_data, f)

        self.env_patch = patch.dict(os.environ, {
            "XERO_CLIENT_ID": "test_client_id",
            "XERO_CLIENT_SECRET": "test_client_secret",
            "XERO_TENANT_ID": "test_tenant_id",
        })
        self.env_patch.start()

    def tearDown(self) -> None:
        self.env_patch.stop()

    @patch("xero_client.requests.request")
    @patch("xero_client.time.sleep")
    def test_retries_on_500_error(self, mock_sleep: MagicMock, mock_request: MagicMock) -> None:
        """Should retry on 500 errors with exponential backoff."""
        mock_request.side_effect = [
            MagicMock(status_code=500, text="Internal Server Error"),
            MagicMock(status_code=500, text="Internal Server Error"),
            MagicMock(status_code=200, json=MagicMock(return_value={"Contacts": []})),
        ]

        client = XeroClient(token_file=self.token_file)
        client._last_request_time = 0

        result = client._request("GET", "Contacts")
        self.assertEqual(mock_request.call_count, 3)
        self.assertEqual(result, {"Contacts": []})

    @patch("xero_client.requests.request")
    @patch("xero_client.time.sleep")
    def test_retries_on_429_with_retry_after(self, mock_sleep: MagicMock, mock_request: MagicMock) -> None:
        """Should respect Retry-After header on 429 responses."""
        rate_limit_response = MagicMock(
            status_code=429,
            text="Rate limit",
            headers={"Retry-After": "10"},
        )
        success_response = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"ok": True}),
        )
        mock_request.side_effect = [rate_limit_response, success_response]

        client = XeroClient(token_file=self.token_file)
        client._last_request_time = 0

        result = client._request("GET", "Invoices")

        self.assertEqual(result, {"ok": True})
        # Should have slept for at least 10 seconds (Retry-After value)
        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list if call.args]
        self.assertTrue(any(s >= 10 for s in sleep_calls))

    @patch("xero_client.requests.request")
    @patch("xero_client.time.sleep")
    def test_raises_after_max_retries(self, mock_sleep: MagicMock, mock_request: MagicMock) -> None:
        """Should raise XeroApiError after exhausting all retries."""
        mock_request.return_value = MagicMock(status_code=503, text="Service Unavailable")

        client = XeroClient(token_file=self.token_file)
        client._last_request_time = 0

        with self.assertRaises(XeroApiError) as ctx:
            client._request("GET", "Contacts")

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(mock_request.call_count, MAX_RETRIES)

    @patch("xero_client.requests.request")
    def test_does_not_retry_on_400(self, mock_request: MagicMock) -> None:
        """Should not retry on 400 Bad Request (client error)."""
        mock_request.return_value = MagicMock(status_code=400, text="Bad Request")

        client = XeroClient(token_file=self.token_file)
        client._last_request_time = 0

        with self.assertRaises(XeroApiError) as ctx:
            client._request("POST", "Invoices", json_body={"bad": "data"})

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(mock_request.call_count, 1)


class TestXeroContactManagement(unittest.TestCase):
    """Tests for contact creation and lookup."""

    def setUp(self) -> None:
        self.token_dir = tempfile.mkdtemp()
        self.token_file = Path(self.token_dir) / ".xero-tokens.json"

        token_data = {
            "access_token": "test_access",
            "refresh_token": "test_refresh",
            "expires_at": time.time() + 3600,
        }
        with open(self.token_file, "w") as f:
            json.dump(token_data, f)

        self.env_patch = patch.dict(os.environ, {
            "XERO_CLIENT_ID": "test_client_id",
            "XERO_CLIENT_SECRET": "test_client_secret",
            "XERO_TENANT_ID": "test_tenant_id",
        })
        self.env_patch.start()

    def tearDown(self) -> None:
        self.env_patch.stop()

    @patch("xero_client.requests.request")
    def test_create_contact_with_full_details(self, mock_request: MagicMock) -> None:
        """Should create contact with all fields mapped correctly."""
        mock_request.side_effect = [
            MagicMock(status_code=200, json=MagicMock(return_value={"Contacts": []})),
            MagicMock(status_code=200, json=MagicMock(return_value={
                "Contacts": [{"ContactID": "new-contact", "Name": "SafeGas Ltd"}]
            })),
        ]

        client = XeroClient(token_file=self.token_file)
        client._last_request_time = 0

        contractor = {
            "company_name": "SafeGas Ltd",
            "email": "billing@safegas.co.uk",
            "phone": "+447700900456",
            "vat_number": "GB123456789",
            "address_line_1": "42 Gas Works Lane",
            "city": "London",
            "postcode": "EC2M 7PP",
        }

        contact = client.create_contact(contractor)

        self.assertEqual(contact["ContactID"], "new-contact")

        create_call = mock_request.call_args_list[1]
        body = create_call.kwargs.get("json", create_call[1].get("json", {}))
        contact_payload = body["Contacts"][0]

        self.assertEqual(contact_payload["Name"], "SafeGas Ltd")
        self.assertEqual(contact_payload["EmailAddress"], "billing@safegas.co.uk")
        self.assertTrue(contact_payload["IsSupplier"])
        self.assertFalse(contact_payload["IsCustomer"])

    @patch("xero_client.requests.request")
    def test_create_contact_returns_existing(self, mock_request: MagicMock) -> None:
        """Should return existing contact without creating a duplicate."""
        existing = {"ContactID": "existing-contact", "Name": "TestCo"}
        mock_request.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"Contacts": [existing]}),
        )

        client = XeroClient(token_file=self.token_file)
        client._last_request_time = 0

        contact = client.create_contact({"company_name": "TestCo"})

        self.assertEqual(contact["ContactID"], "existing-contact")
        self.assertEqual(mock_request.call_count, 1)  # Only the search, no create


if __name__ == "__main__":
    unittest.main()
