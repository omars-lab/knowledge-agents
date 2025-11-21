---
commit: c6a50ea
date: 2025-11-14
type: Fixed
---

# Usage Extraction Fix

## Description

Fixed token count extraction to handle multiple attribute names.

## Changes

- Supports both `input_tokens`/`output_tokens` and `prompt_tokens`/`completion_tokens`
- Handles usage details objects when main attributes are None

## Impact

More robust token counting that works with different API response formats.

