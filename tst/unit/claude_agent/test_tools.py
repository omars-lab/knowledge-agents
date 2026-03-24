"""
Unit tests for Claude Agent MCP tools.

All tests use mocked clients — no real Qdrant, Neo4j, or API calls.

Note: The @tool() decorator returns SdkMcpTool objects, not callable functions.
We call .handler(args) to invoke the underlying async function in tests.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
class TestSemanticSearch:
    """Tests for the semantic_search tool."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mocked tool clients before each test."""
        import knowledge_agents.claude_agent.tools as tools_mod

        self.settings = MagicMock()
        self.settings.qdrant_collection_name = "test_collection"
        self.settings.semantic_search_limit = 5
        self.settings.litellm_proxy_embedding_model = "test-model"

        tools_mod._settings = self.settings
        tools_mod._qdrant_client = MagicMock()
        tools_mod._embedding_client = MagicMock()

        # Mock embedding generation
        mock_embedding_data = MagicMock()
        mock_embedding_data.data = [MagicMock(embedding=[0.1] * 128)]
        tools_mod._embedding_client.embeddings.create.return_value = (
            mock_embedding_data
        )

        self.tools_mod = tools_mod

    @pytest.mark.asyncio
    async def test_semantic_search_returns_results(self):
        """semantic_search should return formatted search results."""
        from knowledge_agents.claude_agent.tools import semantic_search

        mock_result = MagicMock()
        mock_result.payload = {
            "file_path": "notes/test.md",
            "file_name": "test.md",
            "modified_at": "2025-01-15",
            "file_size": 500,
        }
        mock_result.score = 0.95
        self.tools_mod._qdrant_client.search.return_value = [mock_result]

        result = await semantic_search.handler({"query": "test query"})

        assert "content" in result
        assert not result.get("is_error")
        data = json.loads(result["content"][0]["text"])
        assert len(data) == 1
        assert data[0]["file_path"] == "notes/test.md"
        assert data[0]["similarity_score"] == 0.95

    @pytest.mark.asyncio
    async def test_semantic_search_empty_results(self):
        """semantic_search should handle empty results gracefully."""
        from knowledge_agents.claude_agent.tools import semantic_search

        self.tools_mod._qdrant_client.search.return_value = []

        result = await semantic_search.handler({"query": "nonexistent topic"})

        data = json.loads(result["content"][0]["text"])
        assert data == []

    @pytest.mark.asyncio
    async def test_semantic_search_respects_limit(self):
        """semantic_search should pass limit to Qdrant."""
        from knowledge_agents.claude_agent.tools import semantic_search

        self.tools_mod._qdrant_client.search.return_value = []

        await semantic_search.handler({"query": "test", "limit": 10})

        self.tools_mod._qdrant_client.search.assert_called_once()
        call_kwargs = self.tools_mod._qdrant_client.search.call_args
        assert call_kwargs.kwargs["limit"] == 10

    @pytest.mark.asyncio
    async def test_semantic_search_handles_error(self):
        """semantic_search should return error on exception."""
        from knowledge_agents.claude_agent.tools import semantic_search

        self.tools_mod._qdrant_client.search.side_effect = ConnectionError(
            "Connection refused"
        )

        result = await semantic_search.handler({"query": "test"})

        assert result.get("is_error") is True
        assert "Error" in result["content"][0]["text"]


@pytest.mark.unit
class TestReadNote:
    """Tests for the read_note tool."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mocked settings."""
        import knowledge_agents.claude_agent.tools as tools_mod

        self.settings = MagicMock()
        self.settings.noteplan_dir = "/tmp/test_noteplan"
        tools_mod._settings = self.settings

    @pytest.mark.asyncio
    async def test_read_note_success(self, tmp_path):
        """read_note should return file content."""
        import knowledge_agents.claude_agent.tools as tools_mod
        from knowledge_agents.claude_agent.tools import read_note

        # Create a test file
        note_dir = tmp_path / "notes"
        note_dir.mkdir()
        test_file = note_dir / "test.md"
        test_file.write_text("# Test Note\n\nSome content here.")

        tools_mod._settings.noteplan_dir = str(tmp_path)

        result = await read_note.handler({"file_path": "notes/test.md"})

        assert not result.get("is_error")
        assert "Test Note" in result["content"][0]["text"]
        assert "Some content here" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_read_note_file_not_found(self):
        """read_note should return error for missing files."""
        from knowledge_agents.claude_agent.tools import read_note

        result = await read_note.handler({"file_path": "nonexistent.md"})

        assert result.get("is_error") is True
        assert "Error" in result["content"][0]["text"]


@pytest.mark.unit
class TestBuildKnowledgeGraph:
    """Tests for the build_knowledge_graph tool (Graphiti-powered)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mocked settings."""
        import knowledge_agents.claude_agent.tools as tools_mod

        self.settings = MagicMock()
        self.settings.neo4j_database = "neo4j"
        self.settings.noteplan_dir = "/noteplan"
        tools_mod._settings = self.settings
        self.tools_mod = tools_mod

    @pytest.mark.asyncio
    async def test_build_knowledge_graph_with_content(self):
        """build_knowledge_graph should accept file_path + note_content and call Graphiti."""
        from knowledge_agents.claude_agent.tools import build_knowledge_graph

        mock_graphiti = AsyncMock()
        with patch("knowledge_agents.claude_agent.tools.get_graphiti", return_value=mock_graphiti) as mock_get:
            result = await build_knowledge_graph.handler({
                "file_path": "notes/test.md",
                "note_content": "Alice works on the AI Project using Neo4j.",
            })

            assert not result.get("is_error")
            text = result["content"][0]["text"]
            assert "graph" in text.lower()
            mock_graphiti.add_episode.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_knowledge_graph_no_graphiti(self):
        """build_knowledge_graph should return error when Graphiti is unavailable."""
        from knowledge_agents.claude_agent.tools import build_knowledge_graph

        with patch("knowledge_agents.claude_agent.tools.get_graphiti", return_value=None):
            result = await build_knowledge_graph.handler({
                "file_path": "notes/test.md",
                "note_content": "Some content.",
            })
            assert result.get("is_error") is True
            assert "not available" in result["content"][0]["text"]


@pytest.mark.unit
class TestQueryKnowledgeGraph:
    """Tests for the query_knowledge_graph tool (Graphiti hybrid search)."""

    @pytest.mark.asyncio
    async def test_query_returns_results(self):
        """query_knowledge_graph should return Graphiti search results."""
        from knowledge_agents.claude_agent.tools import query_knowledge_graph

        mock_graphiti = AsyncMock()
        mock_graphiti.search.return_value = ["Entity: Alice (Person)", "Entity: Bob (Person)"]

        with patch("knowledge_agents.claude_agent.tools.get_graphiti", return_value=mock_graphiti):
            result = await query_knowledge_graph.handler({
                "query": "Who are the people in the graph?"
            })

            assert not result.get("is_error")
            assert "2 results" in result["content"][0]["text"]
            mock_graphiti.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_no_graphiti(self):
        """query_knowledge_graph should handle Graphiti unavailable."""
        from knowledge_agents.claude_agent.tools import query_knowledge_graph

        with patch("knowledge_agents.claude_agent.tools.get_graphiti", return_value=None):
            result = await query_knowledge_graph.handler({"query": "test"})
            assert result.get("is_error") is True


@pytest.mark.unit
class TestQueryGraphCypher:
    """Tests for the query_graph_cypher fallback tool."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        import knowledge_agents.claude_agent.tools as tools_mod
        self.settings = MagicMock()
        self.settings.neo4j_database = "neo4j"
        tools_mod._settings = self.settings
        tools_mod._neo4j_driver = MagicMock()
        self.tools_mod = tools_mod

    @pytest.mark.asyncio
    async def test_cypher_rejects_mutations(self):
        """query_graph_cypher should reject write queries."""
        from knowledge_agents.claude_agent.tools import query_graph_cypher

        for cypher in [
            "CREATE (n:Node {name: 'test'})",
            "MATCH (n) DELETE n",
            "MERGE (n:Node {name: 'test'})",
        ]:
            result = await query_graph_cypher.handler({"cypher_query": cypher})
            assert result.get("is_error") is True

    @pytest.mark.asyncio
    async def test_cypher_handles_error(self):
        """query_graph_cypher should handle Neo4j errors."""
        from knowledge_agents.claude_agent.tools import query_graph_cypher

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.side_effect = Exception("Neo4j connection failed")
        self.tools_mod._neo4j_driver.session.return_value = mock_session

        result = await query_graph_cypher.handler({
            "cypher_query": "MATCH (n) RETURN n LIMIT 1"
        })

        assert result.get("is_error") is True


@pytest.mark.unit
class TestDeriveXcallbackUrl:
    """Tests for the derive_xcallback_url tool."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mocked settings."""
        import knowledge_agents.claude_agent.tools as tools_mod

        self.settings = MagicMock()
        self.settings.tidy_mcp_url = "http://tidy-mcp:8000"
        tools_mod._settings = self.settings

    @pytest.mark.asyncio
    @patch("knowledge_agents.claude_agent.tools.requests.post")
    async def test_xcallback_success(self, mock_post):
        """derive_xcallback_url should return a valid URL."""
        from knowledge_agents.claude_agent.tools import derive_xcallback_url

        mock_post.return_value.json.return_value = {
            "success": True,
            "x_callback_url": "noteplan://x-callback-url/openNote?filename=test.md",
        }
        mock_post.return_value.raise_for_status = MagicMock()

        result = await derive_xcallback_url.handler({"file_path": "test.md"})

        assert not result.get("is_error")
        assert "noteplan://" in result["content"][0]["text"]

    @pytest.mark.asyncio
    @patch("knowledge_agents.claude_agent.tools.requests.post")
    async def test_xcallback_with_heading(self, mock_post):
        """derive_xcallback_url should include heading parameter."""
        from knowledge_agents.claude_agent.tools import derive_xcallback_url

        mock_post.return_value.json.return_value = {
            "success": True,
            "x_callback_url": "noteplan://x-callback-url/openNote?filename=test.md&heading=Section",
        }
        mock_post.return_value.raise_for_status = MagicMock()

        result = await derive_xcallback_url.handler({
            "file_path": "test.md",
            "heading": "Section",
        })

        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["json"]["heading"] == "Section"

    @pytest.mark.asyncio
    @patch("knowledge_agents.claude_agent.tools.requests.post")
    async def test_xcallback_service_error(self, mock_post):
        """derive_xcallback_url should handle service errors."""
        from knowledge_agents.claude_agent.tools import derive_xcallback_url

        mock_post.side_effect = ConnectionError("Service unavailable")

        result = await derive_xcallback_url.handler({"file_path": "test.md"})

        assert result.get("is_error") is True


@pytest.mark.unit
class TestToolClientInitialization:
    """Tests for init_tool_clients and close_tool_clients."""

    @patch("knowledge_agents.claude_agent.tools.QdrantClient")
    @patch("knowledge_agents.claude_agent.tools.OpenAI")
    @patch("knowledge_agents.claude_agent.tools.GraphDatabase")
    def test_init_tool_clients_proxy_provider(
        self, mock_graph_db, mock_openai, mock_qdrant
    ):
        """init_tool_clients should set up Qdrant and Neo4j clients."""
        from knowledge_agents.claude_agent.config import ClaudeAgentSettings
        from knowledge_agents.claude_agent.tools import init_tool_clients

        settings = ClaudeAgentSettings()
        init_tool_clients(settings)

        mock_qdrant.assert_called_once_with(host="qdrant", port=6333)
        # Embedding client is disabled — OpenAI should NOT be called
        mock_openai.assert_not_called()
        mock_graph_db.driver.assert_called_once()

    @patch("knowledge_agents.claude_agent.tools.QdrantClient")
    @patch("knowledge_agents.claude_agent.tools.OpenAI")
    @patch("knowledge_agents.claude_agent.tools.GraphDatabase")
    def test_init_tool_clients_creates_neo4j_driver(
        self, mock_graph_db, mock_openai, mock_qdrant
    ):
        """init_tool_clients should create a Neo4j driver with correct auth."""
        from knowledge_agents.claude_agent.config import ClaudeAgentSettings
        from knowledge_agents.claude_agent.tools import init_tool_clients

        settings = ClaudeAgentSettings()
        init_tool_clients(settings)

        mock_graph_db.driver.assert_called_once_with(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )


@pytest.mark.unit
class TestGenerateEmbedding:
    """Tests for the _generate_embedding helper."""

    def test_generate_embedding_calls_client(self):
        """_generate_embedding should call the embedding client."""
        import knowledge_agents.claude_agent.tools as tools_mod

        mock_client = MagicMock()
        mock_data = MagicMock()
        mock_data.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        mock_client.embeddings.create.return_value = mock_data

        tools_mod._embedding_client = mock_client
        tools_mod._settings = MagicMock()
        tools_mod._settings.litellm_proxy_embedding_model = "test-model"

        result = tools_mod._generate_embedding("test text")

        assert result == [0.1, 0.2, 0.3]
        mock_client.embeddings.create.assert_called_once_with(
            input=["test text"], model="test-model"
        )


@pytest.mark.unit
class TestMCPServerCreation:
    """Tests for MCP server factory."""

    @patch("knowledge_agents.claude_agent.tools.create_sdk_mcp_server")
    def test_create_notes_mcp_server(self, mock_create):
        """create_notes_mcp_server should register all tools."""
        from knowledge_agents.claude_agent.tools import (
            ALL_TOOLS,
            create_notes_mcp_server,
        )

        create_notes_mcp_server()

        mock_create.assert_called_once_with(
            name="notes",
            version="1.0.0",
            tools=ALL_TOOLS,
        )

    def test_tool_names_match_mcp_convention(self):
        """TOOL_NAMES should follow mcp__<server>__<tool> convention."""
        from knowledge_agents.claude_agent.tools import TOOL_NAMES

        assert len(TOOL_NAMES) == 6  # read_note, build_knowledge_graph, query_knowledge_graph, knowledge_changelog, query_graph_cypher, derive_xcallback_url
        for name in TOOL_NAMES:
            assert name.startswith("mcp__notes__"), f"Invalid tool name: {name}"
