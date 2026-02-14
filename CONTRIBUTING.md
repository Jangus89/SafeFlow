# Contributing to SafeFlow

## Development Workflow

### Making Changes

1. **Configuration Changes** (prompts, schemas, mappings):
   - Edit the relevant file in this repository
   - Run affected tests
   - Apply the change in the corresponding platform (Make.com, Airtable)
   - Commit the change with a descriptive message

2. **Prompt Changes**:
   - Edit the prompt file in `prompts/`
   - Run prompt regression tests: `pytest tests/prompts/ -v`
   - Test with real messages in development environment
   - Monitor classification confidence for 24h after deployment
   - Update prompt changelog

3. **Make.com Scenario Changes**:
   - Make changes in Make.com visual editor
   - Export updated blueprint
   - Update the corresponding JSON file in `make-scenarios/`
   - Document the change in commit message

4. **Airtable Schema Changes**:
   - Make changes in Airtable
   - Update `airtable/schemas/base-schema.json`
   - Update any affected Make.com scenarios
   - Run schema validation: `python scripts/setup/validate_config.py`

### Code Standards

- JSON files: 2-space indentation, sorted keys where logical
- Python: Follow PEP 8, use type hints for function signatures
- Markdown: One sentence per line for better git diffs
- Prompt files: Include version number and changelog

### Commit Messages

Follow conventional commit format:

```
type(scope): description

[optional body]
```

Types:
- `feat` - New feature or workflow
- `fix` - Bug fix
- `prompt` - Prompt engineering changes
- `schema` - Airtable schema changes
- `docs` - Documentation updates
- `test` - Test additions or modifications
- `config` - Configuration changes
- `refactor` - Workflow restructuring

Examples:
```
feat(escalation): add level 4 director escalation path
prompt(classifier): improve emergency detection for gas leaks
schema(airtable): add Insurance Expiry field to Contractors
fix(inbound): handle empty message body gracefully
```

### Testing Requirements

Before deploying any change:

1. Run validation: `python scripts/setup/validate_config.py`
2. Run affected test suite
3. Test in development environment with sample messages
4. Verify no regression in Error Log after deployment

### Security

- NEVER commit API keys, tokens, or credentials
- NEVER log message content in monitoring (use reference numbers)
- Always use `.env` for sensitive configuration
- Rotate keys every 90 days
- Report security concerns immediately
