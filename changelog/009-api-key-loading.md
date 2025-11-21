---
commit: c6a50ea
date: 2025-11-14
type: Changed
---

# API Key Loading

## Description

Centralized API key management in `secrets_config.py`.

## Changes

- Unified loading from Docker secrets, local files, and environment variables
- Removed hardcoded fallback keys
- Better test support with explicit overrides

## Impact

More secure and flexible API key management with better test support.

