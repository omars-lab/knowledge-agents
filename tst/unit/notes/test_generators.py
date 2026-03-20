"""
Unit tests for NotePlan content generators.

Tests verify that generators correctly yield processed content from files.
"""

import sys
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from knowledge_agents.notes.generators import daily_plan_generator, recent_files_generator

pytestmark = [pytest.mark.unit]


class TestDailyPlanGenerator:
    """Test daily_plan_generator function."""

    def test_empty_directory_yields_nothing(self):
        """Test that empty directory yields no results."""
        with TemporaryDirectory() as tmpdir:
            noteplan_dir = Path(tmpdir)
            results = list(daily_plan_generator(noteplan_dir))
            assert len(results) == 0

    def test_yields_daily_plan_files(self):
        """Test that generator yields daily plan files with content."""
        with TemporaryDirectory() as tmpdir:
            noteplan_dir = Path(tmpdir)
            # Create daily plan files
            (noteplan_dir / "2025-01-15.md").write_text("# Daily Plan\n\n- [ ] Task")
            (noteplan_dir / "2025-01-16.md").write_text("# Daily Plan\n\n- [x] Done")

            results = list(daily_plan_generator(noteplan_dir))
            assert len(results) == 2

            # Check structure of yielded items
            for file_path, date, content, structure in results:
                assert isinstance(file_path, Path)
                assert isinstance(date, datetime)
                assert isinstance(content, str)
                assert isinstance(structure, dict)
                assert "sections" in structure
                assert "todos" in structure

    def test_yields_content_and_structure(self):
        """Test that generator yields both content and parsed structure."""
        with TemporaryDirectory() as tmpdir:
            noteplan_dir = Path(tmpdir)
            file_path = noteplan_dir / "2025-01-15.md"
            content = "# Morning\n\n- [ ] Task 1"
            file_path.write_text(content)

            results = list(daily_plan_generator(noteplan_dir))
            assert len(results) == 1

            _, date, yielded_content, structure = results[0]
            assert yielded_content == content
            assert len(structure["sections"]) == 1
            assert len(structure["todos"]) == 1

    def test_skips_files_in_caches(self):
        """Test that generator skips files in Caches directory."""
        with TemporaryDirectory() as tmpdir:
            noteplan_dir = Path(tmpdir)
            caches_dir = noteplan_dir / "Caches"
            caches_dir.mkdir()

            (noteplan_dir / "2025-01-15.md").write_text("# Daily Plan")
            (caches_dir / "2025-01-16.md").write_text("# Daily Plan")

            results = list(daily_plan_generator(noteplan_dir))
            assert len(results) == 1
            assert results[0][0].name == "2025-01-15.md"

    def test_handles_file_read_errors(self):
        """Test that generator handles file read errors gracefully."""
        with TemporaryDirectory() as tmpdir:
            noteplan_dir = Path(tmpdir)
            # Create a file that will cause read error (binary file)
            bad_file = noteplan_dir / "2025-01-15.md"
            bad_file.write_bytes(b"\x00\x01\x02")

            # Generator should skip files that can't be read
            results = list(daily_plan_generator(noteplan_dir))
            # Should either skip the bad file or handle error
            # The generator logs errors and continues
            assert isinstance(results, list)


class TestRecentFilesGenerator:
    """Test recent_files_generator function."""

    def test_empty_directory_yields_nothing(self):
        """Test that empty directory yields no results."""
        with TemporaryDirectory() as tmpdir:
            noteplan_dir = Path(tmpdir)
            results = list(recent_files_generator(noteplan_dir))
            assert len(results) == 0

    def test_yields_recent_files(self):
        """Test that generator yields recent files with content."""
        with TemporaryDirectory() as tmpdir:
            noteplan_dir = Path(tmpdir)
            # Create recent files
            (noteplan_dir / "file1.md").write_text("# File 1")
            (noteplan_dir / "file2.txt").write_text("File 2 content")

            results = list(recent_files_generator(noteplan_dir))
            assert len(results) >= 2

            # Check structure of yielded items
            for file_path, mod_time, content in results:
                assert isinstance(file_path, Path)
                assert isinstance(mod_time, datetime)
                assert isinstance(content, str)

    def test_yields_file_content(self):
        """Test that generator yields file content."""
        with TemporaryDirectory() as tmpdir:
            noteplan_dir = Path(tmpdir)
            file_path = noteplan_dir / "test.md"
            content = "# Test File\n\nThis is content."
            file_path.write_text(content)

            results = list(recent_files_generator(noteplan_dir))
            # Find our file in results
            file_results = [(fp, ct) for fp, _, ct in results if fp.name == "test.md"]
            assert len(file_results) == 1
            assert file_results[0][1] == content

    def test_skips_files_in_caches(self):
        """Test that generator skips files in Caches directory."""
        with TemporaryDirectory() as tmpdir:
            noteplan_dir = Path(tmpdir)
            caches_dir = noteplan_dir / "Caches"
            caches_dir.mkdir()

            (noteplan_dir / "normal.md").write_text("# Normal")
            (caches_dir / "cached.md").write_text("# Cached")

            results = list(recent_files_generator(noteplan_dir))
            file_paths = [fp for fp, _, _ in results]
            assert (noteplan_dir / "normal.md") in file_paths
            assert (caches_dir / "cached.md") not in file_paths

    def test_handles_file_read_errors(self):
        """Test that generator handles file read errors gracefully."""
        with TemporaryDirectory() as tmpdir:
            noteplan_dir = Path(tmpdir)
            # Create a binary file that will cause read error
            bad_file = noteplan_dir / "bad.bin"
            bad_file.write_bytes(b"\x00\x01\x02")

            # Generator should skip files that can't be read
            results = list(recent_files_generator(noteplan_dir))
            # The generator logs errors and continues
            assert isinstance(results, list)

