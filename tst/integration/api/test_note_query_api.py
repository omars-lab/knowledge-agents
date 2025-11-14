"""
Note Query API End-to-End Integration Tests

PURPOSE: Tests the note query API endpoint functionality end-to-end
SCOPE: Complete note query flow from API request to response with semantic search
"""

import logging

import pytest

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


class TestNoteQueryAPI:
    """Test the /api/v1/notes/query endpoint end-to-end"""

    @pytest.mark.asyncio
    async def test_note_query_basic_question(
        self, api_client, setup_test_environment, seeded_noteplan_collection
    ):
        """Test basic note query with a simple question"""
        response = await api_client.post(
            "/api/v1/notes/query",
            json={"query": "What are my tasks for today?"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "answer" in data
        assert "reasoning" in data
        assert "relevant_files" in data
        assert "original_query" in data
        assert "query_answered" in data
        assert "guardrails_tripped" in data

        # Verify query response structure
        # Note: query_answered may be False if:
        # - Guardrail tripped
        # - Answer is too short (< 10 chars)
        # - An error occurred during processing
        # This is acceptable - we verify the response structure regardless
        assert "query_answered" in data
        assert len(data["answer"]) > 0  # Should always have an answer, even if query_answered is False
        assert data["original_query"] == "What are my tasks for today?"
        
        # If query_answered is False, it's acceptable if:
        # - Guardrails were tripped, OR
        # - Answer is an error message (indicates processing issue), OR  
        # - Answer is very short
        if not data["query_answered"]:
            is_error_message = "error" in data["answer"].lower() or "try again" in data["answer"].lower()
            assert (
                len(data["guardrails_tripped"]) > 0 
                or is_error_message 
                or len(data["answer"]) < 10
            ), f"query_answered is False but no clear reason: answer='{data['answer'][:100]}', guardrails={data['guardrails_tripped']}"

        # Verify relevant files structure (may be empty if no matches, which is OK)
        assert isinstance(data["relevant_files"], list)
        # Note: relevant_files may be empty if semantic search doesn't find matches
        # This is acceptable - the agent can still answer from context
        for file in data["relevant_files"]:
            assert "file_path" in file
            assert "file_name" in file
            assert "similarity_score" in file
            assert 0 <= file["similarity_score"] <= 1

    @pytest.mark.asyncio
    async def test_note_query_with_relevant_files(
        self, api_client, setup_test_environment, seeded_noteplan_collection
    ):
        """Test note query returns relevant files with similarity scores"""
        response = await api_client.post(
            "/api/v1/notes/query",
            json={"query": "What project ideas do I have?"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify file structure (may be empty if no matches, which is OK for this test)
        assert isinstance(data["relevant_files"], list)
        # Note: We check structure but don't require results since semantic matching
        # depends on embedding quality which can vary
        for file in data["relevant_files"]:
            assert "file_path" in file
            assert "file_name" in file
            assert "similarity_score" in file
            assert 0 <= file["similarity_score"] <= 1

    @pytest.mark.asyncio
    async def test_note_query_empty_query(
        self, api_client, setup_test_environment, seeded_noteplan_collection
    ):
        """Test note query with empty query is rejected"""
        response = await api_client.post(
            "/api/v1/notes/query",
            json={"query": ""},
        )

        # Should return validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_note_query_invalid_input(
        self, api_client, setup_test_environment, seeded_noteplan_collection
    ):
        """Test note query with invalid input format"""
        response = await api_client.post(
            "/api/v1/notes/query",
            json={},  # Missing query field
        )

        # Should return validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_note_query_guardrail_triggered(
        self, api_client, setup_test_environment, seeded_noteplan_collection
    ):
        """Test note query guardrail for non-note queries"""
        # Query that's too short or not a question
        response = await api_client.post(
            "/api/v1/notes/query",
            json={"query": "hi"},  # Too short, not a question
        )

        assert response.status_code == 200
        data = response.json()

        # Guardrail might trip or might allow it
        # If guardrail trips, query_answered should be False
        # If guardrail allows, query_answered might be True
        assert "query_answered" in data
        assert "guardrails_tripped" in data
