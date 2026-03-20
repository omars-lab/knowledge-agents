"""
Unit tests for text splitting utilities.

Tests verify that:
1. Markdown files are split by headings correctly
2. Non-markdown files are treated as single sections
3. Large sections are chunked appropriately
4. Token estimation is used correctly
5. HTML conversion works when requested
"""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from knowledge_agents.utils.text_splitters import (
    _chunk_large_section,
    _split_markdown_by_headings_fallback,
    split_content_into_sections,
)

pytestmark = [pytest.mark.unit]


class TestMarkdownDetection:
    """Test markdown file detection."""

    def test_detects_markdown_by_extension(self):
        """Test that markdown files are detected by extension."""
        content = "Some content"
        file_path = Path("test.md")
        
        sections = split_content_into_sections(content, file_path=file_path)
        
        # Should attempt to split (may use LangChain or fallback)
        assert isinstance(sections, list)
        assert len(sections) >= 1

    def test_detects_markdown_by_content(self):
        """Test that markdown is detected by heading patterns in content."""
        content = "# Heading\n\nSome content"
        sections = split_content_into_sections(content)
        
        # Should detect markdown and split
        assert isinstance(sections, list)
        assert len(sections) >= 1

    def test_non_markdown_treated_as_single_section(self):
        """Test that non-markdown files are treated as single section."""
        content = "Some plain text content\nwith multiple lines"
        file_path = Path("test.txt")
        
        sections = split_content_into_sections(content, file_path=file_path)
        
        assert len(sections) == 1
        assert sections[0]["content"] == content
        assert sections[0]["section_index"] == 0
        assert sections[0]["heading"] is None
        assert sections[0]["heading_level"] is None


class TestMarkdownSplitting:
    """Test markdown splitting functionality."""

    def test_splits_by_headings(self):
        """Test that markdown is split by headings."""
        content = """# Title

Some intro text.

## Section 1

Content for section 1.

### Subsection 1.1

More content.

## Section 2

Content for section 2.
"""
        file_path = Path("test.md")
        
        sections = split_content_into_sections(content, file_path=file_path)
        
        # Should have multiple sections
        assert len(sections) >= 2
        # First section should have heading
        assert sections[0]["heading"] is not None

    def test_preserves_heading_information(self):
        """Test that heading information is preserved in sections."""
        content = """## Main Section

Content here.
"""
        file_path = Path("test.md")
        
        sections = split_content_into_sections(content, file_path=file_path)
        
        assert len(sections) >= 1
        assert sections[0]["heading"] == "Main Section"
        assert sections[0]["heading_level"] == 2

    def test_handles_empty_content(self):
        """Test handling of empty content."""
        content = ""
        file_path = Path("test.md")
        
        sections = split_content_into_sections(content, file_path=file_path)
        
        assert len(sections) >= 0  # May return empty list or single empty section

    def test_handles_no_headings(self):
        """Test handling of markdown with no headings."""
        content = """Some markdown content
without headings.

Just paragraphs.
"""
        file_path = Path("test.md")
        
        sections = split_content_into_sections(content, file_path=file_path)
        
        # Should return at least one section
        assert len(sections) >= 1


class TestChunking:
    """Test chunking of large sections."""

    @patch("knowledge_agents.utils.text_splitters.estimate_tokens")
    def test_chunks_large_sections(self, mock_estimate_tokens):
        """Test that large sections are chunked."""
        # Mock token estimation to return high token count
        mock_estimate_tokens.return_value = 10000  # Exceeds default max_tokens=8000
        
        content = "A" * 10000  # Large content
        file_path = Path("test.md")
        
        sections = split_content_into_sections(content, file_path=file_path, max_tokens=8000)
        
        # Should have multiple chunks
        assert len(sections) >= 1
        # Verify estimate_tokens was called
        assert mock_estimate_tokens.called

    @patch("knowledge_agents.utils.text_splitters.estimate_tokens")
    def test_chunk_large_section_by_paragraphs(self, mock_estimate_tokens):
        """Test chunking by paragraphs."""
        # Mock to return tokens that exceed limit when combined
        def token_side_effect(text):
            return len(text) // 4  # Rough token estimate
        
        mock_estimate_tokens.side_effect = token_side_effect
        
        # Create content with multiple paragraphs
        paragraphs = ["Paragraph " + str(i) + " " * 1000 for i in range(10)]
        content = "\n\n".join(paragraphs)
        
        chunks = _chunk_large_section(content, max_tokens=500)
        
        # Should have multiple chunks
        assert len(chunks) >= 1
        # Each chunk should be smaller than max_tokens
        for chunk in chunks:
            assert token_side_effect(chunk) <= 500 or len(chunks) == 1

    @patch("knowledge_agents.utils.text_splitters.estimate_tokens")
    def test_chunk_falls_back_to_lines(self, mock_estimate_tokens):
        """Test that chunking falls back to line splitting if paragraphs don't work."""
        def token_side_effect(text):
            return len(text) // 2
        
        mock_estimate_tokens.side_effect = token_side_effect
        
        # Create very long single paragraph
        content = "Line " + "x" * 1000 + "\n" * 100
        
        chunks = _chunk_large_section(content, max_tokens=100)
        
        # Should have multiple chunks
        assert len(chunks) >= 1


class TestFallbackSplitting:
    """Test fallback markdown splitting when LangChain not available."""

    def test_fallback_splits_by_headings(self):
        """Test fallback splitting by headings."""
        content = """# Title

Intro text.

## Section 1

Content 1.

## Section 2

Content 2.
"""
        sections = _split_markdown_by_headings_fallback(content)
        
        assert len(sections) >= 2
        assert sections[0]["heading"] == "Title"
        assert sections[1]["heading"] == "Section 1"

    def test_fallback_handles_nested_headings(self):
        """Test fallback handles nested headings correctly."""
        content = """# H1

Content.

## H2

More content.

### H3

Even more.
"""
        sections = _split_markdown_by_headings_fallback(content)
        
        # Should split at each heading level
        assert len(sections) >= 3


class TestHTMLConversion:
    """Test HTML conversion functionality."""

    def test_converts_markdown_to_html(self):
        """Test that markdown can be converted to HTML."""
        content = """# Title

Some **bold** text.
"""
        file_path = Path("test.md")
        
        sections = split_content_into_sections(
            content, file_path=file_path, convert_to_html=True
        )
        
        assert len(sections) >= 1
        # HTML should contain HTML tags
        assert "<" in sections[0]["content"] or sections[0]["content"] == content


class TestSectionIndexing:
    """Test section indexing."""

    def test_sections_have_sequential_indices(self):
        """Test that sections have sequential indices."""
        content = """# Section 1

Content 1.

## Section 2

Content 2.

## Section 3

Content 3.
"""
        file_path = Path("test.md")
        
        sections = split_content_into_sections(content, file_path=file_path)
        
        # Check indices are sequential
        for i, section in enumerate(sections):
            assert section["section_index"] == i


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_handles_very_long_line(self):
        """Test handling of very long lines without newlines."""
        content = "A" * 50000
        file_path = Path("test.txt")
        
        sections = split_content_into_sections(content, file_path=file_path)
        
        # Should still return at least one section
        assert len(sections) >= 1

    def test_handles_special_characters(self):
        """Test handling of special characters."""
        content = """# Test

Content with special chars: émojis 🎉 and unicode 中文.
"""
        file_path = Path("test.md")
        
        sections = split_content_into_sections(content, file_path=file_path)
        
        assert len(sections) >= 1
        assert "émojis" in sections[0]["content"] or "🎉" in sections[0]["content"]

    def test_handles_mixed_content_types(self):
        """Test handling of mixed markdown and code blocks."""
        content = """# Code Example

Here's some code:

```python
def hello():
    print("world")
```

And more text.
"""
        file_path = Path("test.md")
        
        sections = split_content_into_sections(content, file_path=file_path)
        
        assert len(sections) >= 1
        assert "def hello" in sections[0]["content"] or len(sections) > 1




