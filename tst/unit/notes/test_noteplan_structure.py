"""
Unit tests for NotePlan structure detection.

Tests verify that daily plan files are correctly identified based on filename patterns.
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from knowledge_agents.notes.noteplan_structure import is_daily_plan_file

pytestmark = [pytest.mark.unit]


class TestIsDailyPlanFile:
    """Test is_daily_plan_file function."""

    def test_valid_daily_plan_md(self):
        """Test that valid daily plan markdown files are detected."""
        file_path = Path("2025-01-15.md")
        is_daily, date = is_daily_plan_file(file_path)

        assert is_daily is True
        assert date == datetime(2025, 1, 15)

    def test_valid_daily_plan_txt(self):
        """Test that valid daily plan text files are detected."""
        file_path = Path("2025-01-15.txt")
        is_daily, date = is_daily_plan_file(file_path)

        assert is_daily is True
        assert date == datetime(2025, 1, 15)

    def test_daily_plan_in_subdirectory(self):
        """Test that daily plan files in subdirectories are detected."""
        file_path = Path("Calendar/2025-01-15.md")
        is_daily, date = is_daily_plan_file(file_path)

        assert is_daily is True
        assert date == datetime(2025, 1, 15)

    def test_daily_plan_with_prefix(self):
        """Test that daily plan files with prefix are detected."""
        file_path = Path("Calendar/daily-2025-01-15.md")
        is_daily, date = is_daily_plan_file(file_path)

        assert is_daily is True
        assert date == datetime(2025, 1, 15)

    def test_daily_plan_with_suffix(self):
        """Test that daily plan files with suffix are detected."""
        file_path = Path("Calendar/2025-01-15-notes.md")
        is_daily, date = is_daily_plan_file(file_path)

        assert is_daily is True
        assert date == datetime(2025, 1, 15)

    def test_daily_plan_with_prefix_and_suffix(self):
        """Test that daily plan files with both prefix and suffix are detected."""
        file_path = Path("Calendar/daily-2025-01-15-notes.md")
        is_daily, date = is_daily_plan_file(file_path)

        assert is_daily is True
        assert date == datetime(2025, 1, 15)

    def test_invalid_date_format(self):
        """Test that files without date pattern are not detected."""
        file_path = Path("my_note.md")
        is_daily, date = is_daily_plan_file(file_path)

        assert is_daily is False
        assert date is None

    def test_partial_date_format(self):
        """Test that partial date formats are not detected."""
        file_path = Path("2025-01.md")  # Missing day
        is_daily, date = is_daily_plan_file(file_path)

        assert is_daily is False
        assert date is None

    def test_invalid_date_values(self):
        """Test that invalid date values return False."""
        # Invalid month (13 doesn't exist)
        file_path = Path("2025-13-15.md")
        is_daily, date = is_daily_plan_file(file_path)

        # Pattern matches but date parsing fails, so date should be None
        # The function catches ValueError and returns False, None
        assert is_daily is False
        assert date is None

    def test_edge_case_dates(self):
        """Test edge case dates."""
        # First day of year
        file_path = Path("2025-01-01.md")
        is_daily, date = is_daily_plan_file(file_path)
        assert is_daily is True
        assert date == datetime(2025, 1, 1)

        # Last day of year
        file_path = Path("2025-12-31.md")
        is_daily, date = is_daily_plan_file(file_path)
        assert is_daily is True
        assert date == datetime(2025, 12, 31)

        # Leap year date
        file_path = Path("2024-02-29.md")
        is_daily, date = is_daily_plan_file(file_path)
        assert is_daily is True
        assert date == datetime(2024, 2, 29)

    def test_multiple_date_patterns(self):
        """Test that only first date pattern is used."""
        file_path = Path("2025-01-15-2025-02-20.md")
        is_daily, date = is_daily_plan_file(file_path)

        assert is_daily is True
        # Should use first date pattern
        assert date == datetime(2025, 1, 15)

    def test_non_noteplan_file(self):
        """Test that regular note files are not detected as daily plans."""
        file_path = Path("my_project_notes.md")
        is_daily, date = is_daily_plan_file(file_path)

        assert is_daily is False
        assert date is None

    def test_file_with_numbers_but_not_date(self):
        """Test that files with numbers but not date pattern are not detected."""
        file_path = Path("version-1.2.3.md")
        is_daily, date = is_daily_plan_file(file_path)

        assert is_daily is False
        assert date is None

