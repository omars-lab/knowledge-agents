"""
Utility functions for extracting usage/token information from agent results.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.run import RunResult

logger = logging.getLogger(__name__)


def extract_usage_tokens(result: "RunResult") -> tuple[int | None, int | None, int | None]:
    """
    Extract token counts from RunResult.
    
    Usage can be found in multiple places:
    1. result.context_wrapper.usage (aggregated usage from all responses)
    2. result.raw_responses[-1].usage (usage from last model response)
    3. result.usage (if it exists as a direct attribute)
    
    Args:
        result: The RunResult from Runner.run()
        
    Returns:
        Tuple of (input_tokens, output_tokens, total_tokens) or (None, None, None) if not found
    """
    usage = None
    
    # Try context_wrapper.usage first (aggregated usage)
    if hasattr(result, "context_wrapper") and hasattr(result.context_wrapper, "usage"):
        usage = result.context_wrapper.usage
        logger.debug(f"Found usage in context_wrapper.usage: {usage}, type: {type(usage)}")
    
    # Try raw_responses (last response usage)
    if (usage is None or (hasattr(usage, "total_tokens") and usage.total_tokens == 0)) and hasattr(result, "raw_responses") and result.raw_responses:
        last_response = result.raw_responses[-1]
        if hasattr(last_response, "usage") and last_response.usage:
            usage = last_response.usage
            logger.debug(f"Found usage in raw_responses[-1].usage: {usage}, type: {type(usage)}")
    
    # Try direct result.usage attribute
    if (usage is None or (hasattr(usage, "total_tokens") and usage.total_tokens == 0)) and hasattr(result, "usage"):
        usage = result.usage
        logger.debug(f"Found usage in result.usage: {usage}, type: {type(usage)}")
    
    if not usage:
        logger.debug("No usage data found in result")
        return None, None, None
    
    # Log all attributes of usage object for debugging
    usage_attrs = [a for a in dir(usage) if not a.startswith('_')]
    logger.debug(f"Usage object attributes: {usage_attrs}")
    
    # Try multiple attribute names for compatibility
    input_tokens = (
        getattr(usage, "input_tokens", None) 
        or getattr(usage, "prompt_tokens", None)
    )
    output_tokens = (
        getattr(usage, "output_tokens", None) 
        or getattr(usage, "completion_tokens", None)
    )
    total_tokens = getattr(usage, "total_tokens", None)
    
    # Try to get from details if main attributes are None
    if input_tokens is None and hasattr(usage, "input_tokens_details"):
        input_tokens_details = getattr(usage, "input_tokens_details", None)
        if input_tokens_details:
            input_tokens = getattr(input_tokens_details, "cached_tokens", None)
    
    if output_tokens is None and hasattr(usage, "output_tokens_details"):
        output_tokens_details = getattr(usage, "output_tokens_details", None)
        if output_tokens_details:
            output_tokens = getattr(output_tokens_details, "reasoning_tokens", None)
    
    # Log what we found for debugging
    logger.info(
        f"Usage from result: input={input_tokens}, output={output_tokens}, total={total_tokens} "
        f"(usage object: {type(usage)})"
    )
    
    # If we have total_tokens but individual counts are None, log it
    if total_tokens is not None and (input_tokens is None or output_tokens is None):
        logger.debug(f"Have total_tokens={total_tokens} but missing individual counts")
    
    return input_tokens, output_tokens, total_tokens

