"""
Notes package for NotePlan file parsing and processing.

This package contains:
- NotePlan folder structure documentation
- File filtering logic
- File traversal and discovery utilities
- NotePlan-specific parsing utilities
- Generators for yielding processed content
"""

from .filter import should_skip_file
from .generators import daily_plan_generator, recent_files_generator
from .parser import parse_markdown_to_structure, read_noteplan_file
from .traversal import get_daily_plan_files, get_files_from_last_month

__all__ = [
    "should_skip_file",
    "read_noteplan_file",
    "parse_markdown_to_structure",
    "get_daily_plan_files",
    "get_files_from_last_month",
    "daily_plan_generator",
    "recent_files_generator",
]
