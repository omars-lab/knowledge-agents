"""
Unit tests for NotePlan file filtering logic.

Tests verify that files are correctly filtered based on directory location,
file extensions, and system file patterns.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from knowledge_agents.notes.filter import should_skip_file

pytestmark = [pytest.mark.unit]


class TestShouldSkipFile:
    """Test should_skip_file function."""

    def test_normal_file_not_skipped(self):
        """Test that normal markdown files are not skipped."""
        file_path = Path("Calendar/2025-01-15.md")
        assert should_skip_file(file_path) is False

    def test_caches_directory_skipped(self):
        """Test that files in Caches directory are skipped."""
        file_path = Path("Caches/some_file.md")
        assert should_skip_file(file_path) is True

    def test_caches_directory_case_insensitive(self):
        """Test that Caches directory matching is case-insensitive."""
        file_path = Path("caches/some_file.md")
        assert should_skip_file(file_path) is True

        file_path = Path("CACHES/some_file.md")
        assert should_skip_file(file_path) is True

    def test_caches_in_nested_path(self):
        """Test that Caches in nested path is detected."""
        file_path = Path("some/path/Caches/nested/file.md")
        assert should_skip_file(file_path) is True

    def test_backups_directory_skipped(self):
        """Test that files in Backups directory are skipped."""
        file_path = Path("Backups/some_file.md")
        assert should_skip_file(file_path) is True

    def test_backups_directory_case_insensitive(self):
        """Test that Backups directory matching is case-insensitive."""
        file_path = Path("backups/some_file.md")
        assert should_skip_file(file_path) is True

        file_path = Path("BACKUPS/some_file.md")
        assert should_skip_file(file_path) is True

    def test_backups_in_nested_path(self):
        """Test that Backups in nested path is detected."""
        file_path = Path("some/path/Backups/nested/file.md")
        assert should_skip_file(file_path) is True

    def test_ds_store_skipped(self):
        """Test that .DS_Store files are skipped."""
        file_path = Path(".DS_Store")
        assert should_skip_file(file_path) is True

        file_path = Path("some/path/.DS_Store")
        assert should_skip_file(file_path) is True

    def test_database_files_skipped(self):
        """Test that database files are skipped."""
        db_extensions = [".db", ".sqlite", ".sqlite3", ".db-shm", ".db-wal"]
        for ext in db_extensions:
            file_path = Path(f"database{ext}")
            assert should_skip_file(file_path) is True

    def test_database_files_case_insensitive(self):
        """Test that database file extensions are case-insensitive."""
        file_path = Path("database.DB")
        assert should_skip_file(file_path) is True

        file_path = Path("database.SQLITE")
        assert should_skip_file(file_path) is True

    def test_hidden_files_skipped(self):
        """Test that hidden/system files are skipped."""
        file_path = Path(".hidden_file")
        assert should_skip_file(file_path) is True

        file_path = Path(".some_system_file")
        assert should_skip_file(file_path) is True

    def test_gitignore_not_skipped(self):
        """Test that .gitignore is not skipped (exception)."""
        file_path = Path(".gitignore")
        assert should_skip_file(file_path) is False

    def test_env_not_skipped(self):
        """Test that .env is not skipped (exception)."""
        file_path = Path(".env")
        assert should_skip_file(file_path) is False

    def test_normal_markdown_not_skipped(self):
        """Test that normal markdown files are not skipped."""
        file_path = Path("notes/my_note.md")
        assert should_skip_file(file_path) is False

    def test_text_file_not_skipped(self):
        """Test that text files are not skipped."""
        file_path = Path("notes/my_note.txt")
        assert should_skip_file(file_path) is False

    def test_combined_filters(self):
        """Test that multiple filter conditions work together."""
        # File in Caches with database extension
        file_path = Path("Caches/cache.db")
        assert should_skip_file(file_path) is True

        # File in Backups with .DS_Store name
        file_path = Path("Backups/.DS_Store")
        assert should_skip_file(file_path) is True




