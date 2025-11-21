---
commit: c6a50ea
date: 2025-11-14
type: Added
---

# MCP Integration

## Description

Integrated tidy-mcp HTTP service for NotePlan x-callback-url generation.

## Changes

- Uses `function_tool` wrapper to call tidy-mcp HTTP service (compatible with LiteLLM proxy)
- Supports both ChatCompletions and Responses API through proxy
- Configurable tidy-mcp URL via `tidy_mcp_url` setting
- Graceful fallback if MCP service unavailable

## Impact

Enables NotePlan integration for generating x-callback-url links, improving user experience with note navigation.

