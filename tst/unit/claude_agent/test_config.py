"""
Unit tests for ClaudeAgentSettings.
"""
import os

import pytest


@pytest.mark.unit
class TestClaudeAgentSettings:
    """Tests for ClaudeAgentSettings configuration."""

    def test_default_values(self):
        """Settings should have sensible defaults."""
        from knowledge_agents.claude_agent.config import ClaudeAgentSettings

        settings = ClaudeAgentSettings()
        assert settings.qdrant_host == "qdrant"
        assert settings.qdrant_port == 6333
        assert settings.neo4j_uri == "bolt://neo4j:7687"
        assert settings.neo4j_username == "neo4j"
        assert settings.neo4j_database == "neo4j"
        assert settings.noteplan_dir == "/noteplan"
        assert settings.embedding_provider == "proxy"
        assert settings.tidy_mcp_url == "http://tidy-mcp:8000"
        assert settings.max_turns == 50
        assert settings.session_idle_timeout == 600
        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 8000
        assert settings.claude_model is None
        assert settings.semantic_search_limit == 5

    def test_env_prefix(self, monkeypatch):
        """Settings should read from CLAUDE_AGENT_ prefixed env vars."""
        from knowledge_agents.claude_agent.config import ClaudeAgentSettings

        monkeypatch.setenv("CLAUDE_AGENT_QDRANT_HOST", "custom-qdrant")
        monkeypatch.setenv("CLAUDE_AGENT_QDRANT_PORT", "9999")
        monkeypatch.setenv("CLAUDE_AGENT_NEO4J_URI", "bolt://custom:7687")
        monkeypatch.setenv("CLAUDE_AGENT_CLAUDE_MODEL", "claude-sonnet-4-6")

        settings = ClaudeAgentSettings()
        assert settings.qdrant_host == "custom-qdrant"
        assert settings.qdrant_port == 9999
        assert settings.neo4j_uri == "bolt://custom:7687"
        assert settings.claude_model == "claude-sonnet-4-6"

    def test_embedding_provider_toggle(self, monkeypatch):
        """Settings should support different embedding providers."""
        from knowledge_agents.claude_agent.config import ClaudeAgentSettings

        monkeypatch.setenv("CLAUDE_AGENT_EMBEDDING_PROVIDER", "openai")
        settings = ClaudeAgentSettings()
        assert settings.embedding_provider == "openai"
