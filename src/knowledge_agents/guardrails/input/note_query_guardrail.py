"""
Note query input guardrail using OpenAI agents pattern.

This guardrail uses an agent to determine if input is a valid question about notes.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from agents import (
    Agent,
    GuardrailFunctionOutput,
    InputGuardrailTripwireTriggered,
    RunContextWrapper,
    Runner,
    TResponseInputItem,
)
from agents.extensions.models.litellm_model import LitellmModel
from agents.model_settings import ModelSettings
from pydantic import BaseModel

if TYPE_CHECKING:
    from ...config.api_config import Settings

from ...prompts.note_query_guardrail import get_note_query_guardrail_prompt
from ...types.response import GuardrailType
from ...utils.exception_handlers import GuardrailExceptionHandler
from ...utils.guardrail_metrics_util import record_guardrail_metrics
from ...utils.guardrail_settings import get_settings_for_guardrail
from ...utils.model_utils import get_default_litellm_model, is_using_responses_api

logger = logging.getLogger(__name__)


class NoteQueryDetectionOutput(BaseModel):
    """Output from the note query detection guardrail agent."""

    is_note_query: bool
    reasoning: str


def get_note_query_guardrail_agent(settings: "Settings") -> Agent:
    """
    Get note query guardrail agent with LiteLLM model.

    Args:
        settings: Application settings instance (required)
    """
    litellm_model = get_default_litellm_model(settings=settings)

    # Enable include_usage based on settings flag
    # The monkey patch in utils/usage_patch.py handles None values for usage details
    is_responses = is_using_responses_api(litellm_model)
    enable_usage = getattr(settings, "enable_usage_reporting", True)
    include_usage = enable_usage
    logger.info(
        f"Input guardrail model: API={'responses' if is_responses else 'chat_completions'}, "
        f"include_usage={include_usage} (enabled={enable_usage} via enable_usage_reporting setting)"
    )
    model_settings = ModelSettings(
        temperature=settings.openai_temperature,
        max_tokens=settings.openai_max_tokens,
        include_usage=include_usage,
    )

    # Use the model instance directly (same pattern as main agent)
    return Agent(
        name="NoteQueryDetectionGuardrail",
        instructions=get_note_query_guardrail_prompt(),
        model=litellm_model,  # Pass the model instance, not a string
        output_type=NoteQueryDetectionOutput,
        model_settings=model_settings,
    )


async def note_query_guardrail(
    ctx: RunContextWrapper[None], agent: Agent, input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    """Guardrail to detect if input is a question about notes."""
    start_time = time.time()
    logger.info("NOTE QUERY GUARDRAIL: Starting note query guardrail check")

    try:
        # Extract input string
        if isinstance(input, list):
            input_str = " ".join(str(item) for item in input)
        else:
            input_str = str(input)

        logger.info(f"NOTE QUERY GUARDRAIL: Checking input: {input_str[:100]}...")

        # Get guardrail agent - use the same API key as the main agent's model
        # The main agent's model was created with settings from dependencies,
        # and litellm.api_key should be set to that key. Use it to ensure consistency.
        settings = get_settings_for_guardrail()
        note_query_guardrail_agent = get_note_query_guardrail_agent(settings=settings)

        # Run guardrail agent
        logger.info("NOTE QUERY GUARDRAIL: Running note query guardrail agent")
        result = await Runner.run(
            note_query_guardrail_agent,
            input_str,
            context=ctx.context,
        )
        logger.info("NOTE QUERY GUARDRAIL: Agent run completed successfully")

        is_valid = result.final_output.is_note_query

        logger.info(
            f"NOTE QUERY GUARDRAIL: Result - is_note_query={result.final_output.is_note_query}, "
            f"reasoning={result.final_output.reasoning}"
        )

        record_guardrail_metrics(
            guardrail_type=GuardrailType.DESCRIBES_NOTE_QUERY.value,
            log_prefix="NOTE QUERY GUARDRAIL",
            tripwire_triggered=not is_valid,
            start_time=start_time,
            result_data={
                "is_note_query": result.final_output.is_note_query,
                "reasoning": result.final_output.reasoning,
            },
        )

        logger.info(
            f"NOTE QUERY GUARDRAIL: Returning tripwire_triggered={not is_valid}"
        )
        return GuardrailFunctionOutput(
            output_info=result.final_output,
            tripwire_triggered=not is_valid,
        )

    except Exception as e:
        logger.error(
            f"NOTE QUERY GUARDRAIL: {type(e).__name__}: {str(e)}", exc_info=True
        )
        record_guardrail_metrics(
            guardrail_type=GuardrailType.DESCRIBES_NOTE_QUERY.value,
            log_prefix="NOTE QUERY GUARDRAIL",
            tripwire_triggered=True,
            start_time=start_time,
            result_data={"error": str(e)},
        )

        error_response = GuardrailExceptionHandler.handle_guardrail_exception(
            exception=e,
            output_type=NoteQueryDetectionOutput,
            log_prefix="Note query guardrail",
            guardrail_type=GuardrailType.DESCRIBES_NOTE_QUERY.value,
        )
        logger.info(
            f"NOTE QUERY GUARDRAIL: Exception handler returned: {error_response}"
        )
        return GuardrailFunctionOutput(**error_response)
