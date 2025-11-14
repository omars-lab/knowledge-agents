"""
Note query agent using OpenAI agents to answer questions about notes.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from agents import (
    Agent,
    InputGuardrail,
    InputGuardrailTripwireTriggered,
    OutputGuardrail,
    OutputGuardrailTripwireTriggered,
    Runner,
    gen_trace_id,
    trace,
)
from agents.tool import function_tool
from agents.extensions.models.litellm_model import LitellmModel
from agents.model_settings import ModelSettings

from ..database.queries.query_vector_store import VectorStoreQueries
from ..guardrails.input import note_query_guardrail
from ..utils.model_utils import is_using_responses_api, get_model_type_info
from ..guardrails.output import judge_note_answer_guardrail
from ..prompts.note_query_agent import augment_prompt
from ..tools.noteplan_tools import derive_xcallback_url_from_noteplan_file
from ..types.note import NoteFileResult, NoteQueryResponse, NoteQueryAgentOutput
from ..types.response import GuardrailType
from ..utils.agent_utils import extract_guardrail_name
from ..utils.agent_output_parser import extract_structured_output
from ..utils.response_generator import (
    process_successful_agent_result,
    build_input_guardrail_response,
    build_output_guardrail_response,
    build_error_response,
)
from ..utils.model_utils import get_default_litellm_model

if TYPE_CHECKING:
    from ..dependencies import Dependencies

logger = logging.getLogger(__name__)


async def run_note_query_agent(
    query: str, dependencies: "Dependencies"
) -> tuple[NoteQueryResponse, dict[str, str]]:
    """
    Run note query agent to answer questions about notes.

    EXECUTION ORDER:
    1. INPUT GUARDRAILS:
       - note_query_guardrail: Validates input is a question about notes

    2. SEMANTIC SEARCH (runs before agent):
       - Performs semantic vector search on user query to find relevant note files
       - Augments prompt with relevant note file information

    3. ANSWER GENERATION AGENT (only runs if input guardrails pass):
       - Uses AI to answer the question based on relevant notes
       - Synthesizes information from multiple note files if needed

    4. OUTPUT GUARDRAILS:
       - judge_note_answer_guardrail: Evaluates quality and accuracy of the answer

    Args:
        query: User's question about notes
        dependencies: Dependencies container (required)
    """
    settings = dependencies.settings
    request_id = gen_trace_id()
    start_time = time.time()
    
    # Initialize metadata variables (will be set when model is created)
    model_name = settings.openai_model
    api_type = "unknown"
    model_info = {"model_class": "unknown"}

    # Perform semantic vector search to find relevant note files
    logger.info(f"Performing semantic search for note files: {query[:100]}...")
    try:
        search_limit = settings.semantic_search_limit
        vector_store_queries = VectorStoreQueries(dependencies=dependencies)
        semantic_results = vector_store_queries.query_files_semantically(
            query=query, limit=search_limit
        )
        logger.info(f"Found {len(semantic_results)} relevant note files")
    except Exception as e:
        logger.error(f"Error performing semantic search: {e}", exc_info=True)
        semantic_results = []
        search_limit = settings.semantic_search_limit

    # Convert semantic results to NoteFileResult format
    relevant_files = [
        NoteFileResult(
            file_path=result["file_path"],
            file_name=result["file_name"],
            similarity_score=result["similarity_score"],
            modified_at=result.get("modified_at"),
        )
        for result in semantic_results
    ]

    # Augment prompt with semantic search results
    augmented_instructions = augment_prompt(semantic_results, search_limit)

    # Create model instance - use Responses API if HostedMCPTool is needed or model requires it
    # Check if we should use Responses API (for HostedMCPTool support)
    use_responses_api = settings.use_responses_api_for_mcp_tools if hasattr(settings, "use_responses_api_for_mcp_tools") else False
    # Model config will auto-detect if model requires Responses API
    litellm_model = get_default_litellm_model(settings=settings, use_responses_api=use_responses_api)
    
    # Log model type information for verification
    model_info = get_model_type_info(litellm_model)
    
    # Get proxy URL for logging (if using proxy)
    proxy_url = None
    if is_using_responses_api(litellm_model):
        # For Responses API, get proxy URL from AsyncOpenAI client if available
        if hasattr(litellm_model, 'openai_client') and hasattr(litellm_model.openai_client, 'base_url'):
            proxy_url = str(litellm_model.openai_client.base_url)
    else:
        # For ChatCompletions API, get proxy URL from settings
        proxy_base_url = f"http://{settings.litellm_proxy_host}:{settings.litellm_proxy_port}"
        proxy_url = f"{proxy_base_url}/v1"
    
    logger.info(
        f"Agent model configuration: API={model_info['api_type']}, "
        f"ModelClass={model_info['model_class']}, "
        f"SupportsMCPTools={model_info['supports_mcp_tools']}, "
        f"ProxyURL={proxy_url}"
    )
    
    # Get model name for metadata
    model_name = getattr(litellm_model, "model", settings.openai_model)
    api_type = model_info['api_type']

    # Create model settings
    # Enable include_usage based on settings flag
    # The monkey patch in utils/usage_patch.py handles None values for usage details
    enable_usage = getattr(settings, "enable_usage_reporting", True)
    include_usage = enable_usage
    logger.info(
        f"Main agent model: API={api_type}, include_usage={include_usage} "
        f"(enabled={enable_usage} via enable_usage_reporting setting)"
    )
    model_settings = ModelSettings(
        temperature=settings.openai_temperature,
        max_tokens=settings.openai_max_tokens,
        include_usage=include_usage,
    )
    # Verify the setting was applied correctly
    if model_settings.include_usage != True:
        logger.warning(
            f"WARNING: include_usage is {model_settings.include_usage}, expected True!"
        )
    else:
        logger.info(f"Verified: model_settings.include_usage = {model_settings.include_usage}")

    # Create agent with guardrails and tools
    # Add NotePlan x-callback-url tool so agent can generate shareable links
    # Note: We use function_tool instead of HostedMCPTool because:
    # 1. LiteLLM proxy doesn't support Responses API MCP tools (HostedMCPTool)
    # 2. function_tool works with both ChatCompletions and Responses API through proxy
    # 3. function_tool wraps the MCP tool as a regular function that makes HTTP calls to tidy-mcp
    agent_tools = []
    try:
        # Always use function_tool when going through proxy (works with both APIs)
        noteplan_tool = function_tool(derive_xcallback_url_from_noteplan_file)
        agent_tools.append(noteplan_tool)
        logger.debug(
            f"NotePlan x-callback-url tool added as function_tool "
            f"(calls tidy-mcp HTTP service at {settings.tidy_mcp_url})"
        )
    except Exception as e:
        logger.warning(f"Could not add NotePlan tool: {e}")
    
    agent = Agent[NoteQueryAgentOutput](
        name="NoteQueryAgent",
        model=litellm_model,  # Pass the model instance, not a string
        model_settings=model_settings,
        instructions=augmented_instructions,
        tools=agent_tools,  # Include NotePlan tools for generating shareable links
        output_type=NoteQueryAgentOutput,
        input_guardrails=[
            InputGuardrail(
                note_query_guardrail,
                name=GuardrailType.DESCRIBES_NOTE_QUERY.value,
            ),
        ],
        output_guardrails=[
            OutputGuardrail(
                judge_note_answer_guardrail,
                name=GuardrailType.JUDGES_NOTE_ANSWER.value,
            ),
        ],
    )

    # Track guardrails that were tripped
    guardrails_tripped = []

    try:
        # Run the agent
        with trace(workflow_name="NoteQueryAgent", trace_id=request_id):
            result = await Runner.run(agent, query)

            # Extract structured output from agent result
            agent_output, answer_text = extract_structured_output(result, NoteQueryAgentOutput)

            # Process successful result into response
            response = process_successful_agent_result(
                result=result,
                agent_output=agent_output,
                answer_text=answer_text,
                relevant_files=relevant_files,
                query=query,
                request_id=request_id,
                derive_xcallback_url_from_noteplan_file=derive_xcallback_url_from_noteplan_file,
            )
            
            # Update guardrails_tripped from response
            guardrails_tripped.extend(response.guardrails_tripped)

            # Calculate generation time
            generation_time = time.time() - start_time
            
            # Build metadata for response headers (includes usage extraction if enabled)
            from ..utils.metadata_utils import build_response_metadata
            metadata = build_response_metadata(
                result=result,
                settings=settings,
                model_name=model_name,
                api_type=api_type,
                model_class=model_info['model_class'],
                proxy_url=proxy_url,
                generation_time=generation_time,
            )

            return response, metadata

    except InputGuardrailTripwireTriggered as e:
        guardrail_name = extract_guardrail_name(e)  # Pass exception object, not string
        guardrails_tripped.append(guardrail_name)
        logger.warning(f"Input guardrail tripped: {guardrail_name}")

        generation_time = time.time() - start_time
        from ..utils.metadata_utils import build_error_metadata
        metadata = build_error_metadata(
            settings=settings,
            model_name=model_name,
            api_type=api_type,
            model_class=model_info.get('model_class', 'unknown'),
            proxy_url=proxy_url,
            generation_time=generation_time,
        )

        response = build_input_guardrail_response(
            guardrail_name=guardrail_name,
            query=query,
            request_id=request_id,
        )
        return response, metadata

    except OutputGuardrailTripwireTriggered as e:
        guardrail_name = extract_guardrail_name(e)  # Pass exception object, not string
        guardrails_tripped.append(guardrail_name)
        logger.warning(f"Output guardrail tripped: {guardrail_name}")

        generation_time = time.time() - start_time
        from ..utils.metadata_utils import build_error_metadata
        metadata = build_error_metadata(
            settings=settings,
            model_name=model_name,
            api_type=api_type,
            model_class=model_info.get('model_class', 'unknown'),
            proxy_url=proxy_url,
            generation_time=generation_time,
        )

        response = build_output_guardrail_response(
            guardrail_name=guardrail_name,
            query=query,
            request_id=request_id,
            relevant_files=relevant_files,
        )
        return response, metadata

    except Exception as e:
        logger.error(f"Unexpected error in note query agent: {e}", exc_info=True)
        generation_time = time.time() - start_time
        
        from ..utils.metadata_utils import build_error_metadata
        metadata = build_error_metadata(
            settings=settings,
            model_name=model_name,
            api_type=api_type,
            model_class=model_info.get('model_class', 'unknown'),
            proxy_url=proxy_url,
            generation_time=generation_time,
        )

        response = build_error_response(
            error=e,
            query=query,
            request_id=request_id,
            relevant_files=relevant_files,
            guardrails_tripped=guardrails_tripped,
        )
        return response, metadata
