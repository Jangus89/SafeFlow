# Engineer User Guide

## Introduction

This guide is for internal engineers and maintenance staff who receive and manage work assignments through SafeFlow via WhatsApp. All your interactions with SafeFlow happen through WhatsApp messages -- you do not need to log in to any other system.

When a maintenance issue is reported by a tenant, SafeFlow automatically triages the request, determines the required trade discipline, and assigns it to the most appropriate engineer based on your skills, availability, and location. You receive the assignment as a WhatsApp message with all the details you need.

---

## Receiving Assignments

When a work item is assigned to you, you will receive a WhatsApp message like this:

> **New Job Assignment -- SF-1042**
>
> **Issue**: Dripping tap in second floor ladies WC
> **Location**: Building B, Second Floor, Ladies WC
> **Site**: Meridian House, 45 Cheapside, EC2V 6AE
> **Urgency**: STANDARD
> **SLA Deadline**: 18/02/2026 14:00
>
> **Description**: Persistent dripping tap in the ladies toilet on the second floor. Ongoing for several days. No water damage reported.
>
> **Required Discipline**: PLUMBING
>
> [ACCEPT] [REJECT]

You must respond promptly. The system expects a response within the timeframes below, depending on the urgency level:

| Urgency | Expected Response | SLA Resolution |
|---------|------------------|----------------|
| EMERGENCY | Immediately | 4 hours |
| URGENT | Within 30 minutes | 24 hours |
| STANDARD | Within 2 hours | 72 hours |
| SCHEDULED | Within 24 hours | 2 weeks |

---

## WhatsApp Commands

You interact with SafeFlow by sending simple commands via WhatsApp. Commands are case-insensitive and can be sent with or without the job reference.

### Core Commands

| Command | When to Use | Example |
|---------|-------------|---------|
| **ACCEPT** | You are taking on the job | "ACCEPT" or "ACCEPT SF-1042" |
| **START** | You have arrived on site and begun work | "START" or "START SF-1042" |
| **DONE** | You have completed the work | "DONE" or "DONE SF-1042" |
| **HOLD** | You need to pause (awaiting parts, access, etc.) | "HOLD SF-1042 Waiting for replacement valve" |
| **REJECT** | You cannot take this job | "REJECT SF-1042 On another job until Thursday" |

### Command Details

#### ACCEPT

Send `ACCEPT` to confirm you are taking on the assigned job. The system will:
- Update the work item to IN_PROGRESS state.
- Notify the tenant that an engineer has been assigned and is on the way.
- Start the SLA resolution clock.

**Tip**: If you have multiple jobs assigned, include the job reference: `ACCEPT SF-1042`.

#### START

Send `START` when you arrive on site and begin work. This:
- Records the start time for reporting purposes.
- Sends the tenant an update that work is underway.

#### DONE

Send `DONE` when you have completed the work. Best practice: **send a photo of the completed work** along with your DONE message.

Example:
> DONE SF-1042 Replaced washer on hot tap. Tested, no further drip.

You can also send a photo in the same message or as a follow-up message. The system will store the photo as completion evidence.

After sending DONE:
- The tenant will be asked to confirm the work is satisfactory.
- Once confirmed, the job moves to CLOSED.

#### HOLD

Send `HOLD` when you need to pause work. Always include a reason:

> HOLD SF-1042 Need to order a replacement isolation valve, 2-day lead time

The system will:
- Move the job to ON_HOLD state.
- Notify the property manager.
- The SLA clock pauses while on hold.

When you are ready to resume, you will receive a new notification to continue.

#### REJECT

Send `REJECT` if you cannot take on a job. Always include a reason so the system can reassign:

> REJECT SF-1042 I'm on annual leave until Monday

The system will:
- Return the job to the assignment pool.
- Attempt to assign it to another engineer.

---

## Uploading Evidence

Photographic evidence is important for verifying completed work and resolving disputes. You can upload evidence at any point during a job by sending a photo via WhatsApp.

### When to Upload Photos

| Situation | Why |
|-----------|-----|
| **Before starting** | Document the issue as found (useful for disputes) |
| **During work** | Record hidden damage or unexpected findings |
| **On completion** | Prove the work has been done to standard |
| **Certifications** | Gas Safe certificate, EICR, or other compliance documents |

### How to Upload

Simply send a photo in the WhatsApp chat with SafeFlow. Include a caption describing what the photo shows:

> [Photo] Completed tap replacement. New washer fitted, no leak.

Or:

> [Photo] Before photo -- corroded isolation valve causing leak.

The system automatically associates photos with your current active job. If you have multiple jobs, include the reference:

> [Photo] SF-1042 Completed work -- new valve installed.

---

## Handling Multiple Jobs

If you have more than one job assigned, you must include the job reference (SF-XXXX) in your commands so the system knows which job you are updating.

### Checking Your Active Jobs

Send `STATUS` to receive a summary of your currently assigned jobs:

> **Your Active Jobs**
>
> SF-1042 -- Dripping tap, Meridian House 2F -- IN_PROGRESS
> SF-1055 -- Broken door handle, Crown Court GF -- ASSIGNED
> SF-1061 -- Light switch fault, Ashton Gate 1F -- ASSIGNED

### Working Multiple Jobs

1. Accept each job individually: `ACCEPT SF-1055`
2. Start work on the current job: `START SF-1042`
3. Complete it: `DONE SF-1042 Fixed`
4. Move to the next: `START SF-1055`

**Important**: Only send `START` for the job you are physically working on. This ensures accurate time tracking.

---

## Emergency Jobs

Emergency jobs require immediate response. You will receive an emergency notification like this:

> **EMERGENCY JOB -- SF-1070**
>
> **Issue**: Water flooding from burst pipe
> **Location**: Ashton Gate, Ground Floor, Server Room
> **Site**: Ashton Gate Business Park, BS3 2HQ
> **SLA Deadline**: 15/02/2026 16:00 (4 hours)
>
> **IMMEDIATE RESPONSE REQUIRED**
>
> [ACCEPT] [REJECT]

For emergency jobs:
- **ACCEPT immediately** if you can attend.
- **REJECT immediately** if you cannot, so the system can reassign without delay.
- Do not wait -- every minute counts against the SLA.

If the emergency involves gas, electrical fire, structural collapse, or trapped persons, ensure the appropriate emergency services have been called (999 or 0800 111 999 for gas).

---

## Common Scenarios

### Arriving On Site But Cannot Access

If you arrive but cannot gain access to the area:

> HOLD SF-1042 On site but unit is locked. No one available to provide access. Tenant not responding.

The system will:
- Notify the property manager.
- Pause the SLA clock.
- The manager will arrange access and notify you when ready.

### Discovering Additional Work Needed

If you find additional issues during a job:

1. Complete the original job as normal (`DONE SF-1042`).
2. Report the additional issue as a new message:

> Found corroded pipework behind the wall panel at Meridian House, 2nd floor ladies WC. Needs a plumber to replace a 2m section of copper pipe. Separate job from SF-1042.

The system will create a new work item for the additional work.

### Job Requires a Different Trade

If the job requires a different specialist (e.g., you arrive for a plumbing job but discover it is a gas boiler issue):

> HOLD SF-1042 This is a gas boiler issue, not standard plumbing. Needs Gas Safe registered engineer. Boiler is a Vaillant ecoTEC Plus, error code F.28 showing on display.

The property manager will reassign to an appropriate Gas Safe engineer.

### Tenant Not Satisfied

If the tenant contacts you directly to say they are not happy with the work, ask them to report it through WhatsApp to SafeFlow. The system will handle the dispute process, and the property manager will be involved if needed.

---

## Tips

1. **Always include job references** when you have multiple active jobs.
2. **Send a photo on completion** -- it speeds up the verification process and protects you if there is a dispute.
3. **Respond to ACCEPT/REJECT promptly** -- jobs auto-escalate after 24 hours with no response.
4. **Include reasons with HOLD and REJECT** -- this helps the property manager act quickly.
5. **Report safety concerns immediately** -- if you encounter asbestos, gas leaks, or structural issues, flag them as urgent.
6. **Keep your contact details current** -- notify your manager if your phone number changes so job assignments reach you.
