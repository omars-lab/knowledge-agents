"""
Types for note query operations.
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class NoteFileResult(BaseModel):
    """Represents a note file found in semantic search."""

    file_path: str = Field(..., description="Path to the note file")
    file_name: str = Field(..., description="Name of the note file")
    similarity_score: float = Field(..., description="Similarity score (0-1)")
    modified_at: Optional[str] = Field(None, description="File modification timestamp")


class NoteQueryResponse(BaseModel):
    """Response schema for note query analysis."""

    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    answer: str = Field(
        ..., description="The answer to the user's question based on notes"
    )
    reasoning: str = Field(..., description="Reasoning for how the answer was derived")
    relevant_files: List[NoteFileResult] = Field(
        default_factory=list,
        description="List of relevant note files used to generate the answer",
    )
    original_query: str = Field(..., description="The original user query")
    query_answered: bool = Field(
        default=True, description="Whether a valid answer was found in the notes"
    )
    guardrails_tripped: List[str] = Field(
        default_factory=list, description="List of guardrails that were tripped"
    )


class NoteQueryAgentOutput(BaseModel):
    """
    Structured output from the NoteQueryAgent.
    
    This Pydantic model defines the expected output format from the agent,
    forcing structured responses with reasoning, file lists, and NotePlan links.
    """
    reasoning: str = Field(..., description="The reasoning and answer to the user's question")
    relevant_note_files: List[str] = Field(
        default_factory=list,
        description="List of non-daily note file paths"
    )
    relevant_daily_files: List[str] = Field(
        default_factory=list,
        description="List of daily plan file paths (YYYY-MM-DD.md format)"
    )
    noteplan_links: List[str] = Field(
        default_factory=list,
        description="List of x-callback-url links, one per file (in order: note files, then daily files)"
    )


class NoteQueryRequest(BaseModel):
    """Request schema for note queries."""

    query: str = Field(..., description="The question to ask about notes", min_length=1)

    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate and clean the query."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()
