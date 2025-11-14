"""
Monkey patch for Usage class to handle None values from proxy.

This patch fixes validation errors when the LiteLLM proxy returns None
for input_tokens_details and output_tokens_details fields.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Track if patch has been applied to avoid double-patching
_patch_applied = False


def apply_usage_patch() -> None:
    """
    Apply monkey patch to Usage class to handle None values.
    
    This patch converts None values for input_tokens_details and output_tokens_details
    to default values before the Usage constructor is called, preventing Pydantic
    validation errors when the proxy returns None for these fields.
    """
    global _patch_applied
    
    if _patch_applied:
        logger.debug("Usage patch already applied, skipping")
        return
    
    try:
        from agents.usage import Usage as OriginalUsage
        from openai.types.responses.response_usage import InputTokensDetails, OutputTokensDetails
        
        # Store original __init__ if not already patched
        if not hasattr(OriginalUsage, '_original_init'):
            OriginalUsage._original_init = OriginalUsage.__init__
            
            def patched_usage_init(self, *args, **kwargs):
                # Convert None values to defaults for usage details
                if 'input_tokens_details' in kwargs and kwargs['input_tokens_details'] is None:
                    kwargs['input_tokens_details'] = InputTokensDetails(cached_tokens=0)
                if 'output_tokens_details' in kwargs and kwargs['output_tokens_details'] is None:
                    kwargs['output_tokens_details'] = OutputTokensDetails(reasoning_tokens=0)
                # Call original __init__
                return OriginalUsage._original_init(self, *args, **kwargs)
            
            OriginalUsage.__init__ = patched_usage_init
            _patch_applied = True
            logger.debug("✅ Applied Usage class patch to handle None values for usage details")
        else:
            _patch_applied = True
            logger.debug("Usage class already patched (found _original_init)")
            
    except ImportError as e:
        logger.warning(f"Could not apply Usage patch - import error: {e}")

