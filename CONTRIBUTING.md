# Contributing to SafeFlow

Thank you for your interest in contributing to SafeFlow. This document provides guidelines and standards for contributing.

## Development Workflow

1. **Branch from `main`** for all changes
2. **Create a feature branch** with descriptive name: `feature/scenario-a-retry-logic`
3. **Make changes** following the code standards below
4. **Run validation** before committing:
   ```bash
   python scripts/validation/validate-airtable-schema.py
   python tests/validation/validate-scenarios.py
   ```
5. **Commit** with conventional commit messages
6. **Create a Pull Request** using the PR template

## Commit Message Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types
- `feat`: New feature or capability
- `fix`: Bug fix
- `docs`: Documentation changes
- `schema`: Airtable schema changes
- `scenario`: Make.com scenario changes
- `prompt`: LLM prompt changes
- `test`: Test additions or modifications
- `ci`: CI/CD pipeline changes
- `refactor`: Code restructuring
- `chore`: Maintenance tasks

### Scopes
- `scenario-a`, `scenario-b`, `scenario-c`, `scenario-d`, `scenario-e`
- `airtable`, `schema`, `migration`
- `llm`, `intake-triage`, `quote-analysis`
- `deploy`, `monitoring`, `docs`

### Examples
```
feat(scenario-b): add auto-reassignment logic for escalated items
fix(schema): correct formula for time_in_current_state
prompt(intake-triage): improve emergency detection accuracy
docs(runbook): add procedure for 360dialog outage
```

## Code Standards

### Python
- PEP 8 compliance
- Type hints on all function signatures
- Docstrings on all public functions
- `#!/usr/bin/env python3` shebang on executable scripts

### JSON
- Valid JSON (no trailing commas, no comments)
- 2-space indentation
- Prettified (not minified)
- Schema files use consistent field naming

### Bash
- `set -euo pipefail` at the top
- Quote all variables
- Use `shellcheck` for linting

### Markdown
- ATX-style headers (`#` not `===`)
- Fenced code blocks with language identifier
- Tables aligned with pipes
- UK English spelling

## Testing Requirements

### Before Merging
- [ ] All JSON files validate (`python tests/validation/validate-scenarios.py`)
- [ ] Airtable schema validates (`python scripts/validation/validate-airtable-schema.py`)
- [ ] Migration tests pass (`pytest airtable/tests/`)
- [ ] No secrets in committed files

### For Prompt Changes
- [ ] Run evaluation against test cases
- [ ] Emergency detection accuracy >= 98%
- [ ] Overall accuracy >= 90%
- [ ] A/B test if changing production prompt

### For Scenario Changes
- [ ] Test payloads updated
- [ ] Metadata.json updated with new version
- [ ] CHANGELOG.md updated
- [ ] README.md reflects changes

## Airtable Schema Changes

1. **Never modify `schema.json` directly** for production changes
2. Create a numbered migration file in `airtable/migrations/`
3. Update `schema.json` to reflect the post-migration state
4. Update individual table JSON files
5. Run schema validation
6. Document the change in migration README

## Security

- **Never commit** `.env` files, API keys, or credentials
- **Never include** real tenant data in test fixtures
- Use placeholder values: `+447700900000` (Ofcom test range)
- Review `.gitignore` before committing

## Questions?

Open a GitHub Issue with the `question` label.
