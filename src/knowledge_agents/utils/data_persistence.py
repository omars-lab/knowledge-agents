"""
Data persistence utilities for saving extracted data and embeddings.

This module provides functions to save and load extracted graph data,
embeddings, and processing logs for NotePlan files.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from ..dependencies import Dependencies
    from ..types.graph import GraphBuilderAgentOutput

logger = logging.getLogger(__name__)


def get_data_dir(base_dir: Path, noteplan_dir: Path) -> Path:
    """
    Get the data directory path, creating it if needed.
    
    Args:
        base_dir: Base directory for data (e.g., build/)
        noteplan_dir: NotePlan directory (for structure reference)
        
    Returns:
        Path to data directory
    """
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_file_data_dir(data_dir: Path, relative_path: str) -> Path:
    """
    Get the data directory for a specific NotePlan file, creating it if needed.
    
    Creates a directory structure that mirrors the NotePlan folder structure.
    
    Args:
        data_dir: Base data directory (from get_data_dir())
        relative_path: Relative path from NotePlan root (e.g., "Calendar/2025-01-15.md")
        
    Returns:
        Path to file's data directory
    """
    # Remove file extension and create directory structure
    file_data_dir = data_dir / relative_path
    file_data_dir = file_data_dir.parent  # Remove filename, keep directory structure
    file_data_dir.mkdir(parents=True, exist_ok=True)
    return file_data_dir


def get_file_base_name(relative_path: str) -> str:
    """
    Get base name for data files (without extension).
    
    Args:
        relative_path: Relative path from NotePlan root
        
    Returns:
        Base name (e.g., "2025-01-15" from "Calendar/2025-01-15.md")
    """
    return Path(relative_path).stem


def save_nodes_edges(
    data_dir: Path,
    relative_path: str,
    output: "GraphBuilderAgentOutput",
    source_file_path: Optional[Path] = None,
) -> Path:
    """
    Save extracted nodes (entities) and edges (relationships) to JSON.
    
    Also saves cache metadata with content hash for cache validation.
    
    Args:
        data_dir: Base data directory
        relative_path: Relative path from NotePlan root
        output: GraphBuilderAgentOutput with entities and relationships
        source_file_path: Path to source NotePlan file (for content hash)
        
    Returns:
        Path to saved JSON file
    """
    file_data_dir = get_file_data_dir(data_dir, relative_path)
    base_name = get_file_base_name(relative_path)
    file_path = file_data_dir / f"{base_name}_nodes_edges.json"
    
    data = {
        "file_path": relative_path,
        "entities": [
            {
                "name": entity.name,
                "type": entity.type,
                "properties": entity.properties,
            }
            for entity in output.entities
        ],
        "relationships": [
            {
                "from_entity": rel.from_entity,
                "to_entity": rel.to_entity,
                "type": rel.type,
                "properties": rel.properties,
            }
            for rel in output.relationships
        ],
        "insights": output.insights,
    }
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # Save cache metadata with content hash
    if source_file_path:
        from .cache_utils import save_cache_metadata
        save_cache_metadata(file_path, source_file_path=source_file_path)
    
    logger.debug(f"Saved nodes/edges to {file_path}")
    return file_path


def save_sections_embeddings(
    data_dir: Path,
    relative_path: str,
    sections: List[Dict[str, Any]],
    source_file_path: Optional[Path] = None,
) -> Path:
    """
    Save sections with embeddings and tokens to JSON.
    
    Also saves cache metadata with content hash for cache validation.
    
    Args:
        data_dir: Base data directory
        relative_path: Relative path from NotePlan root
        sections: List of section dicts with keys:
            - content: str (section text)
            - embedding: List[float] (embedding vector)
            - tokens: int (token count)
            - section_index: int (optional, 0-based index)
        source_file_path: Path to source NotePlan file (for content hash)
            
    Returns:
        Path to saved JSON file
    """
    file_data_dir = get_file_data_dir(data_dir, relative_path)
    base_name = get_file_base_name(relative_path)
    file_path = file_data_dir / f"{base_name}_sections_embeddings.json"
    
    data = {
        "file_path": relative_path,
        "sections": sections,
        "total_sections": len(sections),
    }
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # Save cache metadata with content hash
    if source_file_path:
        from .cache_utils import save_cache_metadata
        save_cache_metadata(file_path, source_file_path=source_file_path)
    
    logger.debug(f"Saved sections/embeddings to {file_path}")
    return file_path


def save_stdout(
    data_dir: Path,
    relative_path: str,
    stdout_content: str,
) -> Path:
    """
    Save stdout log to file.
    
    Args:
        data_dir: Base data directory
        relative_path: Relative path from NotePlan root
        stdout_content: Content captured from stdout
        
    Returns:
        Path to saved log file
    """
    file_data_dir = get_file_data_dir(data_dir, relative_path)
    base_name = get_file_base_name(relative_path)
    file_path = file_data_dir / f"{base_name}_stdout.log"
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(stdout_content)
    
    logger.debug(f"Saved stdout to {file_path}")
    return file_path


def save_stderr(
    data_dir: Path,
    relative_path: str,
    stderr_content: str,
) -> Path:
    """
    Save stderr log to file.
    
    Args:
        data_dir: Base data directory
        relative_path: Relative path from NotePlan root
        stderr_content: Content captured from stderr
        
    Returns:
        Path to saved log file
    """
    file_data_dir = get_file_data_dir(data_dir, relative_path)
    base_name = get_file_base_name(relative_path)
    file_path = file_data_dir / f"{base_name}_stderr.log"
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(stderr_content)
    
    logger.debug(f"Saved stderr to {file_path}")
    return file_path


def check_file_cached(
    data_dir: Path,
    relative_path: str,
    check_nodes_edges: bool = True,
    check_sections_embeddings: bool = False,
) -> Tuple[bool, Optional[Path], Optional[Path]]:
    """
    Check if a file's data is already cached.
    
    Args:
        data_dir: Base data directory
        relative_path: Relative path from NotePlan root
        check_nodes_edges: If True, check for nodes_edges.json
        check_sections_embeddings: If True, check for sections_embeddings.json
        
    Returns:
        Tuple of (is_cached, nodes_edges_path, sections_embeddings_path)
        - is_cached: True if all requested files exist
        - nodes_edges_path: Path to nodes_edges.json if exists, else None
        - sections_embeddings_path: Path to sections_embeddings.json if exists, else None
    """
    file_data_dir = get_file_data_dir(data_dir, relative_path)
    base_name = get_file_base_name(relative_path)
    
    nodes_edges_path = None
    sections_embeddings_path = None
    
    if check_nodes_edges:
        nodes_edges_path = file_data_dir / f"{base_name}_nodes_edges.json"
        if not nodes_edges_path.exists():
            return False, None, None
    
    if check_sections_embeddings:
        sections_embeddings_path = file_data_dir / f"{base_name}_sections_embeddings.json"
        if not sections_embeddings_path.exists():
            return False, nodes_edges_path, None
    
    return True, nodes_edges_path, sections_embeddings_path


def load_nodes_edges(file_path: Path) -> Dict[str, Any]:
    """
    Load nodes and edges from JSON file.
    
    Args:
        file_path: Path to nodes_edges.json file
        
    Returns:
        Dictionary with entities, relationships, and insights
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_sections_embeddings(file_path: Path) -> Dict[str, Any]:
    """
    Load sections with embeddings from JSON file.
    
    Args:
        file_path: Path to sections_embeddings.json file
        
    Returns:
        Dictionary with sections array and metadata
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


async def process_file_with_sections_and_embeddings(
    file_path: Path,
    relative_path: str,
    dependencies: "Dependencies",
    data_dir: Path,
    generate_embeddings_flag: bool = True,
    use_cache: bool = True,
) -> Tuple[Optional["GraphBuilderAgentOutput"], List[Dict[str, Any]]]:
    """
    Process a file: extract nodes/edges and generate sections with embeddings.
    
    This function:
    1. Checks cache for existing data (if use_cache=True)
    2. Sets up file logging to stdout.log and stderr.log
    3. Extracts nodes/edges if not cached
    4. Splits content into sections
    5. Generates embeddings for sections if requested
    6. Returns all data for saving
    
    **Logging:**
    All logging output (logger.info, logger.error, print statements) is automatically
    written to the stdout.log and stderr.log files for this file, while still
    appearing in the console.
    
    Args:
        file_path: Full path to NotePlan file
        relative_path: Relative path from NotePlan root
        dependencies: Dependencies container
        data_dir: Base data directory
        generate_embeddings_flag: If True, generate embeddings (default: True)
        use_cache: If True, check cache before processing (default: True)
        
    Returns:
        Tuple of (output, sections_with_embeddings)
        - output: GraphBuilderAgentOutput or None if extraction failed
        - sections_with_embeddings: List of section dicts with embeddings and tokens
        
    Note:
        Logs are automatically written to stdout.log and stderr.log files.
        No need to capture or return log content separately.
    """
    from ..notes.parser import read_noteplan_file
    from ..agents.graph_builder_agent import run_graph_builder_agent
    from .file_logging import file_logging_context, setup_file_logger
    from .vector_store_utils import estimate_tokens, generate_embeddings
    
    # Set up file logging
    stdout_file, stderr_file = setup_file_logger(relative_path, data_dir)
    
    output = None
    sections_with_embeddings = []
    
    # Process file with file logging context
    with file_logging_context(stdout_file, stderr_file):
        logger.info(f"Processing file: {relative_path}")
        
        # Check cache for nodes/edges
        if use_cache:
            is_cached, nodes_edges_path, _ = check_file_cached(
                data_dir, relative_path, check_nodes_edges=True, check_sections_embeddings=False
            )
            if is_cached and nodes_edges_path:
                logger.debug(f"Cache found for {relative_path}, but will still extract for consistency")
        
        # Read file content once
        content = None
        try:
            content = read_noteplan_file(file_path)
            logger.debug(f"Read {len(content)} characters from {relative_path}")
        except Exception as e:
            logger.error(f"Error reading file {relative_path}: {e}", exc_info=True)
            return None, []
        
        # Extract nodes/edges
        try:
            logger.info(f"Extracting entities and relationships from {relative_path}")
            output = await run_graph_builder_agent(
                note_content=content,
                file_path=relative_path,
                dependencies=dependencies,
            )
            if output:
                logger.info(
                    f"Extracted {len(output.entities)} entities, "
                    f"{len(output.relationships)} relationships from {relative_path}"
                )
            else:
                logger.warning(f"Failed to extract entities/relationships from {relative_path}")
        except Exception as e:
            logger.error(f"Error extracting from {relative_path}: {e}", exc_info=True)
            output = None
        
        # Split into sections and generate embeddings
        try:
            logger.info(f"Generating sections and embeddings for {relative_path}")
            from .text_splitters import split_content_into_sections
            sections = split_content_into_sections(content, file_path=file_path)
            
            if generate_embeddings_flag:
                # Generate embeddings for each section
                section_texts = [s["content"] for s in sections]
                logger.debug(f"Generating embeddings for {len(section_texts)} sections")
                embeddings_list = generate_embeddings(
                    texts=section_texts,
                    dependencies=dependencies,
                    batch_size=10,
                )
                
                # Combine sections with embeddings and tokens
                for i, (section, embedding) in enumerate(zip(sections, embeddings_list)):
                    tokens = estimate_tokens(section["content"])
                    sections_with_embeddings.append({
                        "content": section["content"],
                        "embedding": embedding,
                        "tokens": tokens,
                        "section_index": i,
                    })
                logger.info(
                    f"Generated embeddings for {len(sections_with_embeddings)} sections "
                    f"from {relative_path}"
                )
            else:
                # Just add token counts without embeddings
                for section in sections:
                    tokens = estimate_tokens(section["content"])
                    sections_with_embeddings.append({
                        "content": section["content"],
                        "tokens": tokens,
                        "section_index": section["section_index"],
                    })
                logger.info(f"Created {len(sections_with_embeddings)} sections from {relative_path}")
        except Exception as e:
            logger.error(f"Error generating sections/embeddings for {relative_path}: {e}", exc_info=True)
    
    return output, sections_with_embeddings

