"""
Utility functions for generating response metadata headers.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.run import RunResult
    from ..config.api_config import Settings

logger = logging.getLogger(__name__)


def build_response_metadata(
    result: "RunResult",
    settings: "Settings",
    model_name: str,
    api_type: str,
    model_class: str,
    proxy_url: str | None,
    generation_time: float,
) -> dict[str, str]:
    """
    Build metadata dictionary for response headers.
    
    Args:
        result: The RunResult from Runner.run()
        settings: Application settings
        model_name: Name of the model used
        api_type: API type ("responses" or "chat_completions")
        model_class: Model class name
        proxy_url: Proxy URL if using proxy, None otherwise
        generation_time: Generation time in seconds
        
    Returns:
        Dictionary of metadata headers to include in response
    """
    from .usage_extraction import extract_usage_tokens
    
    enable_usage = getattr(settings, "enable_usage_reporting", True)
    
    # Build base metadata
    metadata = {
        "X-Model-Name": model_name,
        "X-API-Type": api_type,
        "X-Generation-Time-Seconds": f"{generation_time:.3f}",
        "X-Model-Class": model_class,
        "X-Proxy-URL": proxy_url if proxy_url else "none",
    }
    
    # Add token counts if usage reporting is enabled
    if enable_usage:
        input_tokens, output_tokens, total_tokens = extract_usage_tokens(result)
        
        # Only add token headers if we have real data (not None, >= 0)
        if input_tokens is not None and input_tokens >= 0:
            metadata["X-Input-Tokens"] = str(input_tokens)
        if output_tokens is not None and output_tokens >= 0:
            metadata["X-Output-Tokens"] = str(output_tokens)
        if total_tokens is not None and total_tokens >= 0:
            metadata["X-Total-Tokens"] = str(total_tokens)
        
        # Log if we expected usage but didn't get it
        if input_tokens is None and output_tokens is None and total_tokens is None:
            logger.warning(
                "Usage reporting enabled but no token counts found. "
                "Checked: context_wrapper.usage, raw_responses[-1].usage, result.usage. "
                "This may indicate include_usage=False or the proxy not returning usage data."
            )
    
    return metadata


def build_error_metadata(
    settings: "Settings",
    model_name: str,
    api_type: str,
    model_class: str,
    proxy_url: str | None,
    generation_time: float,
) -> dict[str, str]:
    """
    Build metadata dictionary for error response headers.
    
    Args:
        settings: Application settings
        model_name: Name of the model used
        api_type: API type ("responses" or "chat_completions")
        model_class: Model class name
        proxy_url: Proxy URL if using proxy, None otherwise
        generation_time: Generation time in seconds
        
    Returns:
        Dictionary of metadata headers to include in error response
    """
    return {
        "X-Model-Name": model_name,
        "X-API-Type": api_type,
        "X-Generation-Time-Seconds": f"{generation_time:.3f}",
        "X-Model-Class": model_class,
        "X-Proxy-URL": proxy_url if proxy_url else "none",
    }

