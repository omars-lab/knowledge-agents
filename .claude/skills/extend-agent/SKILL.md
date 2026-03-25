---
name: extend-agent
description: Guide for adding a new @tool() to the Claude Agent MCP server
user_invocable: true
---

# /extend-agent — Add a new tool to the Claude Agent

Guide for adding a new @tool() to the Claude Agent MCP server.

## Steps

1. **Define the tool function** in `src/knowledge_agents/claude_agent/tools.py`:
   - Add a new function with the `@tool()` decorator
   - Include `name`, `description`, and `input_schema` parameters
   - The function should be `async def` and accept `args: dict[str, Any]`
   - Return `{"content": [{"type": "text", "text": "..."}]}` on success
   - Return `{"content": [...], "is_error": True}` on failure

2. **Register in ALL_TOOLS and TOOL_NAMES** at the bottom of `tools.py`:
   - Add the function reference to `ALL_TOOLS`
   - Add `"mcp__notes__<tool_name>"` to `TOOL_NAMES`

3. **Update the system prompt** in `src/knowledge_agents/claude_agent/prompts.py`:
   - Add a section documenting the new tool under `## Capabilities`
   - Add any new workflow patterns that use the tool

4. **Create unit test** in `tst/unit/claude_agent/test_tools.py`:
   - Test success case with mocked dependencies
   - Test error handling
   - Test edge cases (empty input, invalid data)

5. **Add eval test cases** in `evals/claude_agent/datasets/tool_selection.json`:
   - Add a case that verifies the agent selects the new tool appropriately

6. **Update docs** in `docs/CLAUDE_AGENT_ARCHITECTURE.md`:
   - Add the tool to the tools table
   - Update any workflow diagrams if applicable

7. **Update use case doc** in `docs/USE_CASES.md` if the tool enables a new use case
