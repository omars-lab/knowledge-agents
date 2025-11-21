# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Note**: Detailed changelog entries are stored in the [`changelog/`](changelog/) directory, each mapped to a specific git commit. See [changelog/README.md](changelog/README.md) for the complete index.

## [Unreleased]

**Commit:** `c6a50ea` (2025-11-14)

### Added
- **Agent File Organization Refactoring** - [Details](changelog/001-agent-file-organization-refactoring.md)
  - Separated agent orchestration from response generation, usage extraction, and metadata building
  - Created `utils/response_generator.py` for response construction logic
  - Created `utils/metadata_utils.py` for response header generation
  - Created `utils/usage_extraction.py` for token count extraction
  - Created `utils/usage_patch.py` for framework compatibility (monkey patch for Usage class)
  - Reduced `note_query_agent.py` from 455 to 312 lines (~31% reduction)
- **Usage Reporting** - [Details](changelog/002-usage-reporting.md)
  - Added configurable usage reporting with token counts in response headers
  - Added `enable_usage_reporting` setting to control usage collection
  - Extracts input/output/total tokens from agent results
  - Includes `X-Input-Tokens`, `X-Output-Tokens`, `X-Total-Tokens` headers when enabled
  - Handles multiple usage data sources: `context_wrapper.usage`, `raw_responses[-1].usage`, `result.usage`
- **Response Metadata Headers** - [Details](changelog/003-response-metadata-headers.md)
  - Enhanced API responses with detailed metadata
  - `X-Model-Name`: Model identifier
  - `X-API-Type`: API type (responses/chat_completions)
  - `X-Generation-Time-Seconds`: Query processing time
  - `X-Model-Class`: Model class name
  - `X-Proxy-URL`: Proxy URL if using LiteLLM proxy
  - Token count headers (when usage reporting enabled)
- **MCP Integration** - [Details](changelog/004-mcp-integration.md)
  - Integrated tidy-mcp HTTP service for NotePlan x-callback-url generation
  - Uses `function_tool` wrapper to call tidy-mcp HTTP service (compatible with LiteLLM proxy)
  - Supports both ChatCompletions and Responses API through proxy
  - Configurable tidy-mcp URL via `tidy_mcp_url` setting
  - Graceful fallback if MCP service unavailable
- **API Key Management** - [Details](changelog/005-api-key-management.md)
  - Centralized API key loading and separation
  - Created `secrets_config.py` for unified secret management
  - Supports multiple sources: Docker secrets (`/run/secrets/openai_api_key`), local files (`secrets/openai_api_key.txt`), environment variables
  - Test-friendly: Supports API key overrides via `Settings(openai_api_key="...")`
  - Removed hardcoded fallback keys for better security
  - Clear separation between production and test key handling
- **Framework Compatibility** - [Details](changelog/006-framework-compatibility.md)
  - Added monkey patch for `Usage` class to handle `None` values from LiteLLM proxy
  - Prevents Pydantic validation errors when proxy returns incomplete usage data
  - Isolated in `utils/usage_patch.py` for maintainability
- **Neo4j Graph Infrastructure** - [Details](changelog/015-neo4j-graph-infrastructure.md)
  - Complete Neo4j integration for knowledge graph construction from NotePlan notes
  - Graph builder agent for extracting entities and relationships using LLM
  - Vector store seeding with LiteLLM proxy for embeddings
  - Graph database seeding with entities, relationships, and indexes
  - Docker-based graph builder service with live code updates
  - Strict JSON schema validation for graph types
  - Makefile targets for Neo4j operations (seed, build, query, manage service)
  - Foundation for graph-powered RAG combining vector search with graph patterns

### Changed
- **Agent Architecture** - [Details](changelog/007-agent-architecture-refactor.md)
  - Refactored agent files to focus on orchestration only
  - Response generation moved to dedicated utility modules
  - Improved separation of concerns and testability
  - Better code organization and maintainability
- **MCP Tool Integration** - [Details](changelog/008-mcp-tool-integration.md)
  - Switched from `HostedMCPTool` to `function_tool` wrapper
  - Better compatibility with LiteLLM proxy (doesn't fully support Responses API MCP tools)
  - Works with both ChatCompletions and Responses API
  - HTTP-based integration with tidy-mcp service
- **API Key Loading** - [Details](changelog/009-api-key-loading.md)
  - Centralized API key management in `secrets_config.py`
  - Unified loading from Docker secrets, local files, and environment variables
  - Removed hardcoded fallback keys
  - Better test support with explicit overrides
- **Error Handling** - [Details](changelog/010-error-handling.md)
  - Improved error response generation
  - Centralized error response building in `response_generator.py`
  - Consistent error messages across all error types
  - Better JSON parsing error detection and logging

### Fixed
- **Import Error** - [Details](changelog/011-import-error-fix.md)
  - Fixed `NoteQueryResponse` not defined error in `response_generator.py`
  - Added runtime import for `NoteQueryResponse` in `process_successful_agent_result()`
- **Usage Extraction** - [Details](changelog/012-usage-extraction-fix.md)
  - Fixed token count extraction to handle multiple attribute names
  - Supports both `input_tokens`/`output_tokens` and `prompt_tokens`/`completion_tokens`
  - Handles usage details objects when main attributes are None

## [Previous Releases]

**Commit:** `a945fde` (2025-11-03)

### Note Query System Implementation - [Details](changelog/013-note-query-system-implementation.md)
- Note query agent for answering questions about personal notes
- Semantic search integration with Qdrant vector store
- NotePlan markdown parsing and database seeding
- Input/output guardrails for query validation and answer quality
- FastAPI endpoints for note queries

### Infrastructure - [Details](changelog/014-infrastructure.md)
- Docker-based development environment
- LiteLLM proxy integration for LLM access
- PostgreSQL database for structured note data
- Qdrant vector store for semantic search
- Prometheus metrics collection

---

## How to Update This Changelog

When adding new features or changes:

1. **Create a detailed entry** in the `changelog/` directory:
   - Use format: `XXX-description.md` (where XXX is the next sequential number)
   - Include commit hash, date, type, description, changes, and impact
   - See existing entries for format reference

2. **Update the main CHANGELOG.md**:
   - Add a summary entry under the appropriate section (`[Unreleased]` or versioned section)
   - Link to the detailed entry: `[Details](changelog/XXX-description.md)`
   - Include commit hash and date in the section header

3. **Update changelog/README.md**:
   - Add the new entry to the index

4. **Entry types**:
   - **Added**: New features
   - **Changed**: Changes in existing functionality
   - **Deprecated**: Soon-to-be removed features
   - **Removed**: Removed features
   - **Fixed**: Bug fixes
   - **Security**: Security fixes

Add entries under `[Unreleased]` section. When releasing, move entries to a new versioned section.

