# Migration Template

## Migration: [NUMBER]_[description]

**Version:** [semver]
**Date:** DD/MM/YYYY
**Author:** [name]
**Depends on:** [previous migration number or "none"]

## Description

[What this migration does and why]

## Pre-checks

- [ ] [Pre-condition that must be true before applying]

## Changes

### Tables Added
| Table Name | Table ID | Description |
|-----------|----------|-------------|

### Tables Modified
| Table Name | Change | Details |
|-----------|--------|---------|

### Fields Added
| Table | Field Name | Field ID | Type | Options |
|-------|-----------|----------|------|---------|

### Fields Modified
| Table | Field Name | Change | Before | After |
|-------|-----------|--------|--------|-------|

### Fields Removed
| Table | Field Name | Reason |
|-------|-----------|--------|

### Views Added/Modified
| Table | View Name | Type | Filter/Sort |
|-------|----------|------|------------|

## Rollback Instructions

1. [Step-by-step rollback procedure]

## Post-checks

- [ ] [Verification that migration was applied correctly]

## Notes

[Any additional context, warnings, or considerations]
