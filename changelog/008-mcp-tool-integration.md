---
commit: c6a50ea
date: 2025-11-14
type: Changed
---

# MCP Tool Integration

## Description

Switched from `HostedMCPTool` to `function_tool` wrapper.

## Changes

- Better compatibility with LiteLLM proxy (doesn't fully support Responses API MCP tools)
- Works with both ChatCompletions and Responses API
- HTTP-based integration with tidy-mcp service

## Impact

Improved compatibility with LiteLLM proxy and broader API support.

