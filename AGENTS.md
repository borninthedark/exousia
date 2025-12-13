# AGENTS.md - GPT-Codex AI Agent Configuration

## Overview

This document defines the AI agent configurations, workflows, and best practices used in the Exousia project for AI-assisted development. Exousia leverages multiple AI agents (Claude, GPT Codex, and specialized coding assistants) to enhance development velocity, code quality, and system reliability.

## Project Context

**Exousia** is a declarative bootc image builder with:
- **FastAPI backend** (`api/`) for build orchestration and configuration management
- **Python tools** (`tools/`) for YAML transpilation, package validation, and build configuration
- **GitHub Actions CI/CD** (`.github/workflows/`) for automated builds, tests, and deployments
- **YAML-based configuration** (`yaml-definitions/`) for defining bootc images
- **Comprehensive test suite** (52+ tests covering API, tools, and integration)

### Project Structure

```
exousia/
├── .github/workflows/     # CI/CD pipeline definitions
│   └── build.yml         # Main build workflow
├── api/                  # FastAPI backend
│   ├── routers/         # API endpoint handlers
│   ├── services/        # Business logic services
│   ├── tests/           # API and integration tests
│   └── models.py        # Pydantic data models
├── tools/               # Python CLI tools
│   ├── resolve_build_config.py    # Build configuration resolver
│   ├── yaml-to-containerfile.py  # YAML → Containerfile transpiler
│   ├── package_loader.py          # Package definition loader
│   └── validate_installed_packages.py  # Package validator
├── yaml-definitions/    # YAML configuration files
├── custom-scripts/      # Shell scripts for builds
├── custom-tests/        # Bats integration tests
├── packages/           # Package definitions
│   ├── common/         # Base packages
│   ├── desktop-environments/
│   └── window-managers/
└── docs/               # Documentation
```

## Philosophy: AI-Augmented Development

Exousia embraces AI as a collaborative development partner rather than a replacement for human expertise. The goal is to:

- **Accelerate Development**: Leverage AI for rapid prototyping, boilerplate generation, and iterative refinement
- **Enhance Quality**: Use AI for code review, test generation, and documentation
- **Maintain Control**: Keep humans in the decision-making loop for architecture and critical logic
- **Preserve Transparency**: Document AI contributions and maintain clear attribution

### Test-Driven Development (TDD) - Core Principle

**ALL development work in Exousia MUST follow test-driven development practices:**

1. **Write Tests First**: Before implementing any feature or fix, write the test that validates the expected behavior
2. **Red-Green-Refactor**: Follow the TDD cycle:
   - **Red**: Write a failing test that defines the desired behavior
   - **Green**: Implement the minimal code needed to make the test pass
   - **Refactor**: Clean up the code while keeping tests passing
3. **No Untested Code**: Every new function, class, or feature must have corresponding tests
4. **Test Coverage**: Maintain minimum coverage thresholds (80% for API, 75% for tools)
5. **Integration Tests**: Complex features require both unit tests and integration tests

**Why TDD is mandatory:**
- Prevents regressions and ensures code correctness
- Provides living documentation of expected behavior
- Enables confident refactoring and continuous improvement
- Catches bugs early in the development cycle
- Facilitates AI-assisted development by providing clear validation criteria

## 🔴 HIGH PRIORITY: Continuous Quality Requirements

**These requirements MUST be met on EVERY branch before merging, regardless of the feature or fix being implemented.**

### Test Conformance (Mandatory)

Every branch must ensure:

#### 1. **Existing Tests Pass**
```bash
# Run all existing tests before starting work
python -m pytest api/tests/ -v
python -m pytest tools/test_*.py -v

# Bats tests for shell scripts
bats custom-tests/*.bats
```

#### 2. **New Tests for New Code**
- **New features**: Must include unit tests and integration tests
- **Bug fixes**: Must include regression test that would have caught the bug
- **API changes**: Must update API tests and include examples
- **Configuration changes**: Must validate with test cases

```bash
# Example: Adding new API endpoint
# REQUIRED: Add tests in api/tests/test_<feature>.py

# Example: Adding new YAML definition
# REQUIRED: Add validation tests
```

#### 3. **Test Coverage Requirements**
```bash
# Minimum coverage thresholds
pytest --cov=api --cov-report=term --cov-fail-under=80
pytest --cov=tools --cov-report=term --cov-fail-under=75
```

#### 4. **Linting & Type Checks**
```bash
# Python linting (must pass)
ruff check api/ tools/
pylint api/**/*.py tools/*.py

# Type checking
mypy api/ --strict

# Shell script linting
shellcheck custom-scripts/*
```

### Admin Tasks Checklist

Before opening a PR, complete this checklist:

- [ ] **All tests pass** (pytest, bats, integration tests)
- [ ] **Linting passes** (ruff, pylint, shellcheck)
- [ ] **Type checks pass** (mypy for Python code)
- [ ] **Documentation updated** (README, API docs, inline comments)
- [ ] **CHANGELOG.md updated** (if applicable)
- [ ] **API examples updated** (if API changes were made)
- [ ] **Security scan clean** (no new vulnerabilities introduced)
- [ ] **Performance tested** (if performance-critical code was changed)
- [ ] **Backwards compatibility verified** (or breaking changes documented)

## Common Development Scenarios (Exousia-Specific)

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
# - Add examples to README.md and WEBHOOK_API.md

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

### Scenario 5: Updating YAML Path Resolution

The project uses automatic YAML path resolution in `tools/resolve_build_config.py`:

1. **Exact path**: Try the path as specified
2. **yaml-definitions/ directory**: Prepend `yaml-definitions/` and try again
3. **Repo-wide search**: Use `find` to search entire repo (prefer yaml-definitions matches)
4. **Security**: Reject path traversal attempts (`..` or absolute paths)

When modifying this logic:
- Update tests in `api/tests/test_resolve_build_config.py`
- Ensure path traversal protection remains intact
- Document changes in `docs/WEBHOOK_API.md`

### Scenario 6: Modifying yaml-to-containerfile Transpiler

The YAML-to-Containerfile transpiler (`tools/yaml-to-containerfile.py`) is a critical component that converts BlueBuild-style YAML definitions into Dockerfile/Containerfile format:

```bash
# Step 1: Understand the transpiler architecture
# Key components:
# - BuildContext: Holds build configuration (image_type, fedora_version, enable_plymouth, enable_rke2, etc.)
# - ContainerfileGenerator: Main transpiler class
# - Module processors: _process_script_module, _process_files_module, _process_package_loader_module, etc.

# Step 2: Test existing functionality before changes
python3 tools/test_yaml_to_containerfile.py

# Step 3: When adding new conditionals:
# - Add to BuildContext dataclass
# - Extract from build config in main()
# - Implement evaluation in _evaluate_condition()
# - Update tests

# Example: Adding enable_feature conditional
# 1. Add to BuildContext:
@dataclass
class BuildContext:
    enable_feature: bool  # New field

# 2. Extract from config:
enable_feature = build_config.get("enable_feature", False)

# 3. Add evaluation:
if left == "enable_feature":
    return self.context.enable_feature == (right.lower() == "true")

# Step 4: Script rendering best practices:
# - Backslash continuations: _render_script_lines handles automatic semicolon insertion
# - Compound statements: Keywords like fi/done/esac get proper semicolons before next command
# - Heredocs: Supported but avoid when static files can be used (Hadolint compatibility)
# - Comments: Preserved verbatim in generated Containerfile

# Step 5: Required validations:
# - Generate test Containerfile: python3 tools/yaml-to-containerfile.py -c adnyeus.yml -o /tmp/test.txt
# - Run hadolint: hadolint /tmp/test.txt
# - Verify build: buildah build -f /tmp/test.txt
# - Run unit tests: python3 tools/test_yaml_to_containerfile.py
# - Test with conditions: Verify modules skip/include based on conditionals

# Step 6: Update documentation
# - Add examples to tools/README.md
# - Document new conditionals in YAML schema
```

**Important Transpiler Development Principles:**
- **Static files over heredocs**: Prefer COPY instructions with static files over RUN + heredoc
- **Hadolint validation**: All generated Containerfiles must pass Hadolint linting
- **Conditional evaluation**: Support image_type, enable_plymouth, enable_rke2, use_upstream_sway_config
- **Shell syntax**: Properly handle backslash continuations, compound statements, and quoted strings
- **Test coverage**: Add unit tests for any new module processors or conditionals
- **Error messages**: Provide clear error messages for invalid YAML or unsupported features

### Scenario 7: Working with RKE2 Integration

RKE2 (Rancher Kubernetes Engine 2) is integrated into Exousia as an optional bootc feature. When working with RKE2:

```bash
# Step 1: Enable RKE2 in your YAML definition
# Set enable_rke2: true in adnyeus.yml or your custom YAML

# Step 2: Use the rke2_ops Python module for all operations
# Located at tools/rke2_ops.py - DO NOT create shell scripts

# Available operations:
python3 tools/rke2_ops.py registry start    # Start local registry
python3 tools/rke2_ops.py vm build          # Build bootc disk image
python3 tools/rke2_ops.py vm create         # Create VM
python3 tools/rke2_ops.py vm start          # Start VM
python3 tools/rke2_ops.py vm status         # Check status
python3 tools/rke2_ops.py kubeconfig        # Get kubeconfig
python3 tools/rke2_ops.py quickstart        # Run all steps

# Or use Makefile targets:
make rke2-quickstart                        # Complete automated setup
make rke2-registry-start                    # Start registry
make rke2-vm-build                          # Build VM image
make rke2-vm-status                         # Check VM status

# Step 3: Test RKE2 integration
# Run the integration tests (now enabled by default)
ENABLE_RKE2=true bats custom-tests/image_content.bats

# Step 4: Required validations when modifying RKE2:
# - All 10 RKE2 integration tests must pass:
#   1. RKE2 binary installation
#   2. kubectl installation
#   3. Configuration files (registries.yaml, config.yaml)
#   4. Systemd drop-in directory
#   5. rke2_ops management tool
#   6. bootc kargs configuration
#   7. Data directory creation
#   8. MOTD configuration
#   9. Dependencies installation
#   10. Kubernetes repository configuration
# - Verify installation follows official RKE2 docs:
#   https://docs.rke2.io/install/methods
#   https://docs.rke2.io/install/quickstart
# - Test registry connectivity (192.168.122.1:5000)
# - Verify kubeconfig export works
# - Check systemd integration (rke2-server.service)

# Step 5: Update documentation
# - docs/RKE2_INTEGRATION.md for feature changes
# - docs/RKE2_BOOTC_SETUP.md for setup procedures
# - k8s/rke2/QUICKSTART.md for quick reference
# - README.md acknowledgements section
```

**Important RKE2 Development Principles:**
- **No shell scripts**: Use `tools/rke2_ops.py` for all RKE2 operations
- **Follow official docs**: Reference https://docs.rke2.io for installation methods
- **Test thoroughly**: RKE2 integration tests verify binary, config, systemd, and networking
- **Default enabled**: `enable_rke2` defaults to `true` in GitHub Actions and should remain so
- **Registry-first**: RKE2 uses local Podman registry on libvirt bridge (192.168.122.1:5000)
- **Bootc integration**: RKE2 is deployed via bootc image with proper kernel args and SELinux contexts
- **Prefer static files**: Use static repository files (custom-repos/*.repo) over dynamically generated heredocs
- **Hadolint compatibility**: Avoid shell heredocs in Containerfile generation; they confuse Hadolint's parser

## Common Pitfalls & Lessons Learned

### Containerfile Generation

**Issue**: Hadolint fails with "unexpected '[' expecting Dockerfile directive"
**Cause**: Shell heredocs in RUN commands confuse Hadolint's parser
**Solution**: Use static files (COPY) instead of heredocs. Example:
```yaml
# ❌ BAD: Heredoc in RUN command
- type: script
  scripts:
    - |
      cat <<'EOF' > /etc/yum.repos.d/kubernetes.repo
      [kubernetes]
      name=Kubernetes
      baseurl=https://pkgs.k8s.io/core:/stable:/v1.34/rpm/
      EOF

# ✅ GOOD: Static file with COPY
- type: files
  files:
    - src: custom-repos/kubernetes.repo
      dst: /etc/yum.repos.d/
      mode: "0644"
```

**Issue**: "RUN: command not found" errors in generated Containerfile
**Cause**: Multiple RUN commands being incorrectly merged into a single command
**Solution**: Verify each script module generates a separate RUN instruction. Check module separation in YAML.

**Issue**: Backslash continuation syntax errors (`\;`)
**Cause**: Script renderer adding semicolons after backslash continuations
**Solution**: The transpiler now detects lines ending with `\` and skips semicolon insertion

**Issue**: "unexpected tokens after compound command" (SC1141)
**Cause**: Missing semicolons after fi/done/esac before next command
**Solution**: The transpiler now adds semicolons after compound statement enders (fi, done, esac)

### Directory Creation in Images

**Issue**: `/mnt` directory creation failures in bootc images
**Cause**: Attempting to create system directories that are guaranteed to exist
**Solution**: Don't create standard system directories (/mnt, /tmp, /var, etc.). Only create application-specific subdirectories if needed at build time.

**Best Practice**: For mount points and runtime directories, let cloud-init or systemd tmpfiles.d handle creation at runtime.

### Package Management

**Issue**: Package file conflicts (e.g., swaylock vs swaylock-effects)
**Cause**: Not removing conflicting packages before installation
**Solution**: Use packages/common/remove.yml to remove conflicting packages. The package-loader module processes removals BEFORE installations.

**Issue**: Missing COPR repositories for specialized packages
**Cause**: Repository not added to custom-repos/ or not configured in tools/copr_manager.py
**Solution**:
1. Add `.repo` file to custom-repos/
2. Register in tools/copr_manager.py COPR_REPOS dict
3. Test with package-loader module

### Testing

**Issue**: Tests pass locally but fail in CI
**Cause**: Different default values for build flags (enable_rke2, enable_plymouth, etc.)
**Solution**: Check .github/workflows/build.yml for default input values. Ensure tests account for both enabled and disabled states.

**Issue**: Bats tests skip unexpectedly
**Cause**: Helper functions like is_rke2_enabled() checking environment variables
**Solution**: Set ENABLE_RKE2=true when running tests that depend on RKE2 features

## Key Project Features

### Automatic YAML Path Resolution (Added: 2025-12-04)

The build system automatically resolves YAML configuration paths:
- Users can specify just a filename: `sway-bootc.yml`
- System searches: exact path → yaml-definitions/ → entire repo
- Prevents path traversal attacks
- Documented in `docs/WEBHOOK_API.md`

### Cron Schedule (Updated: 2025-12-04)

- Nightly builds run at 3:10 AM UTC
- Schedule: `10 3 * * *` in `.github/workflows/build.yml`

### Build Status Badges

The project uses custom badges in README.md:
- **Reiatsu** (霊圧, spiritual pressure) - Build status
- **Last Build** - Dynamic badge showing OS version and desktop environment
- **Code Quality** - Workflow status
- **Highly Experimental** - Warning badge

Code coverage badge was removed as of 2025-12-04.

### Documentation Requirements

Every significant change requires:

#### 1. **Code-Level Documentation**
```python
# Example: All new functions/classes need docstrings
def new_feature(param: str) -> dict:
    """
    Brief description of what this does.

    Args:
        param: Description of parameter

    Returns:
        Description of return value

    Raises:
        ValueError: When param is invalid
    """
```

#### 2. **User-Facing Documentation**
- Update README.md if user-visible behavior changes
- Update API documentation in `api/README.md`
- Update webhook examples in `docs/WEBHOOK_API.md`
- Add examples for new features

#### 3. **Developer Documentation**
- Update `tools/README.md` for new tools
- Document new configuration options
- Update architecture docs if structure changes

### Quick Validation Script

Use this before committing:

```bash
#!/bin/bash
# .git/hooks/pre-commit or run manually

echo "🔍 Running quality checks..."

# 1. Run tests
echo "📋 Running tests..."
pytest api/tests/ -q || exit 1
pytest tools/test_*.py -q || exit 1

# 2. Linting
echo "🔧 Running linters..."
ruff check api/ tools/ || exit 1
shellcheck custom-scripts/* || exit 1

# 3. Type checking
echo "📐 Type checking..."
mypy api/ || exit 1

# 4. Check for common issues
echo "🔎 Security scan..."
semgrep --config auto api/ || exit 1

echo "✅ All quality checks passed!"
```

### AI Agent Responsibilities

When using AI agents (Claude, Codex, etc.) for development:

1. **Always run tests after AI-generated changes**
2. **Review all AI-generated code for security issues**
3. **Ensure AI-generated code has proper error handling**
4. **Add tests for AI-generated functionality**
5. **Update documentation for AI-generated features**

### Exemptions

The only valid exemptions from these requirements:

- **Documentation-only changes** (README updates, typo fixes)
- **CI/CD configuration** (workflow files only, must still be tested)
- **Emergency hotfixes** (must be followed up with tests in next commit)

All other changes require full compliance with quality requirements.

---

## AI Agent Roles

### Primary Development Agents

#### 1. **Claude (Anthropic)** - Architecture & Documentation Specialist
- **Primary Use Cases**:
  - System architecture design and review
  - Comprehensive documentation generation
  - Complex code refactoring and optimization
  - Security analysis and vulnerability assessment
  - Test suite design and implementation
- **Strengths**: Long context window, strong reasoning, excellent documentation quality
- **Integration Points**: Direct API access, VS Code extensions, CLI tools

#### 2. **GPT-4 / GPT Codex (OpenAI)** - Code Generation & Debugging
- **Primary Use Cases**:
  - Rapid code generation and prototyping
  - Debugging assistance and error resolution
  - API integration and library usage
  - Script automation and tooling
  - Pattern recognition in codebases
- **Strengths**: Fast iteration, broad language support, strong debugging capabilities
- **Integration Points**: GitHub Copilot, OpenAI API, VS Code extensions

#### 3. **GitHub Copilot** - Real-time Code Assistance
- **Primary Use Cases**:
  - Inline code completion
  - Function and class generation
  - Comment-to-code translation
  - Boilerplate reduction
- **Strengths**: IDE integration, context-aware suggestions, real-time feedback
- **Integration Points**: Native IDE plugins (VS Code, JetBrains, Neovim)

### Specialized Agents

#### 4. **Shell Script Assistant** - Automation & DevOps
- **Primary Use Cases**:
  - CI/CD pipeline scripts
  - Build automation
  - System administration tasks
  - Container orchestration scripts
- **Model**: Claude or GPT-4 with shell scripting focus
- **Quality Gates**: ShellCheck validation, Bats testing

#### 5. **Documentation Agent** - Technical Writing
- **Primary Use Cases**:
  - README generation and maintenance
  - API documentation
  - User guides and tutorials
  - Architecture decision records (ADRs)
- **Model**: Claude (preferred for long-form content)
- **Output Formats**: Markdown, reStructuredText, AsciiDoc

#### 6. **Test Generation Agent** - Quality Assurance
- **Primary Use Cases**:
  - Unit test generation
  - Integration test scaffolding
  - Test data creation
  - Edge case identification
- **Model**: GPT-4 or Claude
- **Frameworks**: Bats, pytest, Jest, Go testing

## AI-Assisted Workflows

### 1. Feature Development Workflow

```mermaid
graph TD
    A[Feature Request] --> B[AI: Generate Design Doc]
    B --> C[Human Review & Refinement]
    C --> D[AI: Generate Implementation]
    D --> E[Human Code Review]
    E --> F[AI: Generate Tests]
    F --> G[Human Test Review]
    G --> H[AI: Generate Documentation]
    H --> I[Human Final Review]
    I --> J[Merge to Main]
```

**Process**:
1. Human provides feature requirements
2. AI agent generates design document with Claude
3. Human reviews and refines architecture
4. AI generates initial implementation with GPT-4/Copilot
5. Human reviews code for correctness and security
6. AI generates comprehensive test suite
7. Human validates test coverage and edge cases
8. AI generates user-facing documentation
9. Human performs final review and approval

### 2. Bug Fix Workflow

```bash
# Step 1: AI analyzes error logs and stack traces
$ ai-debug analyze --logs error.log --context src/

# Step 2: AI suggests root cause and fixes
$ ai-debug suggest --issue "authentication failure"

# Step 3: Human reviews and selects approach

# Step 4: AI generates fix with tests
$ ai-debug fix --apply --test

# Step 5: Human validates fix in development environment
```

### 3. Refactoring Workflow

```bash
# Step 1: AI analyzes codebase for improvements
$ ai-refactor analyze --target src/legacy/ --metrics complexity,duplication

# Step 2: AI generates refactoring plan
$ ai-refactor plan --priority high

# Step 3: Human approves plan

# Step 4: AI performs incremental refactoring
$ ai-refactor apply --incremental --with-tests

# Step 5: Human reviews each increment before proceeding
```

### 4. Documentation Workflow

```bash
# Step 1: AI scans codebase for undocumented areas
$ ai-docs scan --missing --outdated

# Step 2: AI generates documentation drafts
$ ai-docs generate --format markdown --target docs/

# Step 3: Human reviews and enhances with domain expertise

# Step 4: AI updates README and cross-references
$ ai-docs update-readme --auto-link
```

## AI Integration Points

### Development Environment

#### VS Code Configuration
```json
{
  "github.copilot.enable": {
    "*": true,
    "yaml": true,
    "markdown": true,
    "shellscript": true
  },
  "claude.apiKey": "${CLAUDE_API_KEY}",
  "claude.model": "claude-sonnet-4-20250514",
  "openai.apiKey": "${OPENAI_API_KEY}"
}
```

#### CLI Tools
```bash
# Install AI development assistants
pip install anthropic openai
npm install -g @anthropic-ai/sdk

# Configure environment
export CLAUDE_API_KEY="your-key-here"
export OPENAI_API_KEY="your-key-here"
```

### CI/CD Integration

#### GitHub Actions AI Workflows

```yaml
# .github/workflows/ai-review.yml
name: AI Code Review
on: [pull_request]

jobs:
  ai-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: AI Security Scan
        uses: anthropic/claude-action@v1
        with:
          model: claude-sonnet-4
          task: security-review
          files: "**/*.{py,js,sh,go}"
          
      - name: AI Code Quality Check
        run: |
          ai-review --model gpt-4 --standards pep8,shellcheck
          
      - name: Post Review Comment
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: process.env.AI_REVIEW_OUTPUT
            })
```

### API Usage Patterns

#### Claude API Example
```python
import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("CLAUDE_API_KEY"))

def generate_tests(source_code: str, language: str) -> str:
    """Generate comprehensive test suite using Claude."""
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": f"""Generate a comprehensive test suite for this {language} code:

```{language}
{source_code}
```

Include:
- Unit tests for all functions
- Edge case coverage
- Error handling tests
- Integration test stubs
"""
        }]
    )
    return message.content[0].text
```

#### OpenAI API Example
```python
import openai

def debug_error(error_message: str, code_context: str) -> str:
    """Use GPT-4 to analyze and suggest fixes for errors."""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an expert debugger."},
            {"role": "user", "content": f"""
Error: {error_message}

Code Context:
{code_context}

Provide:
1. Root cause analysis
2. Suggested fix with code
3. Prevention strategies
"""}
        ]
    )
    return response.choices[0].message.content
```

## Quality Gates & Validation

### AI-Generated Code Standards

All AI-generated code must pass:

1. **Linting**: Language-specific linters (pylint, eslint, shellcheck)
2. **Testing**: Minimum 80% test coverage
3. **Security**: Vulnerability scanning with Trivy/Semgrep
4. **Human Review**: Mandatory code review by maintainer
5. **Documentation**: Inline comments and user documentation

### Review Checklist for AI Contributions

- [ ] Code follows project style guidelines
- [ ] No hardcoded secrets or credentials
- [ ] Error handling is comprehensive
- [ ] Tests cover happy path and edge cases
- [ ] Documentation is clear and accurate
- [ ] No obvious security vulnerabilities
- [ ] Performance considerations addressed
- [ ] Dependencies are justified and minimal

## Best Practices

### Prompting Guidelines

#### Effective Prompts
```
✅ GOOD: "Generate a bash function that validates YAML files using yq, 
includes error handling, and returns exit code 0 on success. Add inline 
comments explaining each step."

❌ BAD: "Make a YAML validator"
```

#### Context Provision
```bash
# Provide relevant context for better results
$ cat src/config.py | ai-assist refactor --context "
This config loader needs to:
- Support environment variable overrides
- Validate required fields
- Handle missing files gracefully
- Use type hints
"
```

#### Iterative Refinement
```
1st prompt: "Create a Containerfile for a Python FastAPI app"
2nd prompt: "Add multi-stage build to reduce image size"
3rd prompt: "Include security scanning and non-root user"
4th prompt: "Optimize layer caching for faster rebuilds"
```

### Attribution & Transparency

#### Code Comments
```python
# AI-generated with Claude Sonnet 4 (2025-01-15)
# Prompt: "Create async function to fetch and parse remote YAML configs"
# Human modifications: Added retry logic and custom timeout handling
async def fetch_remote_config(url: str, timeout: int = 10) -> dict:
    """Fetch and parse YAML configuration from remote URL."""
    # ... implementation
```

#### Commit Messages
```bash
git commit -m "feat: Add remote config loader

AI-assisted implementation using Claude for initial structure
and error handling patterns. Human review added retry logic
and custom timeout handling.

Co-authored-by: Claude <ai@anthropic.com>"
```

#### Documentation
```markdown
## AI Development Notes

This module was developed with AI assistance:
- Initial architecture: Claude Sonnet 4
- Implementation: GitHub Copilot + GPT-4
- Test generation: Claude Sonnet 4
- Documentation: Claude Sonnet 4

All AI-generated code was reviewed and modified by human maintainers.
```

## Security Considerations

### AI-Specific Security Risks

1. **Prompt Injection**: Never pass unsanitized user input directly to AI APIs
2. **Data Leakage**: Avoid sending sensitive data (credentials, PII) to AI services
3. **Code Vulnerabilities**: AI may generate insecure patterns (SQL injection, XSS)
4. **Dependency Risks**: AI might suggest outdated or vulnerable libraries

### Mitigation Strategies

```python
# Sanitize inputs before AI processing
def sanitize_for_ai(user_input: str) -> str:
    """Remove sensitive patterns before sending to AI."""
    # Remove potential secrets
    sanitized = re.sub(r'(api[_-]?key|token|password)\s*=\s*[\'\"][^\'\"]+[\'\"]', 
                       r'\1=REDACTED', user_input)
    # Remove internal URLs
    sanitized = re.sub(r'https?://internal\.[^\s]+', 'INTERNAL_URL', sanitized)
    return sanitized
```

## Troubleshooting AI Agents

### Common Issues

#### Issue: AI generates incorrect or insecure code
**Solution**: 
- Provide more specific context and constraints
- Use stricter system prompts
- Increase human review frequency
- Add automated security scanning

#### Issue: Inconsistent code style across AI generations
**Solution**:
- Define explicit style guide in prompts
- Use auto-formatters (black, prettier, gofmt)
- Create reusable prompt templates
- Maintain project style documentation

#### Issue: AI misunderstands project architecture
**Solution**:
- Provide architecture diagrams in prompts
- Include relevant code context
- Use project-specific glossary
- Maintain up-to-date technical documentation

## Metrics & Evaluation

### AI Contribution Metrics

Track AI effectiveness with:
- Lines of code generated vs. retained
- Test coverage of AI-generated code
- Bug rate in AI vs. human code
- Time saved on routine tasks
- Developer satisfaction surveys

### Quality Metrics

```bash
# Generate AI contribution report
$ ai-metrics report --since 2025-01-01

AI Contributions Summary:
- Total commits with AI assistance: 127
- Lines of code generated: 15,430
- Lines retained after review: 12,890 (83.5%)
- Test coverage: 87.3%
- Security vulnerabilities: 0 critical, 2 medium (patched)
- Time saved estimate: 156 hours
```

## Future Enhancements

### Planned AI Capabilities

- [ ] Automated dependency updates with compatibility testing
- [ ] AI-powered code review bot with project-specific rules
- [ ] Intelligent test case generation from requirements
- [ ] Automated documentation synchronization
- [ ] Predictive issue detection from commit patterns
- [ ] AI-assisted architecture decision records (ADRs)
- [ ] Automated security patch generation and testing

### Research Areas

- Fine-tuning models on project-specific codebases
- Local LLM deployment for sensitive codebases
- AI-powered pair programming workflows
- Automated regression detection
- Natural language to infrastructure-as-code translation

## Resources

### AI Development Tools

- **Claude API**: https://www.anthropic.com/api
- **OpenAI API**: https://platform.openai.com/
- **GitHub Copilot**: https://github.com/features/copilot
- **Cursor IDE**: https://cursor.sh/
- **Continue**: https://continue.dev/

### Prompt Libraries

- **Awesome ChatGPT Prompts**: https://github.com/f/awesome-chatgpt-prompts
- **LangChain Prompt Templates**: https://python.langchain.com/docs/modules/model_io/prompts/
- **Anthropic Prompt Library**: https://docs.anthropic.com/claude/prompt-library

### Learning Resources

- **OpenAI Cookbook**: https://github.com/openai/openai-cookbook
- **Anthropic Documentation**: https://docs.anthropic.com/
- **AI-Assisted Development Guide**: https://github.blog/developer-skills/github/how-to-use-github-copilot-for-explaining-code/

## Contributing to AI Workflows

We welcome contributions that improve our AI-assisted development practices:

1. Share effective prompts and patterns
2. Report AI-generated code quality issues
3. Suggest new AI integration points
4. Document AI limitations and workarounds
5. Contribute to prompt template library

## License

AI-generated contributions are subject to the same MIT License as the rest of the project. All AI-generated code becomes part of the project codebase with appropriate attribution.

## Acknowledgments

- **Claude** (Anthropic) - Architecture design, documentation, and complex reasoning
- **GPT-4** (OpenAI) - Code generation and debugging assistance
- **GitHub Copilot** - Real-time coding assistance and productivity enhancement
- The broader AI developer tools community for advancing AI-assisted development practices

---

**AI-Augmented Development**

*This AGENTS.md was initially generated with Claude Sonnet 4 and human oversight on 2025-12-01*
*Last updated: 2025-12-13 - Added yaml-to-containerfile transpiler scenario, common pitfalls, and RKE2 test updates*

*For questions about AI workflows, open an issue or contact the maintainers*
