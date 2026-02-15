#!/usr/bin/env python3
"""A/B test two prompt versions for statistical significance.

Runs both prompt versions against the same test cases and performs
a two-proportion z-test to determine if one version is significantly
better than the other.

Usage:
    python llm-prompts/evaluation/ab-test.py --prompt intake-triage --version-a v1.0.0 --version-b v2.0.0
    python llm-prompts/evaluation/ab-test.py --prompt intake-triage --version-a v1.0.0 --version-b v2.0.0 --limit 50
"""

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def two_proportion_z_test(
    successes_a: int,
    total_a: int,
    successes_b: int,
    total_b: int,
) -> dict[str, float]:
    """Perform two-proportion z-test.

    Tests H0: p_a = p_b vs H1: p_a != p_b.

    Returns:
        Dict with z_statistic, p_value, and significance flag.
    """
    if total_a == 0 or total_b == 0:
        return {"z_statistic": 0.0, "p_value": 1.0, "significant": False}

    p_a = successes_a / total_a
    p_b = successes_b / total_b

    # Pooled proportion
    p_pool = (successes_a + successes_b) / (total_a + total_b)

    # Standard error
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / total_a + 1 / total_b))

    if se == 0:
        return {"z_statistic": 0.0, "p_value": 1.0, "significant": False}

    z = (p_b - p_a) / se

    # Approximate p-value using normal distribution
    # Using the complementary error function approximation
    p_value = 2 * (1 - _norm_cdf(abs(z)))

    return {
        "z_statistic": round(z, 4),
        "p_value": round(p_value, 6),
        "significant": p_value < 0.05,
    }


def _norm_cdf(x: float) -> float:
    """Approximate standard normal CDF using Abramowitz & Stegun."""
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    d = 0.3989422804014327  # 1/sqrt(2*pi)
    poly = (
        1.330274429
        - 1.821255978 * t
        + 1.781477937 * t * t
        - 0.356563782 * t * t * t
        + 0.319381530 * t * t * t * t
    )
    # Actually use Horner's method properly
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    result = 1.0 - d * math.exp(-x * x / 2.0) * poly
    return result if x >= 0 else 1.0 - result


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="A/B test two prompt versions"
    )
    parser.add_argument(
        "--prompt", required=True, help="Prompt name (e.g., intake-triage)"
    )
    parser.add_argument(
        "--version-a", required=True, help="Version A (baseline)"
    )
    parser.add_argument(
        "--version-b", required=True, help="Version B (candidate)"
    )
    parser.add_argument(
        "--limit", type=int, help="Limit number of test cases"
    )
    parser.add_argument(
        "--confidence", type=float, default=0.95,
        help="Confidence level (default: 0.95)"
    )
    args = parser.parse_args()

    print(f"SafeFlow A/B Prompt Test")
    print(f"  Prompt: {args.prompt}")
    print(f"  Version A (baseline): {args.version_a}")
    print(f"  Version B (candidate): {args.version_b}")
    print(f"  Confidence level: {args.confidence}")
    print()

    # Check prompt files exist
    path_a = Path(f"llm-prompts/{args.prompt}/versions/{args.version_a}-system-prompt.txt")
    path_b = Path(f"llm-prompts/{args.prompt}/versions/{args.version_b}-system-prompt.txt")

    if not path_a.exists():
        print(f"ERROR: Version A prompt not found: {path_a}")
        sys.exit(1)
    if not path_b.exists():
        print(f"ERROR: Version B prompt not found: {path_b}")
        sys.exit(1)

    # Load test cases
    test_dir = Path(f"llm-prompts/{args.prompt}/test-cases")
    cases: list[dict[str, Any]] = []
    for test_file in sorted(test_dir.glob("*.json")):
        with open(test_file) as f:
            data = json.load(f)
        if "test_cases" in data:
            cases.extend(data["test_cases"])

    if args.limit:
        cases = cases[: args.limit]

    print(f"Running {len(cases)} test cases against both versions...")
    print()

    # Import evaluation functions
    sys.path.insert(0, str(Path("llm-prompts/evaluation")))
    from importlib import import_module

    # We need the evaluate-prompt module functions
    # Since we can't import with hyphens, call API directly
    prompt_a = path_a.read_text()
    prompt_b = path_b.read_text()

    results_a: list[bool] = []
    results_b: list[bool] = []

    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package required. Run: pip install anthropic")
        sys.exit(1)

    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    for i, case in enumerate(cases):
        case_id = case.get("id", f"case-{i}")
        message = case.get("input", {}).get("message", "")
        expected = case.get("expected", {})

        print(f"  [{i + 1}/{len(cases)}] {case_id}...", end=" ")

        # Test Version A
        try:
            resp_a = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                temperature=0.2,
                system=prompt_a,
                messages=[{"role": "user", "content": message}],
            )
            parsed_a = json.loads(resp_a.content[0].text)
            pass_a = (
                parsed_a.get("triage", {}).get("discipline") == expected.get("discipline")
                and parsed_a.get("triage", {}).get("urgency") == expected.get("urgency")
            )
        except Exception:
            pass_a = False

        results_a.append(pass_a)
        time.sleep(0.3)

        # Test Version B
        try:
            resp_b = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                temperature=0.2,
                system=prompt_b,
                messages=[{"role": "user", "content": message}],
            )
            parsed_b = json.loads(resp_b.content[0].text)
            pass_b = (
                parsed_b.get("triage", {}).get("discipline") == expected.get("discipline")
                and parsed_b.get("triage", {}).get("urgency") == expected.get("urgency")
            )
        except Exception:
            pass_b = False

        results_b.append(pass_b)
        time.sleep(0.3)

        status_a = "PASS" if pass_a else "FAIL"
        status_b = "PASS" if pass_b else "FAIL"
        print(f"A={status_a}, B={status_b}")

    # Calculate statistics
    successes_a = sum(results_a)
    successes_b = sum(results_b)
    total = len(cases)

    rate_a = round(successes_a / total * 100, 1) if total > 0 else 0
    rate_b = round(successes_b / total * 100, 1) if total > 0 else 0

    z_test = two_proportion_z_test(successes_a, total, successes_b, total)

    # Determine recommendation
    if z_test["significant"] and rate_b > rate_a:
        recommendation = "switch_to_b"
    elif z_test["significant"] and rate_a > rate_b:
        recommendation = "keep_a"
    else:
        recommendation = "inconclusive"

    # Print results
    print()
    print("=" * 50)
    print("A/B TEST RESULTS")
    print("=" * 50)
    print(f"Version A ({args.version_a}): {rate_a}% ({successes_a}/{total})")
    print(f"Version B ({args.version_b}): {rate_b}% ({successes_b}/{total})")
    print(f"Difference: {round(rate_b - rate_a, 1)}%")
    print()
    print(f"Z-statistic: {z_test['z_statistic']}")
    print(f"P-value: {z_test['p_value']}")
    print(f"Significant (p < 0.05): {z_test['significant']}")
    print()
    print(f"RECOMMENDATION: {recommendation.upper()}")

    # Save report
    report = {
        "prompt": args.prompt,
        "version_a": args.version_a,
        "version_b": args.version_b,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_cases": total,
        "results_a": {"pass_rate": rate_a, "passed": successes_a, "total": total},
        "results_b": {"pass_rate": rate_b, "passed": successes_b, "total": total},
        "z_test": z_test,
        "recommendation": recommendation,
    }

    results_dir = Path(f"llm-prompts/{args.prompt}/evaluation-results")
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = results_dir / f"ab_test_{timestamp}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
