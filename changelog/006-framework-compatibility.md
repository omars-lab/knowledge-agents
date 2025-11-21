---
commit: c6a50ea
date: 2025-11-14
type: Added
---

# Framework Compatibility

## Description

Added monkey patch for `Usage` class to handle `None` values from LiteLLM proxy.

## Changes

- Prevents Pydantic validation errors when proxy returns incomplete usage data
- Isolated in `utils/usage_patch.py` for maintainability

## Impact

Improves compatibility with LiteLLM proxy by gracefully handling incomplete usage data.

