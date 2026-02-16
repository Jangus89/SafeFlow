#!/usr/bin/env python3
"""Xero API client for SafeFlow invoice and contact management.

Handles OAuth2 token lifecycle, invoice creation from accepted quotes,
contact management, and payment status synchronisation.

Usage:
    from integrations.xero.xero_client import XeroClient

    client = XeroClient()
    invoice = client.create_invoice_from_quote(work_item, quote, contractor)
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: requests package required. Run: pip install requests")
    sys.exit(1)


# ─── Structured Logging ─────────────────────────────────────────────────────

logger = logging.getLogger("safeflow.xero")

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            json.dumps({
                "timestamp": "%(asctime)s",
                "level": "%(levelname)s",
                "logger": "%(name)s",
                "message": "%(message)s",
            })
        )
    )
    logger.addHandler(handler)
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


# ─── Constants ───────────────────────────────────────────────────────────────

XERO_AUTH_URL = "https://identity.xero.com/connect/token"
XERO_API_BASE = "https://api.xero.com/api.xro/2.0"
XERO_CONNECTIONS_URL = "https://api.xero.com/connections"

RATE_LIMIT_CALLS_PER_MINUTE = 60
RATE_LIMIT_DELAY = 60.0 / RATE_LIMIT_CALLS_PER_MINUTE

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

VAT_RATE = 0.20
DEFAULT_PAYMENT_TERMS = 30  # NET 30
DEFAULT_ACCOUNT_CODE = "200"  # Sales account code

TOKEN_FILE = Path(__file__).parent / ".xero-tokens.json"


# ─── Exceptions ──────────────────────────────────────────────────────────────


class XeroApiError(Exception):
    """Raised when a Xero API call fails after all retries."""

    def __init__(self, message: str, status_code: int | None = None, response_body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class XeroTokenError(Exception):
    """Raised when OAuth2 token operations fail."""


# ─── Client ──────────────────────────────────────────────────────────────────


class XeroClient:
    """Xero API client with OAuth2 token management and retry logic."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        tenant_id: str | None = None,
        token_file: Path | None = None,
    ) -> None:
        self.client_id = client_id or os.environ.get("XERO_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("XERO_CLIENT_SECRET", "")
        self.tenant_id = tenant_id or os.environ.get("XERO_TENANT_ID", "")
        self.token_file = token_file or TOKEN_FILE
        self._access_token: str = ""
        self._refresh_token: str = ""
        self._token_expires_at: float = 0
        self._last_request_time: float = 0

        if not self.client_id or not self.client_secret:
            raise XeroTokenError(
                "XERO_CLIENT_ID and XERO_CLIENT_SECRET environment variables are required"
            )

        self._load_tokens()

    # ── Token Management ─────────────────────────────────────────────────────

    def _load_tokens(self) -> None:
        """Load stored OAuth2 tokens from file."""
        if not self.token_file.exists():
            logger.warning("No token file found at %s - OAuth2 authorisation required", self.token_file)
            return

        try:
            with open(self.token_file) as f:
                data = json.load(f)
            self._access_token = data.get("access_token", "")
            self._refresh_token = data.get("refresh_token", "")
            self._token_expires_at = data.get("expires_at", 0)
            logger.info("Loaded Xero tokens from %s", self.token_file)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load token file: %s", e)

    def _save_tokens(self) -> None:
        """Persist OAuth2 tokens to file."""
        data = {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "expires_at": self._token_expires_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with open(self.token_file, "w") as f:
                json.dump(data, f, indent=2)
            self.token_file.chmod(0o600)
            logger.info("Saved Xero tokens to %s", self.token_file)
        except OSError as e:
            logger.error("Failed to save token file: %s", e)

    def _token_is_valid(self) -> bool:
        """Check if the current access token is still valid (with 60s buffer)."""
        return bool(self._access_token) and time.time() < (self._token_expires_at - 60)

    def refresh_access_token(self) -> None:
        """Refresh the OAuth2 access token using the refresh token."""
        if not self._refresh_token:
            raise XeroTokenError("No refresh token available. Run initial OAuth2 authorisation flow.")

        logger.info("Refreshing Xero access token")
        try:
            response = requests.post(
                XERO_AUTH_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            self._access_token = data["access_token"]
            self._refresh_token = data.get("refresh_token", self._refresh_token)
            self._token_expires_at = time.time() + data.get("expires_in", 1800)
            self._save_tokens()
            logger.info("Xero access token refreshed successfully")

        except requests.exceptions.RequestException as e:
            raise XeroTokenError(f"Failed to refresh Xero token: {e}") from e

    def _ensure_token(self) -> str:
        """Ensure we have a valid access token, refreshing if needed."""
        if not self._token_is_valid():
            self.refresh_access_token()
        return self._access_token

    def exchange_auth_code(self, auth_code: str, redirect_uri: str) -> None:
        """Exchange an authorisation code for access and refresh tokens."""
        logger.info("Exchanging Xero authorisation code for tokens")
        response = requests.post(
            XERO_AUTH_URL,
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        self._access_token = data["access_token"]
        self._refresh_token = data["refresh_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 1800)
        self._save_tokens()
        logger.info("Xero authorisation complete")

    # ── HTTP with Retry ──────────────────────────────────────────────────────

    def _rate_limit_wait(self) -> None:
        """Enforce rate limit of 60 calls/minute."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated request to the Xero API with retry logic."""
        url = f"{XERO_API_BASE}/{path}"
        token = self._ensure_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Xero-Tenant-Id": self.tenant_id,
        }

        for attempt in range(1, MAX_RETRIES + 1):
            self._rate_limit_wait()

            try:
                response = requests.request(
                    method, url, headers=headers, json=json_body, params=params, timeout=30
                )

                if response.status_code < 400:
                    return response.json()

                if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", str(int(delay))))
                        delay = max(delay, retry_after)
                    logger.warning(
                        "Xero API %s %s returned %d, retrying in %.1fs (attempt %d/%d)",
                        method, path, response.status_code, delay, attempt, MAX_RETRIES,
                    )
                    time.sleep(delay)
                    continue

                raise XeroApiError(
                    f"Xero API error: {response.status_code} {response.text}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            except requests.exceptions.ConnectionError as e:
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning("Connection error, retrying in %.1fs: %s", delay, e)
                    time.sleep(delay)
                    continue
                raise XeroApiError(f"Connection failed after {MAX_RETRIES} attempts: {e}") from e

        raise XeroApiError(f"Request to {url} failed after {MAX_RETRIES} attempts")

    # ── Contacts ─────────────────────────────────────────────────────────────

    def find_contact_by_name(self, name: str) -> dict[str, Any] | None:
        """Search for an existing Xero contact by name."""
        result = self._request("GET", "Contacts", params={"where": f'Name=="{name}"'})
        contacts = result.get("Contacts", [])
        return contacts[0] if contacts else None

    def create_contact(self, contractor: dict[str, Any]) -> dict[str, Any]:
        """Create a Xero contact from a SafeFlow contractor record."""
        name = contractor.get("company_name", contractor.get("name", "Unknown"))

        existing = self.find_contact_by_name(name)
        if existing:
            logger.info("Xero contact already exists for %s: %s", name, existing["ContactID"])
            return existing

        payload = {
            "Name": name,
            "EmailAddress": contractor.get("email", ""),
            "Phones": [],
            "IsSupplier": True,
            "IsCustomer": False,
            "ContactStatus": "ACTIVE",
            "TaxNumber": contractor.get("vat_number", ""),
        }

        if contractor.get("phone"):
            payload["Phones"].append({
                "PhoneType": "DEFAULT",
                "PhoneNumber": contractor["phone"],
            })

        if contractor.get("address_line_1"):
            payload["Addresses"] = [{
                "AddressType": "STREET",
                "AddressLine1": contractor.get("address_line_1", ""),
                "City": contractor.get("city", ""),
                "PostalCode": contractor.get("postcode", ""),
                "Country": "GB",
            }]

        result = self._request("POST", "Contacts", json_body={"Contacts": [payload]})
        contact = result["Contacts"][0]
        logger.info("Created Xero contact: %s (%s)", name, contact["ContactID"])
        return contact

    # ── Invoices ─────────────────────────────────────────────────────────────

    def find_invoice_by_reference(self, reference: str) -> dict[str, Any] | None:
        """Find an existing invoice by SafeFlow reference to prevent duplicates."""
        result = self._request(
            "GET", "Invoices", params={"where": f'Reference=="{reference}"'}
        )
        invoices = result.get("Invoices", [])
        return invoices[0] if invoices else None

    def create_invoice_from_quote(
        self,
        work_item: dict[str, Any],
        quote: dict[str, Any],
        contractor: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a Xero Accounts Payable invoice from an accepted SafeFlow quote.

        Args:
            work_item: Airtable Work_Items record fields
            quote: Airtable Quotes record fields (status must be ACCEPTED)
            contractor: Airtable Contractors record fields

        Returns:
            Xero Invoice object
        """
        work_item_id = work_item.get("work_item_id", work_item.get("id", "unknown"))
        reference = f"SF-{work_item_id}"

        existing = self.find_invoice_by_reference(reference)
        if existing:
            logger.info("Invoice already exists for %s: %s", reference, existing["InvoiceID"])
            return existing

        contact = self.create_contact(contractor)

        line_items = []

        labour_cost = quote.get("labour_cost", 0)
        if labour_cost > 0:
            line_items.append({
                "Description": f"Labour - {work_item.get('title', 'Facilities work')}",
                "Quantity": 1,
                "UnitAmount": labour_cost,
                "AccountCode": DEFAULT_ACCOUNT_CODE,
                "TaxType": "OUTPUT2",  # 20% VAT
            })

        materials_cost = quote.get("materials_cost", 0)
        if materials_cost > 0:
            line_items.append({
                "Description": f"Materials - {work_item.get('title', 'Facilities work')}",
                "Quantity": 1,
                "UnitAmount": materials_cost,
                "AccountCode": DEFAULT_ACCOUNT_CODE,
                "TaxType": "OUTPUT2",
            })

        if not line_items:
            raise XeroApiError("Cannot create invoice with no line items")

        due_date = datetime.now(timezone.utc)
        due_date = due_date.replace(day=due_date.day)  # Current date

        invoice_payload = {
            "Type": "ACCPAY",  # Accounts Payable (bill from contractor)
            "Contact": {"ContactID": contact["ContactID"]},
            "LineItems": line_items,
            "Date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "DueDate": (
                datetime.now(timezone.utc).replace(
                    day=min(datetime.now(timezone.utc).day + DEFAULT_PAYMENT_TERMS, 28)
                )
            ).strftime("%Y-%m-%d"),
            "Reference": reference,
            "Status": "AUTHORISED",
            "LineAmountTypes": "Exclusive",  # Amounts are ex-VAT
            "CurrencyCode": "GBP",
        }

        result = self._request("POST", "Invoices", json_body={"Invoices": [invoice_payload]})
        invoice = result["Invoices"][0]

        logger.info(
            "Created Xero invoice %s for %s (total: £%.2f + VAT)",
            invoice["InvoiceID"],
            reference,
            labour_cost + materials_cost,
        )
        return invoice

    # ── Invoice Status ───────────────────────────────────────────────────────

    def get_invoice(self, invoice_id: str) -> dict[str, Any]:
        """Get a Xero invoice by ID."""
        result = self._request("GET", f"Invoices/{invoice_id}")
        invoices = result.get("Invoices", [])
        if not invoices:
            raise XeroApiError(f"Invoice not found: {invoice_id}", status_code=404)
        return invoices[0]

    def get_invoice_status(self, invoice_id: str) -> str:
        """Get the current status of a Xero invoice."""
        invoice = self.get_invoice(invoice_id)
        return invoice.get("Status", "UNKNOWN")

    def void_invoice(self, invoice_id: str) -> dict[str, Any]:
        """Void a Xero invoice."""
        result = self._request(
            "POST",
            f"Invoices/{invoice_id}",
            json_body={"Invoices": [{"InvoiceID": invoice_id, "Status": "VOIDED"}]},
        )
        logger.info("Voided Xero invoice: %s", invoice_id)
        return result["Invoices"][0]
