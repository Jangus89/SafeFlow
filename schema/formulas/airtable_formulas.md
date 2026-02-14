# SafeFlow — Airtable Formulas Reference

All formulas use Airtable formula syntax. Test in a formula field before deploying.

---

## 1. Job Reference (Work_Items)

**Field:** `job_reference`
**Type:** Formula

```
"WO-" & REPT("0", MAX(5 - LEN(RECORD_NUMBER() & ""), 0)) & RECORD_NUMBER()
```

**Output:** `WO-00001`, `WO-00002`, … `WO-99999`

> Note: `RECORD_NUMBER()` returns the auto-number value. If you're using a separate
> `record_id` auto-number field instead, replace with: `"WO-" & REPT("0", MAX(5 - LEN({record_id} & ""), 0)) & {record_id}`

---

## 2. Site Reference (Sites)

**Field:** `site_reference`

```
"SITE-" & REPT("0", MAX(4 - LEN({site_id} & ""), 0)) & {site_id}
```

**Output:** `SITE-0001`, `SITE-0012`

---

## 3. Quote Reference (Quotes)

**Field:** `quote_reference`

```
"QT-" & REPT("0", MAX(5 - LEN({quote_id} & ""), 0)) & {quote_id}
```

---

## 4. Payment Reference (Payments)

**Field:** `payment_reference`

```
"INV-" & REPT("0", MAX(5 - LEN({payment_id} & ""), 0)) & {payment_id}
```

---

## 5. Error Reference (Errors)

**Field:** `error_reference`

```
"ERR-" & REPT("0", MAX(5 - LEN({error_id} & ""), 0)) & {error_id}
```

---

## 6. SLA Deadline (Work_Items)

**Field:** `sla_deadline`

```
DATEADD({created_at}, {sla_target_hours}, 'hours')
```

**Depends on:** `created_at` (date), `sla_target_hours` (number)

---

## 7. Is Overdue (Work_Items)

**Field:** `is_overdue`

```
IF(
  AND(
    {current_state} != "CLOSED",
    {current_state} != "",
    {sla_deadline},
    NOW() > {sla_deadline}
  ),
  TRUE(),
  FALSE()
)
```

**Returns:** Checkbox-style TRUE/FALSE. Use in views to filter overdue items.

---

## 8. Time in Current State — Hours (Work_Items)

**Field:** `time_in_current_state_hours`

```
IF(
  {state_started_at},
  ROUND(DATETIME_DIFF(NOW(), {state_started_at}, 'hours'), 1),
  BLANK()
)
```

**Output:** `14.5` (hours). Updates live with NOW().

> Warning: Airtable formulas using NOW() recalculate roughly every 5–15 minutes,
> not in real-time. For exact timing, use automation timestamps.

---

## 9. Time in Current State — Human Readable (Work_Items)

**Field:** `time_in_current_state_display`

```
IF(
  {state_started_at},
  IF(
    DATETIME_DIFF(NOW(), {state_started_at}, 'days') >= 1,
    DATETIME_DIFF(NOW(), {state_started_at}, 'days') & "d " &
    MOD(DATETIME_DIFF(NOW(), {state_started_at}, 'hours'), 24) & "h",
    DATETIME_DIFF(NOW(), {state_started_at}, 'hours') & "h " &
    MOD(DATETIME_DIFF(NOW(), {state_started_at}, 'minutes'), 60) & "m"
  ),
  ""
)
```

**Output:** `2d 5h` or `3h 42m`

---

## 10. Total Resolution Hours (Work_Items)

**Field:** `total_resolution_hours`

```
IF(
  {closed_at},
  ROUND(DATETIME_DIFF({closed_at}, {created_at}, 'hours'), 1),
  BLANK()
)
```

**Output:** `72.5` (blank while job is still open)

---

## 11. SLA Performance (Work_Items)

**Field:** `sla_status`

```
IF(
  {current_state} = "CLOSED",
  IF(
    {closed_at} <= {sla_deadline},
    "✅ Met",
    "❌ Breached (" & DATETIME_DIFF({closed_at}, {sla_deadline}, 'hours') & "h over)"
  ),
  IF(
    NOW() > {sla_deadline},
    "⚠️ Overdue (" & DATETIME_DIFF(NOW(), {sla_deadline}, 'hours') & "h over)",
    "🟢 On track (" & DATETIME_DIFF({sla_deadline}, NOW(), 'hours') & "h remaining)"
  )
)
```

---

## 12. Quote Subtotal (Quotes)

**Field:** `subtotal`

```
{labour_cost} + {materials_cost} + {callout_charge}
```

---

## 13. Quote VAT Amount (Quotes)

**Field:** `vat_amount`

```
ROUND({subtotal} * {vat_rate}, 2)
```

---

## 14. Quote Total Including VAT (Quotes)

**Field:** `total_amount`

```
{subtotal} + {vat_amount}
```

---

## 15. Quote Response Time (Quotes)

**Field:** `response_time_hours`

```
IF(
  {submitted_at},
  ROUND(DATETIME_DIFF({submitted_at}, {requested_at}, 'hours'), 1),
  BLANK()
)
```

---

## 16. Payment Gross Amount (Payments)

**Field:** `gross_amount`

```
{net_amount} + {vat_amount}
```

---

## 17. Payment Amount Payable (Payments)

**Field:** `amount_payable`

```
{gross_amount} - {retention_amount}
```

---

## 18. Payment Is Overdue (Payments)

**Field:** `is_overdue`

```
IF(
  AND(
    {status} != "PAID",
    {status} != "CANCELLED",
    {due_date},
    NOW() > {due_date}
  ),
  TRUE(),
  FALSE()
)
```

---

## 19. Payment Days Overdue (Payments)

**Field:** `days_overdue`

```
IF(
  {is_overdue},
  DATETIME_DIFF(NOW(), {due_date}, 'days'),
  0
)
```

---

## 20. MRR — Monthly Recurring Revenue (Sites)

To calculate MRR across your base, create a **summary view** on the Sites table:

**Field:** `mrr_contribution` (on Sites table)

```
IF({status} = "ACTIVE", {monthly_fee}, 0)
```

Then use a **Summary bar** at the bottom of the Sites grid view → SUM of `mrr_contribution`.

**For a dashboard field showing total MRR**, you would need an Airtable Interface or
a dedicated Metrics table with a single record that uses rollups:

```
Table: Metrics (single record)
Field: total_mrr (Rollup)
  → Linked to: Sites
  → Rollup field: mrr_contribution
  → Aggregation: SUM
```

**ARR (Annual Recurring Revenue):**

```
{total_mrr} * 12
```

**MRR by Tier** — Use grouped summary in a Sites view, grouped by `subscription_tier`,
with SUM of `monthly_fee` in the summary bar.

---

## 21. Contractor Performance Score (Contractors)

Composite score for ranking contractors. Create on the Contractors table:

```
IF(
  {total_jobs_completed} > 0,
  ROUND(
    ({avg_rating} * 20) * 0.4 +
    ({rfq_acceptance_rate}) * 0.2 +
    ({quote_win_rate}) * 0.2 +
    (100 - MIN({avg_response_time_hours}, 100)) * 0.2,
    1
  ),
  BLANK()
)
```

**Weighting:** 40% tenant rating, 20% acceptance rate, 20% win rate, 20% response speed.
Score is 0–100. Blank if no completed jobs yet.

---

## Notes on Airtable Formula Limitations

1. **NOW() refresh rate**: Formulas using `NOW()` refresh every ~5–15 minutes. For
   time-critical SLA tracking, supplement with n8n automations that write timestamps.

2. **No SUMIFS/COUNTIFS**: Airtable can't do conditional aggregation in formulas.
   Use filtered views with summary bars, or rollup fields with filtered linked records.

3. **Rollup limitations**: Rollups can only aggregate one field from a linked table.
   For complex metrics, create intermediate formula fields on the source table first,
   then roll those up.

4. **String length**: Long text fields in formulas are limited. For `state_history`
   JSON, consider using Airtable's native revision history or an external store
   if the array grows beyond ~10KB.
