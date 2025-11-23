"""
Caching utilities for file-based and in-memory caching.

This module provides utilities for checking cache validity, managing cache metadata,
and supporting various caching strategies (file-based, content-hash-based, etc.).
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def compute_content_hash(file_path: Path) -> str:
    """
    Compute SHA256 hash of file content.
    
    Args:
        file_path: Path to file to hash
        
    Returns:
        Hexadecimal hash string
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files efficiently
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


@dataclass
class CacheMetadata:
    """Metadata about a cached item."""
    
    cached_at: datetime
    source_file_path: Optional[Path] = None
    source_content_hash: Optional[str] = None  # SHA256 hash of source file content
    cache_version: str = "1.0"
    additional_metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize additional_metadata if None."""
        if self.additional_metadata is None:
            self.additional_metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "cached_at": self.cached_at.isoformat(),
            "source_file_path": str(self.source_file_path) if self.source_file_path else None,
            "source_content_hash": self.source_content_hash,
            "cache_version": self.cache_version,
            "additional_metadata": self.additional_metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheMetadata":
        """Create from dictionary."""
        return cls(
            cached_at=datetime.fromisoformat(data["cached_at"]),
            source_file_path=Path(data["source_file_path"]) if data.get("source_file_path") else None,
            source_content_hash=data.get("source_content_hash"),
            cache_version=data.get("cache_version", "1.0"),
            additional_metadata=data.get("additional_metadata", {}),
        )


def check_file_cache_valid(
    cache_file_path: Path,
    source_file_path: Optional[Path] = None,
    check_content_hash: bool = True,
) -> Tuple[bool, Optional[CacheMetadata]]:
    """
    Check if a cached file is valid based on content hash.
    
    Args:
        cache_file_path: Path to the cached file
        source_file_path: Path to the source file (for content hash checking)
        check_content_hash: If True, check if source file content hash matches cached hash
        
    Returns:
        Tuple of (is_valid, metadata)
        - is_valid: True if cache exists and is valid
        - metadata: CacheMetadata if cache exists, else None
    """
    # Check if cache file exists
    if not cache_file_path.exists():
        return False, None
    
    # Load metadata if available
    metadata_file = cache_file_path.parent / f"{cache_file_path.stem}_metadata.json"
    metadata = None
    if metadata_file.exists():
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata_data = json.load(f)
                metadata = CacheMetadata.from_dict(metadata_data)
        except Exception as e:
            logger.warning(f"Failed to load cache metadata from {metadata_file}: {e}")
            metadata = None
    
    # If no metadata, create default based on cache file mtime
    if metadata is None:
        cache_mtime = cache_file_path.stat().st_mtime
        metadata = CacheMetadata(
            cached_at=datetime.fromtimestamp(cache_mtime),
            source_file_path=source_file_path,
        )
    
    # Check content hash if requested
    if check_content_hash and source_file_path and source_file_path.exists():
        # Compute current content hash
        current_hash = compute_content_hash(source_file_path)
        
        # If no cached hash, compute and store it (first time caching)
        if metadata.source_content_hash is None:
            logger.debug(
                f"No cached hash found for {source_file_path}, "
                f"computing and storing: {current_hash[:16]}..."
            )
            metadata.source_content_hash = current_hash
            # Save updated metadata
            save_cache_metadata(cache_file_path, source_file_path)
            return True, metadata
        
        # Compare hashes - if different, content changed, cache is invalid
        if current_hash != metadata.source_content_hash:
            logger.debug(
                f"Cache invalid: source file {source_file_path} content changed "
                f"(cached hash: {metadata.source_content_hash[:16]}..., "
                f"current hash: {current_hash[:16]}...)"
            )
            return False, metadata
    
    return True, metadata


def save_cache_metadata(
    cache_file_path: Path,
    source_file_path: Optional[Path] = None,
    additional_metadata: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Save cache metadata to a metadata file.
    
    Computes and stores content hash of source file for cache validation.
    
    Args:
        cache_file_path: Path to the cached file
        source_file_path: Path to the source file
        additional_metadata: Additional metadata to store
        
    Returns:
        Path to the metadata file
    """
    metadata_file = cache_file_path.parent / f"{cache_file_path.stem}_metadata.json"
    
    source_content_hash = None
    if source_file_path and source_file_path.exists():
        source_content_hash = compute_content_hash(source_file_path)
        logger.debug(f"Computed content hash for {source_file_path}: {source_content_hash[:16]}...")
    
    metadata = CacheMetadata(
        cached_at=datetime.now(),
        source_file_path=source_file_path,
        source_content_hash=source_content_hash,
        additional_metadata=additional_metadata or {},
    )
    
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False)
    
    logger.debug(f"Saved cache metadata to {metadata_file}")
    return metadata_file


def invalidate_cache(cache_file_path: Path) -> bool:
    """
    Invalidate a cache by deleting the cache file and its metadata.
    
    Args:
        cache_file_path: Path to the cached file
        
    Returns:
        True if cache was invalidated, False if it didn't exist
    """
    cache_invalidated = False
    
    # Delete cache file
    if cache_file_path.exists():
        cache_file_path.unlink()
        cache_invalidated = True
        logger.debug(f"Deleted cache file: {cache_file_path}")
    
    # Delete metadata file
    metadata_file = cache_file_path.parent / f"{cache_file_path.stem}_metadata.json"
    if metadata_file.exists():
        metadata_file.unlink()
        logger.debug(f"Deleted cache metadata: {metadata_file}")
    
    return cache_invalidated


def check_data_file_cache(
    data_dir: Path,
    relative_path: str,
    check_nodes_edges: bool = True,
    check_sections_embeddings: bool = False,
    source_file_path: Optional[Path] = None,
    check_content_hash: bool = True,
) -> Tuple[bool, Optional[Path], Optional[Path], Optional[CacheMetadata]]:
    """
    Check if a NotePlan file's data is cached and valid.
    
    Enhanced version of check_file_cached() with content hash validation.
    
    Args:
        data_dir: Base data directory
        relative_path: Relative path from NotePlan root
        check_nodes_edges: If True, check for nodes_edges.json
        check_sections_embeddings: If True, check for sections_embeddings.json
        source_file_path: Path to source NotePlan file (for content hash checking)
        check_content_hash: If True, check if source file content hash matches cached hash
        
    Returns:
        Tuple of (is_cached, nodes_edges_path, sections_embeddings_path, metadata)
        - is_cached: True if all requested files exist and are valid
        - nodes_edges_path: Path to nodes_edges.json if exists and valid, else None
        - sections_embeddings_path: Path to sections_embeddings.json if exists and valid, else None
        - metadata: CacheMetadata from nodes_edges if available, else None
    """
    from .data_persistence import get_file_data_dir, get_file_base_name
    
    file_data_dir = get_file_data_dir(data_dir, relative_path)
    base_name = get_file_base_name(relative_path)
    
    nodes_edges_path = None
    sections_embeddings_path = None
    metadata = None
    
    if check_nodes_edges:
        nodes_edges_path = file_data_dir / f"{base_name}_nodes_edges.json"
        if nodes_edges_path.exists():
            is_valid, metadata = check_file_cache_valid(
                nodes_edges_path,
                source_file_path=source_file_path,
                check_content_hash=check_content_hash,
            )
            if not is_valid:
                return False, None, None, None
        else:
            return False, None, None, None
    
    if check_sections_embeddings:
        sections_embeddings_path = file_data_dir / f"{base_name}_sections_embeddings.json"
        if sections_embeddings_path.exists():
            is_valid, _ = check_file_cache_valid(
                sections_embeddings_path,
                source_file_path=source_file_path,
                check_content_hash=check_content_hash,
            )
            if not is_valid:
                return False, nodes_edges_path, None, metadata
        else:
            return False, nodes_edges_path, None, metadata
    
    return True, nodes_edges_path, sections_embeddings_path, metadata

