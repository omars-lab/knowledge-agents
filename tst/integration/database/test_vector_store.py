"""
Integration tests for Qdrant vector store semantic search with NotePlan files.
"""
from pathlib import Path

import pytest

from knowledge_agents.database.queries.query_vector_store import VectorStoreQueries
from tst.integration.fixtures.vector_store import (
    EMBEDDING_SIZE,
    cleanup_collection,
    qdrant_client_instance,
    seeded_noteplan_collection,
)

pytestmark = [pytest.mark.integration]

# Test collection name for NotePlan files
TEST_COLLECTION_NAME = "test_noteplan_files_collection"


@pytest.fixture
def sample_noteplan_files():
    """Create sample NotePlan file content for testing."""
    return [
        {
            "file_path": "2024-01-15.md",
            "file_name": "2024-01-15.md",
            "content": "# Daily Plan - January 15\n\n## Morning\n- [ ] Go to gym\n- [ ] Breakfast\n\n## Work\n- [ ] Review PRs\n- [x] Standup meeting",
            "modified_at": "2024-01-15T09:00:00",
            "file_size": 120,
        },
        {
            "file_path": "2024-01-16.md",
            "file_name": "2024-01-16.md",
            "content": "# Daily Plan - January 16\n\n## Exercise\n- [ ] Morning run\n- [ ] Stretch\n\n## Projects\n- [ ] Work on feature X",
            "modified_at": "2024-01-16T08:00:00",
            "file_size": 110,
        },
        {
            "file_path": "notes/ideas.md",
            "file_name": "ideas.md",
            "content": "# Project Ideas\n\n## AI Projects\n- [ ] Build chatbot\n- [ ] ML model training\n\n## Automation\n- [ ] CI/CD pipeline",
            "modified_at": "2024-01-14T10:00:00",
            "file_size": 95,
        },
    ]


# Use fixtures from vector_store.py:
# - seeded_noteplan_collection: Creates collection with test data
# - cleanup_collection: Cleans up collection before/after tests


class TestNotePlanVectorStoreSearch:
    """Test semantic search functionality for NotePlan files."""

    def test_create_collection_and_insert_vectors(
        self, qdrant_client_instance, seeded_noteplan_collection, sample_noteplan_files
    ):
        """Test creating a collection and inserting NotePlan file vectors."""
        # Verify collection exists and has correct configuration
        collection_info = qdrant_client_instance.get_collection(
            seeded_noteplan_collection
        )
        assert collection_info.config.params.vectors.size == EMBEDDING_SIZE

        # Verify points were inserted
        assert collection_info.points_count == len(sample_noteplan_files)

    def test_semantic_search_exercise_content(
        self, test_dependencies, seeded_noteplan_collection
    ):
        """Test semantic search for exercise-related content."""
        vector_store_queries = VectorStoreQueries(dependencies=test_dependencies)

        # Search for exercise-related content
        query_text = "I want to go to the gym and work out"
        results = vector_store_queries.query_files_semantically(
            query=query_text, collection_name=seeded_noteplan_collection, limit=3
        )

        # Verify we get relevant results
        assert len(results) > 0
        # Top result should be related to exercise/gym
        top_result = results[0]
        assert "file_path" in top_result
        assert "file_name" in top_result
        assert "similarity_score" in top_result
        assert 0 <= top_result["similarity_score"] <= 1
        # Should find the daily plan with gym/exercise content
        assert (
            "gym" in top_result["file_name"].lower()
            or "exercise" in top_result.get("file_path", "").lower()
        )

    def test_semantic_search_work_content(
        self, test_dependencies, seeded_noteplan_collection
    ):
        """Test semantic search for work-related content."""
        vector_store_queries = VectorStoreQueries(dependencies=test_dependencies)

        # Search for work-related content
        query_text = "What are my tasks for reviewing code and meetings?"
        results = vector_store_queries.query_files_semantically(
            query=query_text, collection_name=seeded_noteplan_collection, limit=5
        )

        # Should find work-related entries
        assert len(results) > 0
        # Should find files with work-related content (PRs, standup, etc.)
        work_results = [
            r
            for r in results
            if "2024-01-15" in r["file_name"]
            or "work" in r.get("file_path", "").lower()
        ]
        assert len(work_results) > 0

    def test_semantic_search_project_ideas(
        self, test_dependencies, seeded_noteplan_collection
    ):
        """Test semantic search for project ideas."""
        vector_store_queries = VectorStoreQueries(dependencies=test_dependencies)

        # Search for project-related content
        query_text = "What are my ideas for AI and automation projects?"
        results = vector_store_queries.query_files_semantically(
            query=query_text, collection_name=seeded_noteplan_collection, limit=5
        )

        # Should find project ideas file
        assert len(results) > 0
        # Should find the ideas.md file
        ideas_results = [
            r
            for r in results
            if "ideas" in r["file_name"].lower()
            or "ai" in r.get("file_path", "").lower()
        ]
        assert len(ideas_results) > 0

    def test_semantic_search_empty_query(
        self, test_dependencies, seeded_noteplan_collection
    ):
        """Test that empty queries return empty results."""
        vector_store_queries = VectorStoreQueries(dependencies=test_dependencies)

        results = vector_store_queries.query_files_semantically(
            query="", collection_name=seeded_noteplan_collection, limit=5
        )

        assert results == []

    def test_semantic_search_score_threshold(
        self, test_dependencies, seeded_noteplan_collection
    ):
        """Test that score threshold filters results."""
        vector_store_queries = VectorStoreQueries(dependencies=test_dependencies)

        # Search with very high threshold (should return few/no results)
        query_text = "completely unrelated topic that won't match anything"
        results = vector_store_queries.query_files_semantically(
            query=query_text,
            collection_name=seeded_noteplan_collection,
            limit=5,
            score_threshold=0.9,  # Very high threshold
        )

        # Should have fewer or no results due to high threshold
        assert len(results) <= 5
        # All results should meet the threshold
        if results:
            assert all(r["similarity_score"] >= 0.9 for r in results)
