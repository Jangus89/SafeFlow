"""Tests for the facilities classifier prompt.

These tests validate that the classifier prompt produces expected results.
Requires ANTHROPIC_API_KEY environment variable for live tests.

Run with: pytest tests/prompts/test_classifier.py -v
Skip live API tests: pytest tests/prompts/test_classifier.py -v -m "not live"
"""

import json
import os
from pathlib import Path

import pytest

# Mark all tests in this module
pytestmark = pytest.mark.prompts


VALID_INTENTS = [
    "maintenance_request",
    "maintenance_update",
    "rent_inquiry",
    "general_inquiry",
    "emergency",
    "feedback",
    "greeting",
    "unknown",
]

VALID_URGENCIES = ["low", "medium", "high", "emergency"]
VALID_SENTIMENTS = ["positive", "neutral", "negative", "distressed"]


class TestClassifierPromptStructure:
    """Test that the classifier prompt file is well-formed."""

    def test_prompt_file_exists(self, project_root):
        """Classifier prompt file should exist."""
        prompt_path = project_root / "prompts" / "system" / "facilities-classifier.md"
        assert prompt_path.exists(), f"Prompt file not found: {prompt_path}"

    def test_prompt_contains_output_schema(self, project_root):
        """Prompt should define the expected output JSON schema."""
        prompt_path = project_root / "prompts" / "system" / "facilities-classifier.md"
        content = prompt_path.read_text()
        assert '"intent"' in content
        assert '"confidence"' in content
        assert '"urgency"' in content
        assert '"sentiment"' in content

    def test_prompt_contains_examples(self, project_root):
        """Prompt should contain few-shot examples."""
        prompt_path = project_root / "prompts" / "system" / "facilities-classifier.md"
        content = prompt_path.read_text()
        # Should have multiple examples
        assert content.count("Message:") >= 3, "Prompt should have at least 3 examples"

    def test_prompt_contains_constraints(self, project_root):
        """Prompt should contain explicit constraints."""
        prompt_path = project_root / "prompts" / "system" / "facilities-classifier.md"
        content = prompt_path.read_text()
        assert "NEVER" in content, "Prompt should have NEVER constraints"
        assert "ALWAYS" in content, "Prompt should have ALWAYS constraints"

    def test_all_intents_documented(self, project_root):
        """All valid intents should be documented in the prompt."""
        prompt_path = project_root / "prompts" / "system" / "facilities-classifier.md"
        content = prompt_path.read_text()
        for intent in VALID_INTENTS:
            assert intent in content, f"Intent '{intent}' not documented in prompt"


class TestClassificationTestCases:
    """Validate classification test case structure."""

    def test_test_cases_have_required_fields(self, classification_test_cases):
        """Each test case should have input and expected_intent."""
        for case in classification_test_cases:
            assert "input" in case, f"Test case missing 'input': {case}"
            assert "expected_intent" in case, f"Test case missing 'expected_intent': {case}"

    def test_test_cases_have_valid_intents(self, classification_test_cases):
        """Expected intents should be from the valid set."""
        for case in classification_test_cases:
            assert case["expected_intent"] in VALID_INTENTS, (
                f"Invalid expected intent: {case['expected_intent']}"
            )

    def test_test_cases_cover_all_critical_intents(self, classification_test_cases):
        """Test cases should cover all critical intent types."""
        covered_intents = {case["expected_intent"] for case in classification_test_cases}
        critical_intents = {
            "maintenance_request",
            "emergency",
            "rent_inquiry",
            "greeting",
        }
        missing = critical_intents - covered_intents
        assert not missing, f"Missing test cases for critical intents: {missing}"

    def test_emergency_cases_have_emergency_urgency(self, classification_test_cases):
        """Emergency intent cases should have emergency urgency."""
        emergency_cases = [
            c for c in classification_test_cases if c["expected_intent"] == "emergency"
        ]
        for case in emergency_cases:
            if "expected_urgency" in case:
                assert case["expected_urgency"] == "emergency", (
                    f"Emergency case should have emergency urgency: {case['input']}"
                )


@pytest.mark.live
class TestClassifierLiveAPI:
    """Live API tests — only run when ANTHROPIC_API_KEY is available.

    These tests call the actual Claude API to validate prompt behavior.
    Run with: pytest tests/prompts/test_classifier.py -v -m live
    """

    @pytest.fixture(autouse=True)
    def check_api_key(self):
        """Skip if no API key available."""
        if not os.environ.get("ANTHROPIC_API_KEY"):
            pytest.skip("ANTHROPIC_API_KEY not set")

    def _classify(self, message: str) -> dict:
        """Send a message through the classifier and return parsed result."""
        import anthropic

        client = anthropic.Anthropic()
        prompt_path = (
            Path(__file__).parent.parent.parent
            / "prompts"
            / "system"
            / "facilities-classifier.md"
        )
        content = prompt_path.read_text()

        # Extract the system prompt from the markdown
        # It's between the ``` delimiters in the System Prompt section
        lines = content.split("```")
        system_prompt = lines[1] if len(lines) > 1 else content

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            temperature=0.2,
            system=system_prompt,
            messages=[
                {"role": "user", "content": f"Classify this message:\n\n{message}"}
            ],
        )

        return json.loads(response.content[0].text)

    def test_maintenance_classification(self):
        """Kitchen tap message should classify as maintenance_request."""
        result = self._classify("The kitchen tap is leaking")
        assert result["intent"] == "maintenance_request"
        assert result["confidence"] > 0.8

    def test_emergency_classification(self):
        """Gas smell should classify as emergency."""
        result = self._classify("I can smell gas in my apartment")
        assert result["intent"] == "emergency"
        assert result["urgency"] == "emergency"

    def test_rent_classification(self):
        """Rent question should classify as rent_inquiry."""
        result = self._classify("When is my rent due?")
        assert result["intent"] == "rent_inquiry"

    def test_output_schema_valid(self):
        """Response should contain all required fields."""
        result = self._classify("The bathroom light keeps flickering")
        required_fields = [
            "intent", "confidence", "urgency", "sentiment",
            "language_detected", "entities", "requires_followup",
        ]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"
