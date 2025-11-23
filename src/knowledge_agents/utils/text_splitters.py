"""
Text splitting utilities for content processing and embedding.

This module provides utilities for splitting text content into sections,
with special handling for markdown files using LangChain's MarkdownHeaderTextSplitter.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def split_content_into_sections(
    content: str,
    max_tokens: int = 8000,
    file_path: Optional[Path] = None,
    convert_to_html: bool = False,
) -> List[Dict[str, Any]]:
    """
    Split content into sections for embedding.
    
    For markdown files, uses LangChain's MarkdownHeaderTextSplitter to split
    by headings (##, ###, etc.) and groups content under each heading.
    For non-markdown files, treats as single section.
    
    Large sections that exceed max_tokens are chunked into smaller pieces.
    
    Args:
        content: File content to split
        max_tokens: Maximum tokens per section (default: 8000, leaving room for model limit)
        file_path: Optional path to file (used to detect markdown files)
        convert_to_html: If True, convert markdown sections to HTML (default: False)
        
    Returns:
        List of section dicts with keys:
            - content: str (section text, markdown or HTML)
            - section_index: int (0-based index)
            - heading: Optional[str] (heading text if section starts with heading)
            - heading_level: Optional[int] (heading level 1-6 if applicable)
    """
    from .vector_store_utils import estimate_tokens
    
    # Detect if this is a markdown file
    is_markdown = False
    if file_path:
        markdown_extensions = {".md", ".markdown", ".mdown", ".mkd"}
        is_markdown = file_path.suffix.lower() in markdown_extensions
    else:
        # Try to detect markdown by content (look for markdown heading patterns)
        heading_pattern = r'^#{1,6}\s+.+'
        if re.search(heading_pattern, content, re.MULTILINE):
            is_markdown = True
    
    if not is_markdown:
        # Non-markdown: treat as single section
        sections = [
            {
                "content": content,
                "section_index": 0,
                "heading": None,
                "heading_level": None,
            }
        ]
        return sections
    
    # Markdown: use LangChain's MarkdownHeaderTextSplitter
    try:
        from langchain_text_splitters import MarkdownHeaderTextSplitter
        
        # Define headers to split on (h1, h2, h3)
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        
        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on
        )
        md_header_splits = markdown_splitter.split_text(content)
        
        sections = []
        for section_index, split in enumerate(md_header_splits):
            section_content = split.page_content.strip()
            
            # Extract heading info from metadata
            heading = None
            heading_level = None
            
            # Check metadata for heading information
            # LangChain stores headers in metadata like {"Header 1": "Introduction", "Header 2": "Section 1"}
            # We want the most specific (deepest) header
            for level in range(3, 0, -1):  # Check Header 3, then 2, then 1
                header_key = f"Header {level}"
                if header_key in split.metadata:
                    heading = split.metadata[header_key]
                    heading_level = level
                    break
            
            # Convert to HTML if requested
            if convert_to_html:
                import markdown
                section_content = markdown.markdown(
                    section_content, extensions=["extra", "nl2br"]
                )
            
            # Check token count and chunk if necessary
            tokens = estimate_tokens(section_content)
            
            if tokens <= max_tokens:
                # Section fits within token limit
                sections.append(
                    {
                        "content": section_content,
                        "section_index": section_index,
                        "heading": heading,
                        "heading_level": heading_level,
                    }
                )
            else:
                # Section too large, chunk it
                chunks = _chunk_large_section(
                    section_content, max_tokens=max_tokens, is_html=convert_to_html
                )
                
                for chunk_idx, chunk_content in enumerate(chunks):
                    sections.append(
                        {
                            "content": chunk_content,
                            "section_index": len(sections),
                            "heading": heading if chunk_idx == 0 else None,
                            "heading_level": heading_level if chunk_idx == 0 else None,
                        }
                    )
        
        return sections
        
    except ImportError:
        # Fallback to simple implementation if langchain_text_splitters not available
        logger.warning(
            "langchain_text_splitters not available, using fallback markdown splitting"
        )
        sections = _split_markdown_by_headings_fallback(
            content, max_tokens=max_tokens, convert_to_html=convert_to_html
        )
        return sections


def _split_markdown_by_headings_fallback(
    markdown_content: str,
    max_tokens: int = 8000,
    convert_to_html: bool = False,
) -> List[Dict[str, Any]]:
    """
    Split markdown content by headings (fallback when LangChain not available).
    
    Groups content under each heading and creates sections. Large sections
    are chunked if they exceed max_tokens.
    
    Args:
        markdown_content: Raw markdown content
        max_tokens: Maximum tokens per section
        convert_to_html: If True, convert markdown to HTML
        
    Returns:
        List of section dicts
    """
    from .vector_store_utils import estimate_tokens
    
    # Pattern to match markdown headings: # Heading, ## Heading, etc.
    heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    
    # Find all headings with their positions
    headings = []
    for match in heading_pattern.finditer(markdown_content):
        level = len(match.group(1))  # Number of # characters
        text = match.group(2).strip()
        position = match.start()
        headings.append((position, level, text))
    
    if not headings:
        # No headings found, treat as single section
        content = markdown_content
        if convert_to_html:
            import markdown
            content = markdown.markdown(content, extensions=["extra", "nl2br"])
        
        return [
            {
                "content": content,
                "section_index": 0,
                "heading": None,
                "heading_level": None,
            }
        ]
    
    # Split content by headings
    sections = []
    section_index = 0
    
    for i, (heading_pos, heading_level, heading_text) in enumerate(headings):
        # Determine section boundaries
        start_pos = heading_pos
        
        # End position is start of next heading, or end of file
        if i + 1 < len(headings):
            end_pos = headings[i + 1][0]
        else:
            end_pos = len(markdown_content)
        
        # Extract section content (include the heading)
        section_markdown = markdown_content[start_pos:end_pos].strip()
        
        # Convert to HTML if requested
        section_content = section_markdown
        if convert_to_html:
            import markdown
            section_content = markdown.markdown(
                section_markdown, extensions=["extra", "nl2br"]
            )
        
        # Check token count and chunk if necessary
        tokens = estimate_tokens(section_content)
        
        if tokens <= max_tokens:
            # Section fits within token limit
            sections.append(
                {
                    "content": section_content,
                    "section_index": section_index,
                    "heading": heading_text,
                    "heading_level": heading_level,
                }
            )
            section_index += 1
        else:
            # Section too large, chunk it
            chunks = _chunk_large_section(
                section_content, max_tokens=max_tokens, is_html=convert_to_html
            )
            
            for chunk_idx, chunk_content in enumerate(chunks):
                sections.append(
                    {
                        "content": chunk_content,
                        "section_index": section_index,
                        "heading": heading_text if chunk_idx == 0 else None,
                        "heading_level": heading_level if chunk_idx == 0 else None,
                    }
                )
                section_index += 1
    
    return sections


def _chunk_large_section(
    content: str, max_tokens: int = 8000, is_html: bool = False
) -> List[str]:
    """
    Chunk a large section into smaller pieces that fit within token limit.
    
    Tries to split at paragraph boundaries to maintain readability.
    
    Args:
        content: Section content to chunk
        max_tokens: Maximum tokens per chunk
        is_html: If True, content is HTML and should be split at <p> tags
        
    Returns:
        List of chunked content strings
    """
    from .vector_store_utils import estimate_tokens
    
    chunks = []
    
    if is_html:
        # Split HTML by paragraphs
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(content, "html.parser")
        paragraphs = soup.find_all("p")
        
        current_chunk = []
        current_tokens = 0
        
        for p in paragraphs:
            p_text = str(p)
            p_tokens = estimate_tokens(p_text)
            
            if current_tokens + p_tokens > max_tokens and current_chunk:
                # Save current chunk and start new one
                chunks.append("\n".join(current_chunk))
                current_chunk = [p_text]
                current_tokens = p_tokens
            else:
                current_chunk.append(p_text)
                current_tokens += p_tokens
        
        if current_chunk:
            chunks.append("\n".join(current_chunk))
    else:
        # Split markdown/text by paragraphs (double newlines)
        paragraphs = content.split("\n\n")
        
        current_chunk = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = estimate_tokens(para)
            
            if current_tokens + para_tokens > max_tokens and current_chunk:
                # Save current chunk and start new one
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
        
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))
    
    # If still too large, split by lines (fallback)
    if not chunks:
        chunks = [content]
    
    # Final check: if any chunk is still too large, split by lines
    final_chunks = []
    for chunk in chunks:
        chunk_tokens = estimate_tokens(chunk)
        if chunk_tokens <= max_tokens:
            final_chunks.append(chunk)
        else:
            # Split by lines
            lines = chunk.split("\n")
            current_line_chunk = []
            current_line_tokens = 0
            
            for line in lines:
                line_tokens = estimate_tokens(line)
                if current_line_tokens + line_tokens > max_tokens and current_line_chunk:
                    final_chunks.append("\n".join(current_line_chunk))
                    current_line_chunk = [line]
                    current_line_tokens = line_tokens
                else:
                    current_line_chunk.append(line)
                    current_line_tokens += line_tokens
            
            if current_line_chunk:
                final_chunks.append("\n".join(current_line_chunk))
    
    return final_chunks if final_chunks else [content]

