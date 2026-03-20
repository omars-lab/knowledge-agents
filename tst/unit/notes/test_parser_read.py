"""
Unit tests for NotePlan file reading functionality.

Tests verify that files are correctly read and that appropriate errors
are raised for invalid files.
"""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from knowledge_agents.notes.parser import read_noteplan_file

pytestmark = [pytest.mark.unit]


class TestReadNoteplanFile:
    """Test read_noteplan_file function."""

    def test_read_valid_markdown_file(self):
        """Test reading a valid markdown file."""
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"
            content = "# My Note\n\nThis is test content."
            file_path.write_text(content, encoding="utf-8")

            result = read_noteplan_file(file_path)
            assert result == content

    def test_read_valid_text_file(self):
        """Test reading a valid text file."""
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            content = "This is plain text content."
            file_path.write_text(content, encoding="utf-8")

            result = read_noteplan_file(file_path)
            assert result == content

    def test_read_file_with_unicode(self):
        """Test reading a file with unicode characters."""
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"
            content = "# My Note\n\nThis has unicode: 🎉 émojis"
            file_path.write_text(content, encoding="utf-8")

            result = read_noteplan_file(file_path)
            assert result == content

    def test_read_empty_file(self):
        """Test reading an empty file."""
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "empty.md"
            file_path.write_text("", encoding="utf-8")

            result = read_noteplan_file(file_path)
            assert result == ""

    def test_read_file_with_multiline_content(self):
        """Test reading a file with multiple lines."""
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"
            content = "# Header\n\nLine 1\nLine 2\nLine 3"
            file_path.write_text(content, encoding="utf-8")

            result = read_noteplan_file(file_path)
            assert result == content

    def test_read_nonexistent_file_raises_error(self):
        """Test that reading a nonexistent file raises an error."""
        file_path = Path("/nonexistent/path/file.md")

        with pytest.raises(Exception):  # Could be FileNotFoundError or IOError
            read_noteplan_file(file_path)

    def test_read_file_in_caches_raises_error(self):
        """Test that reading a file in Caches directory raises ValueError."""
        with TemporaryDirectory() as tmpdir:
            caches_dir = Path(tmpdir) / "Caches"
            caches_dir.mkdir()
            file_path = caches_dir / "test.md"
            file_path.write_text("content", encoding="utf-8")

            with pytest.raises(ValueError, match="Caches"):
                read_noteplan_file(file_path)

    def test_read_file_in_backups_raises_error(self):
        """Test that reading a file in Backups directory raises ValueError."""
        with TemporaryDirectory() as tmpdir:
            backups_dir = Path(tmpdir) / "Backups"
            backups_dir.mkdir()
            file_path = backups_dir / "test.md"
            file_path.write_text("content", encoding="utf-8")

            with pytest.raises(ValueError, match="Backups"):
                read_noteplan_file(file_path)

    def test_read_database_file_raises_error(self):
        """Test that reading a database file raises ValueError."""
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.db"
            file_path.write_bytes(b"database content")

            with pytest.raises(ValueError, match="database file"):
                read_noteplan_file(file_path)

    def test_read_binary_file_raises_error(self):
        """Test that reading a binary file raises UnicodeDecodeError."""
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "binary.bin"
            file_path.write_bytes(b"\x00\x01\x02\x03\xff")

            with pytest.raises(UnicodeDecodeError):
                read_noteplan_file(file_path)

    def test_read_file_with_special_characters(self):
        """Test reading a file with special markdown characters."""
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.md"
            content = "# Header\n\n- [ ] Task\n- [x] Done\n\n**Bold** and *italic*"
            file_path.write_text(content, encoding="utf-8")

            result = read_noteplan_file(file_path)
            assert result == content




