---
commit: c6a50ea
date: 2025-11-14
type: Added
---

# Response Metadata Headers

## Description

Enhanced API responses with detailed metadata headers.

## Changes

- `X-Model-Name`: Model identifier
- `X-API-Type`: API type (responses/chat_completions)
- `X-Generation-Time-Seconds`: Query processing time
- `X-Model-Class`: Model class name
- `X-Proxy-URL`: Proxy URL if using LiteLLM proxy
- Token count headers (when usage reporting enabled)

## Impact

Provides comprehensive metadata about API responses, enabling better debugging and monitoring.

