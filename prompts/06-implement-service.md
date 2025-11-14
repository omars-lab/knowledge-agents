# Service Implementation Process

## Step 1: Read Implementation Specification
Read `docs/03-implementation-spec.md` as the **single source of truth** for all implementation requirements.

**CRITICAL**: Follow the specification exactly - it contains all necessary details for:
- API specifications and endpoint requirements
- Business logic implementation details
- Data models and validation requirements
- Database schema and integration
- Error handling and response formatting

**FOCUS ON CORE FUNCTIONALITY ONLY**: 
- **DO NOT** implement features from the "Future Enhancements" sections
- **DO NOT** add advanced security, caching, or enterprise features
- **FOCUS ONLY** on core business logic and API functionality

## Step 1.5: Spec Alignment Evaluation
Before implementing, evaluate the current implementation against the spec:

### Architecture Alignment Check
- **MCP Server**: Verify using `FastMCP` with `@mcp.tool()` decorators (NOT FastAPI)
- **Main API**: Verify using `FastAPI` for REST endpoints (NOT FastMCP)
- **Agent Integration**: Verify using `MCPServerStreamableHttp` and `mcp_servers=[mcp_server]`
- **Database Separation**: Verify all DB queries in MCP server, main app uses MCP tools
- **Guardrails**: Verify using `@input_guardrail` decorator pattern (NOT custom validation)

### Response Schema Alignment Check
- **Workflow Steps**: Verify using `workflow_steps: List[Tuple[str, str]]` (NOT separate app/action lists)
- **No Confidence Scores**: Verify NO `confidence_score` or `workflow_detected` fields
- **Dataclass Outputs**: Verify using dataclasses for agent outputs and judge evaluations
- **Tuple Structure**: Verify (app, action) pairs for workflow steps

### Configuration Alignment Check
- **Centralized Config**: Verify separate `config.py` files for main app and MCP server
- **Directory Structure**: Verify using `agentic_api` (NOT generic `app`)
- **Import Paths**: Verify all imports use correct `agentic_api` paths

### Implementation Pattern Alignment Check
- **Guardrail-Driven Logic**: Verify confidence comes from guardrails passing (NOT LLM outputs)
- **Agent Execution**: Verify using `Runner.run()` with proper MCP integration
- **Tool Access**: Verify agents use MCP tools (NOT direct HTTP calls)
- **Error Handling**: Verify proper `InputGuardrailTripwireTriggered` exception handling

**If any misalignment is found, refactor the implementation to match the spec before proceeding.**

## Step 2: Implement Core Services
Follow the **Implementation Phases** section from the specification:

### Phase 1: Core API Setup
- Implement FastAPI application as specified
- Set up LLM integration service
- Create basic API endpoints
- Implement input validation with Pydantic models
- Add basic error handling and responses

### Phase 2: Business Logic Implementation
- Implement unsupported app detection logic
- Implement non-workflow text detection logic
- Implement private app filtering logic
- Implement response formatting
- Add business logic error handling

### Phase 3: Database Integration
- Implement database models as specified
- Set up database queries and operations
- Add database connection handling
- Implement data persistence and retrieval

### Phase 4: Agent Integration (if applicable)
- Implement OpenAI Agents framework
- Set up agent tools for business logic
- Implement input/output guardrails
- Set up LLM judge for response validation
- Configure MCP server integration

## Step 3: Error Handling and Resilience
Follow the **Error Handling & Resilience** section from the specification:

### Timeout and Retry Logic
- Implement timeout configuration
- Add retry logic with exponential backoff
- Set up rate limiting
- Implement structured error handling

### Validation and Testing
- Use existing tests as feedback loop
- **Run coverage analysis**: `make test` to check coverage
- **Iterate until coverage targets met**: 80% critical features, 90% API endpoints
- Iterate until all tests pass
- Validate error handling scenarios
- Test edge cases and failure modes
- **Coverage-driven development**: Add tests for uncovered critical paths

## Step 4: Output Documentation
Save the implementation results to `docs/06-implementation-results.md` with:

### Implementation Summary
- **API Endpoints**: Implemented endpoints and functionality
- **Business Logic**: Core business rules implemented
- **Database Integration**: Data models and operations
- **Error Handling**: Error scenarios and responses
- **Test Results**: Test execution and coverage results

### Next Steps
- Reference the implementation specification for review phase
- Ensure all tests are passing
- Verify API endpoints are working correctly
- Confirm database integration is functional

## Step 5: Final Spec Alignment Validation
After implementation, perform a final validation against the specification:

### Final Architecture Validation
- **✅ MCP Server**: Confirm using `FastMCP` with `@mcp.tool()` decorators
- **✅ Main API**: Confirm using `FastAPI` for REST endpoints  
- **✅ Agent Integration**: Confirm using `MCPServerStreamableHttp` and proper MCP integration
- **✅ Database Separation**: Confirm all DB queries in MCP server only
- **✅ Guardrails**: Confirm using `@input_guardrail` decorator pattern

### Final Response Schema Validation
- **✅ Workflow Steps**: Confirm using `workflow_steps: List[Tuple[str, str]]`
- **✅ No Confidence Scores**: Confirm NO `confidence_score` or `workflow_detected` fields
- **✅ Dataclass Outputs**: Confirm using dataclasses for structured outputs
- **✅ Tuple Structure**: Confirm (app, action) pairs for workflow steps

### Final Implementation Pattern Validation
- **✅ Guardrail-Driven Logic**: Confirm confidence from guardrails passing
- **✅ Agent Execution**: Confirm using `Runner.run()` with MCP integration
- **✅ Tool Access**: Confirm agents use MCP tools (not direct HTTP calls)
- **✅ Error Handling**: Confirm proper guardrail exception handling

### Final Configuration Validation
- **✅ Centralized Config**: Confirm separate `config.py` files
- **✅ Directory Structure**: Confirm using `agentic_api` naming
- **✅ Import Paths**: Confirm all imports use correct paths

**If any validation fails, refactor immediately to match the specification before considering implementation complete.**