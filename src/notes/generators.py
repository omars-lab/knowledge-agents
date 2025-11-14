"""
Generators for yielding processed NotePlan content.

This module provides generators that yield processed content from NotePlan files,
simplifying the seeding logic by handling file reading and parsing.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator, Tuple

from .parser import parse_markdown_to_structure, read_noteplan_file
from .traversal import get_daily_plan_files, get_files_from_last_month

logger = logging.getLogger(__name__)


def daily_plan_generator(
    noteplan_dir: Path,
) -> Iterator[Tuple[Path, datetime, str, Dict]]:
    """
    Generator that yields daily plan files with their parsed content.

    For each daily plan file, yields:
    - file_path: Path to the file
    - date: Parsed date from filename
    - content: Raw markdown content
    - structure: Parsed markdown structure (sections and todos)

    Args:
        noteplan_dir: Path to the NotePlan directory

    Yields:
        Tuple of (file_path, date, content, structure)
    """
    daily_plans = get_daily_plan_files(noteplan_dir)

    for file_path, date in daily_plans:
        try:
            # Read file content
            content = read_noteplan_file(file_path)

            # Parse markdown structure
            structure = parse_markdown_to_structure(content)

            yield file_path, date, content, structure

        except Exception as e:
            logger.error(f"Error processing daily plan file {file_path}: {e}")
            continue


def recent_files_generator(noteplan_dir: Path) -> Iterator[Tuple[Path, datetime, str]]:
    """
    Generator that yields files from the last month with their content.

    For each file, yields:
    - file_path: Path to the file
    - mod_time: Modification time
    - content: File content

    Args:
        noteplan_dir: Path to the NotePlan directory

    Yields:
        Tuple of (file_path, mod_time, content)
    """
    files = get_files_from_last_month(noteplan_dir)

    for file_path, mod_time in files:
        try:
            # Read file content
            content = read_noteplan_file(file_path)

            yield file_path, mod_time, content

        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            continue
