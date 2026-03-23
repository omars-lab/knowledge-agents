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
├── claude_agent/           # Claude Agent SDK multi-turn agent (NEW)
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

# Claude Agent
make claude-agent-up        # Start Claude Agent + dependencies
make claude-agent-down      # Stop Claude Agent
make claude-agent-logs      # View logs
make claude-agent-test      # Run unit tests
make claude-agent-eval      # Run eval suite
make claude-agent-chat MSG="query"  # Quick chat test
make claude-agent-graph             # Render full knowledge graph as SVG
make claude-agent-graph ENTITY="X"  # Render connections for entity X
make claude-agent-auth-seed         # Refresh auth from host keychain
make claude-agent-auth-status       # Check auth + token expiry

# LM Studio (embedding infrastructure on Mac Studio)
make lm-studio-status       # Check server, loaded models, API
make lm-studio-load-embeddings  # Load embedding model
make lm-studio-test-embedding   # Test embedding pipeline
```

### Claude Code Skills
- `/knowledge <query>` — Query notes, build graphs, visualize connections via the Claude Agent

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

### Add Logging to Debug Issues That Survive First Attempt

When a bug or failure cannot be fixed on the first attempt, add structured logging before the next attempt. This ensures repeating issues are diagnosable from logs alone, without needing to reproduce interactively.

Rules:
- Log at **INFO** level: request lifecycle (start, tools used, result, duration), client connections (success/failure), and cost
- Log at **DEBUG** level: SDK subprocess stderr, raw event types, tool input/output details
- Log at **ERROR** level with `exc_info=True`: all caught exceptions, including elapsed time and context (session_id, tool name, query snippet)
- Include a **request_id** in all log lines for request-scoped correlation
- Use `logging.LoggerAdapter` for per-request context rather than modifying global state
- Write logs to both console and rotating file (`build/logs/<service>.log`, 10MB, 5 backups)
- Claude Agent service logging is configured in `server.py:_setup_logging()`

### Document Hard-Won Learnings

When discovering non-obvious gotchas, limitations, or workarounds during implementation, document them immediately in this section. These are things that are not derivable from the code alone and will save future debugging time.

### Gotchas (Living Section — add new entries as discovered)

1. **`@tool()` decorator returns `SdkMcpTool`, not a callable.** To call tool handlers in tests, use `.handler`: `await my_tool.handler(args)`, not `await my_tool(args)`.

2. **`tools=TOOL_NAMES` restricts available tools; `allowed_tools` only controls permissions.** Without `tools=`, the agent has access to ALL Claude Code tools (Bash, Read, Write, ToolSearch) and will use them unpredictably.

3. **`CLAUDE_CODE_STREAM_CLOSE_TIMEOUT` defaults to 60s — kills multi-tool queries.** The SDK silently closes stdin after this timeout when SDK MCP servers are present (`anyio.move_on_after` in `query.py:wait_for_result_and_end_input`). Set to `1800000` (30 min) via env var in docker-compose.yml. Without this, queries die with `CLIConnectionError: ProcessTransport is not ready for writing`. Note: even with the timeout raised, single-turn multi-tool queries can take 5-10+ minutes due to subscription-tier API rate limiting between tool calls. **Best practice: split complex workflows into multi-turn conversations** where each turn does one tool call — this is both faster and more reliable.

4. **Blocking I/O in tool handlers kills the subprocess.** The SDK runs an async event loop to service CLI keepalive messages. Synchronous Neo4j/HTTP calls block this loop, causing `CLIConnectionError: ProcessTransport is not ready for writing`. Always use `asyncio.to_thread()` for blocking operations.

5. **Neo4j schema setup is slow on first call.** Move `setup_graph_schema()` to `init_tool_clients()` at startup, not inside tool handlers. The `IF NOT EXISTS` DDL statements are idempotent but add latency.

6. **OAuth tokens expire ~every 6 hours.** Container auth is stored in a named volume (`claude_agent_config`). Use `make claude-agent-auth-status` to check, `make claude-agent-auth-seed` to refresh from host keychain, `make claude-agent-login` for interactive re-auth.

7. **LiteLLM healthcheck script takes 60s with `--location` flag + API key.** Use `/health/liveliness` endpoint instead of the complex healthcheck script for Docker healthchecks.

8. **Claude API rate limiting causes silent waits, not errors.** The CLI auto-retries 429s with backoff. This manifests as 60-300s response times, not error messages. The SDK emits `RateLimitEvent` with `status` (allowed/allowed_warning/rejected) and `utilization` %. The agent logs these at INFO/WARNING level. The eval runner has `--delay` (seconds between cases, default 3) and `--timeout` (seconds per request, default 300) to manage pacing.

9. **Docker compose env changes require `--force-recreate`, not just restart.** Changing `docker-compose.yml` environment variables (e.g., `LM_STUDIO_HOST`) then running `docker compose up -d` does NOT update running containers. You must use `docker compose up -d --force-recreate <service>` to pick up env var changes. Symptom: container still uses old values (check with `docker exec <container> env | grep VAR`).

10. **LiteLLM proxy config references are resolved at container start, not at request time.** If the LM Studio IP changes (DHCP) or you switch from IP to hostname, the LiteLLM proxy must be recreated. The config file (`config/litellm_config.yaml`) may also cache the host — check both `docker-compose.yml` env vars AND the config file.

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
- `@pytest.mark.claude_agent` — Claude Agent integration tests (needs services + Claude credentials)
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

## Use Cases

See [docs/USE_CASES.md](docs/USE_CASES.md) for the complete use-case catalog mapping features to code.

## Living Documents

These documents must be kept up to date as features are added or changed:
- **`docs/USE_CASES.md`** -- When adding a new feature or agent capability, add a use case entry with links to the implementing code, tests, and evals
- **`docs/GRAPH_SCHEMA.md`** -- When adding node types, relationship types, link resolution rules, or entity properties
- **`docs/OBSERVABILITY.md`** -- When adding metrics, changing log format, or modifying the observability stack
- **`docs/TECH_DESIGN.md`** -- When making architecture decisions, changing models, or modifying infrastructure
- **`docs/SECTION_INDEXING_PIPELINE.md`** -- When changing the section indexing pipeline, models, storage schema, or CLI flags
- **`CLAUDE.md`** -- When adding new commands, conventions, or architectural patterns
- **`DEVELOPMENT.md`** -- When changing build/test workflows or architecture
- **`README.md`** -- When changing setup instructions or project overview
