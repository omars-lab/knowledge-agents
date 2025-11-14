"""
Judge Note Answer Guardrail using OpenAI agents pattern.

This guardrail uses an agent to evaluate the quality and accuracy of answers about notes.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from agents import (
    Agent,
    GuardrailFunctionOutput,
    RunContextWrapper,
    Runner,
    TResponseInputItem,
)
from agents.extensions.models.litellm_model import LitellmModel
from agents.model_settings import ModelSettings
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ...config.api_config import Settings

from ...prompts.judge_note_answer_guardrail import (
    get_judge_note_answer_guardrail_prompt,
)
from ...types.note import NoteFileResult, NoteQueryResponse
from ...types.response import GuardrailType
from ...utils.exception_handlers import GuardrailExceptionHandler
from ...utils.guardrail_metrics_util import record_guardrail_metrics
from ...utils.guardrail_settings import get_settings_for_guardrail
from ...utils.model_utils import get_default_litellm_model, is_using_responses_api

logger = logging.getLogger(__name__)


class JudgeNoteAnswerOutput(BaseModel):
    """Output from the judge note answer guardrail agent."""

    score: str = Field(
        ...,
        description="Score for the agent's answer: 'pass', 'needs_improvement', 'fail'",
    )
    reasoning: str = Field(..., description="Reasoning for the score")
    tripwire_triggered: bool = Field(
        ...,
        description="True if the answer is unacceptable and should trip the guardrail",
    )


def get_judge_note_answer_agent(settings: "Settings") -> Agent:
    """
    Get judge note answer agent with LiteLLM model.

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
        f"Output guardrail model: API={'responses' if is_responses else 'chat_completions'}, "
        f"include_usage={include_usage} (enabled={enable_usage} via enable_usage_reporting setting)"
    )
    model_settings = ModelSettings(
        temperature=settings.openai_temperature,
        max_tokens=settings.openai_max_tokens,
        include_usage=include_usage,
    )
    # Use the model instance directly (same pattern as main agent and input guardrail)
    return Agent(
        name="JudgeNoteAnswerGuardrail",
        instructions=get_judge_note_answer_guardrail_prompt(),
        model=litellm_model,  # Pass the model instance, not a string
        output_type=JudgeNoteAnswerOutput,
        model_settings=model_settings,
    )


async def judge_note_answer_guardrail(
    ctx: RunContextWrapper[None],
    agent: Agent,
    output: Union[NoteQueryResponse, str, TResponseInputItem],
) -> GuardrailFunctionOutput:
    """
    Guardrail to judge the quality and accuracy of the agent's answer to a note query.
    """
    start_time = time.time()
    logger.info(
        "JUDGE NOTE ANSWER GUARDRAIL: Starting judge note answer guardrail check"
    )

    # Extract the answer and relevant files from the agent's output
    answer_text: str = ""
    relevant_files_info: List[Dict[str, Any]] = []
    original_query: str = ""

    if isinstance(output, NoteQueryResponse):
        answer_text = output.answer
        original_query = output.original_query
        relevant_files_info = [f.model_dump() for f in output.relevant_files]
    elif isinstance(output, str):
        answer_text = output
        # In this case, we don't have structured relevant files or original query
        logger.warning(
            "JUDGE NOTE ANSWER GUARDRAIL: Agent output is a string, missing structured data."
        )
    else:
        # Attempt to convert TResponseInputItem to string or extract content
        answer_text = str(output)
        logger.warning(
            f"JUDGE NOTE ANSWER GUARDRAIL: Unexpected agent output type: {type(output)}"
        )

    # Construct the input for the judge agent
    judge_input = {
        "original_query": original_query,
        "agent_answer": answer_text,
        "relevant_files": relevant_files_info,
    }

    try:
        logger.info("JUDGE NOTE ANSWER GUARDRAIL: Getting judge note answer agent")
        # Get guardrail agent - use the same API key as the main agent's model
        # The main agent's model was created with settings from dependencies,
        # and litellm.api_key should be set to that key. Use it to ensure consistency.
        settings = get_settings_for_guardrail()
        judge_agent = get_judge_note_answer_agent(settings=settings)
        logger.info("JUDGE NOTE ANSWER GUARDRAIL: Running judge note answer agent")
        result = await Runner.run(judge_agent, judge_input, context=ctx.context)
        logger.info("JUDGE NOTE ANSWER GUARDRAIL: Agent run completed successfully")

        judge_output: JudgeNoteAnswerOutput = result.final_output

        # Record metrics
        record_guardrail_metrics(
            guardrail_type=GuardrailType.JUDGES_NOTE_ANSWER.value,
            log_prefix="JUDGE NOTE ANSWER GUARDRAIL",
            tripwire_triggered=judge_output.tripwire_triggered,
            start_time=start_time,
            result_data={
                "score": judge_output.score,
                "reasoning": judge_output.reasoning,
            },
        )

        logger.info(
            f"JUDGE NOTE ANSWER GUARDRAIL: Score={judge_output.score}, "
            f"Tripwire={judge_output.tripwire_triggered}, Reasoning={judge_output.reasoning}"
        )

        return GuardrailFunctionOutput(
            output_info=judge_output,
            tripwire_triggered=judge_output.tripwire_triggered,
        )

    except Exception as e:
        logger.error(
            f"JUDGE NOTE ANSWER GUARDRAIL: {type(e).__name__}: {str(e)}", exc_info=True
        )
        record_guardrail_metrics(
            guardrail_type=GuardrailType.JUDGES_NOTE_ANSWER.value,
            log_prefix="JUDGE NOTE ANSWER GUARDRAIL",
            tripwire_triggered=False,  # Do not trip on judge error, allow agent output to pass
            start_time=start_time,
            result_data={"error": str(e)},
        )

        error_response = GuardrailExceptionHandler.handle_guardrail_exception(
            exception=e,
            output_type=JudgeNoteAnswerOutput,
            log_prefix="Judge note answer guardrail",
            guardrail_type=GuardrailType.JUDGES_NOTE_ANSWER.value,
        )
        logger.info(
            f"JUDGE NOTE ANSWER GUARDRAIL: Exception handler returned: {error_response}"
        )
        return GuardrailFunctionOutput(**error_response)
