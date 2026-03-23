"""
Delta tracking for incremental note indexing.

Compares file content hashes against indexed hashes stored in Neo4j
to determine which files need re-indexing.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .cache_utils import compute_content_hash

logger = logging.getLogger(__name__)


def get_indexed_hashes(driver: Any, database: str = "neo4j") -> dict[str, str]:
    """Query Neo4j for all Note nodes' content_hash values.

    Returns:
        Dict mapping file_path → content_hash for all indexed notes.
    """
    with driver.session(database=database) as session:
        result = session.run(
            "MATCH (n:Note) WHERE n.content_hash IS NOT NULL "
            "RETURN n.file_path AS file_path, n.content_hash AS content_hash"
        )
        return {r["file_path"]: r["content_hash"] for r in result}


def compute_delta(
    files: list[tuple[Path, Any]],
    noteplan_dir: Path,
    indexed_hashes: dict[str, str],
) -> tuple[list[tuple[Path, str]], list[str]]:
    """Compare current file hashes against indexed hashes.

    Args:
        files: List of (file_path, modification_time) tuples from traversal.
        noteplan_dir: Base directory for NotePlan files (for relative path computation).
        indexed_hashes: Dict of {relative_path: content_hash} from Neo4j.

    Returns:
        Tuple of (files_to_index, files_to_remove):
        - files_to_index: List of (file_path, content_hash) needing re-indexing.
        - files_to_remove: List of relative paths to remove from index.
    """
    to_index: list[tuple[Path, str]] = []
    seen_paths: set[str] = set()

    for file_path, _ in files:
        try:
            relative = str(file_path.relative_to(noteplan_dir))
        except ValueError:
            relative = str(file_path)

        seen_paths.add(relative)
        current_hash = compute_content_hash(file_path)
        indexed_hash = indexed_hashes.get(relative)

        if indexed_hash != current_hash:
            to_index.append((file_path, current_hash))
            if indexed_hash:
                logger.debug("Changed: %s (hash %s→%s)", relative, indexed_hash[:8], current_hash[:8])
            else:
                logger.debug("New: %s", relative)

    # Files in index but no longer on disk
    to_remove = [fp for fp in indexed_hashes if fp not in seen_paths]
    if to_remove:
        logger.info("Files to remove from index: %d", len(to_remove))

    logger.info(
        "Delta: %d to index, %d unchanged, %d to remove",
        len(to_index),
        len(files) - len(to_index),
        len(to_remove),
    )
    return to_index, to_remove
