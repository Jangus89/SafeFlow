#!/usr/bin/env python3
"""
SafeFlow Configuration Validator

Validates that all required environment variables and configurations
are properly set before deploying the system.

Usage:
    python scripts/setup/validate_config.py
    python scripts/setup/validate_config.py --env production
"""

import json
import os
import sys
from pathlib import Path

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
CHECK = f"{GREEN}✓{RESET}"
CROSS = f"{RED}✗{RESET}"
WARN = f"{YELLOW}!{RESET}"


def check_env_vars():
    """Check all required environment variables are set."""
    print("\n── Environment Variables ──")

    required_vars = {
        "360dialog": [
            "WHATSAPP_API_KEY",
            "WHATSAPP_API_URL",
            "WHATSAPP_WEBHOOK_SECRET",
        ],
        "Make.com": [
            "MAKE_API_TOKEN",
            "MAKE_WEBHOOK_BASE_URL",
            "MAKE_INBOUND_WEBHOOK_ID",
        ],
        "Airtable": [
            "AIRTABLE_API_KEY",
            "AIRTABLE_BASE_ID",
        ],
        "Claude API": [
            "ANTHROPIC_API_KEY",
            "CLAUDE_MODEL",
        ],
        "Xero": [
            "XERO_CLIENT_ID",
            "XERO_CLIENT_SECRET",
            "XERO_TENANT_ID",
        ],
    }

    errors = []
    warnings = []

    for service, vars_list in required_vars.items():
        print(f"\n  {service}:")
        for var in vars_list:
            value = os.environ.get(var)
            if value:
                # Mask the value for display
                masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "****"
                print(f"    {CHECK} {var} = {masked}")
            else:
                print(f"    {CROSS} {var} — NOT SET")
                errors.append(f"{service}: {var} is required")

    # Optional but recommended
    optional_vars = ["APP_TIMEZONE", "APP_LOG_LEVEL", "RATE_LIMIT_MESSAGES_PER_MINUTE"]
    print(f"\n  Optional:")
    for var in optional_vars:
        value = os.environ.get(var)
        if value:
            print(f"    {CHECK} {var} = {value}")
        else:
            print(f"    {WARN} {var} — not set (using defaults)")
            warnings.append(f"{var} not set, using defaults")

    return errors, warnings


def check_files():
    """Check all required configuration files exist."""
    print("\n── Configuration Files ──")

    root = Path(__file__).parent.parent.parent
    required_files = [
        "airtable/schemas/base-schema.json",
        "prompts/system/facilities-classifier.md",
        "prompts/extraction/maintenance-details.md",
        "prompts/generation/maintenance-confirmation.md",
        "prompts/generation/general-response.md",
        "prompts/system/emergency-handler.md",
        "webhooks/validators/whatsapp-webhook-schema.json",
        "xero/mappings/field-mappings.json",
        "make-scenarios/inbound/inbound-message-router.json",
        "make-scenarios/inbound/maintenance-request-flow.json",
        "make-scenarios/escalation/escalation-handler.json",
    ]

    errors = []
    for filepath in required_files:
        full_path = root / filepath
        if full_path.exists():
            print(f"  {CHECK} {filepath}")
        else:
            print(f"  {CROSS} {filepath} — MISSING")
            errors.append(f"Missing file: {filepath}")

    return errors


def check_json_valid():
    """Validate all JSON files parse correctly."""
    print("\n── JSON Validation ──")

    root = Path(__file__).parent.parent.parent
    errors = []

    json_files = list(root.rglob("*.json"))
    # Exclude node_modules, .git, etc.
    json_files = [
        f for f in json_files if ".git" not in str(f) and "node_modules" not in str(f)
    ]

    for json_file in json_files:
        try:
            with open(json_file) as f:
                json.load(f)
            rel_path = json_file.relative_to(root)
            print(f"  {CHECK} {rel_path}")
        except json.JSONDecodeError as e:
            rel_path = json_file.relative_to(root)
            print(f"  {CROSS} {rel_path} — {e}")
            errors.append(f"Invalid JSON: {rel_path}: {e}")

    return errors


def check_schema_integrity():
    """Validate Airtable schema has required tables and fields."""
    print("\n── Schema Integrity ──")

    root = Path(__file__).parent.parent.parent
    schema_path = root / "airtable" / "schemas" / "base-schema.json"
    errors = []

    try:
        with open(schema_path) as f:
            schema = json.load(f)

        required_tables = [
            "Tenants",
            "Properties",
            "Maintenance Requests",
            "Contractors",
            "Conversations",
            "Message Log",
            "Error Log",
        ]

        for table in required_tables:
            if table in schema.get("tables", {}):
                field_count = len(schema["tables"][table].get("fields", []))
                print(f"  {CHECK} {table} ({field_count} fields)")
            else:
                print(f"  {CROSS} {table} — MISSING")
                errors.append(f"Missing table: {table}")

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  {CROSS} Cannot read schema: {e}")
        errors.append(f"Schema error: {e}")

    return errors


def main():
    """Run all validation checks."""
    print("=" * 50)
    print("  SafeFlow Configuration Validator")
    print("=" * 50)

    all_errors = []
    all_warnings = []

    # Check environment variables
    errors, warnings = check_env_vars()
    all_errors.extend(errors)
    all_warnings.extend(warnings)

    # Check files
    errors = check_files()
    all_errors.extend(errors)

    # Check JSON validity
    errors = check_json_valid()
    all_errors.extend(errors)

    # Check schema integrity
    errors = check_schema_integrity()
    all_errors.extend(errors)

    # Summary
    print("\n" + "=" * 50)
    if all_errors:
        print(f"\n{RED}VALIDATION FAILED{RESET}")
        print(f"\n  {len(all_errors)} error(s):")
        for error in all_errors:
            print(f"    {CROSS} {error}")
    else:
        print(f"\n{GREEN}VALIDATION PASSED{RESET}")

    if all_warnings:
        print(f"\n  {len(all_warnings)} warning(s):")
        for warning in all_warnings:
            print(f"    {WARN} {warning}")

    print()
    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())
