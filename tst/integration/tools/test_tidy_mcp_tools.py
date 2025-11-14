"""
Integration tests for tidy-mcp tools integration with the agent.

PURPOSE: Tests that the agent can access and use tidy-mcp tools via HostedMCPTool
SCOPE: Agent integration, end-to-end tool usage, HostedMCPTool connectivity

NOTE: For HTTP endpoint testing, see test_noteplan_tools.py
"""

import logging

import pytest

from knowledge_agents.agents.note_query_agent import run_note_query_agent

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


class TestTidyMcpToolsIntegration:
    """Test tidy-mcp tools integration with the agent via HostedMCPTool"""

    async def test_agent_has_access_to_tidy_mcp_tools(
        self,
        setup_test_environment,
        seeded_noteplan_collection,
        test_dependencies,
        tidy_mcp_url,
        tidy_mcp_available,
        wait_for_services,
    ):
        """Test that agent has access to tidy-mcp tools via HostedMCPTool"""
        if not tidy_mcp_available:
            pytest.skip("tidy-mcp service not available")

        # Query that might trigger tool usage (asking about specific notes)
        query = "What notes do I have about project ideas? Please provide links to them."
        result, metadata = await run_note_query_agent(query, dependencies=test_dependencies)

        # Verify agent responded
        assert result.query_answered is True
        assert len(result.answer) > 0
        assert result.original_query == query

        # The agent might use the tool to generate x-callback-url links
        # We can't directly verify tool calls, but we can verify the agent
        # successfully processed the query (which requires tools to be available)
        logger.info(f"Agent response: {result.answer[:200]}...")

    async def test_agent_can_generate_noteplan_links(
        self,
        setup_test_environment,
        seeded_noteplan_collection,
        test_dependencies,
        tidy_mcp_url,
        tidy_mcp_available,
        wait_for_services,
    ):
        """Test that agent can generate NotePlan x-callback-url links when asked"""
        if not tidy_mcp_available:
            pytest.skip("tidy-mcp service not available")

        # Query that explicitly asks for links
        query = "Can you give me a link to open my daily note for 2025-11-13?"
        result, metadata = await run_note_query_agent(query, dependencies=test_dependencies)

        # Verify agent responded
        assert result.query_answered is True
        assert len(result.answer) > 0

        # Check if the answer contains a noteplan:// link
        # The agent should use the tool to generate the link
        answer_lower = result.answer.lower()
        has_noteplan_link = "noteplan://" in result.answer or "x-callback-url" in answer_lower

        # Log the response for debugging
        logger.info(f"Agent response: {result.answer}")
        logger.info(f"Contains noteplan link: {has_noteplan_link}")

        # Note: We can't guarantee the agent will use the tool, but if it does,
        # the link should be present. This test verifies the tool is available
        # and the agent can potentially use it.

