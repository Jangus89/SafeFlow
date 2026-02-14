# Test Suite

## Overview

Testing a no-code/low-code system requires different approaches than traditional software testing. This test suite validates:

1. **Prompt Quality** - Claude API prompts produce expected classifications and responses
2. **Webhook Payloads** - Inbound/outbound payloads match expected schemas
3. **Data Integrity** - Airtable schema constraints are enforced
4. **Integration Flows** - End-to-end workflows produce expected outcomes
5. **Edge Cases** - System handles malformed inputs gracefully

## Running Tests

```bash
# Install dependencies
pip install -r tests/requirements.txt

# Run all tests
python -m pytest tests/ -v

# Run specific test suite
python -m pytest tests/prompts/ -v
python -m pytest tests/webhooks/ -v
python -m pytest tests/integration/ -v

# Run with coverage
python -m pytest tests/ --cov=scripts --cov-report=html
```

## Test Structure

```
tests/
├── prompts/                 # Prompt regression tests
│   ├── test_classifier.py   # Classification accuracy
│   ├── test_extraction.py   # Data extraction accuracy
│   └── test_generation.py   # Response quality checks
├── webhooks/                # Payload validation tests
│   ├── test_inbound.py      # 360dialog webhook validation
│   └── test_transform.py    # Data transformation tests
├── integration/             # End-to-end flow tests
│   └── test_flows.py        # Workflow simulation tests
├── fixtures/                # Test data
│   ├── messages/            # Sample WhatsApp messages
│   ├── classifications/     # Expected classification outputs
│   └── webhooks/            # Sample webhook payloads
├── conftest.py              # Shared test configuration
└── requirements.txt         # Test dependencies
```

## Adding Tests

When modifying prompts:
1. Add test cases to the corresponding test file
2. Include edge cases (multilingual, ambiguous, empty)
3. Run full regression suite before deploying
4. Update fixtures if the classification schema changes
