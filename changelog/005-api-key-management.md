---
commit: c6a50ea
date: 2025-11-14
type: Added
---

# API Key Management

## Description

Centralized API key loading and separation.

## Changes

- Created `secrets_config.py` for unified secret management
- Supports multiple sources: Docker secrets (`/run/secrets/openai_api_key`), local files (`secrets/openai_api_key.txt`), environment variables
- Test-friendly: Supports API key overrides via `Settings(openai_api_key="...")`
- Removed hardcoded fallback keys for better security
- Clear separation between production and test key handling

## Impact

Improved security by removing hardcoded keys and providing flexible key management across different deployment environments.

