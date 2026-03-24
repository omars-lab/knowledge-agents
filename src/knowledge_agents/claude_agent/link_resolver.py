"""
Schema-driven link resolver for knowledge graph nodes.

Resolves clickable URLs for graph nodes based on their type and properties.
See docs/GRAPH_SCHEMA.md for the full schema reference.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

logger = logging.getLogger(__name__)

TIDY_MCP_URL = "http://localhost:8003"


@dataclass
class NodeTypeConfig:
    """Configuration for a node type's link resolution and visual identity."""

    color: str
    shape: str = "box"
    link_properties: list[str] = field(default_factory=list)
    url_template: str | None = None


NODE_SCHEMA: dict[str, NodeTypeConfig] = {
    "Note": NodeTypeConfig(
        color="#FFF3CD",
        shape="note",
        link_properties=["xcallback_url", "file_path"],
    ),
    "Person": NodeTypeConfig(
        color="#4A90D9",
        link_properties=["url", "email"],
    ),
    "Project": NodeTypeConfig(
        color="#50C878",
        link_properties=["url", "repo"],
    ),
    "Topic": NodeTypeConfig(
        color="#FFB347",
        link_properties=[],
    ),
    "Concept": NodeTypeConfig(
        color="#DDA0DD",
        link_properties=["url"],
    ),
    "Organization": NodeTypeConfig(
        color="#FF6B6B",
        link_properties=["url"],
    ),
    "Tool": NodeTypeConfig(
        color="#98D8C8",
        link_properties=["url"],
    ),
    "Location": NodeTypeConfig(
        color="#F0E68C",
        link_properties=["url"],
        url_template="https://maps.google.com/?q={name}",
    ),
    "Event": NodeTypeConfig(
        color="#C9B1FF",
        link_properties=["url"],
    ),
    "Date": NodeTypeConfig(
        color="#87CEEB",
        link_properties=["date"],
    ),
    "Task": NodeTypeConfig(
        color="#FFD6D6",
        link_properties=["note_file_path"],
    ),
    "Episode": NodeTypeConfig(
        color="#E8F5E9",
        shape="box",
        link_properties=["source_description"],
    ),
}

DEFAULT_COLOR = "#D3D3D3"


def _noteplan_url_from_file_path(file_path: str) -> str | None:
    """Derive a noteplan:// xcallback URL from a file path.

    Handles two patterns:
    - Calendar notes: noteplan://x-callback-url/openNote?noteDate=YYYYMMDD
    - Regular notes: noteplan://x-callback-url/openNote?filename={encoded_path}
    """
    if not file_path:
        return None

    # Calendar note: Calendar/YYYYMMDD.md → noteDate=YYYYMMDD
    calendar_match = re.match(r"Calendar/(\d{8})\.md$", file_path)
    if calendar_match:
        return f"noteplan://x-callback-url/openNote?noteDate={calendar_match.group(1)}"

    # Regular note: encode the relative path
    # Strip leading "Notes/" if present for the filename parameter
    note_path = file_path
    if note_path.startswith("Notes/"):
        note_path = note_path[6:]
    # Remove .md extension — NotePlan uses the title
    if note_path.endswith(".md"):
        note_path = note_path[:-3]

    encoded = quote(note_path, safe="")
    return f"noteplan://x-callback-url/openNote?filename={encoded}"


def _noteplan_url_from_date(date_str: str) -> str | None:
    """Derive a noteplan:// URL for a calendar date.

    Accepts YYYY-MM-DD or YYYYMMDD format.
    """
    if not date_str:
        return None
    clean = date_str.replace("-", "")
    if re.match(r"^\d{8}$", clean):
        return f"noteplan://x-callback-url/openNote?noteDate={clean}"
    return None


def resolve_link(node_type: str, properties: dict[str, Any]) -> str | None:
    """Resolve a clickable URL for a graph node based on its type and properties.

    Resolution priority:
    1. Explicit `url` property (any type)
    2. Pre-resolved `xcallback_url` (Note nodes)
    3. Type-specific derivation (file_path, email, repo, date, etc.)
    4. URL template with name substitution
    5. None (no link)
    """
    # Priority 1: explicit url property on any node type
    url = properties.get("url")
    if url and isinstance(url, str) and url.startswith(("http", "noteplan:", "mailto:")):
        return url

    config = NODE_SCHEMA.get(node_type)

    # Priority 2: pre-resolved xcallback_url (Note nodes)
    xcallback = properties.get("xcallback_url")
    if xcallback:
        return xcallback

    # Priority 3: type-specific derivation
    if node_type == "Note":
        file_path = properties.get("file_path")
        if file_path:
            return _noteplan_url_from_file_path(file_path)

    elif node_type == "Date":
        date = properties.get("date") or properties.get("name")
        return _noteplan_url_from_date(date)

    elif node_type == "Person":
        email = properties.get("email")
        if email:
            return f"mailto:{email}"

    elif node_type == "Project":
        repo = properties.get("repo")
        if repo:
            return f"https://github.com/{repo}"

    elif node_type == "Task":
        note_path = properties.get("note_file_path")
        if note_path:
            return _noteplan_url_from_file_path(note_path)

    # Priority 4: URL template with name substitution
    if config and config.url_template:
        name = properties.get("name", "")
        if name:
            return config.url_template.format(name=quote(name, safe=""))

    return None


def get_color(node_type: str) -> str:
    """Get the display color for a node type."""
    config = NODE_SCHEMA.get(node_type)
    return config.color if config else DEFAULT_COLOR


def get_shape(node_type: str) -> str:
    """Get the display shape for a node type."""
    config = NODE_SCHEMA.get(node_type)
    return config.shape if config else "box"
