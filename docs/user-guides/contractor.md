# Contractor User Guide

## Introduction

This guide is for external contractors who provide specialist trade services through the SafeFlow facilities management platform. SafeFlow connects you with property managers managing UK commercial properties. You receive job requests, submit quotes, perform work, and manage invoicing -- all through WhatsApp.

---

## Onboarding

### Registration Process

To become a SafeFlow contractor, you need to provide:

1. **Company details**: Company name, registered address, Companies House number (if applicable).
2. **Primary contact**: Name, email, phone number, WhatsApp number (must be +44 format).
3. **Trade disciplines**: Your areas of expertise (Plumbing, Electrical, Gas Safe, HVAC, Lift Engineer, Fire Safety, General Maintenance, Specialist).
4. **Coverage area**: UK postcode prefixes you can cover (e.g., SW, EC, SE1, W1, E14).
5. **Certifications**: All current trade certifications with registration numbers and expiry dates.
6. **Commercial terms**: Hourly rate, callout fee, payment terms preference (NET_7, NET_14, NET_30, NET_60).
7. **Emergency availability**: Whether you are available for out-of-hours emergency callouts.

### Required Certifications

Depending on your trade disciplines, you must provide:

| Discipline | Required Certification | Registration Body |
|-----------|----------------------|-------------------|
| GAS_SAFE | Gas Safe Register number | [Gas Safe Register](https://www.gassaferegister.co.uk/) |
| ELECTRICAL | NICEIC or NAPIT registration | [NICEIC](https://www.niceic.com/) / [NAPIT](https://www.napit.org.uk/) |
| HVAC (refrigerant) | F-Gas certification | [Refcom](https://www.refcom.org.uk/) |
| LIFT_ENGINEER | SAFed member / LOLER competent person | [SAFed](https://www.safed.co.uk/) |
| SPECIALIST (asbestos) | Licensed asbestos contractor | [HSE](https://www.hse.gov.uk/) |

**Important**: You must keep your certifications current. Expired certifications will prevent new jobs from being assigned to you. Notify your property manager contact when you renew certifications so your records can be updated.

### Xero Setup

SafeFlow processes invoices through Xero. During onboarding:

1. Your company will be set up as a contact in the property manager's Xero organisation.
2. Your agreed payment terms will be configured.
3. Invoices will be created automatically when you complete work -- you do not need a Xero account yourself.

---

## Receiving RFQs (Requests for Quote)

When a maintenance job requires your trade discipline in your coverage area, you will receive an RFQ via WhatsApp:

> **Request for Quote -- SF-1085**
>
> **Issue**: Air conditioning unit blowing warm air -- 4th floor office
> **Location**: Canary Wharf Tower, 4th Floor, Main Office
> **Site**: One Canada Square, E14 5AB
> **Urgency**: URGENT
> **Required Discipline**: HVAC
>
> **Description**: Split system AC unit in the main open-plan office is blowing warm air. Unit is a Daikin FTXS50 wall-mounted split. Temperature in the office currently 28C. Approximately 40 staff affected.
>
> **Please submit your quote by replying with QUOTE followed by your pricing.**
>
> **SLA**: Response within 24 hours

---

## Submitting Quotes

To submit a quote, reply with the `QUOTE` command followed by your pricing details:

### Basic Quote Format

> QUOTE SF-1085 Labour: 280 Materials: 150 Lead time: 2 days

The system will parse this as:
- Labour: GBP 280.00 (excl. VAT)
- Materials: GBP 150.00 (excl. VAT)
- Total (excl. VAT): GBP 430.00
- VAT (20%): GBP 86.00
- Total (incl. VAT): GBP 516.00
- Lead time: 2 working days

### Detailed Quote Format

For more complex jobs, you can include scope and exclusions:

> QUOTE SF-1085
> Labour: 280
> Materials: 150
> Lead time: 2 days
> Scope: Diagnose and repair Daikin FTXS50 split unit. Includes refrigerant top-up if required (up to 1kg R32). Electrical checks on outdoor unit.
> Exclusions: Full regassing beyond 1kg. Replacement of compressor or PCB if faulty. Scaffolding or access equipment.

### Quote Tips

1. **Be specific on scope** -- clearly state what is included to avoid disputes later.
2. **List exclusions** -- if there is a risk of additional work, state what is not included.
3. **Be realistic on lead time** -- the property manager will factor this into their decision.
4. **Price competitively** -- your quote will be compared with others. Consistently high quotes reduce your assignment frequency.
5. **VAT**: All prices should be **excluding VAT**. The system automatically calculates 20% VAT.

---

## Accepting Work

If your quote is accepted, you will receive a confirmation:

> **Quote Accepted -- SF-1085**
>
> Your quote of GBP 430.00 (excl. VAT) has been accepted.
>
> **Please confirm you can proceed by replying ACCEPT.**
>
> **SLA Deadline**: 17/02/2026 14:00
>
> [ACCEPT] [REJECT]

Reply with `ACCEPT` to confirm you will carry out the work.

If your circumstances have changed and you can no longer do the work, reply with `REJECT` and a reason:

> REJECT SF-1085 Engineer unavailable due to illness. Available again from Monday.

---

## Completing Jobs

### During the Job

| Command | When | Example |
|---------|------|---------|
| `ACCEPT` | You confirm you will do the job | "ACCEPT SF-1085" |
| `START` | You arrive on site and begin work | "START SF-1085" |
| `HOLD` | You need to pause (parts, access, etc.) | "HOLD SF-1085 Waiting for replacement part -- 3 day lead time from Daikin" |
| `DONE` | You have completed the work | "DONE SF-1085 Refrigerant topped up, unit cooling correctly. Filters cleaned." |

### Completion Evidence

When marking a job as DONE, you should:

1. **Send a photo** of the completed work via WhatsApp.
2. **Include completion notes** describing what was done.
3. **Attach any certificates** (Gas Safe certificate, EICR, F-Gas log, etc.) as document attachments.

Example:

> DONE SF-1085 Diagnosed low refrigerant charge on Daikin FTXS50. Topped up with 0.6kg R32. Checked for leaks with electronic detector -- none found. Unit now cooling to setpoint 22C. Filters removed, cleaned, and refitted. Recommend annual service to prevent recurrence.
>
> [Photo: AC unit running with temperature display showing 22C]

### What Happens After DONE

1. The tenant is asked to confirm the work is satisfactory.
2. If the tenant confirms, the job moves to PAYMENT_PENDING.
3. A purchase invoice is automatically created in Xero for the quoted amount.
4. You will be paid according to your agreed payment terms.

If the tenant is not satisfied, the property manager will contact you to discuss remedial work.

---

## Invoicing via Xero

SafeFlow automates the invoicing process. You do **not** need to submit a separate invoice.

### How It Works

1. When your job is marked as complete and the tenant confirms, a **draft purchase invoice** is created in the property manager's Xero account.
2. The invoice details:
   - **Reference**: SF-{work_item_id} (e.g., SF-1085)
   - **Amount**: Your quoted amount (labour + materials)
   - **VAT**: 20% standard rate
   - **Due date**: Based on your agreed payment terms
3. The property manager reviews and approves the invoice in Xero.
4. Payment is made according to your agreed terms.

### Invoice Queries

If you have queries about an invoice or payment:
- Send a WhatsApp message referencing the job: "Invoice query for SF-1085 -- payment not received after 30 days"
- The property manager will investigate and respond.

### Keeping Your Bank Details Current

Ensure your bank details are up to date in the property manager's Xero records. Contact the property manager directly if your banking details change.

---

## Certifications

### Keeping Certifications Current

Your certifications are checked automatically when jobs are assigned. If a certification expires:

1. You will **stop receiving new RFQs** for the affected discipline.
2. You will receive a WhatsApp notification reminding you to renew.
3. Once renewed, send your updated certificate number and expiry date to the property manager.

### Certification Requirements by Job Type

| Job Type | Certification Checked | Consequence if Expired |
|----------|----------------------|----------------------|
| Gas work | Gas Safe Register | Cannot be assigned gas jobs. Legal requirement. |
| Electrical (notifiable) | NICEIC / NAPIT | Cannot be assigned complex electrical jobs. |
| Refrigerant handling | F-Gas | Cannot handle refrigerants. |
| Lift work | LOLER competent person | Cannot be assigned lift jobs. |
| Asbestos | HSE licensed contractor | Cannot be assigned asbestos work. |

---

## WhatsApp Command Reference

| Command | Format | Example |
|---------|--------|---------|
| **QUOTE** | `QUOTE SF-XXXX Labour: N Materials: N Lead time: N days` | "QUOTE SF-1085 Labour: 280 Materials: 150 Lead time: 2 days" |
| **ACCEPT** | `ACCEPT SF-XXXX` | "ACCEPT SF-1085" |
| **START** | `START SF-XXXX` | "START SF-1085" |
| **DONE** | `DONE SF-XXXX [completion notes]` | "DONE SF-1085 Refrigerant topped up, unit cooling" |
| **HOLD** | `HOLD SF-XXXX [reason]` | "HOLD SF-1085 Waiting for replacement part" |
| **REJECT** | `REJECT SF-XXXX [reason]` | "REJECT SF-1085 Not available this week" |

---

## Frequently Asked Questions

### How quickly do I need to respond to an RFQ?

- **EMERGENCY**: Respond immediately. These are safety-critical and time-sensitive.
- **URGENT**: Within 2 hours.
- **STANDARD**: Within 24 hours.
- **SCHEDULED**: Within 48 hours.

If you do not respond within the expected time, the RFQ may be sent to another contractor.

### Can I adjust my quote after submitting?

Yes, send a new QUOTE message with the updated figures. The latest quote replaces the previous one, provided the property manager has not already accepted it.

### What if I discover additional work is needed on site?

Contact the property manager via WhatsApp:

> SF-1085 Additional work found: condensate drain blocked, causing water damage to ceiling tile below. Recommend replacing drain line and damaged tile. Additional cost: Labour GBP 120, Materials GBP 45. Please advise.

Wait for approval before proceeding with additional work.

### What if the tenant is not available for access?

Send a HOLD command with the reason:

> HOLD SF-1085 Arrived on site at 10:00. No access to 4th floor -- security pass required. Contacted building management, awaiting response.

The property manager will arrange access and notify you.

### How do I get paid?

Payment is processed automatically through Xero once the job is verified and closed:

1. You complete the work (DONE).
2. The tenant confirms satisfaction.
3. A Xero invoice is created automatically at your quoted amount.
4. The property manager approves the invoice.
5. Payment is made according to your agreed terms (NET_7, NET_14, NET_30, or NET_60).

### How is my contractor rating calculated?

Your rating (1-5 stars) is based on:
- **Quality**: Tenant satisfaction and rework rate.
- **Timeliness**: Percentage of jobs completed within SLA.
- **Communication**: Responsiveness to RFQs and updates during work.

Higher-rated contractors are prioritised for job assignments.
