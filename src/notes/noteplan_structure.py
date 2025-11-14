"""
NotePlan Folder Structure Documentation

This module documents the structure and conventions used in NotePlan.

FOLDER STRUCTURE:
- NotePlan stores files in a directory structure
- Daily plans are typically named with date format: YYYY-MM-DD.md
- Files may be organized in subdirectories
- NotePlan may create cache and system files that should be ignored

FILE NAMING CONVENTIONS:
- Daily plans: YYYY-MM-DD.md (e.g., 2025-11-04.md)
- Goal-focused plans: May use different naming conventions
- Other notes: Various naming conventions

DIRECTORIES TO IGNORE:
- Caches/: Contains cache files that should not be processed
- Backups/: Contains backup files that should not be processed
- Any directory containing "Caches" or "Backups" in its path

FILES TO IGNORE:
- .DS_Store: macOS metadata files
- Any system/hidden files

MARKDOWN STRUCTURE:
- Headers (h1-h6) represent sections/buckets
- Todo items are marked with [ ] or [x]
- Tasks can be nested under multiple header levels
- Hierarchy is preserved through header nesting

DAILY PLAN DETECTION:
- Files matching YYYY-MM-DD pattern in filename are considered daily plans
- Date is extracted from filename for plan_date field
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# Regex pattern for daily plan files (YYYY-MM-DD.md or similar)
DAILY_PLAN_PATTERN = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def is_daily_plan_file(file_path: Path) -> Tuple[bool, Optional[datetime]]:
    """
    Check if a file is a daily plan file based on its name.

    Args:
        file_path: Path to the file

    Returns:
        Tuple of (is_daily_plan, date) where date is parsed from filename or None
    """
    # Check if filename matches date pattern (YYYY-MM-DD)
    match = DAILY_PLAN_PATTERN.search(file_path.stem)
    if match:
        try:
            year, month, day = map(int, match.groups())
            date = datetime(year, month, day)
            return True, date
        except ValueError:
            return False, None
    return False, None
