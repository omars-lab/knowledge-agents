"""
Graph builder agent using OpenAI agents to extract entities and relationships from notes.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agents import Agent, Runner, gen_trace_id, trace
from agents.extensions.models.litellm_model import LitellmModel
from agents.model_settings import ModelSettings

from ..utils.model_utils import get_model_type_info, get_default_litellm_model
from ..prompts.graph_builder_agent import get_graph_builder_prompt
from ..types.graph import GraphBuilderAgentOutput
from ..utils.agent_output_parser import extract_structured_output

if TYPE_CHECKING:
    from ..dependencies import Dependencies

logger = logging.getLogger(__name__)


async def run_graph_builder_agent(
    note_content: str,
    file_path: str,
    dependencies: "Dependencies",
) -> GraphBuilderAgentOutput:
    """
    Run graph builder agent to extract entities and relationships from note content.

    Args:
        note_content: Content of the note to process
        file_path: Path to the note file
        dependencies: Dependencies container (required)

    Returns:
        GraphBuilderAgentOutput with extracted entities, relationships, and insights
    """
    settings = dependencies.settings
    request_id = gen_trace_id()

    # Create model instance
    # Use ChatCompletions API for graph building (no MCP tools needed)
    use_responses_api = False
    litellm_model = get_default_litellm_model(
        settings=settings, use_responses_api=use_responses_api
    )

    # Log model type information
    model_info = get_model_type_info(litellm_model)
    model_name = getattr(litellm_model, "model", settings.openai_model)
    api_type = model_info["api_type"]

    logger.info(
        f"Graph builder agent model: API={api_type}, "
        f"ModelClass={model_info['model_class']}, "
        f"Model={model_name}"
    )

    # Create model settings
    enable_usage = getattr(settings, "enable_usage_reporting", True)
    model_settings = ModelSettings(
        temperature=0.1,  # Lower temperature for more consistent extraction
        max_tokens=8000,  # Increased for large entity lists (was 2000)
        include_usage=enable_usage,
    )

    # Get prompt
    instructions = get_graph_builder_prompt(note_content, file_path)

    # Create agent with strict schema (enforced via custom JSON schema generators in types)
    agent = Agent[GraphBuilderAgentOutput](
        name="GraphBuilderAgent",
        model=litellm_model,
        model_settings=model_settings,
        instructions=instructions,
        output_type=GraphBuilderAgentOutput,
        # No guardrails needed for graph building - we want to extract everything
    )

    try:
        # Run the agent
        with trace(workflow_name="GraphBuilderAgent", trace_id=request_id):
            # Use the note content as input (the prompt already includes it)
            result = await Runner.run(agent, note_content[:500])  # Use first 500 chars as input

            # Extract structured output from agent result
            agent_output, _ = extract_structured_output(result, GraphBuilderAgentOutput)

            # Handle case where extraction failed
            if agent_output is None:
                logger.warning(f"Could not extract structured output from agent result for {file_path}")
                return GraphBuilderAgentOutput(
                    entities=[],
                    relationships=[],
                    insights=[],
                )

            logger.info(
                f"Extracted {len(agent_output.entities)} entities, "
                f"{len(agent_output.relationships)} relationships, "
                f"{len(agent_output.insights)} insights from {file_path}"
            )

            return agent_output

    except Exception as e:
        logger.error(
            f"Error in graph builder agent for {file_path}: {e}", exc_info=True
        )
        # Return empty output on error
        return GraphBuilderAgentOutput(
            entities=[],
            relationships=[],
            insights=[],
        )

