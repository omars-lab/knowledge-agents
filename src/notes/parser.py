"""
NotePlan file parsing utilities.

This module provides functions for reading and parsing NotePlan files.
"""

import logging
from pathlib import Path
from typing import Dict, List, Tuple

import markdown
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def read_noteplan_file(file_path: Path) -> str:
    """
    Read a NotePlan file and return its content.

    Args:
        file_path: Path to the NotePlan file

    Returns:
        File content as string

    Raises:
        IOError: If the file cannot be read
        UnicodeDecodeError: If the file is not valid UTF-8 (e.g., binary files)
        ValueError: If the file should be filtered out (database files, etc.)
    """
    # Defensive check: skip database files and files in Caches/Backups directories
    # This is a last resort - files should be filtered before calling this function
    path_str = str(file_path).lower()
    if "caches" in path_str or "backups" in path_str:
        raise ValueError(
            f"File {file_path} is in a Caches or Backups directory and should be filtered out"
        )
    
    db_extensions = {".db", ".sqlite", ".sqlite3", ".db-shm", ".db-wal"}
    if file_path.suffix.lower() in db_extensions:
        raise ValueError(
            f"File {file_path} is a database file and should be filtered out"
        )
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except UnicodeDecodeError as e:
        # This usually means the file is binary (e.g., .DS_Store, images, etc.)
        # These should be filtered out before calling this function
        logger.warning(
            f"Cannot read file {file_path}: not a valid UTF-8 text file "
            f"(likely binary file: {e}). This file should be filtered out."
        )
        raise
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        raise


def parse_markdown_to_structure(markdown_content: str) -> Dict:
    """
    Parse markdown content to extract structure: headers and todos.

    First converts markdown to HTML, then parses HTML for better structure.

    Args:
        markdown_content: Raw markdown content

    Returns:
        Dictionary with structure:
        {
            'sections': [
                {
                    'level': 1-6,
                    'text': 'Header text',
                    'id': 'unique-id',
                    'parent_id': 'parent-section-id' or None
                },
                ...
            ],
            'todos': [
                {
                    'text': 'Task text',
                    'completed': bool,
                    'section_ids': ['section_0', 'section_1', ...]  # Hierarchy chain
                },
                ...
            ]
        }
    """
    # Convert markdown to HTML
    html = markdown.markdown(markdown_content, extensions=["extra", "nl2br"])

    # Parse HTML with BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    structure = {"sections": [], "todos": []}

    # Track section hierarchy
    section_stack: List[Tuple[int, str]] = []  # Stack of (level, id) pairs
    section_id_counter = 0

    # Process elements in order
    for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "li"]):
        tag_name = element.name

        if tag_name.startswith("h"):
            # This is a header
            level = int(tag_name[1])
            text_content = element.get_text().strip()

            # Generate unique ID
            section_id = f"section_{section_id_counter}"
            section_id_counter += 1

            # Pop sections from stack that are at same or deeper level
            while section_stack and section_stack[-1][0] >= level:
                section_stack.pop()

            # Get parent ID (top of stack)
            parent_id = section_stack[-1][1] if section_stack else None

            section_info = {
                "level": level,
                "text": text_content,
                "id": section_id,
                "parent_id": parent_id,
            }
            structure["sections"].append(section_info)

            # Add to stack
            section_stack.append((level, section_id))

        elif tag_name == "li":
            # Check if this is a todo item
            # Markdown todos typically render as <li> with checkbox or special class
            text_content = element.get_text().strip()

            # Check if it's a todo (starts with [ ] or [x])
            is_todo = False
            completed = False

            # Check text content for todo markers
            if (
                text_content.startswith("[ ]")
                or text_content.startswith("[x]")
                or text_content.startswith("[X]")
            ):
                is_todo = True
                completed = text_content.startswith("[x]") or text_content.startswith(
                    "[X]"
                )
                # Remove the checkbox marker
                text_content = text_content[3:].strip()

            # Also check for checkbox input in HTML
            checkbox = element.find("input", {"type": "checkbox"})
            if checkbox:
                is_todo = True
                completed = checkbox.get("checked") is not None
                # Get text without the checkbox
                text_content = element.get_text().strip()

            if is_todo and text_content:
                # Get all section IDs in hierarchy (from stack)
                section_ids = [sid for _, sid in section_stack]

                todo_info = {
                    "text": text_content,
                    "completed": completed,
                    "section_ids": section_ids,
                }
                structure["todos"].append(todo_info)

    return structure
