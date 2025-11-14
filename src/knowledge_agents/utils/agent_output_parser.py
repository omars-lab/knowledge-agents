"""
Utility functions for parsing and processing agent output.

This module handles extraction and processing of structured output from agents,
including file categorization, link generation, and answer building.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from notes.noteplan_structure import is_daily_plan_file

from ..types.note import NoteFileResult, NoteQueryAgentOutput

if TYPE_CHECKING:
    from agents.run import RunResult

logger = logging.getLogger(__name__)


def extract_structured_output(
    result: "RunResult", output_type: type
) -> tuple["NoteQueryAgentOutput", str]:
    """
    Extract structured output from agent RunResult.

    Args:
        result: The RunResult from Runner.run()
        output_type: The expected output type (Pydantic BaseModel)

    Returns:
        Tuple of (structured_output, answer_text)
    """
    structured_output: "NoteQueryAgentOutput" | None = None
    answer_text = ""

    # Log what we're working with for debugging
    logger.debug(f"RunResult type: {type(result)}")
    logger.debug(f"RunResult attributes: {dir(result)}")

    # Try multiple ways to extract structured output
    # 1. Check result.final_output directly
    if hasattr(result, "final_output"):
        final_output = result.final_output
        logger.debug(f"result.final_output type: {type(final_output)}, value: {final_output}")
        
        if isinstance(final_output, output_type):
            structured_output = final_output
            logger.info("✅ Extracted structured output from result.final_output")
        elif hasattr(final_output, "__dict__"):
            # Try to construct from dict if it's a similar object
            try:
                structured_output = output_type(**final_output.__dict__)
                logger.info("✅ Constructed structured output from result.final_output.__dict__")
            except Exception as e:
                logger.debug(f"Could not construct from __dict__: {e}")
        elif isinstance(final_output, str):
            # Check if it's a JSON string that might be truncated
            if final_output.strip().startswith("{") and not final_output.strip().endswith("}"):
                logger.warning(
                    f"⚠️ Detected potentially truncated JSON in final_output (starts with {{ but doesn't end with }}). "
                    f"Length: {len(final_output)}. This may indicate max_tokens is too low."
                )
                # Try to extract reasoning from partial JSON if possible
                if '"reasoning"' in final_output:
                    try:
                        import json
                        # Try to parse what we have and extract reasoning
                        # This is a best-effort attempt
                        reasoning_match = final_output.split('"reasoning"')[1] if '"reasoning"' in final_output else None
                        if reasoning_match:
                            # Try to extract the reasoning value
                            parts = reasoning_match.split('"', 2)
                            if len(parts) >= 3:
                                answer_text = parts[2].split('"')[0] if '"' in parts[2] else parts[2].split(',')[0]
                    except Exception:
                        pass
    
    # 2. Check result.output
    if structured_output is None and hasattr(result, "output"):
        output = result.output
        logger.debug(f"result.output type: {type(output)}, value: {output}")
        
        if isinstance(output, output_type):
            structured_output = output
            logger.info("✅ Extracted structured output from result.output")
        elif isinstance(output, dict):
            # Try to construct from dict (works for Pydantic models)
            try:
                structured_output = output_type(**output)
                logger.info("✅ Constructed structured output from result.output dict")
            except Exception as e:
                logger.debug(f"Could not construct from dict: {e}")
        elif hasattr(output, "model_dump"):
            # Pydantic model - try to convert
            try:
                structured_output = output_type(**output.model_dump())
                logger.info("✅ Constructed structured output from Pydantic model")
            except Exception as e:
                logger.debug(f"Could not construct from Pydantic model: {e}")
    
    # 3. Check result.content (might contain structured data)
    if structured_output is None and hasattr(result, "content"):
        content = result.content
        logger.debug(f"result.content type: {type(content)}")
        
        if isinstance(content, output_type):
            structured_output = content
            logger.info("✅ Extracted structured output from result.content")
        elif isinstance(content, dict):
            try:
                structured_output = output_type(**content)
                logger.info("✅ Constructed structured output from result.content dict")
            except Exception as e:
                logger.debug(f"Could not construct from content dict: {e}")
        elif isinstance(content, str):
            answer_text = content

    # Fallback: try to extract answer text from result
    if structured_output is None:
        logger.warning("⚠️ Agent output not in expected structured format, using fallback")
        logger.warning(f"RunResult repr: {repr(result)}")
        
        # Try to extract text from final_output if it's a string
        if not answer_text:
            if hasattr(result, "final_output") and result.final_output:
                final_output = result.final_output
                if isinstance(final_output, str):
                    # Check if it's a RunResult string representation
                    if "RunResult:" in final_output and "Final output" in final_output:
                        # Try to extract the actual content from the RunResult string
                        # Format: "Final output (str):\n    <content>"
                        lines = final_output.split("\n")
                        for i, line in enumerate(lines):
                            if "Final output" in line and i + 1 < len(lines):
                                # Get the content after "Final output (str):"
                                # Skip the first line after "Final output" if it's just "(str):"
                                content_start = i + 1
                                if lines[content_start].strip().startswith("(str):"):
                                    content_start = i + 2
                                # Get all remaining lines and strip leading whitespace
                                content_lines = []
                                for j in range(content_start, len(lines)):
                                    # Remove leading whitespace (usually 4 spaces)
                                    content_lines.append(lines[j].lstrip())
                                answer_text = "\n".join(content_lines).strip()
                                break
                        if not answer_text:
                            answer_text = final_output
                    else:
                        answer_text = final_output
                else:
                    answer_text = str(final_output)
            elif hasattr(result, "content") and result.content:
                content = result.content
                if isinstance(content, str):
                    answer_text = content
                else:
                    answer_text = str(content)
            else:
                # Last resort - use string representation but log warning
                logger.error(f"⚠️ Could not extract structured output - using RunResult string representation")
                answer_text = str(result)

    # Create default structured output if not found
    if structured_output is None:
        logger.warning("⚠️ Creating default structured output - agent did not return structured format")
        # Use a clean reasoning message instead of the RunResult string
        if answer_text and "RunResult:" in answer_text:
            # Extract meaningful content from RunResult string if possible
            reasoning = "Answer generated from relevant notes."
            # Try to find actual content in the RunResult string
            if "Final output" in answer_text:
                parts = answer_text.split("Final output")
                if len(parts) > 1:
                    content = parts[1].strip()
                    if content and not content.startswith("(str):"):
                        reasoning = content
        else:
            reasoning = answer_text if answer_text else "Answer generated from relevant notes."
        
        structured_output = output_type(
            reasoning=reasoning,
            relevant_note_files=[],
            relevant_daily_files=[],
            noteplan_links=[],
        )
        # Clear answer_text if it's just the RunResult string
        if answer_text and "RunResult:" in answer_text:
            answer_text = reasoning

    return structured_output, answer_text


def categorize_files(
    file_results: list["NoteFileResult"],
) -> tuple[list["NoteFileResult"], list["NoteFileResult"]]:
    """
    Categorize note files into daily plans and regular notes.

    Args:
        file_results: List of NoteFileResult objects

    Returns:
        Tuple of (regular_files, daily_files)
    """
    regular_files = []
    daily_files = []

    for file_result in file_results:
        file_path_obj = Path(file_result.file_path)
        is_daily, _ = is_daily_plan_file(file_path_obj)
        if is_daily:
            daily_files.append(file_result)
        else:
            regular_files.append(file_result)

    return regular_files, daily_files


def merge_agent_files_with_search_results(
    agent_output: "NoteQueryAgentOutput",
    search_results: list["NoteFileResult"],
) -> tuple[list["NoteFileResult"], list["NoteFileResult"]]:
    """
    Merge files from agent output with semantic search results.

    Args:
        agent_output: Structured output from agent
        search_results: Files from semantic search

    Returns:
        Tuple of (regular_files, daily_files) with all unique files
    """
    # Categorize search results
    regular_files, daily_files = categorize_files(search_results)

    # Add agent-provided daily files that aren't in search results
    for file_path in agent_output.relevant_daily_files:
        if not any(f.file_path == file_path for f in daily_files):
            daily_files.append(
                NoteFileResult(
                    file_path=file_path,
                    file_name=Path(file_path).name,
                    similarity_score=0.0,
                    modified_at=None,
                )
            )

    # Add agent-provided regular files that aren't in search results
    for file_path in agent_output.relevant_note_files:
        if not any(f.file_path == file_path for f in regular_files):
            regular_files.append(
                NoteFileResult(
                    file_path=file_path,
                    file_name=Path(file_path).name,
                    similarity_score=0.0,
                    modified_at=None,
                )
            )

    return regular_files, daily_files


def generate_noteplan_links(
    file_paths: list[str], link_generator: callable
) -> dict[str, str]:
    """
    Generate NotePlan x-callback-url links for a list of file paths.

    Args:
        file_paths: List of file paths to generate links for
        link_generator: Function that takes file_path and returns link

    Returns:
        Dictionary mapping file_path -> link
    """
    links_map = {}
    for file_path in file_paths:
        try:
            link = link_generator(file_path)
            links_map[file_path] = link
        except Exception as e:
            logger.warning(f"Failed to generate link for {file_path}: {e}")
            links_map[file_path] = f"Error generating link for {file_path}"
    return links_map


def merge_agent_links_with_generated(
    agent_output: "NoteQueryAgentOutput",
    file_paths: list[str],
    generated_links_map: dict[str, str],
) -> list[str]:
    """
    Merge agent-provided links with generated links.

    Agent-provided links take precedence over generated links.

    Args:
        agent_output: Structured output from agent containing noteplan_links
        file_paths: List of file paths (in order)
        generated_links_map: Dictionary mapping file_path -> generated link

    Returns:
        List of links in the same order as file_paths
    """
    final_links = []
    for i, file_path in enumerate(file_paths):
        # First try agent-provided links (if they exist and match the file)
        if i < len(agent_output.noteplan_links) and agent_output.noteplan_links[i]:
            final_links.append(agent_output.noteplan_links[i])
        elif file_path in generated_links_map:
            # Fall back to generated links
            final_links.append(generated_links_map[file_path])
        else:
            final_links.append("")
    return final_links


def build_answer_with_links(
    answer_text: str,
    reasoning: str,
    file_paths: list[str],
    links: list[str],
) -> str:
    """
    Build the final answer text with NotePlan links appended.

    Args:
        answer_text: Primary answer text from agent
        reasoning: Reasoning from structured output
        file_paths: List of file paths that have links
        links: List of NotePlan links (same order as file_paths)

    Returns:
        Complete answer string with links appended
    """
    answer_parts = []

    # Use answer_text if available, otherwise use reasoning
    if answer_text and answer_text.strip():
        answer_parts.append(answer_text)
    elif reasoning:
        answer_parts.append(reasoning)
    else:
        answer_parts.append("Answer generated from relevant notes.")

    # Add NotePlan links if available
    if links and file_paths:
        links_section = "\n\nNotePlan Links:\n"
        for file_path, link in zip(file_paths, links):
            if link:
                links_section += f"- {file_path}: {link}\n"
        answer_parts.append(links_section.rstrip())

    return "\n".join(answer_parts)

