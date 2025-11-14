# Development Guide

This document explains how this repository is structured and how to properly make changes to it.

## 🏗️ Repository Structure

```
├── src/                          # Source code
│   ├── agentic_api/             # FastAPI application
│   │   └── main.py              # Main API entry point
│   └── shared/                  # Shared utilities
│       ├── config.py            # Configuration management
│       ├── database.py          # Database connectivity
│       ├── exceptions.py        # Custom exceptions
│       └── logging_config.py    # Logging setup
├── tst/                         # Test files
│   └── test_app.py              # API tests
├── scripts/                     # Utility scripts
│   ├── setup_db.py              # Database initialization
│   ├── internally_verify_infra.py   # Infrastructure testing
│   └── externally_verify_infra.sh # Infrastructure verification
├── config/                      # Configuration files
│   ├── prometheus.yml           # Prometheus configuration
│   └── recording_rules.yml      # Prometheus recording rules
├── data/                        # Database initialization scripts
│   ├── 01-init-db.sql           # Database schema
│   └── 02-bootstrap-data.sql    # Initial data
├── build/                       # Generated files (gitignored)
│   ├── logs/                    # Application logs
│   ├── reports/                 # Test and security reports
│   └── metrics/                 # Metrics data
├── docker-compose.yml           # Docker orchestration
├── Dockerfile                   # Application container
├── Makefile                     # Build automation
├── pyproject.toml               # Python package configuration
└── FUTURE_ENHANCEMENTS.md       # Planned future improvements
```

## 🚀 Getting Started

### 1. Initial Setup
After cloning the repository, run the setup command:

```bash
make setup
```

This will:
- Create the build directory structure
- Build all Docker images
- Set up the development environment

### 2. Start Development
```bash
# Build everything
make build

# Start services
make docker-up

# Run tests
make test
```

## 🔧 Development Workflow

### Core Development Commands

| Command | When to Use | What it Does |
|---------|-------------|--------------|
| `make setup` | After cloning | Initial repository setup |
| `make build` | Before development | Builds Docker images and setup |
| `make test` | During development | Runs tests with coverage |
| `make format` | Before committing | Formats code with black/isort |
| `make release` | Before deployment | Runs all quality checks |
| `make clean` | When done | Cleans up temporary files |

### Integration Test Commands

| Command | When to Use | What it Does |
|---------|-------------|--------------|
| `make integration-tests` | Run all integration tests | Runs all integration tests with debug logging |
| `make integration-tests-one-by-one` | Debug integration tests | Runs tests one by one, stops at first failure |
| `make integration-test-one TEST="path"` | Debug specific test | Runs single integration test with debug logging |
| `make sample-test` | Quick test | Runs specific unit and integration tests |

### Docker Build Commands

| Command | When to Use | What it Does |
|---------|-------------|--------------|
| `docker compose up --build` | Standard rebuild | Builds and starts services, uses cache when possible |
| `docker compose down --volumes --remove-orphans` | Clean rebuild | Removes all containers, volumes, and networks |
| `docker compose up --build -d` | Background rebuild | Builds and starts services in background |

### Daily Development Flow

1. **Start your day:**
   ```bash
   make build
   make docker-up
   ```

2. **Make changes:**
   - Edit files in `src/` directory
   - Add tests in `tst/` directory
   - Update configuration in `config/` directory

3. **Test your changes:**
   ```bash
   make test
   ```

4. **Format code:**
   ```bash
   make format
   ```

5. **Check quality:**
   ```bash
   make release
   ```

6. **Clean up:**
   ```bash
   make clean
   ```

## 📁 Key Directories

### `src/` - Source Code
- **`agentic_api/`**: FastAPI application with endpoints
- **`shared/`**: Shared utilities and configuration
- **Pattern**: All business logic goes here

### `tst/` - Tests
- **`test_app.py`**: API and infrastructure tests
- **Pattern**: One test file per major component

### `scripts/` - Utility Scripts
- **`setup_db.py`**: Database initialization
- **`internally_verify_infra.py`**: End-to-end testing
- **`externally_verify_infra.sh`**: Infrastructure verification

### `config/` - Configuration
- **`prometheus.yml`**: Monitoring configuration
- **`recording_rules.yml`**: Metrics aggregation rules

### `build/` - Generated Files (Gitignored)
- **`logs/`**: Application logs
- **`reports/`**: Test and security reports
- **`metrics/`**: Metrics data

## 🐳 Docker Architecture

### Services
- **`postgres`**: PostgreSQL database
- **`agentic-api`**: FastAPI application (port 8001)
- **`prometheus`**: Monitoring (port 9090)
- **`canary`**: Automated testing service
- **`test`**: Testing container

### Key Features
- **Multi-stage builds**: Optimized for production
- **Volume mounts**: Persistent data and logs
- **Health checks**: Automatic service monitoring
- **Network isolation**: Secure inter-service communication

## 🧪 Testing Strategy

### Test Types
1. **Unit Tests**: Individual component testing
2. **Integration Tests**: Database and API connectivity
3. **Infrastructure Tests**: End-to-end system verification

### Integration Test Iteration Workflow

#### **Database Seeding & Cleanup Pattern**
Integration tests use a **session-scoped fixture** that automatically:
- **Seeds database** before each test with comprehensive test data
- **Cleans up** after each test to ensure isolation
- **Commits changes** to make data visible to all database sessions
- **Includes delay** after seeding to ensure data propagation

#### **Test Data Isolation**
- **Session-scoped**: Each test session gets fresh data
- **Automatic cleanup**: Database is wiped after each test
- **Comprehensive seeding**: Apps, actions, and relationships are seeded
- **Data persistence**: Seeded data is committed and visible to agents

#### **Integration Test Commands**
```bash
# Run all integration tests
make integration-tests

# Run integration tests one by one (stops at first failure)
make integration-tests-one-by-one

# Run specific integration test
make integration-test-one TEST="/app/tst/integration/agents/test_end_to_end_agents.py"

# Run with debug logging
make integration-tests-one-by-one  # Includes --log-cli-level=DEBUG
```

### Integ Test Feedback Loop

This section documents the practical, repeatable loop we use to get all integration tests green. It focuses on running tests one-by-one, inspecting fixtures and expectations, and iterating quickly inside Docker.

#### Goals
- Ensure each test uses explicit dataset fixtures
- Keep seeds and test expectations aligned (apps/actions must actually exist)
- Maintain isolation: data is seeded before a test and wiped after
- Avoid changes that disable guardrails; fix root causes instead

#### Loop Overview
1. Run tests one-by-one with DEBUG logging and fail fast:
   ```bash
   make integration-tests-one-by-one
   # or a single file/test
   make integration-test-one TEST="/app/tst/integration/api/test_agentic_api_workflow_endpoints.py::TestClass::test_case"
   ```
2. When a test fails, identify its declared fixtures and expectations:
   - Check the test method signature for fixtures like `setup_test_environment`, `dataset_comprehensive`, `dataset_ambiguous_leads`, etc.
   - Read `tst/integration/fixtures/integ_test_data.py` to see the exact apps/actions seeded by the referenced fixture(s).
   - Confirm the test assertions reference only seeded app and action names.
3. Compare test expectations vs fixtures:
   - If a test expects an action that is not seeded (e.g., `Google Sheets` → `add_row`), either add it to the seed or adjust the test to an existing action.
   - If a test is directly seeding data inside the test body, remove that and rely on dataset fixtures instead.
4. Rebuild and rerun quickly:
   ```bash
   docker compose up --build -d
   make integration-test-one TEST="<failing test>"
   ```
5. Repeat until the test passes, then proceed to the next failing test.

#### Fixture Study Checklist
- Open `tst/integration/fixtures/integ_test_data.py` and verify:
  - Apps and actions seeded by `seed_comprehensive_public_set()` include what tests assert against.
  - Specialized datasets (e.g., `dataset_ambiguous_leads`, `dataset_unique_leads`, `dataset_private_public`) match the scenario.
  - `seed_apps_and_actions()` commits transactions and closes sessions.
- Open `tst/integration/fixtures/db_setup.py` and verify:
  - `setup_test_environment` drops/recreates schema, seeds once per session as intended, and commits.
  - A short delay can be present after seeding to ensure visibility across sessions.
  - No direct `src.` imports are required by tests; containers are configured to import packages correctly.

#### Guardrail Expectations Alignment
- These agents perform single-step analysis. If a test expects multi-step fields (e.g., `workflow_steps`), update the test to assert against `WorkflowStepAnalysisResponse` fields: `app`, `action`, `reasoning`, `workflow_step_detected`.
- Do not disable guardrails. Fix seeds, prompts, or test expectations so that valid inputs pass and invalid ones fail with structured responses.

#### Logging and Observability During the Loop
- CLI logging is already enabled via `--log-cli-level=DEBUG` in Makefile targets.
- Service logs:
  ```bash
  docker compose logs -f agentic-api
  ```
- Metrics and health checks are available if deeper inspection is needed.

#### Common Pitfalls and Fixes
- KeyError on `workflow_steps`: Switch to single-step response assertions.
- Guardrail trip due to missing seeded data: Add the missing action/app to the dataset fixture (e.g., `Google Sheets` → `add_row`).
- Duplicate key errors: Remove direct seeding in tests and rely on dataset fixtures; ensure cleanup is running between tests.
- Agent using hardcoded IDs: Ensure prompts instruct using IDs from `get_public_apps` tool and that seeds are visible to the API container.

#### Example Alignment
- Test expects:
  - Apps: `Salesforce`, `Gmail`, `Slack`, `HubSpot`, `Google Sheets`
  - Actions: `create_lead`, `send_email`, `send_message`, `create_contact`, `add_row`
- Ensure `seed_comprehensive_public_set()` includes all of the above before running the test.

### **Key Learnings from Integration Test Iteration**

#### **1. Guardrail Exception Handling Pattern**
**Problem**: Guardrails were tripping but the `guardrails_tripped` list in responses was empty, making it impossible to test guardrail behavior.

**Root Cause**: The `Runner.run()` method in the agents framework raises `InputGuardrailTripwireTriggered` and `OutputGuardrailTripwireTriggered` exceptions, but our exception handlers weren't catching them properly due to incorrect ordering.

**Solution**: 
- Reorder exception handlers to catch specific guardrail exceptions before generic `Exception`
- Extract guardrail names from `guardrail_exception.guardrail_result.guardrail.name`
- Use `InputGuardrail` and `OutputGuardrail` classes with `guardrail_function` parameter instead of decorators

**Key Pattern**:
```python
try:
    result = await Runner.run(starting_agent=agent, input=description)
    # Process successful result
except InputGuardrailTripwireTriggered as e:
    guardrail_name = _extract_guardrail_name(e)
    return WorkflowStepAnalysisResponse(
        app=None, action=None, reasoning=f"Input guardrail tripwire triggered: {guardrail_name}",
        workflow_step_detected=False, guardrails_tripped=[guardrail_name]
    )
except OutputGuardrailTripwireTriggered as e:
    guardrail_name = _extract_guardrail_name(e)
    return WorkflowStepAnalysisResponse(
        app=None, action=None, reasoning=f"Output guardrail tripwire triggered: {guardrail_name}",
        workflow_step_detected=False, guardrails_tripped=[guardrail_name]
    )
except Exception as e:
    # Handle unexpected errors
```

#### **2. Agent Instruction Refinement for Ambiguity Handling**
**Problem**: Agent was too aggressive in resolving ambiguity, picking one app even when multiple apps had identical actions for the same business context.

**Root Cause**: Agent instructions were not conservative enough about ambiguity detection, leading to arbitrary choices in truly ambiguous scenarios.

**Solution**: 
- Updated agent instructions to be more conservative about ambiguity detection
- Added explicit guidance to mark ambiguity when apps are truly equivalent
- Added specific example for CRM lead creation ambiguity
- Made agent prefer making a choice over marking ambiguity when context allows

**Key Pattern**:
```python
# Agent instructions now include:
- **Prefer making a choice over marking ambiguity.** When multiple apps have similar actions, try to pick the most appropriate one based on context, domain knowledge, and semantic relevance.
- **Only mark ambiguity for truly equivalent cases.** If, after using all available context, two or more apps remain equally plausible with no meaningful tie-breaker, then set `ambiguity_detected=True`.
- **CRM Lead Creation Choice**: If both Salesforce and HubSpot have identical `create_lead` actions, choose the most appropriate one based on context. Salesforce is often the default choice for CRM lead creation.
```

#### **3. Test Data Alignment Strategy**
**Problem**: Tests were failing because they expected specific app/action combinations that weren't seeded in the database.

**Root Cause**: Mismatch between test expectations and actual seeded data in `integ_test_data.py`.

**Solution**:
- Systematically review each failing test's expectations
- Compare against `seed_comprehensive_public_set()` in `integ_test_data.py`
- Add missing actions (e.g., `deal_closed` for HubSpot, `add_row` for Google Sheets)
- Ensure test assertions match seeded data exactly

**Key Pattern**:
```python
# Before: Test expects action that doesn't exist
assert result.action == "deal_closed"  # Fails if not seeded

# After: Add missing action to seed data
def seed_comprehensive_public_set():
    # ... existing actions ...
    actions_data = [
        # ... existing actions ...
        {"name": "deal_closed", "app_id": hubspot_id, "description": "Deal closed in HubSpot"},
        {"name": "add_row", "app_id": sheets_id, "description": "Add row to Google Sheets"},
    ]
```

#### **4. Docker Build Iteration Strategy**
**Problem**: Code changes weren't being reflected in containers, leading to persistent test failures.

**Root Cause**: Docker was using cached layers, preventing local changes from being reflected in containers.

**Solution**:
- Use `docker compose up --build` for standard rebuilds
- Use `docker compose down --volumes --remove-orphans` followed by `docker compose up --build` for clean rebuilds
- Always rebuild after making code changes to ensure changes are reflected

**Key Pattern**:
```bash
# Standard rebuild (uses cache when possible)
docker compose up --build

# Clean rebuild (bypasses all cache)
docker compose down --volumes --remove-orphans
docker compose up --build

# Background rebuild for testing
docker compose up --build -d
```

#### **5. Guardrail Name Consistency**
**Problem**: Tests were expecting specific guardrail names that didn't match the actual names being recorded.

**Root Cause**: Mismatch between `GuardrailType` enum values and actual guardrail names being recorded in responses.

**Solution**:
- Use `GuardrailType` enum for consistent naming
- Update test assertions to expect correct guardrail names
- Ensure guardrail names match between enum and actual implementation

**Key Pattern**:
```python
# Use enum for consistency
from ..types.response import GuardrailType

# In tests, use enum values
WorkflowStepResponseAssertions.assert_guardrails_tripped(
    result.model_dump(), [GuardrailType.DESCRIBES_WORKFLOW_STEP.value]
)

# In guardrail definitions, use enum values
InputGuardrail(
    guardrail_function=workflow_guardrail,
    name=GuardrailType.DESCRIBES_WORKFLOW_STEP.value,
)
```

#### **6. Test Isolation and Data Seeding**
**Problem**: Tests were interfering with each other due to improper data isolation.

**Root Cause**: Tests were directly calling seeding functions instead of using fixtures, leading to data conflicts.

**Solution**:
- Use `setup_test_environment` fixture for database setup
- Use dataset fixtures (`dataset_comprehensive`, `dataset_ambiguous_leads`, etc.) for data seeding
- Remove direct seeding calls from test methods
- Ensure proper cleanup between tests

**Key Pattern**:
```python
# Before: Direct seeding in test
async def test_workflow_analysis(self, setup_test_environment):
    await seed_comprehensive_public_set()  # Don't do this
    # ... test logic

# After: Use dataset fixtures
async def test_workflow_analysis(self, setup_test_environment, dataset_comprehensive):
    # ... test logic (data is already seeded by fixture)
```

#### **7. Debug Logging Strategy**
**Problem**: Test failures were difficult to debug due to lack of visibility into agent and guardrail behavior.

**Root Cause**: Insufficient logging made it hard to understand why tests were failing.

**Solution**:
- Add comprehensive debug logging to all guardrails and agents
- Use `--log-cli-level=DEBUG` in Makefile targets
- Add logging to exception handlers and guardrail functions
- Clean up excessive debug logging after issues are resolved

**Key Pattern**:
```python
# Add debug logging during development
logger.debug(f"Guardrail input: {input}")
logger.debug(f"Guardrail output: {output}")
logger.debug(f"Guardrail tripwire: {tripwire_triggered}")

# Clean up after issues are resolved
logger.info(f"Guardrail processed: {result}")
```

#### **8. Iterative Test Fixing Strategy**
**Problem**: Multiple test failures made it difficult to make progress.

**Root Cause**: Trying to fix all tests at once instead of focusing on one at a time.

**Solution**:
- Use `make integration-tests-one-by-one` to run tests sequentially
- Fix one test at a time, ensuring it passes before moving to the next
- Use `make integration-test-one TEST="specific_test"` for targeted debugging
- Rebuild containers after each fix to ensure changes are reflected

**Key Pattern**:
```bash
# Run tests one by one
make integration-tests-one-by-one

# Debug specific test
make integration-test-one TEST="tst/integration/agents/test_end_to_end_agents.py::TestWorkflowAgentEndToEnd::test_guardrails"

# Rebuild after fixes
docker compose up --build -d
```

These learnings provide a systematic approach to debugging integration tests, ensuring that guardrails work correctly, test data is properly aligned, and the entire system functions as expected.

#### **Docker Build & Test Iteration**
```bash
# Clean rebuild (bypasses cache)
docker compose up --build

# Clean stack and rebuild
docker compose down --volumes --remove-orphans
docker compose up --build

# Run tests in background
docker compose up --build -d
make integration-tests-one-by-one
```

#### **Test Debugging Workflow**
1. **Run one-by-one tests**: `make integration-tests-one-by-one`
2. **Check specific test**: `make integration-test-one TEST="path/to/test"`
3. **Debug with logs**: Tests include `--log-cli-level=DEBUG` automatically
4. **Check database**: Verify seeded data is present
5. **Rebuild if needed**: `docker compose up --build`

### Running Tests
```bash
# Run all tests
make test

# Run specific test file
docker compose run --rm test pytest tst/test_app.py -v

# Run with coverage
docker compose run --rm test pytest tst/ --cov=src --cov-report=html

# Run integration tests with debug logging
make integration-tests-one-by-one
```

## 📊 Monitoring & Observability

### Metrics Collection
- **Prometheus**: Metrics collection and storage
- **Custom Metrics**: HTTP requests, database connections
- **Health Checks**: Service availability monitoring

### Logging
- **Structured Logging**: JSON format with rotation
- **Log Levels**: DEBUG, INFO, WARNING, ERROR
- **Log Files**: Stored in `build/logs/`

### Dashboards
```bash
# Open Prometheus UI
make open-prometheus

# Generate dashboard URL
make dashboard-url
```

## 🔒 Code Quality

### Automated Checks
- **Linting**: `flake8` for code style
- **Type Checking**: `mypy` for static analysis
- **Security**: `safety` and `bandit` scanning
- **Formatting**: `black` and `isort` for consistency

### AI Agent Code Quality Prompt

**🤖 AI Agent Instructions: Code Quality Fixes**

When working on this codebase, you should:

1. **Check Build Reports**: Always run `make static-analysis` first to generate current reports
2. **Analyze Issues**: Look at the reports in `build/reports/`:
   - `pylint-report.json` - Code quality and style issues
   - `bandit-report.json` - Security vulnerabilities  
   - `mypy-report.xml` - Type checking errors
3. **Fix Issues Systematically**:
   - **Security issues first** (Bandit findings)
   - **Type errors second** (Mypy findings)
   - **Code quality issues third** (Pylint findings)
4. **Verify Fixes**: Re-run `make static-analysis` to confirm issues are resolved
5. **Update Documentation**: Keep this section updated with current status

**Current Priority Issues** (check `build/reports/` for latest):
- Run `make static-analysis` to generate current reports
- Fix any security vulnerabilities found by Bandit
- Resolve type errors reported by Mypy
- Address code quality issues from Pylint

**Commands to use:**
```bash
# Generate fresh reports
make static-analysis

# Check specific report types
make lint          # Flake8 linting
make type-check    # Mypy type checking  
make security-check # Bandit security scan

# Fix formatting issues
make format        # Black + isort formatting
```

## 🚀 Deployment

### Release Process
1. **Code Quality**: `make release` must pass
2. **Testing**: All tests must pass
3. **Security**: No security vulnerabilities
4. **Documentation**: Update relevant docs

### Production Considerations
- **Environment Variables**: Use `config/env.example` as template
- **Database**: Ensure proper initialization
- **Monitoring**: Configure alerts and dashboards
- **Logging**: Set appropriate log levels

## 🐛 Troubleshooting

### Common Issues

**Docker Issues:**
```bash
# Clean and rebuild
make clean
make build
```

**Database Issues:**
```bash
# Reinitialize database
make db-init
```

**Test Issues:**
```bash
# Run tests with verbose output
docker compose run --rm test pytest tst/ -v -s
```

**Port Conflicts:**
```bash
# Check what's using ports
lsof -i :8001
lsof -i :9090
```

### Debugging
- **Logs**: Check `build/logs/app.log`
- **Metrics**: Visit `http://localhost:9090`
- **Health**: Check `http://localhost:8001/health`

## 📚 Additional Resources

- **Makefile**: `make help` for all available commands
- **Docker**: `docker compose logs <service>` for service logs
- **Prometheus**: `http://localhost:9090` for metrics
- **API**: `http://localhost:8001/docs` for API documentation

## 🛡️ Exception Handling Best Practices

### **Proper Exception Handling Approach**

This repository follows a **specific exception handling pattern** that should be used throughout the codebase:

#### **1. Use Specific Exception Types, Not String Parsing**
```python
# ✅ CORRECT: Catch specific exception types
from openai import RateLimitError, AuthenticationError, APITimeoutError, APIConnectionError

try:
    result = await some_openai_call()
except RateLimitError as e:
    logger.warning(f"Rate limit exceeded: {str(e)}")
    return error_response("Rate limit exceeded. Please try again later.")
except AuthenticationError as e:
    logger.error(f"Authentication error: {str(e)}")
    return error_response("API authentication error. Please contact support.")
except (APITimeoutError, APIConnectionError) as e:
    logger.warning(f"Connection/timeout error: {str(e)}")
    return error_response("Service temporarily unavailable. Please try again later.")
except Exception as e:
    logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    return error_response("An unexpected error occurred.")
```

```python
# ❌ WRONG: Don't parse error messages
try:
    result = await some_openai_call()
except Exception as e:
    error_message = str(e)
    if "rate_limit" in error_message.lower():
        # Handle rate limit
    elif "authentication" in error_message.lower():
        # Handle auth error
    # ... more string parsing
```

#### **2. Multiple Except Blocks Pattern**
- **Use multiple `except` blocks** instead of one catch-all with if/else
- **Order matters**: Most specific exceptions first, generic `Exception` last
- **Group related exceptions**: Use tuples for similar error types
- **Provide meaningful error messages** to users

#### **3. Exception Handling in Key Components**

**Guardrails (`workflow_guardrail.py`, `app_guardrail.py`, `action_guardrail.py`):**
- Catch OpenAI exceptions specifically
- Fail closed for rate limits and auth errors
- Fail open for unexpected errors
- Log appropriate levels (warning vs error)

**Services (`workflow_service.py`):**
- Handle OpenAI API exceptions gracefully
- Return structured error responses
- Include guardrail trip information
- Provide actionable user feedback

#### **4. Error Response Structure**
```python
# Consistent error response format
{
    "app": None,
    "action": None,
    "reasoning": "User-friendly error message",
    "workflow_step_detected": False,
    "guardrails_tripped": ["rate_limit_exceeded", "authentication_error"]
}
```

#### **5. Logging Standards**
- **Rate limits**: `logger.warning()` - expected, temporary
- **Auth errors**: `logger.error()` - configuration issue
- **Timeouts**: `logger.warning()` - network issue
- **Unexpected**: `logger.error()` with `exc_info=True`

### **Implementation Examples**

#### **Guardrail Exception Handling**
```python
async def workflow_guardrail(ctx, agent, input):
    try:
        result = await Runner.run(workflow_guardrail_agent, input, context=ctx.context)
        return GuardrailFunctionOutput(
            output_info=result.final_output,
            tripwire_triggered=not is_valid,
        )
    except RateLimitError as e:
        logger.warning(f"Rate limit in workflow guardrail: {str(e)}")
        return GuardrailFunctionOutput(
            output_info=WorkflowDetectionOutput(
                is_workflow=False,
                has_app_reference=False,
                has_action_reference=False,
                reasoning="Rate limit exceeded. Please try again later.",
            ),
            tripwire_triggered=True,
        )
    except AuthenticationError as e:
        logger.error(f"Auth error in workflow guardrail: {str(e)}")
        return GuardrailFunctionOutput(
            output_info=WorkflowDetectionOutput(
                is_workflow=False,
                has_app_reference=False,
                has_action_reference=False,
                reasoning="API authentication error. Please contact support.",
            ),
            tripwire_triggered=True,
        )
    except (APITimeoutError, APIConnectionError) as e:
        logger.warning(f"Connection error in workflow guardrail: {str(e)}")
        return GuardrailFunctionOutput(
            output_info=WorkflowDetectionOutput(
                is_workflow=False,
                has_app_reference=False,
                has_action_reference=False,
                reasoning="Service temporarily unavailable. Please try again later.",
            ),
            tripwire_triggered=True,
        )
    except Exception as e:
        logger.error(f"Unexpected error in workflow guardrail: {str(e)}", exc_info=True)
        return GuardrailFunctionOutput(
            output_info=WorkflowDetectionOutput(
                is_workflow=True,
                has_app_reference=True,
                has_action_reference=True,
                reasoning="Guardrail error - allowing request to proceed",
            ),
            tripwire_triggered=False,
        )
```

#### **Service Exception Handling**
```python
async def analyze_workflow_step(self, description: str):
    try:
        analysis_result = await self.workflow_agent.analyze_workflow_step(description)
        return WorkflowStepAnalysisResponse(
            app=analysis_result.app,
            action=analysis_result.action,
            reasoning=analysis_result.reasoning,
            workflow_step_detected=analysis_result.workflow_step_detected,
            guardrails_tripped=analysis_result.guardrails_tripped,
        )
    except RateLimitError as e:
        logger.warning(f"Rate limit exceeded: {str(e)}")
        return WorkflowStepAnalysisResponse(
            app=None,
            action=None,
            reasoning="Service temporarily unavailable due to rate limits. Please try again later.",
            workflow_step_detected=False,
            guardrails_tripped=["rate_limit_exceeded"],
        )
    except AuthenticationError as e:
        logger.error(f"Authentication error: {str(e)}")
        return WorkflowStepAnalysisResponse(
            app=None,
            action=None,
            reasoning="Service configuration error. Please contact support.",
            workflow_step_detected=False,
            guardrails_tripped=["authentication_error"],
        )
    except APITimeoutError as e:
        logger.warning(f"API timeout: {str(e)}")
        return WorkflowStepAnalysisResponse(
            app=None,
            action=None,
            reasoning="Service timeout. Please try again with a shorter description.",
            workflow_step_detected=False,
            guardrails_tripped=["timeout"],
        )
    except APIConnectionError as e:
        logger.warning(f"Connection error: {str(e)}")
        return WorkflowStepAnalysisResponse(
            app=None,
            action=None,
            reasoning="Service temporarily unavailable. Please try again later.",
            workflow_step_detected=False,
            guardrails_tripped=["connection_error"],
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return WorkflowStepAnalysisResponse(
            app=None,
            action=None,
            reasoning=f"Error in workflow step analysis: {str(e)}",
            workflow_step_detected=False,
            guardrails_tripped=["analysis_error"],
        )
```

### **Benefits of This Approach**
- **More reliable**: Catches actual exception types instead of parsing error text
- **Better user experience**: Provides specific, actionable error messages
- **Easier to maintain**: Clear separation of different error handling logic
- **More robust**: Handles edge cases that string parsing might miss
- **Consistent**: Same pattern across all components
- **Debuggable**: Proper logging levels and error information

## 🔧 Centralized Exception Handling Utilities

### **Overview**

The `src/knowledge_agents/utils/exception_handlers.py` module provides centralized exception handling for OpenAI API calls throughout the application. Instead of duplicating exception handling code across guardrails and services, use these utilities to handle OpenAI exceptions consistently.

### **Usage Patterns**

#### **For Guardrails**

```python
from ...utils.exception_handlers import GuardrailExceptionHandler

@input_guardrail
async def my_guardrail(ctx, agent, input):
    try:
        # Your guardrail logic here
        result = await some_openai_call()
        return GuardrailFunctionOutput(
            output_info=result,
            tripwire_triggered=False,
        )
    except Exception as e:
        # Use centralized exception handler with metrics
        error_response = GuardrailExceptionHandler.handle_guardrail_exception(
            exception=e,
            output_type=MyOutputType,
            log_prefix="My guardrail",
            start_time=start_time,
            guardrail_type="my_guardrail"
        )
        return GuardrailFunctionOutput(**error_response)
```

#### **For Services**

```python
from ...utils.exception_handlers import ServiceExceptionHandler

async def my_service_method(self, description: str):
    try:
        # Your service logic here
        result = await some_openai_call()
        return MyResponseType(
            app=result.app,
            action=result.action,
            reasoning=result.reasoning,
        )
    except Exception as e:
        # Use centralized exception handler with metrics
        return ServiceExceptionHandler.handle_service_exception(
            exception=e,
            response_type=MyResponseType,
            log_prefix="My service",
            start_time=start_time,
            service_type="my_service"
        )
```

### **Benefits**

1. **Consistent Error Handling**: All components handle exceptions the same way
2. **Reduced Code Duplication**: No need to repeat exception handling logic
3. **Centralized Updates**: Change error handling behavior in one place
4. **Proper Logging**: Consistent logging levels and messages
5. **Standardized Responses**: Uniform error response formats
6. **Automatic Metrics**: Exception counters and duration metrics are automatically recorded

### **Exception Types Handled**

- `RateLimitError`: Rate limit exceeded
- `AuthenticationError`: API key or authentication issues
- `APITimeoutError`: Request timeout
- `APIConnectionError`: Connection issues
- `Exception`: Any other unexpected errors

### **Response Patterns**

#### **Guardrails**
- **Rate limits/Auth errors**: Fail closed (tripwire=True)
- **Connection issues**: Fail closed (tripwire=True)  
- **Other errors**: Fail open (tripwire=False)

#### **Services**
- **All errors**: Return structured error response with appropriate guardrails_tripped
- **User-friendly messages**: Clear, actionable error messages
- **Consistent format**: Same response structure for all error types

### **Migration Guide**

#### **Before (Duplicated Code)**
```python
except RateLimitError as e:
    logger.warning(f"Rate limit exceeded: {str(e)}")
    return ErrorResponse(...)
except AuthenticationError as e:
    logger.error(f"Auth error: {str(e)}")
    return ErrorResponse(...)
# ... more exception types
```

#### **After (Centralized)**
```python
except Exception as e:
    return ExceptionHandler.handle_exception(
        exception=e,
        response_type=MyResponseType,
        log_prefix="My component"
    )
```

This approach reduces code duplication and ensures consistent error handling across the entire application.

### **Standardized Metrics Recording**

The exception handlers use a centralized `_record_exception_metrics()` function that:

- **Eliminates Duplication**: Single function handles all exception metrics recording
- **Consistent Behavior**: Same metrics recorded for all components
- **Easy Maintenance**: Changes to metrics logic only need to be made in one place
- **Flexible**: Works for both guardrails and services with appropriate component labels

```python
def _record_exception_metrics(
    exception: Exception,
    component: str,  # "guardrail" or "service"
    component_type: Optional[str] = None  # Specific type for guardrails_total
) -> None:
    # Records standardized metrics for any component
```

### **Automatic Metrics Recording**

The exception handlers use a standardized `_record_exception_metrics()` function to record the following metrics:

#### **Guardrail Metrics**
- `guardrails_total{guardrail_type, result="error"}` - Total guardrail errors by type
- `openai_rate_limits_total{model, limit_type}` - OpenAI rate limit hits (model from settings)
- `request_error_total{component="guardrail", error_type}` - Specific error types (authentication, connection, unexpected)

#### **Service Metrics**
- `guardrails_total{guardrail_type, result="error"}` - Total service errors by type
- `openai_rate_limits_total{model, limit_type}` - OpenAI rate limit hits (model from settings)
- `request_error_total{component="service", error_type}` - Specific error types (rate_limit, authentication, timeout, connection, unexpected)

#### **Usage Example with Metrics**
```python
# Guardrail with metrics
try:
    result = await some_guardrail_operation()
    return success_response(result)
except Exception as e:
    return GuardrailExceptionHandler.handle_guardrail_exception(
        exception=e,
        output_type=MyOutputType,
        log_prefix="My guardrail",
        guardrail_type="workflow_detection"  # Records error counter
    )

# Service with metrics
try:
    result = await some_service_operation()
    return success_response(result)
except Exception as e:
    return ServiceExceptionHandler.handle_service_exception(
        exception=e,
        response_type=MyResponseType,
        log_prefix="My service",
        service_type="workflow_analysis"  # Records error counter
    )
```

## 🤖 AI Agents Development Guide

### **Repository Overview**

This is an **AI-driven development workflow** repository for a Knowledge Applied AI Engineering Skills Interview project. The repository uses a structured approach with numbered prompts and documentation to guide development phases.

### **Integration Test Development Workflow**

#### **Database Seeding & Test Isolation**
The integration test system uses a sophisticated database seeding pattern:

```python
# Session-scoped fixture in tst/integration/fixtures/db_setup.py
@pytest.fixture(scope="session")
async def setup_test_environment():
    # 1. Drop and recreate all tables
    # 2. Seed comprehensive test data (apps, actions, relationships)
    # 3. Commit changes to make data visible to all sessions
    # 4. Add delay for data propagation
    # 5. Verify seeding success
```

#### **Test Data Pattern**
- **Apps**: Salesforce, Gmail, HubSpot, Google Sheets, Slack
- **Actions**: create_lead, send_email, deal_closed, create_contact, etc.
- **Relationships**: Proper app-action associations
- **Isolation**: Each test session gets fresh, clean data

#### **Docker Build Iteration**
```bash
# Standard rebuild (uses cache when possible)
docker compose up --build

# Clean rebuild (bypasses all cache)
docker compose down --volumes --remove-orphans
docker compose up --build

# Background rebuild for testing
docker compose up --build -d
```

#### **Test Debugging Commands**
```bash
# Run tests one by one (stops at first failure)
make integration-tests-one-by-one

# Run specific test with debug logging
make integration-test-one TEST="/app/tst/integration/agents/test_end_to_end_agents.py"

# Check database state
docker compose exec test psql -U postgres -h postgres -d test_db -c "SELECT * FROM apps;"
```

#### **Common Test Issues & Solutions**

**Issue**: Database appears empty after seeding
- **Solution**: Check if `setup_test_environment` fixture is being used
- **Debug**: Verify seeding with manual database queries
- **Fix**: Ensure test methods use fixture parameter

**Issue**: Agent can't find seeded data
- **Solution**: Verify data is committed and visible to all sessions
- **Debug**: Check database directly through container
- **Fix**: Add delay after seeding for data propagation

**Issue**: Tests fail due to missing actions
- **Solution**: Update seeded data to include required actions
- **Debug**: Check what actions are actually seeded
- **Fix**: Add missing actions to `db_setup.py`

#### **AI Agent Test Patterns**
```python
# Test expects WorkflowStepAnalysisResponse structure
async def test_valid_single_step_workflow(self, setup_test_environment):
    agent = WorkflowAgent()
    result = await agent.analyze_workflow_step("When a lead is created in Salesforce")
    
    # Assert against single-step response structure
    assert result.app is not None
    assert result.action is not None
    assert result.workflow_step_detected is True
    assert result.reasoning is not None
```

#### **Guardrail Testing**
- **Input Guardrails**: Test workflow detection, app validation, action validation
- **Output Guardrails**: Test judge quality assessment, relationship validation
- **Debug Logging**: All guardrails include comprehensive debug logging
- **Exception Handling**: Test rate limits, auth errors, timeouts, connection issues

### **Current Implementation Status**

#### ✅ **Completed Features**
- **Real OpenAI API Integration**: Agents use OpenAI with proper API key management
- **Guardrail System (Input + Output)**: Input guardrails (workflow/app/action) and output guardrail (quality)
- **Centralized Client Management**: Unified OpenAI client management with lazy loading
- **Real Database Integration**: PostgreSQL with proper schema and data
- **Docker-Based Development**: Full containerized development and testing environment
- **Proper Exception Handling**: Specific exception types with appropriate error responses

#### 🔄 **In Progress**
- **Metrics Format Issues**: Some Prometheus metrics missing HELP lines

#### 📋 **Architecture Decisions Made**
- **AI-First Approach**: Replaced keyword-based systems with intelligent AI analysis
- **Real API Integration**: No mocks in integration tests - all real OpenAI calls
- **Centralized Configuration**: Lazy loading of settings to prevent build-time failures
- **Docker Secrets**: OpenAI API key only via Docker secrets, not environment variables
- **Exception Handling**: Specific exception types instead of string parsing

### **Key Architecture Principles**

#### 1. **AI-Driven Guardrail System**
- **Input Guardrails**: Single enhanced workflow guardrail (workflow + apps + actions), plus app/action existence guardrails
- **Output Guardrail**: Judge-quality evaluation guardrail attached to the agent
- **Strict Business Focus**: Rejects personal tasks, weather queries, pizza orders, etc.
- **Semantic Workflow Detection**: Uses LLM semantic understanding to determine if input is a workflow, NOT hardcoded keywords

#### 2. **Real OpenAI Integration**
- **Actual API Calls**: All agents make real OpenAI API calls with proper error handling
- **Centralized Client Management**: Single `get_openai_client()` function for all agents
- **Lazy Loading**: Settings loaded only when needed to prevent build-time failures
- **Docker Secrets**: API key only accessible via Docker secrets for security
- **Exception Handling**: Proper handling of rate limits, auth errors, timeouts, and connection issues

#### 3. **Semantic AI Analysis Principles**
- **NO Hardcoded Keywords**: Never use "when", "if", "then" or other keyword-based detection
- **LLM Semantic Understanding**: Let the AI agent determine workflow intent through semantic analysis
- **Context-Aware Detection**: AI understands business context, not just trigger words
- **Intelligent Workflow Recognition**: AI can identify workflows even without explicit trigger words

#### 4. **Tuple-Based Workflow Steps**
- Use `workflow_steps: List[Tuple[str, str]]` for (app, action) pairs
- **Enhanced Response Schema**: Includes `workflow_detected`, `apps_identified`, `actions_identified`
- **Real AI Analysis**: OpenAI determines workflow steps, apps, and actions intelligently

#### 5. **Database Architecture**
- **PostgreSQL Integration**: Real database with proper schema and relationships
- **Integer IDs**: Uses `SERIAL PRIMARY KEY` instead of UUIDs for better performance

#### 6. **Prometheus Metrics Naming Convention**
- **Counters**: Use `_total` suffix (e.g., `workflow_detection_total`, `request_success_total`)
- **Histograms**: Use descriptive names (e.g., `guardrails_tripped_per_request`, `end_to_end_duration_seconds`)
- **Rates**: Calculate using `rate()` function on counters (e.g., `rate(workflow_detection_total[5m])`)
- **NO "rate" in Counter Names**: Counters should never be named with "rate" - use `_total` instead
- **Business Metrics**: Focus on guardrail success/failure, workflow detection, API usage
- **Async Sessions**: SQLAlchemy async sessions with proper connection management
- **Test Data**: Comprehensive bootstrap data for testing scenarios

#### 7. **Centralized Configuration**
- **Lazy Settings Loading**: Prevents build-time failures when secrets aren't available
- **Environment-Specific**: Different configurations for test, development, and production
- **Docker Secrets**: Secure API key management via Docker secrets
- **Validation**: Proper validation of required environment variables

### **Critical Patterns to Follow**

#### 1. **Response Schema Design**
```python
@dataclass
class WorkflowStepAnalysisResponse:
    workflow_steps: List[Tuple[str, str]]  # (app, action) pairs
    reasoning: str
    request_id: Optional[str] = None
    # NO: workflow_detected, confidence_score, apps_identified, actions_identified
```

#### 2. **Guardrail Implementation**
```python
@dataclass
class EvaluationFeedback:
    feedback: str
    score: str  # "pass", "needs_improvement", "fail"
    reasoning: str
    # NO: confidence field
```

#### 3. **Exception Handling Pattern**
```python
# Always use specific exception types
from openai import RateLimitError, AuthenticationError, APITimeoutError, APIConnectionError

try:
    result = await openai_call()
except RateLimitError as e:
    # Handle rate limits
except AuthenticationError as e:
    # Handle auth errors
except (APITimeoutError, APIConnectionError) as e:
    # Handle connection issues
except Exception as e:
    # Handle unexpected errors
```

### **Common Mistakes to Avoid**

#### ❌ **DON'T DO THESE**
- Add `confidence_score` or `workflow_detected` fields
- Put database queries in main app (use MCP server)
- Use separate `apps_identified` and `actions_identified` lists
- Hardcode configuration values
- Use generic `app` directory name (use `knowledge_agents`)
- Put Docker files in subdirectories (keep at root)
- Forget to update import paths after renaming directories
- **NEVER use hardcoded keywords** like "when", "if", "then" for workflow detection
- **NEVER use token-based logic** instead of semantic LLM understanding
- **NEVER parse error messages** instead of catching specific exception types

#### ✅ **DO THESE INSTEAD**
- Use tuple-based `workflow_steps: List[Tuple[str, str]]`
- Put all DB queries in MCP server
- Use centralized `config.py` files
- Use `knowledge_agents` for main application directory
- Keep Docker files at repository root
- Update all import paths when restructuring
- **ALWAYS use semantic LLM analysis** for workflow detection
- **Let AI agents determine intent** through natural language understanding
- **ALWAYS catch specific exception types** instead of parsing error messages

### **File Modification Guidelines**

#### 1. **Before Making Changes**
- Read this guide completely
- Understand the current architecture
- Check existing patterns in the codebase
- Verify import paths are correct
- **CRITICAL**: Evaluate current implementation against the spec

#### 2. **Spec Alignment Evaluation (MANDATORY)**
Before making any changes, perform a spec alignment check:

##### Architecture Alignment Check
- **MCP Server**: Verify using `FastMCP` with `@mcp.tool()` decorators (NOT FastAPI)
- **Main API**: Verify using `FastAPI` for REST endpoints (NOT FastMCP)
- **Agent Integration**: Verify using `MCPServerStreamableHttp` and `mcp_servers=[mcp_server]`
- **Database Separation**: Verify all DB queries in MCP server, main app uses MCP tools
- **Guardrails**: Verify using `@input_guardrail` decorator pattern (NOT custom validation)
- **Exception Handling**: Verify using specific exception types (NOT string parsing)

##### Response Schema Alignment Check
- **Workflow Steps**: Verify using `workflow_steps: List[Tuple[str, str]]` (NOT separate app/action lists)
- **No Confidence Scores**: Verify NO `confidence_score` or `workflow_detected` fields
- **Dataclass Outputs**: Verify using dataclasses for agent outputs and judge evaluations
- **Tuple Structure**: Verify (app, action) pairs for workflow steps

##### Configuration Alignment Check
- **Centralized Config**: Verify separate `config.py` files for main app and MCP server
- **Directory Structure**: Verify using `knowledge_agents` (NOT generic `app`)
- **Import Paths**: Verify all imports use correct `knowledge_agents` paths

##### Implementation Pattern Alignment Check
- **Guardrail-Driven Logic**: Verify confidence comes from guardrails passing (NOT LLM outputs)
- **Agent Execution**: Verify using `Runner.run()` with proper MCP integration
- **Tool Access**: Verify agents use MCP tools (NOT direct HTTP calls)
- **Error Handling**: Verify proper `InputGuardrailTripwireTriggered` exception handling
- **Exception Types**: Verify catching specific OpenAI exceptions (NOT parsing error messages)

**If any misalignment is found, refactor the implementation to match the spec before proceeding.**

#### 3. **When Adding New Features**
- Follow the guardrail-driven approach
- Use tuple-based workflow steps
- Implement in MCP server if database-related
- Add proper configuration management
- Include comprehensive tests
- **Use proper exception handling patterns**
- **Validate against spec** after implementation

#### 4. **When Refactoring**
- Update all import statements
- Maintain the directory structure
- Update documentation references
- Ensure Docker compatibility
- Test in containerized environment
- **Update exception handling to use specific types**
- **Perform spec alignment validation** after refactoring

#### 5. **Final Validation Checklist**
After any implementation or refactoring, perform final validation:

##### Final Architecture Validation
- **✅ MCP Server**: Confirm using `FastMCP` with `@mcp.tool()` decorators
- **✅ Main API**: Confirm using `FastAPI` for REST endpoints  
- **✅ Agent Integration**: Confirm using `MCPServerStreamableHttp` and proper MCP integration
- **✅ Database Separation**: Confirm all DB queries in MCP server only
- **✅ Guardrails**: Confirm using `@input_guardrail` decorator pattern
- **✅ Exception Handling**: Confirm using specific exception types

##### Final Response Schema Validation
- **✅ Workflow Steps**: Confirm using `workflow_steps: List[Tuple[str, str]]`
- **✅ No Confidence Scores**: Confirm NO `confidence_score` or `workflow_detected` fields
- **✅ Dataclass Outputs**: Confirm using dataclasses for structured outputs
- **✅ Tuple Structure**: Confirm (app, action) pairs for workflow steps

##### Final Implementation Pattern Validation
- **✅ Guardrail-Driven Logic**: Confirm confidence from guardrails passing
- **✅ Agent Execution**: Confirm using `Runner.run()` with MCP integration
- **✅ Tool Access**: Confirm agents use MCP tools (not direct HTTP calls)
- **✅ Error Handling**: Confirm proper guardrail exception handling
- **✅ Exception Types**: Confirm catching specific OpenAI exceptions

##### Final Configuration Validation
- **✅ Centralized Config**: Confirm separate `config.py` files
- **✅ Directory Structure**: Confirm using `knowledge_agents` naming
- **✅ Import Paths**: Confirm all imports use correct paths

**If any validation fails, refactor immediately to match the specification before considering implementation complete.**

## 📚 Recent Refactoring Learnings

### Latest iteration highlights (intent matching, ambiguity, prompts, API cleanup)
- Threaded `original_description` through `WorkflowStepAnalysisResponse` so the judge guardrail can compare extracted `(app, action)` against the user's actual request.
- Added `ambiguity_detected: bool` to `WorkflowStepAnalysisResponse`; tests assert this flag instead of parsing reasoning text, eliminating flakiness.
- Refined workflow agent prompt to bias against “slight ambiguity” and only set `ambiguity_detected=True` for true 50/50 cases; added a concrete GitHub example to illustrate domain-disambiguation.
- Externalized the workflow agent instructions to `src/knowledge_agents/prompts/workflow_agent.py` and load via `get_workflow_agent_prompt()` for consistency with other prompts.
- Simplified agent API: removed `analyze_workflow` and standardized on `analyze_workflow_step` only; updated tests and docs accordingly.


### **Centralized Exception Handling Pattern**

#### **Problem Solved**
Previously, each guardrail and service had duplicated exception handling code with inconsistent error responses and metrics recording.

#### **Solution Implemented**
Created centralized exception handling utilities in `src/knowledge_agents/utils/exception_handlers.py`:

```python
# Before: Duplicated exception handling in each guardrail
except RateLimitError as e:
    logger.warning(f"Rate limit: {str(e)}")
    return GuardrailFunctionOutput(...)
except AuthenticationError as e:
    logger.error(f"Auth error: {str(e)}")
    return GuardrailFunctionOutput(...)
# ... repeated in every guardrail

# After: Centralized exception handling
except Exception as e:
    return GuardrailExceptionHandler.handle_guardrail_exception(
        exception=e,
        output_type=MyOutputType,
        log_prefix="My guardrail",
        guardrail_type="workflow_detection"
    )
```

#### **Key Benefits**
- **Consistent Error Responses**: All components return standardized error formats
- **Reduced Code Duplication**: Single source of truth for exception handling logic
- **Automatic Metrics**: Centralized metrics recording for all exception types
- **Easier Maintenance**: Changes to error handling behavior in one place
- **Better Logging**: Consistent logging levels and structured messages

### **Prompt Management Refactoring**

#### **Problem Solved**
Agent instructions were hardcoded within agent definitions, making them difficult to maintain and update.

#### **Solution Implemented**
Created dedicated `src/knowledge_agents/prompts/` directory with individual Python files:

```python
# Before: Hardcoded instructions in agent files
instructions = """
You are a workflow validation agent...
"""

# After: Externalized prompt management
# src/knowledge_agents/prompts/action_validation_agent.py
PROMPT = """
You are a workflow validation agent...
"""

def get_prompt() -> str:
    return PROMPT.strip()
```

#### **Key Benefits**
- **Modularity**: Each agent's instructions in separate files
- **Maintainability**: Easy to update prompts without touching agent code
- **Version Control**: Better tracking of prompt changes
- **Reusability**: Prompts can be shared across different contexts

### **Test Data Management Refactoring**

#### **Problem Solved**
Integration tests had tight coupling between database schema setup and test data seeding, making tests less flexible and potentially non-deterministic.

#### **Solution Implemented**
Decoupled schema setup from data seeding:

```python
# Before: setup_test_environment handled both schema and data
@pytest.fixture(scope="session")
async def setup_test_environment():
    # Create tables AND seed data
    await create_tables()
    await seed_comprehensive_data()

# After: Separate concerns
@pytest.fixture(scope="session")
async def setup_test_environment():
    # Only handle schema creation
    await create_tables()

@pytest.fixture
async def dataset_comprehensive():
    # Explicit data seeding per test
    await clear_all_data()
    await seed_comprehensive_public_set()
    yield
```

#### **Key Benefits**
- **Explicit Dependencies**: Tests declare exactly what data they need
- **Deterministic Tests**: Each test controls its own data setup
- **Flexible Scenarios**: Different tests can use different datasets
- **Better Isolation**: Tests don't depend on implicit data from other tests

### **Judge Output Guardrail Enhancement**

#### **Problem Solved**
The judge guardrail wasn't effectively evaluating agent output against the original user intent, and had confusing parameter naming.

#### **Solution Implemented**
Enhanced judge guardrail with intent matching focus:

```python
# Before: Generic output evaluation
@dataclass
class MessageOutput:
    feedback: str
    score: str

# After: Intent-focused evaluation
@dataclass
class JudgeOutput:
    feedback: str
    score: str
    intent_match_score: float  # New field for intent matching

# Before: Confusing parameter naming
def judge_output_guardrail(output: MessageOutput | str | TResponseInputItem):

# After: Clear parameter naming
def judge_output_guardrail(agent_output: WorkflowStepAnalysisResponse | str | TResponseInputItem):
```

#### **Key Benefits**
- **Intent Matching**: Judge now focuses on matching user intent with extracted app/action pairs
- **Clearer Naming**: Parameter names reflect actual usage
- **Better Evaluation**: More sophisticated scoring of agent output quality
- **Structured Input**: Better handling of WorkflowStepAnalysisResponse objects

### **Test Utility Organization**

#### **Problem Solved**
Test utilities were in a generic location with unclear naming, making them hard to find and use.

#### **Solution Implemented**
Organized test utilities in dedicated directory:

```python
# Before: Generic location and naming
tst/test_utils.py

# After: Organized structure
tst/utils/test_assertion_utils.py
```

#### **Key Benefits**
- **Clear Organization**: Dedicated utils directory for test utilities
- **Better Naming**: Descriptive file names that indicate purpose
- **Easier Discovery**: Developers know where to find test utilities
- **Maintainability**: Easier to add new test utilities

### **Metrics Recording Centralization**

#### **Problem Solved**
Each guardrail had its own metrics recording logic, leading to inconsistency and duplication.

#### **Solution Implemented**
Created centralized metrics utility:

```python
# Before: Manual metrics in each guardrail
guardrails_total.labels(guardrail_type="workflow", result="success").inc()
guardrails_processing_duration_seconds.labels(guardrail_type="workflow").observe(duration)

# After: Centralized metrics recording
from ...utils.guardrail_metrics_util import record_guardrail_metrics

record_guardrail_metrics(
    guardrail_type="workflow",
    result="success",
    duration=duration,
    start_time=start_time
)
```

#### **Key Benefits**
- **Consistency**: All guardrails record metrics the same way
- **Reduced Duplication**: Single function handles all metrics recording
- **Easier Maintenance**: Changes to metrics logic in one place
- **Standardized Behavior**: Same metrics recorded for all components

### **Integration Test Data Dependencies**

#### **Problem Solved**
Integration tests relied on implicit data seeding, making it unclear what data each test actually needed.

#### **Solution Implemented**
Explicit dataset fixtures for different test scenarios:

```python
# Before: Implicit data dependencies
async def test_workflow_analysis(self, api_client, setup_test_environment):
    # Unclear what data is available

# After: Explicit data dependencies
async def test_workflow_analysis(self, api_client, setup_test_environment, dataset_comprehensive):
    # Clear what data is available

async def test_ambiguous_scenario(self, api_client, setup_test_environment, dataset_ambiguous_leads):
    # Specific dataset for ambiguous scenarios
```

#### **Key Benefits**
- **Clear Dependencies**: Tests explicitly declare what data they need
- **Deterministic**: Each test gets exactly the data it expects
- **Flexible**: Different tests can use different datasets
- **Maintainable**: Easy to understand and modify test data requirements

### **Agent File Organization and Response Generation**

#### **Problem Solved**
Large agent files (400+ lines) mixed orchestration logic with response generation, usage extraction, and metadata building, making them difficult to maintain and test.

#### **Solution Implemented**
Refactored agent files into focused utility modules with clear separation of concerns:

```python
# Before: Large agent file with mixed concerns (455 lines)
async def run_note_query_agent(query: str, dependencies):
    # ... 100+ lines of orchestration ...
    # ... 50+ lines of usage extraction ...
    # ... 50+ lines of metadata building ...
    # ... 50+ lines of response construction ...
    return NoteQueryResponse(...), metadata

# After: Focused agent file (312 lines) + utility modules
# src/knowledge_agents/agents/note_query_agent.py - Orchestration only
async def run_note_query_agent(query: str, dependencies):
    # ... orchestration logic ...
    response = process_successful_agent_result(...)
    metadata = build_response_metadata(...)
    return response, metadata

# src/knowledge_agents/utils/response_generator.py - Response building
def process_successful_agent_result(...) -> NoteQueryResponse:
    # Merges files, generates links, builds answer
    return NoteQueryResponse(...)

# src/knowledge_agents/utils/metadata_utils.py - Metadata generation
def build_response_metadata(...) -> dict[str, str]:
    # Extracts usage, builds headers
    return metadata

# src/knowledge_agents/utils/usage_extraction.py - Usage extraction
def extract_usage_tokens(result) -> tuple[int | None, ...]:
    # Extracts token counts from multiple sources
    return input_tokens, output_tokens, total_tokens

# src/knowledge_agents/utils/usage_patch.py - Framework compatibility
def apply_usage_patch():
    # Monkey patch for Usage class to handle None values
    ...
```

#### **Key Benefits**
- **Reduced File Size**: Agent files reduced by ~31% (455 → 312 lines)
- **Separation of Concerns**: Each module has a single, clear responsibility
- **Improved Testability**: Utilities can be tested independently
- **Better Reusability**: Response generation logic can be reused across agents
- **Easier Maintenance**: Changes to response format don't require touching agent orchestration

#### **Pattern Structure**
1. **Agent Files** (`agents/*.py`): Focus on orchestration - model setup, agent creation, running agents, exception handling
2. **Response Generator** (`utils/response_generator.py`): Handles all response construction logic
   - `process_successful_agent_result()` - Success case response building
   - `build_input_guardrail_response()` - Input guardrail error responses
   - `build_output_guardrail_response()` - Output guardrail error responses
   - `build_error_response()` - General error responses
3. **Metadata Utils** (`utils/metadata_utils.py`): Builds response headers
   - `build_response_metadata()` - Success case with usage extraction
   - `build_error_metadata()` - Error case without usage data
4. **Usage Extraction** (`utils/usage_extraction.py`): Extracts token counts from agent results
   - Checks multiple sources: `context_wrapper.usage`, `raw_responses[-1].usage`, `result.usage`
   - Handles different attribute names for compatibility
5. **Usage Patch** (`utils/usage_patch.py`): Framework compatibility layer
   - Monkey patches `Usage` class to handle `None` values from proxy
   - Prevents Pydantic validation errors when proxy returns incomplete usage data

#### **When to Apply This Pattern**
- Agent files exceed 300-400 lines
- Response construction logic is duplicated across multiple agents
- Usage extraction or metadata building is complex
- Framework compatibility issues require monkey patching

### **Best Practices Established**

#### **1. Centralized Utilities Pattern**
- Create shared utilities for common operations (exception handling, metrics, logging)
- Use consistent interfaces across all components
- Document usage patterns and benefits

#### **2. Explicit Dependencies Pattern**
- Make test dependencies explicit through fixture parameters
- Avoid implicit data dependencies
- Use descriptive fixture names that indicate purpose

#### **3. Separation of Concerns Pattern**
- Separate schema setup from data seeding
- Separate prompt management from agent logic
- Separate metrics recording from business logic
- Separate agent orchestration from response generation
- Separate usage extraction from metadata building

#### **4. Intent-Focused Design Pattern**
- Design components around user intent and business value
- Focus on what the user is trying to accomplish
- Make intent matching explicit in evaluation logic

#### **5. Consistent Naming Pattern**
- Use descriptive names that reflect actual usage
- Avoid generic or confusing names
- Update names when refactoring to maintain clarity

These patterns can be applied to future development to maintain code quality, reduce duplication, and improve maintainability.

## 🛡️ Guardrail System Documentation

### **Overview**
The agentic workflow API uses a comprehensive guardrail system to ensure input validation, output quality, and business logic compliance. Guardrails are implemented as decorators on agent functions and provide both input validation and output quality assessment.

### **Guardrail Types**

#### **Input Guardrails**
Input guardrails validate user input before it reaches the main workflow agent:

| Guardrail Name | Purpose | Triggers When |
|---|---|---|
| `describes_workflow_step` | Validates that input describes a workflow step | Input doesn't describe a workflow, is incomplete, or is off-topic |
| `mentions_existing_app` | Validates that referenced apps exist and are public | References non-existent apps or private apps |
| `mentions_existing_action` | Validates that referenced actions exist for the app | References invalid actions for the specified app |

#### **Output Guardrails**
Output guardrails assess the quality and validity of agent output:

| Guardrail Name | Purpose | Triggers When |
|---|---|---|
| `judges_output` | Evaluates output quality and intent matching | Agent output doesn't match user intent or is low quality |
| `returns_valid_app_action_pairs` | Validates app-action relationship integrity | Invalid app-action combinations or relationship issues |

### **Guardrail Implementation**

#### **Enum Definition**
```python
class GuardrailType(Enum):
    """Enum for guardrail type names"""
    
    # Input guardrails
    DESCRIBES_WORKFLOW_STEP = "describes_workflow_step"
    MENTIONS_EXISTING_APP = "mentions_existing_app"
    MENTIONS_EXISTING_ACTION = "mentions_existing_action"
    
    # Output guardrails
    JUDGES_OUTPUT = "judges_output"
    RETURNS_VALID_APP_ACTION_PAIRS = "returns_valid_app_action_pairs"
```

#### **Guardrail Flow**
1. **Input Validation**: User input passes through input guardrails
2. **Agent Processing**: If input is valid, workflow agent processes the request
3. **Output Validation**: Agent output passes through output guardrails
4. **Quality Assessment**: Judge guardrail evaluates output against original intent
5. **Final Response**: Validated response returned to user

### **Guardrail Behavior**

#### **Input Guardrail Failures**
- **Response**: `workflow_step_detected=False`, `app=None`, `action=None`
- **Guardrails Tripped**: Specific input guardrail name
- **Reasoning**: Clear explanation of why input was rejected

#### **Output Guardrail Failures**
- **Response**: `workflow_step_detected=False`, `app=None`, `action=None`
- **Guardrails Tripped**: Specific output guardrail name
- **Reasoning**: Explanation of output quality issues

### **Testing Guardrails**

#### **Test Coverage**
```python
# Test input guardrails
result = await agent.analyze_workflow_step("Use Gmail to...")  # Incomplete
assert_guardrails_tripped(result.model_dump(), [GuardrailType.DESCRIBES_WORKFLOW_STEP.value])

result = await agent.analyze_workflow_step("Use MadeUpApp to send email")  # Invalid app
assert_guardrails_tripped(result.model_dump(), [GuardrailType.MENTIONS_EXISTING_APP.value])

result = await agent.analyze_workflow_step("Use Gmail to archive_calendar")  # Invalid action
assert_guardrails_tripped(result.model_dump(), [GuardrailType.MENTIONS_EXISTING_ACTION.value])
```

#### **Assertion Utilities**
- `assert_guardrails_tripped()`: Verifies specific guardrails were triggered
- `assert_no_step_detected()`: Confirms workflow step detection failed
- `assert_successful_step_detected()`: Confirms successful processing

### **Guardrail Configuration**

#### **Centralized Exception Handling**
All guardrails use centralized exception handling utilities:
- `GuardrailExceptionHandler`: Standardized error responses
- `record_guardrail_metrics()`: Consistent metrics recording
- Automatic logging and monitoring

#### **Prompt Management**
Guardrail instructions are externalized to dedicated prompt files:
- `src/knowledge_agents/prompts/action_validation_agent.py`
- `src/knowledge_agents/prompts/app_validation_agent.py`
- `src/knowledge_agents/prompts/judge_output_guardrail.py`
- `src/knowledge_agents/prompts/relationship_validation_guardrail.py`

### **Best Practices**

#### **Adding New Guardrails**
1. Create guardrail function with appropriate decorator
2. Add enum value to `GuardrailType`
3. Update tests with new guardrail assertions
4. Document guardrail purpose and triggers

#### **Guardrail Maintenance**
1. Use centralized exception handling utilities
2. Externalize prompts to dedicated files
3. Use enum values for consistency
4. Include comprehensive test coverage

### **Metrics and Monitoring**

#### **Guardrail Metrics**
- `guardrails_total{guardrail_type, result}`: Total guardrail executions
- `guardrails_trip_total{guardrail_type}`: Total guardrail trips
- `guardrails_processing_duration_seconds`: Processing time per guardrail

#### **Quality Metrics**
- `workflow_quality_score`: Output quality assessment
- `judge_evaluations_total`: Judge guardrail evaluations
- `judge_score_distribution_total`: Quality score distribution

This guardrail system ensures robust input validation, high-quality output, and comprehensive business logic compliance throughout the workflow analysis process.

## 📊 Prometheus Dashboard Monitoring

The system includes a comprehensive Prometheus dashboard for monitoring agentic workflow metrics. The dashboard is generated via `scripts/generate_prometheus_dashboard.py` and focuses on total counts over 1-minute periods rather than rates.

### **Dashboard Structure**

The dashboard prioritizes agentic metrics over infrastructure metrics:

1. **🤖 AGENTIC METRICS** - Workflow analysis, guardrails, success/failure rates
2. **🧠 AI AGENT QUALITY METRICS** - Tokens, duration, cost analysis  
3. **💰 COST & USAGE METRICS** - OpenAI API usage and costs
4. **🏥 INFRASTRUCTURE METRICS** - HTTP, database, system health (last)

### **Key Metrics Tracked**

#### **Workflow Analysis Metrics**
- `workflow_analysis_total{status="success|error"}` - Total workflow analysis requests
- `workflow_analysis_duration` - Analysis duration in seconds
- `workflow_analysis_input_tokens` - Input tokens consumed
- `workflow_analysis_output_tokens` - Output tokens generated
- `workflow_analysis_cost_usd` - Analysis cost in USD
- `workflow_analysis_apps_found` - Apps found in analysis
- `workflow_analysis_actions_found` - Actions found in analysis

#### **Guardrail Metrics**
- `guardrails_total{guardrail_type="workflow_detection|app_validation|action_validation", result="passed|failed"}` - Guardrail checks performed
- `guardrails_tripped_total` - Total guardrails tripped
- `guardrails_trip_total{guardrail_type}` - Guardrail trips by type
- `guardrails_processing_duration` - Guardrail processing time

#### **Infrastructure Metrics**
- `up{job="agentic-api"}` - Service health status
- `http_requests_total` - HTTP request counts
- `http_request_duration_seconds` - HTTP request duration
- `database_connections_total` - Database connection counts
- `database_connection_duration_seconds` - Database connection duration

### **Dashboard Generation**

Generate the dashboard URL using:
```bash
make dashboard
```

This creates a Prometheus dashboard URL with all panels configured for agentic workflow monitoring, using `increase(metric[1m])` expressions for total counts over 1-minute periods.

## 🐦 Canary Monitoring

### **Purpose**
Canary monitoring provides continuous system health validation through random payload testing, simulating real-world usage patterns and ensuring system resilience.

### **Implementation**
The canary monitoring system (`scripts/canary_monitor.py`) runs as a continuous Docker service that generates random workflow descriptions based on bootstrap data and tests both valid and invalid scenarios.

#### **Random Valid Workflows**
- **Generation**: Uses templates with valid apps/actions from bootstrap data
- **Apps**: Gmail, Slack, Google Sheets, Trello, Salesforce, HubSpot, Knowledge
- **Actions**: Matched to each app (e.g., Gmail: send_email, read_email, search_emails, delete_email)
- **Templates**: "When {trigger}, {action} using {app}", "If {condition}, then {action} with {app}"
- **Expected**: Should either succeed or be detected as ambiguous (not fail guardrails)

#### **Random Invalid Workflows**
- **Non-workflow inputs**: "What's the weather?", "I want to order pizza"
- **Invalid apps**: NonExistentApp, FakeApp, MadeUpApp
- **Invalid actions**: invalid_action, fake_action, unknown_action
- **Private apps**: "Use Private App to send an email"
- **Ambiguous scenarios**: "When a new lead is created, send an email" (which CRM?)
- **Expected**: Should trip appropriate guardrails

#### **Edge Case Scenarios**
- **Empty input**: `""`
- **Whitespace only**: `"   "`
- **Very long input**: `"a" * 1000`
- **Bad instructions**: "give me a bad recommendation with poor reasoning"
- **Wordplay ambiguity**: "When I'm feeling slack, I want to add a row to my sheet"

#### **Guardrail Effectiveness Testing**
Tests specific guardrail types with targeted invalid inputs:
- **Workflow Detection**: Non-workflow queries
- **App Existence**: Non-existent apps
- **Action Validation**: Invalid actions for valid apps
- **Private App**: Private app usage attempts

### **Usage**
```bash
# Start the full stack with canary monitoring
make start

# View canary logs
docker compose logs -f canary

# Check canary status
docker compose ps canary

# Adjust canary interval (default: 30 seconds)
CANARY_INTERVAL=60 docker compose up canary
```

### **Benefits**
- **Continuous Health Monitoring**: Detects system degradation over time
- **Real-world Simulation**: Tests actual usage patterns and edge cases
- **Guardrail Validation**: Ensures guardrails consistently catch invalid inputs
- **System Resilience**: Validates system stability under varied load
- **Regression Detection**: Catches issues that might not be caught by specific tests
- **Automatic Restart**: Docker service automatically restarts on failure
- **Configurable Interval**: Adjustable monitoring frequency via environment variables
- **Centralized Logging**: All canary activity logged to build/logs directory

## 🔧 Integration Test Debugging Learnings

### **Latest Integration Test Iteration Results**

During our recent integration test debugging sessions, we discovered several critical patterns and solutions that significantly improved our test reliability and system understanding. Here are the key learnings:

#### **9. Guardrail Execution Order Understanding**
**Problem**: Tests were failing because they expected guardrails to execute sequentially, but input guardrails actually run in parallel.

**Root Cause**: Misunderstanding of guardrail execution model - input guardrails are executed concurrently, not sequentially.

**Solution**: 
- Updated test assertions to use flexible guardrail checking
- Created `assert_any_guardrails_tripped()` method to accept multiple possible guardrail outcomes
- Updated tests to expect either guardrail when multiple can legitimately fail

**Key Pattern**:
```python
# Before: Expected single guardrail
WorkflowStepResponseAssertions.assert_guardrails_tripped(
    result.model_dump(), [GuardrailType.MENTIONS_EXISTING_APP.value]
)

# After: Accept multiple possible guardrails
WorkflowStepResponseAssertions.assert_any_guardrails_tripped(
    result.model_dump(),
    [GuardrailType.MENTIONS_EXISTING_APP.value, GuardrailType.MENTIONS_EXISTING_ACTION.value]
)
```

#### **10. Workflow Guardrail Scope Refinement**
**Problem**: Workflow guardrail was being too strict about action validation, rejecting legitimate workflow requests.

**Root Cause**: Workflow guardrail was trying to validate action legitimacy instead of just detecting workflow patterns.

**Solution**:
- Refined workflow guardrail to focus on workflow detection, not action validation
- Removed strict action validation from workflow guardrail
- Let action guardrail handle action-specific validation

**Key Pattern**:
```python
# Before: Workflow guardrail rejected valid workflows
# "Use Gmail to archive_calendar" -> rejected as not a workflow

# After: Workflow guardrail focuses on workflow detection
# "Use Gmail to archive_calendar" -> passes workflow detection
# Action guardrail handles action validation separately
```

#### **11. Agent Ambiguity Resolution Refinement**
**Problem**: Agent was being too conservative about ambiguity detection, marking unambiguous scenarios as ambiguous.

**Root Cause**: Agent instructions were too conservative, not considering that if only one app has the required action, it's not ambiguous.

**Solution**:
- Updated agent instructions to be more nuanced about ambiguity detection
- Added logic to choose single app when only one has the required action
- Maintained conservative approach for truly ambiguous scenarios

**Key Pattern**:
```python
# Before: Always ambiguous if multiple apps could match
# "When a new lead is created, send an email" -> ambiguous (Salesforce + HubSpot)

# After: Choose when only one app has the required action
# "When a new lead is created, send an email" -> choose Salesforce (only one with create_lead)
# "When a new lead is created, send an email" -> ambiguous (if both have create_lead)
```

#### **12. Security Enhancement in Workflow Detection**
**Problem**: Workflow guardrail wasn't properly rejecting malicious inputs and security threats.

**Root Cause**: Workflow guardrail focused only on business workflow detection, not security considerations.

**Solution**:
- Enhanced workflow guardrail prompt to include security considerations
- Added explicit rejection of malicious intent, injection attempts, and security threats
- Maintained focus on legitimate business workflows

**Key Pattern**:
```python
# Enhanced workflow guardrail prompt includes:
## Security Requirements
**REJECT the following types of inputs as NOT workflows:**
- **Malicious intent**: Inputs that attempt to exploit, hack, or cause harm
- **Injection attempts**: SQL injection, XSS, code injection, or other injection attacks
- **Security threats**: Attempts to bypass security, access unauthorized data, or compromise systems
- **Suspicious patterns**: Inputs that look like attacks, exploits, or security testing
```

#### **13. XSS Security Test Refinement**
**Problem**: XSS security tests were failing because they expected sanitized `original_description` field.

**Root Cause**: Misunderstanding of security requirements - `original_description` should contain raw user input.

**Solution**:
- Updated XSS tests to expect raw user input in `original_description` field
- Added security assertions to verify other fields are sanitized
- Created `SecurityAssertions.assert_no_malicious_content()` for comprehensive security testing

**Key Pattern**:
```python
# Before: Expected sanitized original_description
assert data["original_description"] == sanitized_input

# After: Expect raw user input in original_description, sanitized elsewhere
assert data["original_description"] == xss_description
SecurityAssertions.assert_no_malicious_content(
    {k: v for k, v in data.items() if k != "original_description"},
    ["<script>", "javascript:", "DROP TABLE", "{{7*7}}"]
)
```

#### **14. Flexible Test Assertion Pattern**
**Problem**: Tests were brittle because they expected specific guardrail outcomes when multiple guardrails could legitimately fail.

**Root Cause**: Tests were written with assumption of sequential guardrail execution.

**Solution**:
- Created flexible assertion methods that accept multiple possible outcomes
- Updated tests to use `assert_any_guardrails_tripped()` for scenarios where multiple guardrails can fail
- Maintained strict assertions for scenarios where only one guardrail should fail

**Key Pattern**:
```python
# New flexible assertion method
@staticmethod
def assert_any_guardrails_tripped(
    response_data: Dict[str, Any], possible_guardrails: List[str]
) -> None:
    """Assert that any of the possible guardrails were tripped"""
    tripped_guardrails = response_data["guardrails_tripped"]
    any_tripped = any(guardrail in tripped_guardrails for guardrail in possible_guardrails)
    assert any_tripped, f"Expected one of {possible_guardrails} to be tripped, but got {tripped_guardrails}"
```

#### **15. Test Data Alignment Strategy**
**Problem**: Tests were failing because they expected specific app/action combinations that weren't seeded in the database.

**Root Cause**: Mismatch between test expectations and actual seeded data in `integ_test_data.py`.

**Solution**:
- Systematically reviewed each failing test's expectations
- Compared against `seed_comprehensive_public_set()` in `integ_test_data.py`
- Added missing actions (e.g., `deal_closed` for HubSpot, `add_row` for Google Sheets)
- Ensured test assertions match seeded data exactly

**Key Pattern**:
```python
# Before: Test expects action that doesn't exist
assert result.action == "deal_closed"  # Fails if not seeded

# After: Add missing action to seed data
def seed_comprehensive_public_set():
    actions_data = [
        # ... existing actions ...
        {"name": "deal_closed", "app_id": hubspot_id, "description": "Deal closed in HubSpot"},
        {"name": "add_row", "app_id": sheets_id, "description": "Add row to Google Sheets"},
    ]
```

#### **16. Docker Build Iteration Strategy**
**Problem**: Code changes weren't being reflected in containers, leading to persistent test failures.

**Root Cause**: Docker was using cached layers, preventing local changes from being reflected in containers.

**Solution**:
- Use `docker compose up --build` for standard rebuilds
- Use `docker compose down --volumes --remove-orphans` followed by `docker compose up --build` for clean rebuilds
- Always rebuild after making code changes to ensure changes are reflected

**Key Pattern**:
```bash
# Standard rebuild (uses cache when possible)
docker compose up --build

# Clean rebuild (bypasses all cache)
docker compose down --volumes --remove-orphans
docker compose up --build

# Background rebuild for testing
docker compose up --build -d
```

#### **17. Debug Logging Strategy**
**Problem**: Test failures were difficult to debug due to lack of visibility into agent and guardrail behavior.

**Root Cause**: Insufficient logging made it hard to understand why tests were failing.

**Solution**:
- Add comprehensive debug logging to all guardrails and agents
- Use `--log-cli-level=DEBUG` in Makefile targets
- Add logging to exception handlers and guardrail functions
- Clean up excessive debug logging after issues are resolved

**Key Pattern**:
```python
# Add debug logging during development
logger.debug(f"Guardrail input: {input}")
logger.debug(f"Guardrail output: {output}")
logger.debug(f"Guardrail tripwire: {tripwire_triggered}")

# Clean up after issues are resolved
logger.info(f"Guardrail processed: {result}")
```

#### **18. Iterative Test Fixing Strategy**
**Problem**: Multiple test failures made it difficult to make progress.

**Root Cause**: Trying to fix all tests at once instead of focusing on one at a time.

**Solution**:
- Use `make integration-tests-one-by-one` to run tests sequentially
- Fix one test at a time, ensuring it passes before moving to the next
- Use `make integration-test-one TEST="specific_test"` for targeted debugging
- Rebuild containers after each fix to ensure changes are reflected

**Key Pattern**:
```bash
# Run tests one by one
make integration-tests-one-by-one

# Debug specific test
make integration-test-one TEST="tst/integration/agents/test_end_to_end_agents.py::TestWorkflowAgentEndToEnd::test_guardrails"

# Rebuild after fixes
docker compose up --build -d
```

### **Integration Test Debugging Workflow**

#### **Systematic Approach**
1. **Run tests one-by-one**: `make integration-tests-one-by-one`
2. **Identify failure**: Check logs for specific error messages
3. **Analyze root cause**: Determine if it's a code issue, test expectation issue, or data alignment issue
4. **Apply targeted fix**: Fix the specific issue without breaking other tests
5. **Verify fix**: Rebuild and rerun the specific test
6. **Continue to next**: Move to the next failing test

#### **Common Debugging Patterns**
- **Guardrail Issues**: Check guardrail execution order and parallel vs sequential behavior
- **Data Issues**: Verify seeded data matches test expectations
- **Agent Issues**: Check agent instructions and ambiguity resolution logic
- **Security Issues**: Verify XSS handling and malicious input rejection
- **Test Issues**: Update test assertions to match actual system behavior

#### **Key Success Metrics**
- **Test Reliability**: Tests pass consistently without flakiness
- **System Understanding**: Clear understanding of guardrail execution order and behavior
- **Code Quality**: Clean, maintainable code with proper exception handling
- **Security**: Proper handling of malicious inputs and XSS attacks
- **Performance**: Efficient test execution with minimal rebuilds

These learnings provide a comprehensive framework for debugging integration tests, ensuring that guardrails work correctly, test data is properly aligned, and the entire system functions as expected.

## 🔑 LiteLLM Proxy Configuration & API Key Management

### **Overview**

This repository uses **LiteLLM Proxy** as an intermediary between the application and LM Studio (local LLM server). The proxy provides:
- **Unified API**: OpenAI-compatible API for all LLM interactions
- **Model Routing**: Routes requests to appropriate models (completion, embedding)
- **API Key Management**: Centralized authentication via Docker secrets
- **LM Studio Integration**: Seamless connection to local LM Studio server

### **Architecture**

```
┌─────────────────┐
│  Application    │
│  (FastAPI)      │
└────────┬────────┘
         │ OpenAI-compatible API
         │ (base_url: http://llm-proxy:4000)
         │ (api_key: from Docker secrets)
         ▼
┌─────────────────┐
│  LiteLLM Proxy  │
│  (Port 4000)    │
└────────┬────────┘
         │ Routes to appropriate model
         │ (completion-model, text-embedding-qwen3-embedding-8b)
         ▼
┌─────────────────┐
│  LM Studio      │
│  (Port 1234)    │
└─────────────────┘
```

### **API Key Management**

#### **Key Principles**

1. **NO Environment Variable Dependencies**: The codebase does NOT read `OPENAI_API_KEY`, `OPENAI_BASE_URL`, or `LITELLM_API_KEY` environment variables
2. **Docker Secrets Only**: API keys are provided via Docker secrets at `/run/secrets/openai_api_key`
3. **Local Development Fallback**: For local development, keys can be read from `secrets/openai_api_key.txt`
4. **Master Key Fallback**: If no key is found, falls back to master key `sk-1234` (configured in `litellm_config.yaml`)

#### **API Key Sources (Priority Order)**

1. **Docker Secret**: `/run/secrets/openai_api_key` (production/containerized)
2. **Local File**: `secrets/openai_api_key.txt` (local development)
3. **Master Key**: `sk-1234` (fallback, configured in `litellm_config.yaml`)

#### **Key Generation**

Generate a new API key for the LiteLLM proxy:

```bash
make litellm-generate-key
```

This script:
- Waits for PostgreSQL and LiteLLM proxy to be ready
- Calls the proxy's `/key/generate` endpoint with master key `sk-1234`
- Saves the generated key to `secrets/openai_api_key.txt`
- Uses the admin API key (`sk-1234`) for authentication

#### **Key Configuration**

The master key `sk-1234` is configured in `config/litellm_config.yaml`:

```yaml
general_settings:
  master_key: sk-1234
```

This master key is used for:
- Admin operations (key generation, health checks)
- Fallback when no user-generated key is found

### **LiteLLM Proxy Configuration**

#### **Configuration File**

The proxy configuration is in `config/litellm_config.yaml`:

```yaml
general_settings:
  master_key: sk-1234
  database_url: "postgresql://knowledge:knowledge123@postgres:5432/knowledge_workflow"

litellm_settings:
  drop_params: true  # Drop unsupported parameters for LM Studio models

model_list:
  - model_name: completion-model
    litellm_params:
      model: lm_studio/qwen3-coder-30b
      api_base: ${LM_STUDIO_API_BASE}
      api_key: "lm-studio"
  
  - model_name: text-embedding-qwen3-embedding-8b
    litellm_params:
      model: lm_studio/text-embedding-qwen3-embedding-8b
      api_base: ${LM_STUDIO_API_BASE}
      api_key: "lm-studio"
```

#### **Model Configuration**

- **Completion Model**: `completion-model` → routes to `lm_studio/qwen3-coder-30b`
- **Embedding Model**: `text-embedding-qwen3-embedding-8b` → routes to `lm_studio/text-embedding-qwen3-embedding-8b`
- **Embedding Size**: 4096 dimensions (configured in `api_config.py`)

#### **LM Studio Connection**

The proxy connects to LM Studio using environment variables:
- `LM_STUDIO_HOST`: LM Studio server host (default: `192.168.1.168`)
- `LM_STUDIO_PORT`: LM Studio server port (default: `1234`)

For Docker Desktop (Mac/Windows), `localhost` is automatically converted to `host.docker.internal`.

### **Code Implementation**

#### **1. Secrets Configuration**

All API key loading is centralized in `src/knowledge_agents/config/secrets_config.py`:

```python
def get_openai_api_key(
    required: bool = True,
    allow_test_key: bool = False,
    environment: str = "development",
    base_dir: Optional[str] = None,
) -> Optional[str]:
    """
    Get API key from Docker secrets or local files (no env var dependencies).
    
    Priority order:
    1. Docker secret: /run/secrets/openai_api_key
    2. Local file: secrets/openai_api_key.txt
    3. Test key: sk-1234 (if allow_test_key=True and environment=test)
    
    Returns:
        API key, or None if not found (unless required=True)
    """
    # Reads from Docker secrets or local files only
    # NO environment variable dependencies
```

#### **2. Model Utilities**

`LitellmModel` instances are created via `src/knowledge_agents/utils/model_utils.py`:

```python
def get_default_litellm_model(model: str = None) -> LitellmModel:
    """
    Get a default LitellmModel instance configured for the LiteLLM proxy.
    
    - Reads API key from Docker secrets/local files
    - Configures litellm.api_base and litellm.api_key
    - Passes api_key explicitly to LitellmModel constructor
    """
    api_key = get_openai_api_key(...)  # From secrets
    litellm.api_base = proxy_url
    litellm.api_key = api_key
    return LitellmModel(model=model_name, api_key=api_key)
```

#### **3. Proxy Client**

OpenAI clients are configured via `src/knowledge_agents/clients/proxy_client.py`:

```python
class ProxyClientManager:
    """Manages OpenAI client instances configured to use LiteLLM proxy"""
    
    def get_client(self) -> OpenAI:
        """Get OpenAI client pointing to LiteLLM proxy"""
        # Reads API key from Docker secrets/local files
        # NO environment variable dependencies
        api_key = get_openai_api_key(...)
        return OpenAI(
            api_key=api_key,
            base_url=f"{proxy_url}/v1",
            timeout=300.0,
        )
```

### **Environment Variables - What NOT to Use**

#### **❌ DO NOT USE**

The codebase does NOT use these environment variables:

- `OPENAI_API_KEY` - Not read anywhere in the codebase
- `OPENAI_BASE_URL` - Not read anywhere in the codebase
- `LITELLM_API_KEY` - Not read anywhere in the codebase
- `LITELLM_PROXY_API_KEY` - Not read anywhere in the codebase

#### **✅ What IS Used**

- **Docker Secrets**: `/run/secrets/openai_api_key`
- **Local Files**: `secrets/openai_api_key.txt`
- **Module-Level Settings**: `litellm.api_base` and `litellm.api_key` (set programmatically)
- **Explicit Parameters**: `api_key` passed directly to `LitellmModel` and `OpenAI` clients

### **Docker Configuration**

#### **Docker Compose Secrets**

The `docker-compose.yml` file configures secrets:

```yaml
secrets:
  openai_api_key:
    file: ./secrets/openai_api_key.txt
  admin_api_key:
    file: ./secrets/admin_api_key.txt

services:
  llm-proxy:
    secrets:
      - openai_api_key
      - admin_api_key
    healthcheck:
      test: ["CMD-SHELL", "/app/scripts/healthcheck_litellm.sh"]
```

#### **Health Checks**

The proxy health check uses the admin API key:

```bash
# scripts/containers/litellm/healthcheck_litellm.sh
# Reads admin_api_key from /run/secrets/admin_api_key
# Falls back to secrets/admin_api_key.txt (local)
# Accepts HTTP 200 or 401 as healthy
```

### **Test Configuration**

#### **Test Fixtures**

Test fixtures in `tst/conftest.py` and `tst/integration/fixtures/agents_client.py`:

```python
def configure_agents_client():
    """Configure AsyncOpenAI to use LiteLLM proxy"""
    # Reads from Docker secrets or local files
    # NO environment variable dependencies
    api_key = None
    try:
        with open("/run/secrets/openai_api_key", "r") as f:
            api_key = f.read().strip()
    except Exception:
        # Try local secrets file
        try:
            secrets_path = os.path.join(project_root, "secrets", "openai_api_key.txt")
            with open(secrets_path, "r") as f:
                api_key = f.read().strip()
        except Exception:
            pass
    
    # Fallback to master key
    if not api_key:
        api_key = "sk-1234"
    
    # Configure AsyncOpenAI with proxy base_url
    proxy_base_url = "http://llm-proxy:4000"
    AsyncOpenAI(api_key=api_key, base_url=f"{proxy_base_url}/v1")
```

### **Embedding Model Configuration**

#### **Dynamic Embedding Sizes**

The system tracks different embedding sizes for different models:

```python
# src/knowledge_agents/config/api_config.py
EMBEDDING_MODEL_SIZES: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "text-embedding-qwen3-embedding-8b": 4096,
    "text-embedding-nomic-embed-text-v1.5": 768,
}

def get_embedding_size(self, model_name: Optional[str] = None) -> int:
    """Dynamically determine embedding size based on model"""
    # Returns appropriate vector dimension for Qdrant collections
```

#### **Qdrant Collection Creation**

Qdrant collections are created with the correct vector size:

```python
# src/knowledge_agents/clients/vector_store.py
vector_size = settings.get_embedding_size(embedding_model)
qdrant_client.create_collection(
    collection_name=collection_name,
    vectors_config=models.VectorParams(
        size=vector_size,  # 4096 for qwen3-embedding-8b
        distance=models.Distance.COSINE,
    ),
)
```

### **Common Issues & Solutions**

#### **Issue: API Key Not Found**

**Symptoms**: Logs show "No API key found, using master key 'sk-1234'"

**Solution**:
1. Generate a new API key: `make litellm-generate-key`
2. Verify key exists: `cat secrets/openai_api_key.txt`
3. Ensure Docker secret is mounted: Check `docker-compose.yml` secrets configuration

#### **Issue: Requests Going to api.openai.com**

**Symptoms**: Logs show requests to `https://api.openai.com/v1/chat/completions`

**Solution**:
1. Verify `base_url` is set correctly in `proxy_client.py`
2. Check that `get_proxy_client()` is being used (not direct `OpenAI()` instantiation)
3. Ensure `litellm.api_base` is set in `model_utils.py`

#### **Issue: Embedding Dimension Mismatch**

**Symptoms**: Qdrant returns `400 Bad Request` when upserting embeddings

**Solution**:
1. Verify collection was created with correct vector size: `settings.get_embedding_size(embedding_model)`
2. Check that embedding model matches: `settings.litellm_proxy_embedding_model` (should be `text-embedding-qwen3-embedding-8b`)
3. Recreate collection with correct size if needed

#### **Issue: LM Studio Connection Failed**

**Symptoms**: Proxy logs show connection errors to LM Studio

**Solution**:
1. Verify LM Studio is running: Check `http://localhost:1234` (or configured host/port)
2. Check environment variables: `LM_STUDIO_HOST` and `LM_STUDIO_PORT`
3. For Docker Desktop: Ensure `localhost` is converted to `host.docker.internal`

#### **Issue: Test API Key Not Working (Authentication Error in Tests)**

**Symptoms**: Integration tests fail with `401 Unauthorized` or `token_not_found_in_db` errors, even though API key is generated

**Root Cause**: 
- `ProxyClientManager` was caching clients with old API keys
- `reset_client()` wasn't resetting API key tracking variables
- Settings were being cached before test fixture injection

**Solution**:
1. Ensure `inject_test_api_key` fixture is properly imported in `conftest.py` (it's autouse, so it should run automatically)
2. Verify `ProxyClientManager._get_settings()` always calls `get_settings()` (not cached) - **DONE**: Always fetches fresh settings
3. Verify `ProxyClientManager.reset_client()` resets both `_last_api_key` and `_last_base_url` - **DONE**: Now resets tracking variables
4. Ensure vector store fixtures call `reset_proxy_clients()` before creating clients - **DONE**: `openai_client` fixture resets clients
5. Settings override: Use `get_settings(openai_api_key=test_key)` instead of environment variables - **DONE**: Settings now support overrides

**How It Works (Updated)**:
- The `litellm_api_key` fixture generates a new API key for the test session
- The `inject_test_api_key` fixture (autouse) initializes global dependencies with test settings
- The `test_dependencies` fixture provides explicit dependency injection for tests
- All client managers now accept `Settings` in their constructor (no lazy loading)
- Tests can use either `test_dependencies` fixture (recommended) or rely on global dependencies initialized by `inject_test_api_key`

#### **Issue: Settings Override Not Working**

**Symptoms**: Tests still use API key from secrets file instead of generated test key

**Root Cause**: 
- Settings were cached globally before test fixture ran
- `get_settings()` was returning cached instance instead of creating new one with overrides
- Environment variables were being used instead of Settings overrides

**Solution (Updated with Dependency Injection)**:
1. **Settings.__init__()** accepts `openai_api_key` as a kwarg override (backward compatible)
2. **Dependencies container** initializes all client managers with explicit Settings
3. **Test fixtures** create test Dependencies instances with test API keys
4. **No monkey-patching**: Tests use explicit dependency injection via `test_dependencies` fixture
5. **No env var dependencies**: Removed all `OPENAI_API_KEY` env var checks from `secrets_config.py`

**Key Changes (Updated)**:
- `Dependencies` container: Centralizes all client managers with explicit Settings
- `ProxyClientManager`, `OpenAIClientManager`, `VectorStoreClientManager`: All accept `Settings` in constructor
- Test fixtures: Create test Dependencies instances instead of monkey-patching
- No global state: All dependencies passed explicitly

#### **Issue: Proxy Client Not Detecting API Key Changes**

**Symptoms**: After resetting clients, old API key is still used

**Root Cause**: `reset_client()` wasn't resetting `_last_api_key` tracking variable

**Solution**:
- `ProxyClientManager.reset_client()` now resets both `_last_api_key` and `_last_base_url`
- This forces the client to be recreated with the new API key on next access

#### **Issue: LiteLLM Database Tables Not Initialized**

**Symptoms**: `relation "LiteLLM_VerificationToken" does not exist` errors

**Root Cause**: LiteLLM proxy needs time to initialize its internal database tables after startup

**Solution**:
- `test-note-query-e2e` target now restarts `llm-proxy` after initial startup
- Waits for proxy to be healthy after restart
- This ensures LiteLLM's database tables are created before API key generation

#### **Issue: Database Seeding Wipes LiteLLM API Keys**

**Symptoms**: After running `make db-seed`, API keys are lost

**Root Cause**: Old `db-seed` target was dropping entire `public` schema, which includes LiteLLM's tables

**Solution**:
- `db-seed` target now only drops application-specific tables: `tasks`, `buckets`, `plans`
- LiteLLM tables are preserved: `LiteLLM_VerificationToken`, `LiteLLM_Key`, etc.
- This prevents accidental deletion of API keys during database seeding

#### **Issue: Task Title Truncation Errors During Seeding**

**Symptoms**: `StringDataRightTruncationError: value too long for type character varying(255)` when seeding tasks

**Root Cause**: Some NotePlan tasks have very long titles (>255 characters)

**Solution**:
- This is expected behavior - tasks with very long titles will fail to seed
- The seeding script continues processing other files
- These errors don't prevent tests from running
- Consider truncating task titles before inserting (future enhancement)

#### **Issue: .DS_Store and Cache File Errors During Seeding**

**Symptoms**: Errors when trying to parse `.DS_Store` or files in `/Caches` directory

**Root Cause**: File traversal includes system files and cache directories

**Solution**:
- Filtering logic in `notes/filter.py` ignores:
  - Files/directories named `.DS_Store`
  - Directories named `/Caches`
  - These errors are expected and logged but don't stop seeding
4. Check that `get_settings()` supports overrides: `get_settings(openai_api_key="sk-...")`
5. If still failing, check logs for which API key is being used:
   ```bash
   docker compose logs agentic-api | grep "API key"
   ```

**Fix Applied**:
- `ProxyClientManager._get_settings()` now always calls `get_settings()` (no caching)
- `ProxyClientManager` now uses `settings.openai_api_key` directly from Settings
- Test fixture `inject_test_api_key` monkey-patches `get_settings()` to return overridden instance

#### **Issue: Settings Override Not Working**

**Symptoms**: Passing `get_settings(openai_api_key="sk-...")` doesn't use the provided key

**Root Cause**: Settings may be cached globally, or override not properly passed through

**Solution**:
1. When providing overrides, always pass them to `get_settings()`: `get_settings(openai_api_key="sk-...")`
2. In tests, use the `inject_test_api_key` fixture which handles this automatically
3. If manually testing, call `reset_settings()` first to clear cache:
   ```python
   from knowledge_agents.config.api_config import reset_settings, get_settings
   reset_settings()
   settings = get_settings(openai_api_key="sk-test-key")
   ```
4. Verify `Settings.__init__()` properly handles `openai_api_key` override

#### **Issue: Proxy Client Using Wrong API Key**

**Symptoms**: Proxy client logs show different API key than expected (e.g., using master key instead of test key)

**Root Cause**: Client was created before settings override, or settings cache wasn't cleared

**Solution**:
1. Ensure `ProxyClientManager` resets client when API key changes
2. Call `reset_proxy_clients()` in test fixtures if needed:
   ```python
   from knowledge_agents.clients.proxy_client import reset_proxy_clients
   reset_proxy_clients()
   ```
3. Verify `ProxyClientManager` tracks `_last_api_key` and resets client on change
4. In tests, the `inject_test_api_key` fixture should handle this automatically

#### **Issue: LiteLLM Database Tables Missing**

**Symptoms**: Error `relation 'LiteLLM_VerificationToken' does not exist` or `LiteLLM_VerificationTokenTable` errors

**Root Cause**: LiteLLM proxy database tables not initialized yet

**Solution**:
1. Restart the LiteLLM proxy service: `docker compose restart llm-proxy`
2. Wait for proxy to be healthy: `docker compose ps llm-proxy` should show "healthy"
3. The proxy creates its tables on first startup, but may need a restart if database was recreated
4. In Makefile targets, ensure proxy is restarted after initial startup:
   ```makefile
   @docker compose restart llm-proxy
   @echo "⏳ Waiting for LiteLLM proxy to be healthy after restart..."
   ```

#### **Issue: Database Seeding Wiping LiteLLM API Keys**

**Symptoms**: After running `make db-seed`, API keys are missing or authentication fails

**Root Cause**: Database seeding was dropping entire schema, including LiteLLM's internal tables

**Solution**:
1. The `db-seed` target now only drops application tables (`plans`, `buckets`, `tasks`)
2. LiteLLM tables are preserved: `LiteLLM_VerificationToken`, `LiteLLM_Key`, etc.
3. If you need to reset everything, manually drop LiteLLM tables:
   ```sql
   DROP TABLE IF EXISTS "LiteLLM_VerificationToken" CASCADE;
   DROP TABLE IF EXISTS "LiteLLM_Key" CASCADE;
   -- etc.
   ```
4. Then regenerate API keys: `make litellm-generate-key`

#### **Issue: Test Fixtures Not Injecting API Key**

**Symptoms**: Tests fail with authentication errors, but API key generation fixture runs successfully

**Root Cause**: Fixture ordering or import issues preventing proper injection

**Solution**:
1. Verify `litellm_api_key` fixture is imported in `conftest.py`:
   ```python
   from tst.integration.fixtures.litellm_api_key import *
   ```
2. Ensure `inject_test_api_key` fixture has `autouse=True` and `scope="function"`
3. Check that `inject_test_api_key` depends on `litellm_api_key` fixture
4. Verify no code is calling `get_settings()` before fixtures run (use lazy loading)
5. Check logs to see which API key is actually being used:
   ```bash
   docker compose logs test | grep "API key"
   ```

## 🔄 Dependency Injection Pattern

### **Overview**

The codebase uses **explicit dependency injection** to eliminate global state, lazy loading, monkey-patching, and circular dependencies. All dependencies are passed explicitly through the `Dependencies` container following a clear layered architecture.

### **Architecture Layers**

The codebase follows a strict layered architecture to prevent circular dependencies:

```mermaid
graph TD
    A[Layer 1: Pure Types] --> B[Layer 2: Client Managers]
    B --> C[Layer 3: Dependencies Container]
    C --> D[Layer 4: Services/Agents/Guardrails]
    D --> E[Layer 5: Routers/API]
    
    A1[Settings<br/>Type Definitions] -.->|no dependencies| A
    B1[ProxyClientManager<br/>OpenAIClientManager<br/>VectorStoreClientManager] -.->|depends on Settings| B
    C1[Dependencies<br/>Container] -.->|depends on Settings + Clients| C
    D1[NoteQueryService<br/>NoteQueryAgent<br/>Guardrails] -.->|depends on Dependencies| D
    E1[FastAPI Routers<br/>API Endpoints] -.->|depends on Services| E
    
    style A fill:#e1f5ff
    style B fill:#fff4e1
    style C fill:#e8f5e9
    style D fill:#f3e5f5
    style E fill:#fce4ec
```

**Layer 1: Pure Types (No Dependencies)**
- `Settings` - Configuration only
- Type definitions (`Note`, `Response`, etc.)
- **Key**: These modules have zero dependencies on other application code

**Layer 2: Client Managers (Only depend on Settings)**
- `ProxyClientManager(settings: Settings)`
- `OpenAIClientManager(settings: Settings)`
- `VectorStoreClientManager(settings: Settings)`
- **Key**: Client managers only depend on `Settings`, never on each other or higher layers

**Layer 3: Dependencies Container (Depends on Settings + Clients)**
- `Dependencies(settings: Settings)` - Eagerly initializes all client managers
- **Key**: All client managers are initialized eagerly in `__init__` to avoid lazy loading
- **Key**: Late imports in `__init__` are safe because `__init__` runs at runtime, not import time

**Layer 4: Services/Agents/Guardrails (Depends on Dependencies)**
- `NoteQueryService`, `NoteQueryAgent`
- Guardrails receive `Settings` explicitly
- **Key**: Services receive `Dependencies` container, never import client managers directly

**Layer 5: Routers/API (Depends on Services)**
- FastAPI routers use dependency injection
- **Key**: Routers depend on services, services depend on dependencies

### **Circular Dependency Prevention**

#### **Eager Initialization Pattern**

The `Dependencies` container uses **eager initialization** to eliminate lazy loading and circular dependencies:

```python
class Dependencies:
    def __init__(self, settings: Settings):
        self.settings = settings
        
        # Eagerly initialize all client managers
        # Late imports in __init__ are safe because:
        # 1. __init__ is called at runtime, not import time
        # 2. Client managers only depend on Settings (no cycle)
        # 3. This eliminates the need for lazy loading in properties
        from .clients.proxy_client import ProxyClientManager
        from .clients.vector_store import VectorStoreClientManager
        from .clients.openai import OpenAIClientManager

        self._proxy_client_manager = ProxyClientManager(settings=settings)
        self._vector_store_client_manager = VectorStoreClientManager(settings=settings)
        self._openai_client_manager = OpenAIClientManager(settings=settings)
    
    @property
    def proxy_client_manager(self) -> ProxyClientManager:
        """Simple accessor - no lazy loading."""
        return self._proxy_client_manager
```

**Why this works:**
- Client managers only depend on `Settings` (no circular dependency)
- `Dependencies` depends on `Settings` and client managers (no cycle)
- Late imports in `__init__` are safe because:
  - `__init__` is called at runtime, not import time
  - All dependencies are already imported
  - No circular import risk

#### **Explicit Settings Passing**

All functions that need `Settings` receive it as a required parameter:

```python
# ✅ DO: Require Settings parameter
def get_async_session(settings: Settings) -> AsyncSession:
    """Settings is REQUIRED - no fallback logic."""
    engine = get_async_engine(settings)
    ...

# ❌ DON'T: Use fallback logic or global accessors
def get_async_session(settings: Optional[Settings] = None) -> AsyncSession:
    if settings is None:
        settings = _get_settings()  # ❌ Fallback logic creates circular dependency risk
    ...
```

#### **Type Hints Only Imports**

Use `TYPE_CHECKING` guards for type hints to avoid circular imports:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config.api_config import Settings  # Only for type hints

class ProxyClientManager:
    def __init__(self, settings: "Settings"):  # String annotation
        self.settings = settings
```

### **Key Principles**

1. **No Global State**: All client managers accept `Settings` in their constructor
2. **No Lazy Loading**: Dependencies are initialized eagerly at startup, not on first access
3. **No Monkey-Patching**: Tests create test instances explicitly, don't patch globals
4. **Explicit is Better**: Pass dependencies explicitly, don't fetch from globals
5. **Layered Architecture**: Follow strict dependency layers to prevent cycles
6. **Eager Initialization**: Initialize all dependencies in `__init__`, not in properties

### **Using Dependencies**

#### **In Production Code**

```python
from knowledge_agents.dependencies import Dependencies
from knowledge_agents.config.api_config import Settings

# Initialize at startup
settings = Settings()
dependencies = Dependencies(settings=settings)

# Use in components
client = dependencies.proxy_client_manager.get_client()
vector_store = dependencies.vector_store_client_manager.get_client()
```

#### **In FastAPI Routers**

```python
from fastapi import Depends
from knowledge_agents.dependencies import get_dependencies

@router.get("/endpoint")
async def endpoint(deps: Dependencies = Depends(get_dependencies)):
    # Use dependencies
    client = deps.proxy_client_manager.get_client()
```

#### **In Tests**

```python
@pytest.fixture
def test_dependencies(litellm_api_key):
    """Create test dependencies with test API key."""
    from knowledge_agents.config.api_config import Settings
    from knowledge_agents.dependencies import Dependencies
    
    test_settings = Settings(
        openai_api_key=litellm_api_key,
        environment="test",
    )
    return Dependencies(settings=test_settings)

def test_something(test_dependencies):
    # Use test dependencies
    client = test_dependencies.proxy_client_manager.get_client()
```

### **Migration from Old Pattern**

**Before (Global State)**:
```python
from knowledge_agents.clients.proxy_client import get_proxy_client

client = get_proxy_client()  # Uses global state
```

**After (Dependency Injection)**:
```python
from knowledge_agents.dependencies import Dependencies

# Dependencies passed explicitly
deps = Dependencies(settings=settings)
client = deps.proxy_client_manager.get_client()
```

### **Best Practices**

#### **1. Always Pass Dependencies Explicitly**

✅ **DO**:
```python
from knowledge_agents.dependencies import Dependencies
from knowledge_agents.config.api_config import Settings

# Initialize dependencies
settings = Settings()
deps = Dependencies(settings=settings)

# Use dependencies
client = deps.proxy_client_manager.get_client()
```

❌ **DON'T**:
```python
# Don't use global get_*_client() functions (deprecated)
from knowledge_agents.clients.proxy_client import get_proxy_client
client = get_proxy_client()  # ❌ Uses global state
```

#### **2. Use Test Dependencies in Tests**

✅ **DO**:
```python
def test_something(test_dependencies):
    # Use test dependencies fixture
    client = test_dependencies.proxy_client_manager.get_client()
```

❌ **DON'T**:
```python
# Don't monkey-patch (old pattern, deprecated)
def test_something():
    # Monkey-patch get_settings  # ❌ Old pattern
    client = get_proxy_client()
```

#### **3. Settings Override Pattern (Deprecated)**

⚠️ **NOTE**: The old monkey-patching pattern for test API keys is deprecated. Use `test_dependencies` fixture instead.

**Old Pattern (Deprecated)**:
```python
# Old: Monkey-patch get_settings
from knowledge_agents.config.api_config import get_settings
settings = get_settings(openai_api_key=test_key)
# Monkey-patch get_settings to return this instance
```

**New Pattern (Recommended)**:
```python
# New: Use test dependencies fixture
def test_something(test_dependencies):
    # test_dependencies already has test API key injected
    client = test_dependencies.proxy_client_manager.get_client()
```

#### **4. Always Pass API Key Explicitly**

✅ **DO**:
```python
# Pass api_key explicitly to LitellmModel
model = LitellmModel(model="completion-model", api_key=api_key)

# Pass api_key explicitly to OpenAI clients
client = OpenAI(api_key=api_key, base_url=proxy_url)
```

❌ **DON'T**:
```python
# Don't rely on environment variables
model = LitellmModel(model="completion-model")  # ❌ May not work correctly
```

#### **3. Always Use Proxy Base URL**

✅ **DO**:
```python
# Use proxy base URL from settings
proxy_url = f"http://{settings.litellm_proxy_host}:{settings.litellm_proxy_port}/v1"
client = OpenAI(api_key=api_key, base_url=proxy_url)
```

❌ **DON'T**:
```python
# Don't use default OpenAI base URL
client = OpenAI(api_key=api_key)  # ❌ Will use api.openai.com
```

### **Avoiding Circular Dependencies**

#### **1. Always Pass Settings Explicitly**

✅ **DO**: Require `Settings` as a parameter
```python
def get_async_session(settings: Settings) -> AsyncSession:
    """Settings is required - no fallback."""
    ...
```

❌ **DON'T**: Use fallback logic or global accessors
```python
def get_async_session(settings: Optional[Settings] = None) -> AsyncSession:
    if settings is None:
        settings = get_dependencies().settings  # ❌ Creates circular dependency risk
    ...
```

#### **2. Use TYPE_CHECKING for Type Hints**

✅ **DO**: Use `TYPE_CHECKING` for type-only imports
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config.api_config import Settings  # Only for type hints

class MyClass:
    def __init__(self, settings: "Settings"):
        self.settings = settings
```

❌ **DON'T**: Import at module level when only used for types
```python
from .config.api_config import Settings  # ❌ May cause circular import

class MyClass:
    def __init__(self, settings: Settings):
        ...
```

#### **3. Initialize Dependencies Eagerly**

✅ **DO**: Initialize all dependencies in `__init__`
```python
class Dependencies:
    def __init__(self, settings: Settings):
        # Eagerly initialize - no lazy loading
        from .clients.proxy_client import ProxyClientManager
        self._proxy_client_manager = ProxyClientManager(settings=settings)
```

❌ **DON'T**: Use lazy loading in properties
```python
@property
def proxy_client_manager(self):
    if self._proxy_client_manager is None:
        from .clients.proxy_client import ProxyClientManager  # ❌ Lazy loading
        self._proxy_client_manager = ProxyClientManager(settings=self.settings)
    return self._proxy_client_manager
```

#### **4. Follow Dependency Layers**

✅ **DO**: Follow the layered architecture
- Layer 1 (Types) → Layer 2 (Clients) → Layer 3 (Dependencies) → Layer 4 (Services) → Layer 5 (Routers)
- Never import from higher layers

❌ **DON'T**: Create circular dependencies
```python
# ❌ DON'T: Client manager importing from Dependencies
class ProxyClientManager:
    def __init__(self):
        from ..dependencies import get_dependencies  # ❌ Circular!
        deps = get_dependencies()
```

### **Debugging**

#### **Check Proxy Health**

```bash
# Check proxy health
make litellm-health

# Check proxy logs
docker compose logs -f llm-proxy

# Test proxy directly
curl -H "Authorization: Bearer sk-1234" http://localhost:4000/health
```

#### **Verify API Key**

```bash
# Check if key exists
cat secrets/openai_api_key.txt

# Test key generation
make litellm-generate-key

# Check Docker secret (inside container)
docker compose exec llm-proxy cat /run/secrets/openai_api_key
```

#### **Test Model Configuration**

```bash
# Test completion model
make litellm-code PROMPT="Hello, world!"

# Test embedding model
make litellm-embedding TEXT="Hello, world!"
```

This configuration ensures secure, centralized API key management with no dependencies on environment variables, making the system more reliable and easier to deploy.

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch**
3. **Make your changes**
4. **Run quality checks**: `make release`
5. **Submit a pull request**

Remember: This repository focuses on infrastructure and plumbing. Business logic should be implemented in the `src/` directory following established patterns.
