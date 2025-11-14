# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Agent File Organization Refactoring**: Separated agent orchestration from response generation, usage extraction, and metadata building
  - Created `utils/response_generator.py` for response construction logic
  - Created `utils/metadata_utils.py` for response header generation
  - Created `utils/usage_extraction.py` for token count extraction
  - Created `utils/usage_patch.py` for framework compatibility (monkey patch for Usage class)
  - Reduced `note_query_agent.py` from 455 to 312 lines (~31% reduction)
- **Usage Reporting**: Added configurable usage reporting with token counts in response headers
  - Added `enable_usage_reporting` setting to control usage collection
  - Extracts input/output/total tokens from agent results
  - Includes `X-Input-Tokens`, `X-Output-Tokens`, `X-Total-Tokens` headers when enabled
  - Handles multiple usage data sources: `context_wrapper.usage`, `raw_responses[-1].usage`, `result.usage`
- **Response Metadata Headers**: Enhanced API responses with detailed metadata
  - `X-Model-Name`: Model identifier
  - `X-API-Type`: API type (responses/chat_completions)
  - `X-Generation-Time-Seconds`: Query processing time
  - `X-Model-Class`: Model class name
  - `X-Proxy-URL`: Proxy URL if using LiteLLM proxy
  - Token count headers (when usage reporting enabled)
- **MCP Integration**: Integrated tidy-mcp HTTP service for NotePlan x-callback-url generation
  - Uses `function_tool` wrapper to call tidy-mcp HTTP service (compatible with LiteLLM proxy)
  - Supports both ChatCompletions and Responses API through proxy
  - Configurable tidy-mcp URL via `tidy_mcp_url` setting
  - Graceful fallback if MCP service unavailable
- **API Key Management**: Centralized API key loading and separation
  - Created `secrets_config.py` for unified secret management
  - Supports multiple sources: Docker secrets (`/run/secrets/openai_api_key`), local files (`secrets/openai_api_key.txt`), environment variables
  - Test-friendly: Supports API key overrides via `Settings(openai_api_key="...")`
  - Removed hardcoded fallback keys for better security
  - Clear separation between production and test key handling
- **Framework Compatibility**: Added monkey patch for `Usage` class to handle `None` values from LiteLLM proxy
  - Prevents Pydantic validation errors when proxy returns incomplete usage data
  - Isolated in `utils/usage_patch.py` for maintainability

### Changed
- **Agent Architecture**: Refactored agent files to focus on orchestration only
  - Response generation moved to dedicated utility modules
  - Improved separation of concerns and testability
  - Better code organization and maintainability
- **MCP Tool Integration**: Switched from `HostedMCPTool` to `function_tool` wrapper
  - Better compatibility with LiteLLM proxy (doesn't fully support Responses API MCP tools)
  - Works with both ChatCompletions and Responses API
  - HTTP-based integration with tidy-mcp service
- **API Key Loading**: Centralized API key management in `secrets_config.py`
  - Unified loading from Docker secrets, local files, and environment variables
  - Removed hardcoded fallback keys
  - Better test support with explicit overrides
- **Error Handling**: Improved error response generation
  - Centralized error response building in `response_generator.py`
  - Consistent error messages across all error types
  - Better JSON parsing error detection and logging

### Fixed
- **Import Error**: Fixed `NoteQueryResponse` not defined error in `response_generator.py`
  - Added runtime import for `NoteQueryResponse` in `process_successful_agent_result()`
- **Usage Extraction**: Fixed token count extraction to handle multiple attribute names
  - Supports both `input_tokens`/`output_tokens` and `prompt_tokens`/`completion_tokens`
  - Handles usage details objects when main attributes are None

## [Previous Releases]

### Note Query System Implementation
- Note query agent for answering questions about personal notes
- Semantic search integration with Qdrant vector store
- NotePlan markdown parsing and database seeding
- Input/output guardrails for query validation and answer quality
- FastAPI endpoints for note queries

### Infrastructure
- Docker-based development environment
- LiteLLM proxy integration for LLM access
- PostgreSQL database for structured note data
- Qdrant vector store for semantic search
- Prometheus metrics collection

---

## How to Update This Changelog

When adding new features or changes:

1. **Added**: New features
2. **Changed**: Changes in existing functionality
3. **Deprecated**: Soon-to-be removed features
4. **Removed**: Removed features
5. **Fixed**: Bug fixes
6. **Security**: Security fixes

Add entries under `[Unreleased]` section. When releasing, move entries to a new versioned section.

