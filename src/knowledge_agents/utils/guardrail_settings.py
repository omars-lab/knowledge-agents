"""
Utility functions for extracting settings for guardrail agents.

This module provides utilities to extract Settings for guardrail agents,
avoiding nested imports and circular dependencies. Guardrails need access
to Settings to create their own sub-agents, but they can't change their
function signatures (they're called by the agents framework).

The solution is to extract settings from:
1. Dependencies (if initialized) - preferred for tests
2. litellm.api_key (if set) - from the main agent's model
3. Global settings (fallback) - for production
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import litellm

from ..config.api_config import Settings, get_settings
from ..dependencies import get_dependencies

if TYPE_CHECKING:
    pass  # TYPE_CHECKING imports would go here if needed

logger = logging.getLogger(__name__)


def get_settings_for_guardrail() -> Settings:
    """
    Get Settings for guardrail agents.

    This function extracts settings in the following priority:
    1. From dependencies (if initialized) - preferred for tests
    2. From litellm.api_key (if set) - from the main agent's model
    3. From global settings (fallback) - for production

    Returns:
        Settings instance with the appropriate API key

    Raises:
        RuntimeError: If no settings can be obtained
    """

    # Try to get settings from dependencies first (has test API key in tests)
    try:
        deps = get_dependencies()
        base_settings = deps.settings

        # Use the API key from litellm module if set (from main agent's model),
        # otherwise use the key from dependencies
        api_key = getattr(litellm, "api_key", None) or base_settings.openai_api_key

        # Create settings with the correct API key
        settings = Settings(
            openai_api_key=api_key,
            environment=base_settings.environment,
            qdrant_collection_name=base_settings.qdrant_collection_name,
        )
        logger.debug(
            f"GUARDRAIL SETTINGS: Using API key from dependencies/litellm (first 10 chars: {api_key[:10]}...)"
        )
        return settings
    except RuntimeError:
        # Dependencies not initialized, use global settings
        settings = get_settings()
        # Override with litellm.api_key if available (from main agent)
        if hasattr(litellm, "api_key") and litellm.api_key:
            settings.openai_api_key = litellm.api_key
            logger.debug(
                f"GUARDRAIL SETTINGS: Using API key from litellm module (first 10 chars: {litellm.api_key[:10]}...)"
            )
        else:
            logger.debug("GUARDRAIL SETTINGS: Using global settings")
        return settings

