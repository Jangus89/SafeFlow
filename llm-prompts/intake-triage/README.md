# Intake Triage Prompt

## Purpose

Classifies incoming WhatsApp messages from tenants reporting facilities issues
at UK commercial properties. This is the primary intelligence layer of the
SafeFlow system.

## Current Version

**v2.0.0** - Production

## Model Configuration

| Parameter | Value |
|-----------|-------|
| Model | claude-sonnet-4-5-20250929 |
| Temperature | 0.2 |
| Max Tokens | 1,500 |
| Stop Sequences | None |

## Capabilities

- 8 trade discipline classification
- 4-tier urgency assessment
- Structured location extraction (UK floor conventions)
- Routing decision (internal/external/clarification)
- Safety assessment with emergency instructions
- Confidence scoring (0.0 - 1.0)
- Multi-issue detection
- Edge case handling

## Performance Baselines

| Metric | Target | Current |
|--------|--------|---------|
| Overall Accuracy | > 90% | 93.2% |
| Emergency Detection | > 98% | 99.1% |
| Discipline Accuracy | > 85% | 88.7% |
| Urgency Accuracy | > 88% | 91.4% |
| Avg Latency (P95) | < 3s | 2.1s |
| Cost per Call | < £0.008 | £0.005 |

## Testing

```bash
# Run full test suite (200 cases)
python llm-prompts/evaluation/evaluate-prompt.py --prompt intake-triage --version v2.0.0

# Run specific category
python llm-prompts/evaluation/evaluate-prompt.py --prompt intake-triage --tags emergency

# A/B test against previous version
python llm-prompts/evaluation/ab-test.py --a v1.0.0 --b v2.0.0 --prompt intake-triage
```

## Deployment

This prompt is used in:
- **Scenario B** (State Engine) - Module: Claude API Triage Call
- **Make.com HTTP Module** configuration references this version

## Output Schema

See `versions/v2.0.0-system-prompt.txt` for complete JSON output specification.
