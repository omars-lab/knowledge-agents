"""
Unit tests for caching utilities.

Tests verify that:
1. Content hash computation works correctly
2. Cache validation checks content hashes
3. Cache metadata is saved and loaded correctly
4. Cache invalidation works
5. Edge cases are handled properly
"""
import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from knowledge_agents.utils.cache_utils import (
    CacheMetadata,
    check_data_file_cache,
    check_file_cache_valid,
    compute_content_hash,
    invalidate_cache,
    save_cache_metadata,
)

pytestmark = [pytest.mark.unit]


class TestContentHash:
    """Test content hash computation."""

    def test_computes_sha256_hash(self):
        """Test that SHA256 hash is computed correctly."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write("test content")
            temp_path = Path(f.name)
        
        try:
            hash_value = compute_content_hash(temp_path)
            
            # Should be a 64-character hex string (SHA256)
            assert len(hash_value) == 64
            assert all(c in '0123456789abcdef' for c in hash_value)
            
            # Verify it's actually SHA256
            expected_hash = hashlib.sha256(b"test content").hexdigest()
            assert hash_value == expected_hash
        finally:
            temp_path.unlink()

    def test_hash_changes_with_content(self):
        """Test that hash changes when content changes."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write("content 1")
            temp_path = Path(f.name)
        
        try:
            hash1 = compute_content_hash(temp_path)
            
            # Change content
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write("content 2")
            
            hash2 = compute_content_hash(temp_path)
            
            assert hash1 != hash2
        finally:
            temp_path.unlink()

    def test_hash_same_for_same_content(self):
        """Test that same content produces same hash."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write("same content")
            temp_path = Path(f.name)
        
        try:
            hash1 = compute_content_hash(temp_path)
            hash2 = compute_content_hash(temp_path)
            
            assert hash1 == hash2
        finally:
            temp_path.unlink()

    def test_handles_large_files(self):
        """Test that large files are handled efficiently."""
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            f.write(b"x" * 1000000)  # 1MB
            temp_path = Path(f.name)
        
        try:
            hash_value = compute_content_hash(temp_path)
            assert len(hash_value) == 64
        finally:
            temp_path.unlink()


class TestCacheMetadata:
    """Test cache metadata dataclass."""

    def test_metadata_creation(self):
        """Test creating cache metadata."""
        now = datetime.now()
        source_path = Path("/test/file.md")
        
        metadata = CacheMetadata(
            cached_at=now,
            source_file_path=source_path,
            source_content_hash="abc123",
            cache_version="1.0",
        )
        
        assert metadata.cached_at == now
        assert metadata.source_file_path == source_path
        assert metadata.source_content_hash == "abc123"
        assert metadata.cache_version == "1.0"
        assert metadata.additional_metadata == {}

    def test_metadata_to_dict(self):
        """Test converting metadata to dictionary."""
        now = datetime.now()
        metadata = CacheMetadata(
            cached_at=now,
            source_file_path=Path("/test/file.md"),
            source_content_hash="abc123",
            additional_metadata={"key": "value"},
        )
        
        data = metadata.to_dict()
        
        assert data["cached_at"] == now.isoformat()
        assert data["source_file_path"] == "/test/file.md"
        assert data["source_content_hash"] == "abc123"
        assert data["cache_version"] == "1.0"
        assert data["additional_metadata"] == {"key": "value"}

    def test_metadata_from_dict(self):
        """Test creating metadata from dictionary."""
        now = datetime.now()
        data = {
            "cached_at": now.isoformat(),
            "source_file_path": "/test/file.md",
            "source_content_hash": "abc123",
            "cache_version": "1.0",
            "additional_metadata": {"key": "value"},
        }
        
        metadata = CacheMetadata.from_dict(data)
        
        assert metadata.cached_at.isoformat() == now.isoformat()
        assert str(metadata.source_file_path) == "/test/file.md"
        assert metadata.source_content_hash == "abc123"
        assert metadata.cache_version == "1.0"
        assert metadata.additional_metadata == {"key": "value"}

    def test_metadata_defaults(self):
        """Test metadata default values."""
        now = datetime.now()
        metadata = CacheMetadata(cached_at=now)
        
        assert metadata.source_file_path is None
        assert metadata.source_content_hash is None
        assert metadata.cache_version == "1.0"
        assert metadata.additional_metadata == {}


class TestCacheValidation:
    """Test cache validation."""

    def test_cache_valid_when_exists_and_hash_matches(self):
        """Test that cache is valid when file exists and hash matches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "cache.json"
            source_file = Path(tmpdir) / "source.txt"
            
            # Create source file
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write("test content")
            
            # Create cache file
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({"data": "cached"}, f)
            
            # Save metadata with correct hash
            source_hash = compute_content_hash(source_file)
            save_cache_metadata(cache_file, source_file_path=source_file)
            
            # Check cache validity
            is_valid, metadata = check_file_cache_valid(
                cache_file, source_file_path=source_file, check_content_hash=True
            )
            
            assert is_valid is True
            assert metadata is not None
            assert metadata.source_content_hash == source_hash

    def test_cache_invalid_when_hash_mismatch(self):
        """Test that cache is invalid when content hash doesn't match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "cache.json"
            source_file = Path(tmpdir) / "source.txt"
            
            # Create source file
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write("original content")
            
            # Create cache file
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({"data": "cached"}, f)
            
            # Save metadata
            save_cache_metadata(cache_file, source_file_path=source_file)
            
            # Change source file content
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write("changed content")
            
            # Check cache validity - should be invalid now
            is_valid, metadata = check_file_cache_valid(
                cache_file, source_file_path=source_file, check_content_hash=True
            )
            
            assert is_valid is False
            assert metadata is not None

    def test_cache_invalid_when_not_exists(self):
        """Test that cache is invalid when file doesn't exist."""
        cache_file = Path("/nonexistent/cache.json")
        
        is_valid, metadata = check_file_cache_valid(cache_file)
        
        assert is_valid is False
        assert metadata is None

    def test_cache_valid_without_hash_check(self):
        """Test that cache can be valid without hash checking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "cache.json"
            
            # Create cache file
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({"data": "cached"}, f)
            
            # Check without hash validation
            is_valid, metadata = check_file_cache_valid(
                cache_file, check_content_hash=False
            )
            
            assert is_valid is True
            assert metadata is not None

    def test_cache_creates_metadata_on_first_check(self):
        """Test that metadata is created on first cache check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "cache.json"
            source_file = Path(tmpdir) / "source.txt"
            
            # Create files
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write("test content")
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({"data": "cached"}, f)
            
            # Check cache (no metadata exists yet)
            is_valid, metadata = check_file_cache_valid(
                cache_file, source_file_path=source_file, check_content_hash=True
            )
            
            # Should create metadata and return valid
            assert is_valid is True
            assert metadata is not None
            # Metadata file should be created
            metadata_file = cache_file.parent / f"{cache_file.stem}_metadata.json"
            assert metadata_file.exists()


class TestSaveCacheMetadata:
    """Test saving cache metadata."""

    def test_saves_metadata_file(self):
        """Test that metadata file is saved correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "cache.json"
            source_file = Path(tmpdir) / "source.txt"
            
            # Create files
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({"data": "cached"}, f)
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write("test content")
            
            # Save metadata
            metadata_path = save_cache_metadata(
                cache_file, source_file_path=source_file, additional_metadata={"key": "value"}
            )
            
            assert metadata_path.exists()
            
            # Load and verify
            with open(metadata_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            assert data["source_content_hash"] == compute_content_hash(source_file)
            assert data["additional_metadata"] == {"key": "value"}
            assert "cached_at" in data

    def test_saves_metadata_without_source_file(self):
        """Test saving metadata without source file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "cache.json"
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({"data": "cached"}, f)
            
            metadata_path = save_cache_metadata(cache_file)
            
            assert metadata_path.exists()
            
            # Load and verify
            with open(metadata_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            assert data["source_file_path"] is None
            assert data["source_content_hash"] is None


class TestInvalidateCache:
    """Test cache invalidation."""

    def test_invalidates_cache_file(self):
        """Test that cache file is deleted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "cache.json"
            
            # Create cache file
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({"data": "cached"}, f)
            
            assert cache_file.exists()
            
            # Invalidate
            result = invalidate_cache(cache_file)
            
            assert result is True
            assert not cache_file.exists()

    def test_invalidates_metadata_file(self):
        """Test that metadata file is also deleted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "cache.json"
            metadata_file = cache_file.parent / f"{cache_file.stem}_metadata.json"
            
            # Create both files
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({"data": "cached"}, f)
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump({"metadata": "test"}, f)
            
            # Invalidate
            invalidate_cache(cache_file)
            
            assert not metadata_file.exists()

    def test_invalidate_nonexistent_cache(self):
        """Test invalidating non-existent cache."""
        cache_file = Path("/nonexistent/cache.json")
        
        result = invalidate_cache(cache_file)
        
        assert result is False


class TestCheckDataFileCache:
    """Test data file cache checking."""

    def test_checks_nodes_edges_cache(self):
        """Test checking nodes/edges cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            relative_path = "test/file.md"
            source_file = Path(tmpdir) / "source.md"
            
            # Create source file
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write("test content")
            
            # Create cache structure
            file_data_dir = data_dir / relative_path
            file_data_dir = file_data_dir.parent
            file_data_dir.mkdir(parents=True, exist_ok=True)
            
            cache_file = file_data_dir / "file_nodes_edges.json"
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({"entities": [], "relationships": []}, f)
            
            save_cache_metadata(cache_file, source_file_path=source_file)
            
            # Check cache
            is_cached, nodes_path, sections_path, metadata = check_data_file_cache(
                data_dir, relative_path, check_nodes_edges=True, source_file_path=source_file
            )
            
            assert is_cached is True
            assert nodes_path == cache_file
            assert sections_path is None
            assert metadata is not None

    def test_checks_sections_embeddings_cache(self):
        """Test checking sections/embeddings cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            relative_path = "test/file.md"
            source_file = Path(tmpdir) / "source.md"
            
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write("test content")
            
            file_data_dir = data_dir / relative_path
            file_data_dir = file_data_dir.parent
            file_data_dir.mkdir(parents=True, exist_ok=True)
            
            cache_file = file_data_dir / "file_sections_embeddings.json"
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({"sections": []}, f)
            
            save_cache_metadata(cache_file, source_file_path=source_file)
            
            is_cached, nodes_path, sections_path, metadata = check_data_file_cache(
                data_dir, relative_path, check_sections_embeddings=True, source_file_path=source_file
            )
            
            assert is_cached is True
            assert nodes_path is None
            assert sections_path == cache_file

    def test_returns_false_when_cache_missing(self):
        """Test that False is returned when cache doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            relative_path = "test/file.md"
            
            is_cached, nodes_path, sections_path, metadata = check_data_file_cache(
                data_dir, relative_path, check_nodes_edges=True
            )
            
            assert is_cached is False
            assert nodes_path is None
            assert sections_path is None
            assert metadata is None




