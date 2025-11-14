"""
File filtering logic for NotePlan files.

This module provides functions to filter out files that should not be processed
during seeding operations.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def should_skip_file(file_path: Path) -> bool:
    """
    Determine if a file should be skipped during processing.

    Files are skipped if they:
    - Are in Caches directories (case-insensitive)
    - Are in Backups directories (case-insensitive)
    - Are .DS_Store files (macOS metadata)
    - Are database files (.db, .sqlite, etc.)
    - Are other system files

    Args:
        file_path: Path to the file to check

    Returns:
        True if the file should be skipped, False otherwise
    """
    # Convert path parts to lowercase for case-insensitive matching
    path_parts_lower = [part.lower() for part in file_path.parts]
    
    # Skip files in Caches directories (case-insensitive)
    if "caches" in path_parts_lower:
        logger.debug(f"Skipping file in Caches directory: {file_path}")
        return True

    # Skip files in Backups directories (case-insensitive)
    if "backups" in path_parts_lower:
        logger.debug(f"Skipping file in Backups directory: {file_path}")
        return True

    # Skip .DS_Store files (macOS metadata)
    if file_path.name == ".DS_Store":
        logger.debug(f"Skipping .DS_Store file: {file_path}")
        return True

    # Skip database files (common cache/database file extensions)
    db_extensions = {".db", ".sqlite", ".sqlite3", ".db-shm", ".db-wal"}
    if file_path.suffix.lower() in db_extensions:
        logger.debug(f"Skipping database file: {file_path}")
        return True

    # Skip other hidden/system files (optional, for future expansion)
    if file_path.name.startswith(".") and file_path.name not in [".gitignore", ".env"]:
        logger.debug(f"Skipping hidden/system file: {file_path}")
        return True

    return False
