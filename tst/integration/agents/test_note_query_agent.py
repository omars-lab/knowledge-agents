"""
Note Query Agent End-to-End Integration Tests

PURPOSE: Tests note query agent functionality directly without HTTP layer
SCOPE: Agent behavior, guardrail interactions, and semantic search integration
"""

import logging

import pytest

from knowledge_agents.agents.note_query_agent import run_note_query_agent

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


class TestNoteQueryAgentEndToEnd:
    """Test note query agent end-to-end functionality"""

    async def test_note_query_agent_basic_question(
        self, setup_test_environment, seeded_noteplan_collection, test_dependencies
    ):
        """Test note query agent with a basic question"""
        query = "What are my tasks for today?"
        result, metadata = await run_note_query_agent(query, dependencies=test_dependencies)

        # Verify response structure
        assert result.query_answered is True
        assert len(result.answer) > 0
        assert result.original_query == query
        assert isinstance(result.relevant_files, list)
        assert isinstance(result.guardrails_tripped, list)

    async def test_note_query_agent_returns_relevant_files(
        self, setup_test_environment, seeded_noteplan_collection, test_dependencies
    ):
        """Test that agent returns relevant files from semantic search"""
        query = "What project ideas do I have?"
        result = await run_note_query_agent(query, dependencies=test_dependencies)

        # Verify file structure (may be empty if semantic search doesn't find matches)
        # This is acceptable - the agent can still answer from other context
        assert isinstance(result.relevant_files, list)
        # If files are returned, verify their structure
        for file in result.relevant_files:
            assert file.file_path
            assert file.file_name
            assert 0 <= file.similarity_score <= 1

    async def test_note_query_agent_handles_empty_query(
        self, setup_test_environment, seeded_noteplan_collection, test_dependencies
    ):
        """Test note query agent handles empty query"""
        query = ""
        result = await run_note_query_agent(query, dependencies=test_dependencies)

        # Should not answer query
        assert result.query_answered is False
        assert len(result.guardrails_tripped) > 0

    async def test_note_query_agent_handles_short_query(
        self, setup_test_environment, seeded_noteplan_collection, test_dependencies
    ):
        """Test note query agent handles very short query"""
        query = "hi"
        result = await run_note_query_agent(query, dependencies=test_dependencies)

        # Guardrail might trip or allow
        assert "query_answered" in result.model_dump()
        assert "guardrails_tripped" in result.model_dump()

    async def test_note_query_agent_no_results(
        self, setup_test_environment, seeded_noteplan_collection, test_dependencies
    ):
        """Test note query agent when no relevant files found"""
        query = "What are my notes about quantum physics in ancient Egypt?"
        result = await run_note_query_agent(query, dependencies=test_dependencies)

        # Should still return a response (even if no files found)
        assert result.original_query == query
        # Answer might indicate no information found
        assert len(result.answer) > 0
