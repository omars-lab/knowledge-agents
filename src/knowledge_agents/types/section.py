"""
Section data types for the note indexing pipeline.

A Section represents a chunk of a NotePlan file split by headings (H1/H2/H3).
Sections are stored in Neo4j as Section nodes and in Qdrant as embedding vectors.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SectionData(BaseModel):
    """A parsed note section ready for indexing."""

    file_path: str = Field(description="Relative path from NotePlan root")
    section_index: int = Field(description="0-based index within the file")
    heading: str | None = Field(default=None, description="Section heading text")
    heading_level: int | None = Field(default=None, description="1-3 for H1-H3")
    heading_path: str = Field(default="", description="Hierarchical path: 'H1 > H2 > H3'")
    raw_text: str = Field(description="Full section text content")
    summary: str | None = Field(default=None, description="LLM-generated summary")
    embedding: list[float] | None = Field(default=None, description="Embedding vector")
    token_count: int = Field(default=0, description="Estimated token count")
    content_hash: str | None = Field(default=None, description="SHA256 of source file content")

    @property
    def section_id(self) -> str:
        """Composite key for Neo4j constraint: '{file_path}::section_{index}'."""
        return f"{self.file_path}::section_{self.section_index}"

    @property
    def embedding_text(self) -> str:
        """Build the text to embed: heading_path + summary + raw_text."""
        parts = []
        if self.heading_path:
            parts.append(self.heading_path)
        if self.summary:
            parts.append(f"Summary: {self.summary}")
        parts.append(self.raw_text)
        return "\n\n".join(parts)


class SectionIndexResult(BaseModel):
    """Result of indexing a single file's sections."""

    file_path: str
    sections_indexed: int = 0
    sections_skipped: int = 0
    content_hash: str | None = None
    errors: list[str] = Field(default_factory=list)


class PipelineStats(BaseModel):
    """Aggregate statistics for a pipeline run."""

    files_discovered: int = 0
    files_changed: int = 0
    files_skipped: int = 0
    sections_total: int = 0
    sections_summarized: int = 0
    sections_skipped_summary: int = 0
    sections_embedded: int = 0
    entities_linked: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
