"""
Utility functions for creating model instances with LiteLLM proxy
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import litellm
from agents import OpenAIResponsesModel
from agents.extensions.models.litellm_model import LitellmModel
from openai import AsyncOpenAI

from ..config.model_config import is_responses_model

if TYPE_CHECKING:
    from ..config.api_config import Settings

logger = logging.getLogger(__name__)


def get_default_litellm_model(
    settings: "Settings", model: str = None, use_responses_api: bool = False
) -> LitellmModel | OpenAIResponsesModel:
    """
    Get a default model instance configured for the LiteLLM proxy or OpenAI Responses API.

    Args:
        settings: Application settings instance (required)
        model: Model name to use. If None, uses the completion model from settings.
               For Responses API, should be an OpenAI model name (e.g., "gpt-4", "gpt-4o").
        use_responses_api: If True, use OpenAIResponsesModel (requires OpenAI API, not LiteLLM proxy).
                          This enables HostedMCPTool support.

    Returns:
        LitellmModel instance configured for proxy (ChatCompletions API), or
        OpenAIResponsesModel for Responses API (supports HostedMCPTool)
    """

    # Get API key from settings (explicitly provided)
    api_key = settings.openai_api_key

    # Never default to a key - raise an error if no key is found
    if not api_key:
        raise ValueError(
            "OpenAI API key is required. " "Provide it via Settings at initialization."
        )
    
    # Log the key being used (first and last few chars for debugging)
    key_preview = f"{api_key[:10]}...{api_key[-4:]}" if len(api_key) > 14 else api_key[:10]
    logger.debug(f"Using API key: {key_preview} (length: {len(api_key)})")

    # If using Responses API, use OpenAIResponsesModel (required for HostedMCPTool)
    if use_responses_api:
        # For Responses API, use responses model from settings (via proxy)
        model_name = getattr(settings, "litellm_proxy_responses_model", "lm_studio/gpt-oss-20b")
        
        # Get proxy configuration for Responses API
        proxy_base_url = (
            f"http://{settings.litellm_proxy_host}:{settings.litellm_proxy_port}"
        )
        proxy_url = f"{proxy_base_url}/v1"
        
        logger.info(
            f"Using OpenAIResponsesModel for Responses API support via LiteLLM proxy "
            f"(model: {model_name}, proxy: {proxy_url}, api_key: {api_key[:10]}...)"
        )
        logger.warning(
            f"Note: LiteLLM proxy may not fully support Responses API MCP tools. "
            f"If HostedMCPTool fails, consider using function_tool instead."
        )
        # OpenAIResponsesModel with AsyncOpenAI configured to use LiteLLM proxy
        # This supports HostedMCPTool which requires Responses API
        # Configure AsyncOpenAI to route through LiteLLM proxy
        openai_client = AsyncOpenAI(
            api_key=api_key,
            base_url=proxy_url,  # Route through LiteLLM proxy
        )
        responses_model = OpenAIResponsesModel(model=model_name, openai_client=openai_client)
        
        # Apply monkey patch to handle None values in usage details (if needed)
        # This fixes validation errors when proxy returns None for usage details fields
        from .usage_patch import apply_usage_patch
        apply_usage_patch()
        
        logger.debug(f"Created OpenAIResponsesModel with model={model_name} via proxy {proxy_url}")
        logger.warning(
            "Note: OpenAIResponsesModel may have issues with proxy usage data. "
            "If you see Usage validation errors, consider using LitellmModel instead."
        )
        return responses_model

    # For ChatCompletions API, use LitellmModel with LiteLLM proxy
    # Determine model name - use completion model from settings
    model_name = settings.litellm_proxy_completion_model

    # Get proxy configuration
    proxy_base_url = (
        f"http://{settings.litellm_proxy_host}:{settings.litellm_proxy_port}"
    )
    proxy_url = f"{proxy_base_url}/v1"

    # Log warning if API key doesn't start with "sk-"
    if api_key and not api_key.startswith("sk-"):
        logger.warning(
            f"API key does not start with 'sk-': {api_key[:20]}... "
            f"(length: {len(api_key)}). This may be a non-standard key format."
        )

    # Explicitly configure LiteLLM module-level settings
    # LitellmModel reads from litellm.api_base and litellm.api_key at runtime
    litellm.api_base = proxy_url
    litellm.api_key = api_key

    logger.info(
        f"Configuring LitellmModel for ChatCompletions API: {proxy_url}, model: {model_name}, "
        f"api_key: {api_key[:10]}..."
    )

    # Create the model - proxy will route the model name to underlying model
    # Pass api_key explicitly from settings
    # Note: model_name must match exactly the model_name in litellm_config.yaml
    # Since litellm.api_base is set to the proxy URL, LiteLLM should route through the proxy
    # and preserve the full model name including the "lm_studio/" prefix
    litellm_model = LitellmModel(model=model_name, api_key=api_key)

    logger.debug(
        f"Created LitellmModel with model={model_name} (proxy base_url={proxy_url})"
    )
    return litellm_model


def is_using_responses_api(model_instance: LitellmModel | OpenAIResponsesModel) -> bool:
    """
    Check if a model instance is using Responses API.

    Args:
        model_instance: The model instance to check

    Returns:
        True if using OpenAIResponsesModel (Responses API), False if using LitellmModel (ChatCompletions API)
    """
    return isinstance(model_instance, OpenAIResponsesModel)


def get_model_type_info(model_instance: LitellmModel | OpenAIResponsesModel) -> dict[str, str]:
    """
    Get information about the model instance type and API being used.

    Args:
        model_instance: The model instance to inspect

    Returns:
        Dictionary with model type information:
        - "api_type": "responses" or "chat_completions"
        - "model_class": Class name of the model instance
        - "supports_mcp_tools": Whether the model supports HostedMCPTool
    """
    is_responses = is_using_responses_api(model_instance)
    
    return {
        "api_type": "responses" if is_responses else "chat_completions",
        "model_class": model_instance.__class__.__name__,
        "supports_mcp_tools": is_responses,
    }
