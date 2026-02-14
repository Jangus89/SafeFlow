# WhatsApp Message Templates

## Overview

WhatsApp Business API requires pre-approved templates for outbound messages sent outside the 24-hour conversation window. Templates must be submitted via 360dialog and approved by Meta.

## Template Registry

### 1. `maintenance_status_update`

**Category**: Utility
**Language**: English (en)

```
Hi {{1}},

Your maintenance request {{2}} has been updated.

New status: {{3}}

{{4}}

If you have any questions, simply reply to this message.
```

**Parameters**:
1. `tenant_name` - Tenant's first name
2. `reference` - Maintenance reference number (e.g., MR-20250214-1234)
3. `new_status` - New status value
4. `details` - Additional context about the update

---

### 2. `urgent_maintenance_alert`

**Category**: Utility
**Language**: English (en)

```
URGENT MAINTENANCE ALERT

Reference: {{1}}
Category: {{2}}
Tenant: {{3}}
Property: {{4}}

This request requires immediate attention. Please review and respond.
```

**Parameters**:
1. `reference` - Maintenance reference number
2. `category` - Maintenance category
3. `tenant_name` - Tenant's name
4. `property_name` - Property name/address

---

### 3. `escalation_notice`

**Category**: Utility
**Language**: English (en)

```
ESCALATION NOTICE

Maintenance request {{1}} ({{2}}) requires your attention.

Issue: {{3}}

Escalation level: {{4}}
Tenant: {{5}}

This request has not been resolved within the expected timeframe. Please take action.
```

**Parameters**:
1. `reference` - Maintenance reference number
2. `category` - Maintenance category
3. `description` - Issue description
4. `escalation_label` - Human-readable escalation level
5. `tenant_name` - Tenant's name

---

### 4. `rent_payment_reminder`

**Category**: Utility
**Language**: English (en)

```
Hi {{1}},

This is a friendly reminder that your rent payment of {{2}} is due on {{3}}.

If you've already made your payment, please disregard this message.

Questions? Reply to this message.
```

**Parameters**:
1. `tenant_name` - Tenant's first name
2. `amount` - Rent amount (formatted with currency)
3. `due_date` - Payment due date

---

### 5. `welcome_new_tenant`

**Category**: Utility
**Language**: English (en)

```
Welcome to SafeFlow, {{1}}!

You can use this WhatsApp number to:
- Report maintenance issues
- Ask about your rent
- Get general property information

Simply send a message describing what you need, and we'll help you out.
```

**Parameters**:
1. `tenant_name` - Tenant's first name

---

## Submission Process

1. Draft template in this file
2. Review for compliance with Meta's commerce policy
3. Submit via 360dialog Hub → Templates
4. Track approval status in Airtable "WhatsApp Templates" table
5. Update `360dialog Template ID` field once approved
6. Reference template name in Make.com scenarios

## Meta Template Rules

- No promotional content in Utility templates
- Must include opt-out information for Marketing templates
- Variable parameters cannot be the entire message body
- Templates rejected for: misleading content, prohibited content, or poor formatting
- Approval typically within 24-48 hours, sometimes up to 72 hours
