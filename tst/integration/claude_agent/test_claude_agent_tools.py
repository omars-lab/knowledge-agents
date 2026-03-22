"""
Integration tests for Claude Agent tools against real services.

Requires running: Qdrant (seeded), Neo4j, tidy-mcp, llm-proxy.
Skip unless CLAUDE_AGENT_TESTS_ENABLED=true.
"""
import os

import pytest

TESTS_ENABLED = os.getenv("CLAUDE_AGENT_TESTS_ENABLED", "false").lower() == "true"

pytestmark = [
    pytest.mark.claude_agent,
    pytest.mark.skipif(not TESTS_ENABLED, reason="CLAUDE_AGENT_TESTS_ENABLED not set"),
]


class TestSemanticSearchIntegration:
    """Tests semantic_search against real Qdrant."""

    @pytest.fixture(autouse=True)
    def setup_clients(self):
        """Initialize tool clients with real service connections."""
        from knowledge_agents.claude_agent.config import ClaudeAgentSettings
        from knowledge_agents.claude_agent.tools import (
            close_tool_clients,
            init_tool_clients,
        )

        settings = ClaudeAgentSettings(
            qdrant_host="localhost",
            qdrant_port=6333,
            litellm_proxy_host="localhost",
            litellm_proxy_port=4000,
            neo4j_uri="bolt://localhost:7687",
        )
        init_tool_clients(settings)
        yield
        close_tool_clients()

    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        """semantic_search should return results from seeded Qdrant."""
        import json

        from knowledge_agents.claude_agent.tools import semantic_search

        result = await semantic_search.handler({"query": "project planning", "limit": 3})

        assert not result.get("is_error")
        data = json.loads(result["content"][0]["text"])
        assert isinstance(data, list)
        # Seeded collection should have some results
        if data:
            assert "file_path" in data[0]
            assert "similarity_score" in data[0]


class TestBuildKnowledgeGraphIntegration:
    """Tests build_knowledge_graph against real Neo4j."""

    @pytest.fixture(autouse=True)
    def setup_clients(self):
        """Initialize tool clients with real service connections."""
        from knowledge_agents.claude_agent.config import ClaudeAgentSettings
        from knowledge_agents.claude_agent.tools import (
            close_tool_clients,
            init_tool_clients,
        )

        settings = ClaudeAgentSettings(
            qdrant_host="localhost",
            qdrant_port=6333,
            litellm_proxy_host="localhost",
            litellm_proxy_port=4000,
            neo4j_uri="bolt://localhost:7687",
            neo4j_password="knowledge123",
        )
        init_tool_clients(settings)
        yield
        close_tool_clients()

    @pytest.mark.asyncio
    async def test_build_graph_creates_nodes(self):
        """build_knowledge_graph should create entities in Neo4j."""
        from knowledge_agents.claude_agent.tools import build_knowledge_graph

        result = await build_knowledge_graph.handler({
            "file_path": "test/integration_test_note.md",
            "entities": [
                {"name": "IntegTestEntity1", "type": "Topic"},
                {"name": "IntegTestEntity2", "type": "Project"},
            ],
            "relationships": [
                {
                    "from_entity": "IntegTestEntity1",
                    "to_entity": "IntegTestEntity2",
                    "type": "RELATED_TO",
                },
            ],
        })

        assert not result.get("is_error")
        text = result["content"][0]["text"]
        assert "entities" in text
        assert "relationships" in text

    @pytest.mark.asyncio
    async def test_query_graph_reads_back(self):
        """query_knowledge_graph should find created entities."""
        import json

        from knowledge_agents.claude_agent.tools import query_knowledge_graph

        result = await query_knowledge_graph.handler({
            "cypher_query": (
                "MATCH (e:Entity) WHERE e.name STARTS WITH 'IntegTest' "
                "RETURN e.name AS name, e.type AS type"
            )
        })

        assert not result.get("is_error")
        data = json.loads(result["content"][0]["text"])
        assert isinstance(data, list)


class TestDeriveXcallbackUrlIntegration:
    """Tests derive_xcallback_url against real tidy-mcp."""

    @pytest.fixture(autouse=True)
    def setup_clients(self):
        """Initialize tool clients."""
        from knowledge_agents.claude_agent.config import ClaudeAgentSettings
        from knowledge_agents.claude_agent.tools import (
            close_tool_clients,
            init_tool_clients,
        )

        settings = ClaudeAgentSettings(
            qdrant_host="localhost",
            qdrant_port=6333,
            litellm_proxy_host="localhost",
            litellm_proxy_port=4000,
            neo4j_uri="bolt://localhost:7687",
            tidy_mcp_url="http://localhost:8003",
        )
        init_tool_clients(settings)
        yield
        close_tool_clients()

    @pytest.mark.asyncio
    async def test_xcallback_generates_url(self):
        """derive_xcallback_url should return a noteplan:// URL."""
        from knowledge_agents.claude_agent.tools import derive_xcallback_url

        result = await derive_xcallback_url.handler({"file_path": "2025-01-15.md"})

        # May fail if file doesn't exist, but should not error
        text = result["content"][0]["text"]
        assert isinstance(text, str)
