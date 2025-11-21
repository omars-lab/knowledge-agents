---
commit: c6a50ea
date: 2025-11-14
type: Added
---

# Usage Reporting

## Description

Added configurable usage reporting with token counts in response headers.

## Changes

- Added `enable_usage_reporting` setting to control usage collection
- Extracts input/output/total tokens from agent results
- Includes `X-Input-Tokens`, `X-Output-Tokens`, `X-Total-Tokens` headers when enabled
- Handles multiple usage data sources: `context_wrapper.usage`, `raw_responses[-1].usage`, `result.usage`

## Impact

Provides visibility into token usage for API consumers, enabling cost tracking and optimization.

