# LLM Prompt Evaluation Metrics

## Key Metrics

### Accuracy Metrics

| Metric | Definition | Target | Critical Threshold |
|--------|-----------|--------|-------------------|
| Overall Accuracy | % of test cases where all fields match expected | > 90% | < 80% |
| Discipline Accuracy | % correct trade discipline classification | > 85% | < 75% |
| Urgency Accuracy | % correct urgency level classification | > 88% | < 80% |
| Emergency Detection | % of emergencies correctly identified as EMERGENCY | > 98% | < 95% |
| Routing Accuracy | % correct routing decisions | > 85% | < 75% |
| Confidence Calibration | Correlation between confidence score and actual accuracy | > 0.7 | < 0.5 |

### Operational Metrics

| Metric | Definition | Target | Critical Threshold |
|--------|-----------|--------|-------------------|
| Latency P50 | Median API response time | < 1.5s | > 3s |
| Latency P95 | 95th percentile response time | < 3s | > 5s |
| Cost per Call | Average API cost (input + output tokens) | < £0.008 | > £0.015 |
| JSON Parse Rate | % of responses that are valid JSON | > 99% | < 95% |
| False Emergency Rate | % of non-emergencies flagged as EMERGENCY | < 2% | > 5% |

## Evaluation Methodology

### Test Case Design

1. **Coverage**: Minimum 200 test cases spanning all disciplines and urgency levels
2. **Distribution**: Weighted towards common scenarios (standard maintenance ~40%)
3. **Edge cases**: Minimum 10% of test cases are edge cases (vague, multilingual, spam)
4. **Emergency cases**: Minimum 25 emergency-specific test cases
5. **Realism**: Messages use actual UK English with informal language, typos, and regional terms

### Evaluation Process

1. Load prompt version and test cases
2. Submit each test case to Claude API with configured parameters
3. Parse JSON response
4. Validate each field against expected values:
   - Exact match for categorical fields (discipline, urgency, routing)
   - Range check for numerical fields (confidence)
   - Presence check for safety flags
   - Keyword check for reasoning text
5. Aggregate results by category and tag
6. Calculate statistical metrics

### Pass/Fail Criteria

A test case **passes** when:
- Discipline matches expected value
- Urgency matches expected value
- Routing decision matches expected value
- Confidence is within expected range
- Safety flags are correctly set (for emergency cases)
- Required certifications are included

A test case **partially passes** when:
- One of discipline/urgency is correct but not both
- Routing is correct but confidence is outside range

### A/B Testing

- Two-proportion z-test at 95% confidence level
- Minimum 50 test cases per comparison
- Run against identical test set in random order
- Same model and temperature for both versions
- Statistical significance required before switching production prompt

## Monitoring and Alerting

### Continuous Monitoring

| Check | Frequency | Alert Threshold |
|-------|-----------|----------------|
| Accuracy spot-check (20 cases) | Daily | < 85% |
| Full evaluation (200 cases) | Weekly | < 90% |
| Emergency detection | Daily | Any miss |
| Latency monitoring | Real-time | P95 > 5s |
| Cost tracking | Daily | > £0.015/call |

### Alert Actions

- **Accuracy drop > 5%**: Investigate prompt, check for model changes, run full evaluation
- **Emergency miss**: Immediate review, consider rollback to previous version
- **Latency spike**: Check API status, consider model fallback
- **Cost increase**: Review token usage, optimise prompt length

## Continuous Improvement

### Prompt Optimisation Cycle

1. **Collect** failing test cases from production (manual review + automated flagging)
2. **Analyse** failure patterns (which disciplines, urgency levels, message types fail most)
3. **Hypothesise** prompt modifications (add examples, clarify rules, adjust wording)
4. **Test** with A/B framework against current version
5. **Deploy** if statistically significant improvement and no regressions
6. **Monitor** post-deployment accuracy for 48 hours

### Version Management

- Semantic versioning: MAJOR.MINOR.PATCH
- MAJOR: Output schema change or complete rewrite
- MINOR: New capabilities (new discipline, new edge case handling)
- PATCH: Wording improvements, example refinements
- Keep minimum 3 previous versions available for rollback
- Document all changes in CHANGELOG.md
