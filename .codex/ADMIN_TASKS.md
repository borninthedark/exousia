# Admin Tasks & Test Conformance for AI Agents

This document provides specific guidance for AI agents (Claude, Codex, etc.) working on this codebase.

## 🎯 Primary Directive

**On every branch, before any code is committed: ENSURE ALL TESTS PASS and quality checks are clean.**

## Pre-Commit Checklist

### 1. Test Execution (MANDATORY)

```bash
# Run ALL tests - these MUST pass
python -m pytest api/tests/ -v --tb=short
python -m pytest tools/test_*.py -v
bats custom-tests/*.bats

# Check test coverage
pytest --cov=api --cov=tools --cov-report=term-missing
```

**Requirements:**
- ✅ All existing tests must pass
- ✅ Coverage must be ≥80% for api/, ≥75% for tools/
- ✅ New code must have corresponding tests

### 2. Code Quality (MANDATORY)

```bash
# Linting - must be clean
ruff check api/ tools/
pylint api/**/*.py tools/*.py || echo "Review pylint warnings"

# Type checking
mypy api/ --strict

# Shell script validation
shellcheck custom-scripts/*
```

### 3. Security Scan

```bash
# Run security scans
semgrep --config auto api/ tools/

# Check for secrets
git secrets --scan

# Dependency vulnerabilities
pip-audit || echo "Review vulnerabilities"
```

### 4. Documentation Updates

**When you modify code, update documentation:**

- `README.md` - User-facing changes
- `api/README.md` - API changes
- `tools/README.md` - Tool changes
- Inline docstrings - All new functions/classes
- `docs/WEBHOOK_API.md` - Webhook/trigger changes

## Common Scenarios

### Scenario 1: Adding New API Endpoint

```bash
# Step 1: Implement endpoint in api/routers/*.py
# Step 2: Add Pydantic models in api/models.py
# Step 3: Create tests in api/tests/test_*.py

# Required tests:
# - Happy path (200 OK)
# - Invalid input (400/422)
# - Auth failure (401/403)
# - Not found (404)
# - Server error handling (500)

# Step 4: Update API documentation
# - Add examples to api/README.md
# - Document request/response schemas

# Step 5: Run tests
pytest api/tests/test_<feature>.py -v

# Step 6: Verify coverage
pytest --cov=api.routers.<module> --cov-report=term
```

### Scenario 2: Modifying Build Pipeline

```bash
# Step 1: Update workflow in .github/workflows/build.yml
# Step 2: Update resolve_build_config.py if needed
# Step 3: Test locally with act or similar

# Required validations:
# - YAML syntax is valid
# - Environment variables are documented
# - Fallback logic is tested

# Step 4: Update documentation
# - Document new workflow inputs
# - Add examples to README.md

# Step 5: Create PR with test plan
```

### Scenario 3: Adding New Package Definition

```bash
# Step 1: Create YAML in packages/desktop-environments/ or packages/window-managers/
# Step 2: Validate YAML structure

# Required validations:
python tools/package_loader.py --validate packages/<category>/<name>.yml

# Step 3: Add to YamlSelectorService mappings (if needed)
# Step 4: Test auto-selection logic

pytest api/tests/test_yaml_selector.py -v

# Step 5: Document in README
```

### Scenario 4: Fixing Bug

```bash
# Step 1: Write failing test that reproduces bug
# Step 2: Implement fix
# Step 3: Verify test now passes
# Step 4: Add regression test to prevent recurrence

# Example test structure:
def test_bug_<issue_number>_<description>():
    """Regression test for bug #<issue_number>."""
    # Setup that triggers bug
    # Assert expected behavior (not buggy behavior)
```

## Testing Best Practices

### Unit Tests

```python
# api/tests/test_feature.py
import pytest
from fastapi.testclient import TestClient

def test_endpoint_success(client: TestClient):
    """Test successful response."""
    response = client.post("/api/endpoint", json={"key": "value"})
    assert response.status_code == 200
    assert response.json()["result"] == "expected"

def test_endpoint_validation_error(client: TestClient):
    """Test validation error handling."""
    response = client.post("/api/endpoint", json={})
    assert response.status_code == 422
```

### Integration Tests

```python
# api/tests/test_integration_workflow.py
async def test_full_build_workflow(db: AsyncSession, client: TestClient):
    """Test complete build trigger -> status -> completion workflow."""
    # 1. Trigger build
    # 2. Check status
    # 3. Simulate completion
    # 4. Verify final state
```

### Shell Script Tests

```bash
# custom-tests/script_tests.bats
@test "script handles missing file" {
    run ./custom-scripts/my-script /nonexistent/file
    [ "$status" -eq 1 ]
    [[ "$output" =~ "Error: File not found" ]]
}

@test "script produces expected output" {
    run ./custom-scripts/my-script test-input.yml
    [ "$status" -eq 0 ]
    [ -f "expected-output.txt" ]
}
```

## Documentation Templates

### Function Docstring Template

```python
def function_name(param1: str, param2: int = 10) -> dict:
    """
    Brief one-line description.

    Longer description with context about why this function exists
    and when it should be used.

    Args:
        param1: Description of first parameter
        param2: Description of second parameter (default: 10)

    Returns:
        Dictionary containing:
            - key1: description
            - key2: description

    Raises:
        ValueError: When param1 is empty
        RuntimeError: When operation fails

    Example:
        >>> result = function_name("test", 5)
        >>> print(result["key1"])
        expected_value
    """
```

### API Endpoint Documentation Template

````markdown
### POST /api/endpoint

Description of what this endpoint does.

**Request Body:**
```json
{
    "field1": "string",
    "field2": 123,
    "optional_field": "string"
}
```

**Response (200 OK):**
```json
{
    "id": 1,
    "status": "success",
    "result": {...}
}
```

**Error Responses:**
- 400: Invalid input
- 401: Unauthorized
- 404: Resource not found
- 500: Server error

**Example:**
```bash
curl -X POST http://localhost:8000/api/endpoint \
  -H "Content-Type: application/json" \
  -d '{"field1": "value", "field2": 123}'
```
````

## Common Pitfalls to Avoid

### ❌ Don't Do This

```python
# Missing tests
def new_feature():
    # No tests written = NO MERGE

# Hardcoded values
API_KEY = "sk-1234567890"  # NEVER commit secrets

# No error handling
def risky_operation():
    result = api_call()  # What if this fails?
    return result

# Incomplete docstrings
def complex_function():
    """Does stuff."""  # Not helpful!
```

### ✅ Do This Instead

```python
# With tests
def new_feature():
    """Proper implementation."""
    pass

# tests/test_feature.py
def test_new_feature():
    result = new_feature()
    assert result == expected

# Proper configuration
API_KEY = os.environ.get("API_KEY")  # From environment
if not API_KEY:
    raise ValueError("API_KEY environment variable required")

# With error handling
def safe_operation():
    try:
        result = api_call()
        return result
    except APIError as e:
        logger.error(f"API call failed: {e}")
        raise

# Complete docstrings
def complex_function(param: str) -> dict:
    """
    Perform complex operation on param.

    Args:
        param: Input string to process

    Returns:
        Dictionary with processed results

    Raises:
        ValueError: If param is invalid
    """
```

## Performance Testing

For performance-critical changes:

```python
# Use pytest-benchmark
def test_performance_critical_function(benchmark):
    """Ensure function completes within acceptable time."""
    result = benchmark(my_function, large_input)
    assert result == expected
    # Benchmark automatically measures time
```

## Integration with Git Hooks

Set up pre-commit hook:

```bash
# .git/hooks/pre-commit
#!/bin/bash

echo "🔍 Running pre-commit checks..."

# Fast checks first (fail early)
ruff check api/ tools/ || exit 1
mypy api/ --strict || exit 1

# Run tests
pytest api/tests/ -q || exit 1

echo "✅ Pre-commit checks passed"
```

## When to Ask for Human Review

AI agents should flag these for human review:

- **Security-sensitive changes** (auth, encryption, secrets handling)
- **Database migrations** (schema changes, data migrations)
- **API contract changes** (breaking changes to public APIs)
- **Performance-critical paths** (hot loops, database queries)
- **Complex business logic** (non-trivial algorithms, edge cases)

## Resources

- **pytest documentation**: https://docs.pytest.org/
- **mypy documentation**: https://mypy.readthedocs.io/
- **ruff documentation**: https://docs.astral.sh/ruff/
- **Bats testing**: https://github.com/bats-core/bats-core

---

**Last Updated**: 2025-12-03
**Maintained by**: AI Agents + Human Maintainers
**For questions**: Open an issue or contact maintainers
