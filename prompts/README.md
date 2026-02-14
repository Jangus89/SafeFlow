# Prompt Engineering Guide

## Overview

All Claude API prompts used in SafeFlow are version-controlled in this directory. Prompts are the core intelligence layer — treat them with the same rigor as production code.

## Directory Structure

```
prompts/
├── system/              # System prompts (persona, rules, constraints)
├── classification/      # Intent classification prompts
├── extraction/          # Structured data extraction prompts
├── generation/          # Response generation prompts
└── README.md            # This file
```

## Prompt Design Principles

1. **Structured Output**: All prompts request JSON output with explicit schemas
2. **Few-Shot Examples**: Include 3-5 examples for classification tasks
3. **Guard Rails**: Every prompt includes explicit constraints on what NOT to do
4. **Context Window**: Prompts are designed to fit within 4K tokens including context
5. **Temperature**: Classification = 0.2, Generation = 0.4, Extraction = 0.2
6. **Versioning**: Each prompt file includes a version number and changelog

## Testing Prompts

Prompt changes require regression testing before deployment:

1. Run test suite: `python tests/prompts/run_prompt_tests.py`
2. Review classification accuracy against test fixtures
3. Check for regressions in edge cases
4. Update test fixtures if intent schema changes

## Prompt Update Process

1. Create new version of prompt file (increment version)
2. Run prompt regression tests
3. Review output quality on sample messages
4. Deploy via Make.com HTTP module update
5. Monitor classification confidence for 24h
6. Document changes in prompt changelog
