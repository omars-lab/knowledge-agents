"""
File traversal and discovery utilities for NotePlan files.

This module provides functions to discover and collect NotePlan files
for processing.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

from .filter import should_skip_file
from .noteplan_structure import is_daily_plan_file

logger = logging.getLogger(__name__)


def get_daily_plan_files(noteplan_dir: Path) -> List[Tuple[Path, datetime]]:
    """
    Get all daily plan files from the NotePlan directory.
    Ignores Caches directories, Backups directories, and .DS_Store files.

    Args:
        noteplan_dir: Path to the NotePlan directory

    Returns:
        List of tuples (file_path, date) sorted by date
    """
    if not noteplan_dir.exists():
        logger.warning(f"NotePlan directory does not exist: {noteplan_dir}")
        return []

    daily_plans = []

    # Walk through the directory recursively
    for file_path in noteplan_dir.rglob("*.md"):
        # Skip filtered files
        if should_skip_file(file_path):
            continue

        # Check if it's a daily plan file
        is_daily, date = is_daily_plan_file(file_path)
        if is_daily and date:
            daily_plans.append((file_path, date))
            logger.debug(f"Found daily plan file: {file_path} (date: {date.date()})")

    logger.info(f"Found {len(daily_plans)} daily plan files")
    return sorted(daily_plans, key=lambda x: x[1])  # Sort by date


def get_files_from_last_month(noteplan_dir: Path) -> List[Tuple[Path, datetime]]:
    """
    Get all files from the NotePlan directory that were modified in the last month.
    Ignores Caches directories, Backups directories, and .DS_Store files.

    Args:
        noteplan_dir: Path to the NotePlan directory

    Returns:
        List of tuples (file_path, modification_time)
    """
    if not noteplan_dir.exists():
        logger.warning(f"NotePlan directory does not exist: {noteplan_dir}")
        return []

    one_month_ago = datetime.now() - timedelta(days=30)
    files = []

    # Walk through the directory recursively
    for file_path in noteplan_dir.rglob("*"):
        if file_path.is_file():
            # Skip filtered files (check BEFORE accessing file metadata)
            if should_skip_file(file_path):
                logger.debug(f"Skipping filtered file in traversal: {file_path}")
                continue

            # Additional check: skip database files explicitly
            if file_path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".db-shm", ".db-wal"}:
                logger.debug(f"Skipping database file in traversal: {file_path}")
                continue

            try:
                # Get modification time
                mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)

                # Filter files from the last month
                if mod_time >= one_month_ago:
                    files.append((file_path, mod_time))
                    logger.debug(
                        f"Found file from last month: {file_path} (modified: {mod_time})"
                    )
            except Exception as e:
                logger.warning(f"Error accessing file {file_path}: {e}")
                continue

    logger.info(f"Found {len(files)} files from the last month")
    return files
