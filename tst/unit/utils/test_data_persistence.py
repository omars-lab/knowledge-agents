"""
Unit tests for data persistence utilities.

Tests verify that:
1. Data directories are created correctly
2. Nodes/edges are saved and loaded correctly
3. Sections/embeddings are saved and loaded correctly
4. File paths are constructed correctly
5. Cache metadata is associated correctly
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from knowledge_agents.types.graph import Entity, GraphBuilderAgentOutput, Relationship
from knowledge_agents.utils.data_persistence import (
    get_data_dir,
    get_file_base_name,
    get_file_data_dir,
    load_nodes_edges,
    load_sections_embeddings,
    save_nodes_edges,
    save_sections_embeddings,
)

pytestmark = [pytest.mark.unit]


class TestDirectoryCreation:
    """Test directory creation utilities."""

    def test_get_data_dir_creates_directory(self):
        """Test that get_data_dir creates the directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir) / "build"
            noteplan_dir = Path(tmpdir) / "noteplan"
            
            data_dir = get_data_dir(base_dir, noteplan_dir)
            
            assert data_dir.exists()
            assert data_dir == base_dir / "data"

    def test_get_file_data_dir_creates_structure(self):
        """Test that get_file_data_dir creates nested structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            relative_path = "Calendar/2025-01-15.md"
            
            file_data_dir = get_file_data_dir(data_dir, relative_path)
            
            assert file_data_dir.exists()
            assert file_data_dir == data_dir / "Calendar"

    def test_get_file_base_name_extracts_name(self):
        """Test that get_file_base_name extracts base name correctly."""
        relative_path = "Calendar/2025-01-15.md"
        base_name = get_file_base_name(relative_path)
        
        assert base_name == "2025-01-15"

    def test_get_file_base_name_handles_nested_paths(self):
        """Test that get_file_base_name handles nested paths."""
        relative_path = "Notes/Projects/MyProject.md"
        base_name = get_file_base_name(relative_path)
        
        assert base_name == "MyProject"


class TestSaveNodesEdges:
    """Test saving nodes and edges."""

    def test_saves_nodes_edges_to_json(self):
        """Test that nodes/edges are saved to JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            relative_path = "test/file.md"
            
            # Create test output
            entities = [Entity(name="Test Entity", type="Person", properties={})]
            relationships = [
                Relationship(
                    from_entity="Entity1",
                    to_entity="Entity2",
                    type="RELATED_TO",
                    properties={},
                )
            ]
            output = GraphBuilderAgentOutput(
                entities=entities, relationships=relationships, insights=[]
            )
            
            # Save
            file_path = save_nodes_edges(data_dir, relative_path, output)
            
            assert file_path.exists()
            
            # Load and verify
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            assert data["file_path"] == relative_path
            assert len(data["entities"]) == 1
            assert len(data["relationships"]) == 1
            assert data["entities"][0]["name"] == "Test Entity"
            assert data["relationships"][0]["from_entity"] == "Entity1"

    def test_saves_with_cache_metadata(self):
        """Test that cache metadata is saved with nodes/edges."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            relative_path = "test/file.md"
            source_file = Path(tmpdir) / "source.md"
            
            # Create source file
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write("test content")
            
            output = GraphBuilderAgentOutput(entities=[], relationships=[], insights=[])
            
            # Save with source file path
            file_path = save_nodes_edges(
                data_dir, relative_path, output, source_file_path=source_file
            )
            
            # Check metadata file exists
            metadata_file = file_path.parent / f"{file_path.stem}_metadata.json"
            assert metadata_file.exists()
            
            # Verify metadata content
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            assert metadata["source_file_path"] == str(source_file)
            assert "source_content_hash" in metadata

    def test_saves_insights(self):
        """Test that insights are saved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            relative_path = "test/file.md"
            
            insights = ["Insight 1", "Insight 2"]
            output = GraphBuilderAgentOutput(
                entities=[], relationships=[], insights=insights
            )
            
            file_path = save_nodes_edges(data_dir, relative_path, output)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            assert data["insights"] == insights


class TestLoadNodesEdges:
    """Test loading nodes and edges."""

    def test_loads_nodes_edges_from_json(self):
        """Test that nodes/edges are loaded from JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test_nodes_edges.json"
            
            # Create test data
            data = {
                "file_path": "test/file.md",
                "entities": [
                    {"name": "Entity1", "type": "Person", "properties": {"age": 30}}
                ],
                "relationships": [
                    {
                        "from_entity": "Entity1",
                        "to_entity": "Entity2",
                        "type": "RELATED_TO",
                        "properties": {},
                    }
                ],
                "insights": ["Test insight"],
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            
            # Load
            loaded_data = load_nodes_edges(file_path)
            
            assert loaded_data["file_path"] == "test/file.md"
            assert len(loaded_data["entities"]) == 1
            assert len(loaded_data["relationships"]) == 1
            assert loaded_data["entities"][0]["name"] == "Entity1"
            assert loaded_data["insights"] == ["Test insight"]

    def test_loads_empty_data(self):
        """Test loading empty nodes/edges."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "empty_nodes_edges.json"
            
            data = {
                "file_path": "test/file.md",
                "entities": [],
                "relationships": [],
                "insights": [],
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            
            loaded_data = load_nodes_edges(file_path)
            
            assert len(loaded_data["entities"]) == 0
            assert len(loaded_data["relationships"]) == 0


class TestSaveSectionsEmbeddings:
    """Test saving sections with embeddings."""

    def test_saves_sections_embeddings_to_json(self):
        """Test that sections/embeddings are saved to JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            relative_path = "test/file.md"
            
            sections = [
                {
                    "content": "Section 1",
                    "embedding": [0.1, 0.2, 0.3],
                    "tokens": 10,
                    "section_index": 0,
                },
                {
                    "content": "Section 2",
                    "embedding": [0.4, 0.5, 0.6],
                    "tokens": 15,
                    "section_index": 1,
                },
            ]
            
            file_path = save_sections_embeddings(data_dir, relative_path, sections)
            
            assert file_path.exists()
            
            # Load and verify
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            assert len(data["sections"]) == 2
            assert data["sections"][0]["content"] == "Section 1"
            assert data["sections"][0]["embedding"] == [0.1, 0.2, 0.3]
            assert data["sections"][0]["tokens"] == 10

    def test_saves_with_cache_metadata(self):
        """Test that cache metadata is saved with sections/embeddings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            relative_path = "test/file.md"
            source_file = Path(tmpdir) / "source.md"
            
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write("test content")
            
            sections = [
                {
                    "content": "Section 1",
                    "embedding": [0.1],
                    "tokens": 10,
                    "section_index": 0,
                }
            ]
            
            file_path = save_sections_embeddings(
                data_dir, relative_path, sections, source_file_path=source_file
            )
            
            # Check metadata file exists
            metadata_file = file_path.parent / f"{file_path.stem}_metadata.json"
            assert metadata_file.exists()

    def test_saves_with_heading_info(self):
        """Test that heading information is preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            relative_path = "test/file.md"
            
            sections = [
                {
                    "content": "Section 1",
                    "embedding": [0.1],
                    "tokens": 10,
                    "section_index": 0,
                    "heading": "Introduction",
                    "heading_level": 2,
                }
            ]
            
            file_path = save_sections_embeddings(data_dir, relative_path, sections)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            assert data["sections"][0]["heading"] == "Introduction"
            assert data["sections"][0]["heading_level"] == 2


class TestLoadSectionsEmbeddings:
    """Test loading sections with embeddings."""

    def test_loads_sections_embeddings_from_json(self):
        """Test that sections/embeddings are loaded from JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test_sections_embeddings.json"
            
            data = {
                "file_path": "test/file.md",
                "sections": [
                    {
                        "content": "Section 1",
                        "embedding": [0.1, 0.2, 0.3],
                        "tokens": 10,
                        "section_index": 0,
                    }
                ],
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            
            loaded_data = load_sections_embeddings(file_path)
            
            assert len(loaded_data["sections"]) == 1
            assert loaded_data["sections"][0]["content"] == "Section 1"
            assert loaded_data["sections"][0]["embedding"] == [0.1, 0.2, 0.3]

    def test_loads_empty_sections(self):
        """Test loading empty sections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "empty_sections_embeddings.json"
            
            data = {"file_path": "test/file.md", "sections": []}
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            
            loaded_data = load_sections_embeddings(file_path)
            
            assert len(loaded_data["sections"]) == 0


class TestPathHandling:
    """Test path handling edge cases."""

    def test_handles_deeply_nested_paths(self):
        """Test handling of deeply nested paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            relative_path = "Level1/Level2/Level3/file.md"
            
            file_data_dir = get_file_data_dir(data_dir, relative_path)
            
            assert file_data_dir.exists()
            assert file_data_dir == data_dir / "Level1" / "Level2" / "Level3"

    def test_handles_root_level_files(self):
        """Test handling of files at root level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            relative_path = "file.md"
            
            file_data_dir = get_file_data_dir(data_dir, relative_path)
            
            assert file_data_dir.exists()
            # Should be data_dir itself or a subdirectory

    def test_handles_special_characters_in_paths(self):
        """Test handling of special characters in paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            relative_path = "Folder with spaces/file-name.md"
            
            file_data_dir = get_file_data_dir(data_dir, relative_path)
            
            assert file_data_dir.exists()




