#!/usr/bin/env python3
"""Validate Make.com scenario blueprints and supporting files.

Checks each scenario directory for:
    - blueprint.json exists and is valid JSON with required keys
    - metadata.json exists and is valid
    - README.md exists
    - CHANGELOG.md exists
    - test-payloads/ directory exists with at least one payload
    - Cross-references between scenarios are consistent

Usage:
    python tests/validation/validate-scenarios.py
    python tests/validation/validate-scenarios.py --scenarios-dir path/to/scenarios
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Any


EXPECTED_SCENARIOS = [
    "scenario-a-inbound",
    "scenario-b-state-engine",
    "scenario-c-outbound",
    "scenario-d-sla",
    "scenario-e-dlq",
]

REQUIRED_BLUEPRINT_KEYS = ["name", "version", "modules"]
REQUIRED_METADATA_KEYS = ["scenario_id", "name", "version"]


class ScenarioValidator:
    """Validates Make.com scenario definitions."""

    def __init__(self, scenarios_dir: str) -> None:
        self.scenarios_dir = Path(scenarios_dir)
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.results: dict[str, dict[str, Any]] = {}

    def validate_json_file(self, path: Path) -> dict[str, Any] | None:
        """Load and validate a JSON file. Returns parsed data or None."""
        if not path.exists():
            self.errors.append(f"Missing file: {path}")
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in {path}: {e}")
            return None

    def validate_scenario(self, scenario_name: str) -> dict[str, Any]:
        """Validate a single scenario directory."""
        result: dict[str, Any] = {"name": scenario_name, "valid": True}
        scenario_dir = self.scenarios_dir / scenario_name

        if not scenario_dir.exists():
            self.errors.append(f"Scenario directory missing: {scenario_dir}")
            result["valid"] = False
            return result

        # Check blueprint.json
        blueprint = self.validate_json_file(scenario_dir / "blueprint.json")
        if blueprint:
            for key in REQUIRED_BLUEPRINT_KEYS:
                if key not in blueprint:
                    self.errors.append(
                        f"{scenario_name}/blueprint.json: missing key '{key}'"
                    )
                    result["valid"] = False

            modules = blueprint.get("modules", [])
            result["module_count"] = len(modules)

            # Check module IDs are unique
            module_ids = [m.get("id") for m in modules if "id" in m]
            if len(module_ids) != len(set(module_ids)):
                self.errors.append(
                    f"{scenario_name}/blueprint.json: duplicate module IDs"
                )
                result["valid"] = False

            # Check connections reference valid modules
            connections = blueprint.get("connections", [])
            for conn in connections:
                from_id = conn.get("from")
                to_val = conn.get("to")
                to_ids = to_val if isinstance(to_val, list) else [to_val]
                for to_id in to_ids:
                    if from_id not in module_ids:
                        self.warnings.append(
                            f"{scenario_name}: connection from unknown module {from_id}"
                        )
                    if to_id not in module_ids:
                        self.warnings.append(
                            f"{scenario_name}: connection to unknown module {to_id}"
                        )
        else:
            result["valid"] = False

        # Check metadata.json
        metadata = self.validate_json_file(scenario_dir / "metadata.json")
        if metadata:
            for key in REQUIRED_METADATA_KEYS:
                if key not in metadata:
                    self.errors.append(
                        f"{scenario_name}/metadata.json: missing key '{key}'"
                    )
                    result["valid"] = False

            # Check scenario_id matches directory name
            if metadata.get("scenario_id") != scenario_name:
                self.warnings.append(
                    f"{scenario_name}: metadata scenario_id "
                    f"'{metadata.get('scenario_id')}' doesn't match directory name"
                )
        else:
            result["valid"] = False

        # Check README.md
        readme_path = scenario_dir / "README.md"
        if not readme_path.exists():
            self.errors.append(f"{scenario_name}: missing README.md")
            result["valid"] = False

        # Check CHANGELOG.md
        changelog_path = scenario_dir / "CHANGELOG.md"
        if not changelog_path.exists():
            self.errors.append(f"{scenario_name}: missing CHANGELOG.md")
            result["valid"] = False

        # Check test-payloads/
        payloads_dir = scenario_dir / "test-payloads"
        if not payloads_dir.exists():
            self.errors.append(f"{scenario_name}: missing test-payloads/ directory")
            result["valid"] = False
        else:
            payloads = list(payloads_dir.glob("*.json"))
            result["payload_count"] = len(payloads)
            if len(payloads) == 0:
                self.warnings.append(
                    f"{scenario_name}: no test payloads found"
                )

            # Validate each payload is valid JSON
            for payload_path in payloads:
                self.validate_json_file(payload_path)

        return result

    def run(self) -> bool:
        """Run all validations."""
        if not self.scenarios_dir.exists():
            self.errors.append(f"Scenarios directory not found: {self.scenarios_dir}")
            return False

        for scenario in EXPECTED_SCENARIOS:
            result = self.validate_scenario(scenario)
            self.results[scenario] = result

        return len(self.errors) == 0

    def report(self) -> str:
        """Generate validation report."""
        lines = ["SafeFlow Scenario Validation", "=" * 40, ""]

        for name, result in self.results.items():
            status = "PASS" if result.get("valid") else "FAIL"
            modules = result.get("module_count", "?")
            payloads = result.get("payload_count", "?")
            lines.append(
                f"  [{status}] {name} "
                f"(modules: {modules}, payloads: {payloads})"
            )

        lines.append("")

        if self.errors:
            lines.append(f"ERRORS ({len(self.errors)}):")
            for err in self.errors:
                lines.append(f"  [ERROR] {err}")
            lines.append("")

        if self.warnings:
            lines.append(f"WARNINGS ({len(self.warnings)}):")
            for warn in self.warnings:
                lines.append(f"  [WARN]  {warn}")
            lines.append("")

        if not self.errors:
            lines.append("RESULT: PASSED")
        else:
            lines.append("RESULT: FAILED")

        lines.append(
            f"  {len(self.errors)} error(s), {len(self.warnings)} warning(s)"
        )
        return "\n".join(lines)


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Validate Make.com scenario blueprints"
    )
    parser.add_argument(
        "--scenarios-dir",
        default="scenarios",
        help="Path to scenarios directory (default: scenarios)",
    )
    args = parser.parse_args()

    validator = ScenarioValidator(args.scenarios_dir)
    success = validator.run()
    print(validator.report())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
