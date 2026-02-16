#!/usr/bin/env python3
"""Evaluate LLM prompt accuracy against test cases.

Runs test cases against a specified prompt version using the Claude API,
validates responses against expected values, and generates detailed
accuracy metrics.  Includes retry with exponential backoff for API calls,
configurable model selection, custom output directory, and a progress bar.

Usage:
    python llm-prompts/evaluation/evaluate-prompt.py --prompt intake-triage --version v2.0.0
    python llm-prompts/evaluation/evaluate-prompt.py --prompt intake-triage --tags emergency --limit 10
    python llm-prompts/evaluation/evaluate-prompt.py --prompt intake-triage --dry-run
    python llm-prompts/evaluation/evaluate-prompt.py --prompt intake-triage --all --json
    python llm-prompts/evaluation/evaluate-prompt.py --prompt intake-triage --model claude-sonnet-4-5-20250929
    python llm-prompts/evaluation/evaluate-prompt.py --prompt intake-triage --output-dir results/
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
MAX_RETRIES = 3
PROGRESS_BAR_WIDTH = 30


# ---------------------------------------------------------------------------
# Progress bar helper
# ---------------------------------------------------------------------------

def progress_bar(current: int, total: int, *, width: int = PROGRESS_BAR_WIDTH) -> str:
    """Return a text progress bar string like [========>       ] 45.0%."""
    if total == 0:
        return "[" + " " * width + "]   0.0%"
    fraction = current / total
    filled = int(width * fraction)
    bar = "=" * filled
    if filled < width:
        bar += ">"
        bar += " " * (width - filled - 1)
    pct = round(fraction * 100, 1)
    return f"[{bar}] {pct:5.1f}%"


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def load_prompt(prompt_name: str, version: str) -> str:
    """Load system prompt text from file."""
    prompt_path = Path(f"llm-prompts/{prompt_name}/versions/{version}-system-prompt.txt")
    if not prompt_path.exists():
        print(f"ERROR: Prompt file not found: {prompt_path}")
        sys.exit(1)
    return prompt_path.read_text()


def load_test_cases(prompt_name: str) -> list[dict[str, Any]]:
    """Load test cases from the test-cases directory."""
    test_dir = Path(f"llm-prompts/{prompt_name}/test-cases")
    if not test_dir.exists():
        print(f"ERROR: Test cases directory not found: {test_dir}")
        sys.exit(1)

    cases: list[dict[str, Any]] = []
    for test_file in sorted(test_dir.glob("*.json")):
        with open(test_file) as f:
            data = json.load(f)
        if "test_cases" in data:
            cases.extend(data["test_cases"])
    return cases


def filter_cases(
    cases: list[dict[str, Any]],
    tags: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Filter test cases by tags and limit."""
    filtered = cases

    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
        filtered = [
            c for c in filtered
            if any(tag in c.get("tags", []) for tag in tag_list)
            or c.get("category", "") in tag_list
        ]

    if limit and limit > 0:
        filtered = filtered[:limit]

    return filtered


def call_claude_api(
    system_prompt: str,
    message: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    max_tokens: int = 1500,
) -> dict[str, Any]:
    """Call the Claude API with retry / exponential backoff and return parsed JSON response."""
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            start_time = time.time()
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": message}],
            )
            latency = time.time() - start_time

            content = response.content[0].text
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                parsed = {"_raw": content, "_parse_error": True}

            return {
                "response": parsed,
                "latency_seconds": round(latency, 3),
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "model": model,
            }
        except Exception as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                backoff = 2 ** (attempt - 1)
                print(f" (retry {attempt}/{MAX_RETRIES}, backoff {backoff}s)", end="")
                time.sleep(backoff)

    raise RuntimeError(
        f"Claude API call failed after {MAX_RETRIES} retries: {last_error}"
    ) from last_error


def validate_response(
    response: dict[str, Any],
    expected: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    """Validate a response against expected values and rules."""
    result: dict[str, Any] = {"passed": True, "checks": [], "failures": []}

    if response.get("_parse_error"):
        result["passed"] = False
        result["failures"].append("Response is not valid JSON")
        return result

    # Check discipline
    if "discipline_must_be" in rules:
        actual = response.get("triage", {}).get("discipline", "")
        expected_val = rules["discipline_must_be"]
        check = actual == expected_val
        result["checks"].append(
            {"field": "discipline", "expected": expected_val, "actual": actual, "passed": check}
        )
        if not check:
            result["passed"] = False
            result["failures"].append(f"discipline: expected {expected_val}, got {actual}")

    if "discipline" in expected:
        actual = response.get("triage", {}).get("discipline", "")
        check = actual == expected["discipline"]
        if not check:
            result["passed"] = False
            result["failures"].append(
                f"discipline: expected {expected['discipline']}, got {actual}"
            )

    # Check urgency
    if "urgency_must_be" in rules:
        actual = response.get("triage", {}).get("urgency", "")
        expected_val = rules["urgency_must_be"]
        check = actual == expected_val
        result["checks"].append(
            {"field": "urgency", "expected": expected_val, "actual": actual, "passed": check}
        )
        if not check:
            result["passed"] = False
            result["failures"].append(f"urgency: expected {expected_val}, got {actual}")

    if "urgency" in expected:
        actual = response.get("triage", {}).get("urgency", "")
        check = actual == expected["urgency"]
        if not check:
            result["passed"] = False
            result["failures"].append(
                f"urgency: expected {expected['urgency']}, got {actual}"
            )

    # Check routing decision
    if "routing_decision" in expected:
        actual = response.get("routing", {}).get("decision", "")
        check = actual == expected["routing_decision"]
        if not check:
            result["passed"] = False
            result["failures"].append(
                f"routing: expected {expected['routing_decision']}, got {actual}"
            )

    # Check confidence range
    confidence = response.get("triage", {}).get("confidence", 0)
    if "confidence_min" in expected:
        if confidence < expected["confidence_min"]:
            result["passed"] = False
            result["failures"].append(
                f"confidence {confidence} below minimum {expected['confidence_min']}"
            )
    if "confidence_max" in expected:
        if confidence > expected["confidence_max"]:
            result["passed"] = False
            result["failures"].append(
                f"confidence {confidence} above maximum {expected['confidence_max']}"
            )

    # Check safety flags
    if rules.get("must_flag_safety"):
        immediate_danger = response.get("safety", {}).get("immediate_danger", False)
        if not immediate_danger:
            result["passed"] = False
            result["failures"].append("Expected immediate_danger to be true")

    # Check certifications
    if "must_include_certification" in rules:
        certs = response.get("routing", {}).get("required_certifications", [])
        for cert in rules["must_include_certification"]:
            if cert not in certs:
                result["passed"] = False
                result["failures"].append(f"Missing required certification: {cert}")

    # Check reasoning mentions
    if "reasoning_must_mention" in rules:
        reasoning = response.get("triage", {}).get("reasoning", "").lower()
        for term in rules["reasoning_must_mention"]:
            if term.lower() not in reasoning:
                result["warnings"] = result.get("warnings", [])
                result["warnings"].append(f"Reasoning doesn't mention: {term}")

    # Check clarification questions
    if "clarification_questions_min" in rules:
        questions = response.get("clarification", {}).get("questions", [])
        if len(questions) < rules["clarification_questions_min"]:
            result["passed"] = False
            result["failures"].append(
                f"Expected at least {rules['clarification_questions_min']} "
                f"clarification questions, got {len(questions)}"
            )

    return result


def run_evaluation(
    prompt_name: str,
    version: str,
    cases: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run evaluation against all test cases."""
    system_prompt = load_prompt(prompt_name, version)

    results: dict[str, Any] = {
        "prompt": prompt_name,
        "version": version,
        "model": model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_cases": len(cases),
        "passed": 0,
        "failed": 0,
        "by_category": {},
        "by_tag": {},
        "latency_stats": {"total": 0, "min": float("inf"), "max": 0, "values": []},
        "case_results": [],
    }

    eval_start = time.time()

    for i, case in enumerate(cases):
        case_id = case.get("id", f"case-{i}")
        category = case.get("category", "unknown")
        tags = case.get("tags", [])
        message = case.get("input", {}).get("message", "")
        expected = case.get("expected", {})
        rules = case.get("validation_rules", {})

        bar = progress_bar(i, len(cases))
        print(f"\r  {bar}  [{i + 1}/{len(cases)}] {case_id} ({category})...", end=" ")

        if dry_run:
            print("SKIP (dry run)")
            continue

        try:
            api_result = call_claude_api(system_prompt, message, model=model)
            validation = validate_response(api_result["response"], expected, rules)

            case_result = {
                "id": case_id,
                "category": category,
                "tags": tags,
                "passed": validation["passed"],
                "failures": validation.get("failures", []),
                "latency": api_result["latency_seconds"],
                "tokens": api_result["input_tokens"] + api_result["output_tokens"],
            }

            if validation["passed"]:
                results["passed"] += 1
                print("PASS")
            else:
                results["failed"] += 1
                print(f"FAIL: {'; '.join(validation['failures'])}")

            # Update category stats
            if category not in results["by_category"]:
                results["by_category"][category] = {"total": 0, "passed": 0}
            results["by_category"][category]["total"] += 1
            if validation["passed"]:
                results["by_category"][category]["passed"] += 1

            # Update tag stats
            for tag in tags:
                if tag not in results["by_tag"]:
                    results["by_tag"][tag] = {"total": 0, "passed": 0}
                results["by_tag"][tag]["total"] += 1
                if validation["passed"]:
                    results["by_tag"][tag]["passed"] += 1

            # Update latency stats
            latency = api_result["latency_seconds"]
            results["latency_stats"]["total"] += latency
            results["latency_stats"]["values"].append(latency)
            results["latency_stats"]["min"] = min(
                results["latency_stats"]["min"], latency
            )
            results["latency_stats"]["max"] = max(
                results["latency_stats"]["max"], latency
            )

            results["case_results"].append(case_result)

            # Rate limit: small delay between API calls
            time.sleep(0.5)

        except Exception as e:
            results["failed"] += 1
            print(f"ERROR: {e}")
            results["case_results"].append({
                "id": case_id,
                "category": category,
                "passed": False,
                "failures": [str(e)],
            })

    # Final progress bar
    if not dry_run and cases:
        bar = progress_bar(len(cases), len(cases))
        print(f"\r  {bar}  Done.{' ' * 40}")

    eval_elapsed = round(time.time() - eval_start, 3)
    results["duration_seconds"] = eval_elapsed

    # Calculate summary statistics
    total = results["passed"] + results["failed"]
    if total > 0:
        results["overall_accuracy"] = round(results["passed"] / total * 100, 1)
    else:
        results["overall_accuracy"] = 0

    if results["latency_stats"]["values"]:
        values = sorted(results["latency_stats"]["values"])
        results["latency_stats"]["avg"] = round(
            results["latency_stats"]["total"] / len(values), 3
        )
        p95_idx = int(len(values) * 0.95)
        results["latency_stats"]["p95"] = values[min(p95_idx, len(values) - 1)]
        del results["latency_stats"]["values"]

    return results


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Evaluate LLM prompt accuracy against test cases"
    )
    parser.add_argument(
        "--prompt", required=True, help="Prompt name (e.g., intake-triage)"
    )
    parser.add_argument(
        "--version", default="v2.0.0", help="Prompt version (default: v2.0.0)"
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--tags", help="Filter by tags (comma-separated)"
    )
    parser.add_argument(
        "--limit", type=int, help="Limit number of test cases"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Load and validate without calling API"
    )
    parser.add_argument(
        "--json", action="store_true", dest="output_json",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--all", action="store_true", help="Run all test cases (no limit)"
    )
    parser.add_argument(
        "--output-dir",
        help="Custom directory for saving evaluation results "
             "(default: llm-prompts/<prompt>/evaluation-results)",
    )
    args = parser.parse_args()

    print(f"SafeFlow Prompt Evaluation")
    print(f"  Prompt: {args.prompt}")
    print(f"  Version: {args.version}")
    print(f"  Model: {args.model}")
    print()

    # Load test cases
    cases = load_test_cases(args.prompt)
    print(f"Loaded {len(cases)} test cases")

    # Filter
    cases = filter_cases(cases, tags=args.tags, limit=args.limit)
    print(f"Running {len(cases)} test cases")
    print()

    # Run evaluation
    results = run_evaluation(
        args.prompt, args.version, cases, model=args.model, dry_run=args.dry_run,
    )

    # Output results
    if args.output_json:
        print(json.dumps(results, indent=2))
    else:
        print()
        print("=" * 50)
        print("RESULTS")
        print("=" * 50)
        print(f"Overall Accuracy: {results.get('overall_accuracy', 0)}%")
        print(f"Passed: {results['passed']} / {results['passed'] + results['failed']}")
        print(f"Duration: {results.get('duration_seconds', 0)}s")
        print()

        if results["by_category"]:
            print("By Category:")
            for cat, stats in sorted(results["by_category"].items()):
                acc = round(stats["passed"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0
                print(f"  {cat}: {acc}% ({stats['passed']}/{stats['total']})")
            print()

        if results.get("latency_stats", {}).get("avg"):
            print("Latency:")
            ls = results["latency_stats"]
            print(f"  Avg: {ls['avg']}s  P95: {ls.get('p95', 'N/A')}s  "
                  f"Min: {ls['min']}s  Max: {ls['max']}s")

    # Save results
    if not args.dry_run:
        if args.output_dir:
            results_dir = Path(args.output_dir)
        else:
            results_dir = Path(f"llm-prompts/{args.prompt}/evaluation-results")
        results_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_path = results_dir / f"eval_{args.version}_{timestamp}.json"
        with open(results_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {results_path}")


if __name__ == "__main__":
    main()
