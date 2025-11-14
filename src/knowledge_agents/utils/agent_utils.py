"""
Agent utility functions for working with OpenAI agents framework.
"""
import logging

logger = logging.getLogger(__name__)


def extract_guardrail_name(guardrail_exception) -> str:
    """
    Safely extract guardrail name from exception, with fallback for errors.

    COMPLEX LOGIC EXPLANATION:
    The OpenAI agents framework can structure guardrail exceptions in different ways:
    1. guardrail_exception.guardrail_result.guardrail.name (preferred)
    2. guardrail_exception.guardrail.get_name() (alternative)
    3. guardrail_exception.guardrail.name (fallback)

    This function tries all approaches to extract the guardrail name safely.
    Influenced by: https://github.com/openai/openai-agents-python/blob/cfddc7c214f8234b20c1c4ca7f085093c79ff90c/src/agents/run.py#L1522-L1534

    Args:
        guardrail_exception: Exception from the OpenAI agents framework

    Returns:
        Guardrail name as string, or "unknown_guardrail" if extraction fails
    """
    try:
        # APPROACH 1: Check if it has guardrail_result with guardrail.name
        # This is the most common structure in the agents framework
        if (
            hasattr(guardrail_exception, "guardrail_result")
            and guardrail_exception.guardrail_result
        ):
            guardrail_result = guardrail_exception.guardrail_result
            if hasattr(guardrail_result, "guardrail") and guardrail_result.guardrail:
                if hasattr(guardrail_result.guardrail, "name"):
                    return guardrail_result.guardrail.name

        # APPROACH 2: Fallback - Check if it has guardrail attribute directly
        # Some exceptions might have the guardrail object directly attached
        if hasattr(guardrail_exception, "guardrail") and guardrail_exception.guardrail:
            if hasattr(guardrail_exception.guardrail, "get_name"):
                return guardrail_exception.guardrail.get_name()
            elif hasattr(guardrail_exception.guardrail, "name"):
                return guardrail_exception.guardrail.name

        # APPROACH 3: Ultimate fallback - return generic name
        return "unknown_guardrail"
    except Exception as e:
        # SAFETY: If any extraction fails, log error and return safe fallback
        logger.error(f"Error extracting guardrail name: {e}")
        return "unknown_guardrail"
