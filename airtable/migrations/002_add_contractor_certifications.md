# Migration 002: Add Contractor Certifications

**Version:** 1.1.0
**Date:** 15/02/2026
**Author:** SafeFlow Team
**Depends on:** 001_initial_schema

## Description

Adds additional certification tracking fields to the Contractors table to support
UK regulatory requirements for trade-specific qualifications. This includes
CSCS card tracking, DBS check status, and public liability insurance details.

## Pre-checks

- [ ] Migration 001 has been applied
- [ ] Contractors table exists with current field structure
- [ ] No active contractor records being edited (avoid field conflicts)

## Changes

### Fields Added

| Table | Field Name | Field ID | Type | Options |
|-------|-----------|----------|------|---------|
| Contractors | cscs_card_type | fldCscsType | singleSelect | LABOURER, SKILLED_WORKER, SUPERVISOR, MANAGER, ACADEMICALLY_QUALIFIED, PROFESSIONALLY_QUALIFIED |
| Contractors | cscs_card_number | fldCscsNumber | singleLineText | |
| Contractors | cscs_expiry | fldCscsExpiry | date | DD/MM/YYYY |
| Contractors | dbs_check_status | fldDbsStatus | singleSelect | CLEAR, PENDING, EXPIRED, NOT_REQUIRED |
| Contractors | dbs_check_date | fldDbsDate | date | DD/MM/YYYY |
| Contractors | public_liability_amount | fldPliAmount | currency | £, precision: 0 |
| Contractors | public_liability_expiry | fldPliExpiry | date | DD/MM/YYYY |
| Contractors | employers_liability_amount | fldEliAmount | currency | £, precision: 0 |
| Contractors | employers_liability_expiry | fldEliExpiry | date | DD/MM/YYYY |
| Contractors | certifications_valid | fldCertsValid | formula | See below |

**Formula for certifications_valid:**
```
IF(
  AND(
    OR({gas_safe_expiry} = BLANK(), {gas_safe_expiry} > NOW()),
    OR({niceic_expiry} = BLANK(), {niceic_expiry} > NOW()),
    OR({cscs_expiry} = BLANK(), {cscs_expiry} > NOW()),
    OR({public_liability_expiry} = BLANK(), {public_liability_expiry} > NOW()),
    OR({dbs_check_status} != 'EXPIRED')
  ),
  TRUE(),
  FALSE()
)
```

### Views Added

| Table | View Name | Type | Filter/Sort |
|-------|----------|------|------------|
| Contractors | Expiring Certifications | grid | Any certification expiring within 30 days |
| Contractors | Compliance Summary | grid | Grouped by certifications_valid |

## Rollback Instructions

1. Delete view "Expiring Certifications" from Contractors table
2. Delete view "Compliance Summary" from Contractors table
3. Delete fields in reverse order:
   - certifications_valid
   - employers_liability_expiry
   - employers_liability_amount
   - public_liability_expiry
   - public_liability_amount
   - dbs_check_date
   - dbs_check_status
   - cscs_expiry
   - cscs_card_number
   - cscs_card_type
4. Verify no formula fields in other tables reference deleted fields

## Post-checks

- [ ] All 10 new fields visible in Contractors table
- [ ] certifications_valid formula calculates correctly for existing contractors
- [ ] Select field choices correct for cscs_card_type and dbs_check_status
- [ ] New views display correctly
- [ ] Expiring Certifications view shows contractors with upcoming expiries
- [ ] Existing contractor data unaffected

## Notes

- CSCS (Construction Skills Certification Scheme) is required for most UK construction sites
- DBS (Disclosure and Barring Service) checks may be required for work in occupied premises
- Public liability insurance minimum £2,000,000 recommended
- Employers' liability insurance is legally required if contractor has employees (£5,000,000 minimum)
