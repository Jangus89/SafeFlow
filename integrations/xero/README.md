# SafeFlow Xero Integration

Synchronises accepted quotes and payment records from SafeFlow to Xero for invoicing.

## Setup

### 1. Register a Xero App

1. Go to [developer.xero.com](https://developer.xero.com/app/manage) and create a new app
2. Select **Web App** as the app type
3. Set the redirect URI to: `https://app.safeflow.io/xero/callback`
4. Note the **Client ID** and generate a **Client Secret**

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
XERO_CLIENT_ID=your_xero_client_id
XERO_CLIENT_SECRET=your_xero_client_secret
XERO_TENANT_ID=your_xero_tenant_id
XERO_REDIRECT_URI=https://app.safeflow.io/xero/callback
```

### 3. Initial OAuth2 Authorisation

First-time setup requires a browser-based OAuth2 flow:

```bash
# Generate the authorisation URL
python -c "
from urllib.parse import urlencode
params = urlencode({
    'response_type': 'code',
    'client_id': 'YOUR_CLIENT_ID',
    'redirect_uri': 'https://app.safeflow.io/xero/callback',
    'scope': 'openid profile email accounting.transactions accounting.contacts offline_access',
})
print(f'https://login.xero.com/identity/connect/authorize?{params}')
"
```

After authorising, exchange the callback code:

```python
from integrations.xero.xero_client import XeroClient

client = XeroClient()
client.exchange_auth_code('AUTH_CODE_FROM_CALLBACK', 'https://app.safeflow.io/xero/callback')
```

Tokens are stored in `integrations/xero/.xero-tokens.json` (auto-refreshed).

### 4. Running the Sync

```bash
# Preview what would be synced
python integrations/xero/xero_sync.py --dry-run

# Sync all pending payments
python integrations/xero/xero_sync.py

# Sync a specific work item
python integrations/xero/xero_sync.py --work-item WI-1042

# Limit the batch size
python integrations/xero/xero_sync.py --limit 10

# JSON output for CI/monitoring
python integrations/xero/xero_sync.py --json
```

### 5. Running Tests

```bash
python -m pytest integrations/xero/tests/ -v
```

## How It Works

1. Queries Airtable `Payments` table for records with `status=PENDING` and no `xero_invoice_id`
2. For each payment, retrieves the linked Work_Item, Quote, and Contractor
3. Creates or finds the Xero Contact (contractor)
4. Creates a Xero Accounts Payable invoice with line items for labour and materials
5. Updates the Airtable Payment record with the Xero invoice ID and sync status

## Invoice Mapping

| SafeFlow Field | Xero Field |
|---|---|
| Work_Items.title | LineItem Description |
| Quotes.labour_cost | LineItem (Labour) UnitAmount |
| Quotes.materials_cost | LineItem (Materials) UnitAmount |
| Contractors.company_name | Contact Name |
| Work_Items.work_item_id | Invoice Reference (SF-{id}) |

- VAT: 20% (standard rate)
- Payment terms: NET 30
- Currency: GBP
- Invoice type: ACCPAY (Accounts Payable)

## Error Handling

- Retries on 429, 500, 502, 503, 504 with exponential backoff (max 3 attempts)
- Rate limit: 60 API calls/minute
- Duplicate detection: checks for existing invoice by reference before creating
- Failed syncs are recorded in Airtable (`xero_sync_status=FAILED`, `xero_sync_error`)
