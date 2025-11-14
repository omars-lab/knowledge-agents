"""
Utility functions for generating NoteQueryResponse objects from agent results.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.run import RunResult
    from ..types.note import NoteFileResult, NoteQueryResponse, NoteQueryAgentOutput
    from ..tools.noteplan_tools import derive_xcallback_url_from_noteplan_file

logger = logging.getLogger(__name__)


def process_successful_agent_result(
    result: "RunResult",
    agent_output: "NoteQueryAgentOutput",
    answer_text: str,
    relevant_files: list["NoteFileResult"],
    query: str,
    request_id: str,
    derive_xcallback_url_from_noteplan_file: "derive_xcallback_url_from_noteplan_file",
) -> "NoteQueryResponse":
    """
    Process a successful agent result and build the response.
    
    This function handles:
    - Merging agent-provided files with semantic search results
    - Generating NotePlan links for files
    - Building the final answer with links
    - Determining if the query was answered
    
    Args:
        result: The RunResult from Runner.run()
        agent_output: Structured output extracted from the agent
        answer_text: Raw answer text from the agent
        relevant_files: Files found via semantic search
        query: Original user query
        request_id: Request trace ID
        derive_xcallback_url_from_noteplan_file: Function to generate NotePlan links
        
    Returns:
        NoteQueryResponse with processed answer and files
    """
    from ..utils.agent_output_parser import (
        merge_agent_files_with_search_results,
        generate_noteplan_links,
        merge_agent_links_with_generated,
        build_answer_with_links,
    )
    
    # Merge agent-provided files with semantic search results
    regular_files, daily_files = merge_agent_files_with_search_results(
        agent_output, relevant_files
    )
    all_relevant_files = regular_files + daily_files

    # Generate NotePlan links for all files mentioned by agent
    all_agent_files = agent_output.relevant_note_files + agent_output.relevant_daily_files
    generated_links_map = generate_noteplan_links(
        all_agent_files, derive_xcallback_url_from_noteplan_file
    )

    # Combine agent-provided links with generated links (agent links take precedence)
    final_links = merge_agent_links_with_generated(
        agent_output, all_agent_files, generated_links_map
    )

    # Build final answer with links
    # Use reasoning from structured output, not answer_text (which might be RunResult string)
    answer = build_answer_with_links(
        answer_text=agent_output.reasoning if agent_output.reasoning else answer_text,
        reasoning=agent_output.reasoning,
        file_paths=all_agent_files,
        links=final_links,
    )

    # Check if any guardrails were tripped
    guardrails_tripped = []
    if hasattr(result, "guardrails_tripped"):
        guardrails_tripped.extend(result.guardrails_tripped)

    # Determine if query was answered
    query_answered = True
    if not answer or len(answer.strip()) < 10:
        query_answered = False
        logger.warning("Agent produced a very short or empty answer")

    from ..types.note import NoteQueryResponse
    
    return NoteQueryResponse(
        request_id=request_id,
        answer=answer,
        reasoning=agent_output.reasoning,
        relevant_files=all_relevant_files,
        original_query=query,
        query_answered=query_answered,
        guardrails_tripped=guardrails_tripped,
    )


def build_input_guardrail_response(
    guardrail_name: str,
    query: str,
    request_id: str,
) -> "NoteQueryResponse":
    """
    Build response for input guardrail trip.
    
    Args:
        guardrail_name: Name of the guardrail that was tripped
        query: Original user query
        request_id: Request trace ID
        
    Returns:
        NoteQueryResponse indicating input guardrail was tripped
    """
    from ..types.note import NoteQueryResponse
    
    return NoteQueryResponse(
        request_id=request_id,
        answer="I couldn't process your query. Please ask a question about your notes.",
        reasoning=f"Input guardrail tripped: {guardrail_name}",
        relevant_files=[],
        original_query=query,
        query_answered=False,
        guardrails_tripped=[guardrail_name],
    )


def build_output_guardrail_response(
    guardrail_name: str,
    query: str,
    request_id: str,
    relevant_files: list["NoteFileResult"],
) -> "NoteQueryResponse":
    """
    Build response for output guardrail trip.
    
    Args:
        guardrail_name: Name of the guardrail that was tripped
        query: Original user query
        request_id: Request trace ID
        relevant_files: Files found via semantic search
        
    Returns:
        NoteQueryResponse indicating output guardrail was tripped
    """
    from ..types.note import NoteQueryResponse
    
    return NoteQueryResponse(
        request_id=request_id,
        answer="I couldn't provide a reliable answer based on your notes. Please try rephrasing your question.",
        reasoning=f"Output guardrail tripped: {guardrail_name}",
        relevant_files=relevant_files,
        original_query=query,
        query_answered=False,
        guardrails_tripped=[guardrail_name],
    )


def build_error_response(
    error: Exception,
    query: str,
    request_id: str,
    relevant_files: list["NoteFileResult"],
    guardrails_tripped: list[str],
) -> "NoteQueryResponse":
    """
    Build response for unexpected errors.
    
    Args:
        error: The exception that occurred
        query: Original user query
        request_id: Request trace ID
        relevant_files: Files found via semantic search
        guardrails_tripped: List of guardrails that were tripped
        
    Returns:
        NoteQueryResponse indicating an error occurred
    """
    from ..types.note import NoteQueryResponse
    
    # Check if it's a JSON parsing error (truncated output)
    error_str = str(error)
    if "Invalid JSON" in error_str or "EOF while parsing" in error_str:
        logger.error(
            "JSON parsing error detected - agent output may have been truncated. "
            "Consider increasing max_tokens or checking model output limits."
        )
    
    return NoteQueryResponse(
        request_id=request_id,
        answer="An error occurred while processing your query. Please try again.",
        reasoning=f"Error: {error_str}",
        relevant_files=relevant_files,
        original_query=query,
        query_answered=False,
        guardrails_tripped=guardrails_tripped,
    )

