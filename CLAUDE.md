# CLAUDE.md

## Project Overview

**knowledge-agents** is an AI-powered personal knowledge management system built around NotePlan. It provides a FastAPI REST API that answers natural language questions about your notes using semantic search (Qdrant) and OpenAI agents (via LiteLLM proxy to local LM Studio models).

### Core Pipeline
1. User sends query to FastAPI API
2. Input guardrail validates query is note-related
3. Qdrant vector store performs semantic search for relevant notes
4. OpenAI Agent synthesizes an answer from retrieved notes
5. Output guardrail judges answer quality
6. Response returned with answer, relevant files, and NotePlan x-callback-url links

### Tech Stack
- **Language**: Python 3.11
- **Framework**: FastAPI + OpenAI Agents SDK
- **LLM**: LiteLLM proxy → LM Studio (local models)
- **Vector Store**: Qdrant
- **Database**: PostgreSQL + SQLAlchemy
- **Graph DB**: Neo4j (knowledge graph features)
- **Containerization**: Docker Compose
- **Monitoring**: Prometheus

## Package Structure

```
src/knowledge_agents/       # Main package
├── agents/                 # OpenAI agent orchestration
├── guardrails/             # Input/output validation
├── services/               # Business logic layer
├── routers/                # FastAPI route handlers
├── clients/                # Client managers (Qdrant, Neo4j, OpenAI, LiteLLM)
├── config/                 # Settings, logging, model config, secrets
├── database/               # SQLAlchemy models + queries
├── notes/                  # NotePlan file parsing (parser, traversal, filter, generators)
├── prompts/                # Agent/guardrail prompt strings
├── tools/                  # MCP tool integrations (NotePlan x-callback-url)
├── types/                  # Pydantic type definitions
└── utils/                  # Utilities (caching, persistence, text splitting, etc.)
```

## Key Commands

```bash
# Build and run
make build                  # Build Docker images
make start                  # Build + docker-up
make docker-up              # Start services

# Testing
make conda-setup            # Set up conda env for unit tests (first time)
make unit-tests             # Run unit tests locally via conda (fast, no Docker)
make unit-test-one TEST="path"  # Run single unit test
make integration-tests      # Run integration tests in Docker
make test                   # Run all tests in Docker

# Code quality
make format                 # black + isort
make lint                   # flake8
make type-check             # mypy

# Data
make db-seed                # Seed PostgreSQL + Qdrant from NotePlan files
```

## Coding Rules

### No Nested Imports

All imports must be at module level. Nested imports indicate circular dependencies or poor organization.

If circular dependencies exist:
1. Create a utility module (e.g., `utils/guardrail_settings.py`) with module-level imports
2. Import and use the utility function
3. Use `TYPE_CHECKING` blocks for type-hint-only imports

Reference: `src/knowledge_agents/utils/guardrail_settings.py`

### Explicit Dependency Injection

The `Dependencies` class holds all client managers, initialized once at startup, passed explicitly. No global state or lazy loading.

## Testing Rules

### Never Remove or Skip Tests

If a test fails, fix the code — not the test. Never `@pytest.mark.skip` without discussion.

Approach:
1. Consider if the code should be updated to match the test's intent
2. Enhance the test (better data, clearer assertions, more context)
3. Never remove or skip without discussion

### Test Data: Synthetic Only

Unit tests must never contain actual note content or personal data. Use synthetic/fake data that mimics structure.

### Test Workflow

- **During development**: `make unit-tests` (fast, local, no Docker)
- **Before committing**: `make integration-tests` (full Docker stack)
- **Debug specific test**: `make unit-test-one TEST="tst/unit/notes/test_filter.py"`

### Test Markers

- `@pytest.mark.unit` — Unit tests (conda, no external services)
- `@pytest.mark.integration` — Integration tests (Docker, needs DB/Qdrant/LiteLLM)
- `@pytest.mark.slow` — Slow tests
- `@pytest.mark.database` — Database-dependent tests

## Documentation Rules

### Read Before Changing

Always consult `DEVELOPMENT.md` before making structural changes. It covers:
- Architecture patterns and dependency layers
- Testing workflows and fixture patterns
- Code organization and import rules
- Build commands and Docker setup

### Update Docs for Structural Changes

When making architectural changes, update:
- `DEVELOPMENT.md` — Architecture, patterns, workflow changes
- `README.md` — Setup instructions, project overview
- `docs/*.md` — Specific implementation docs

Checklist:
- Architecture diagrams/explanations still accurate
- Code examples match current patterns
- Test commands still work
- Setup instructions still valid
