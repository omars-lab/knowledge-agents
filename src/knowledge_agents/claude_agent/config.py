"""
Configuration for the Claude Agent service.

Uses pydantic-settings with CLAUDE_AGENT_ prefix for environment variables.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings


class ClaudeAgentSettings(BaseSettings):
    """Settings for the Claude Agent service."""

    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection_name: str = "app_actions_collection"
    semantic_search_limit: int = 5

    # Neo4j
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "knowledge123"
    neo4j_database: str = "neo4j"

    # NotePlan (read-only mount)
    noteplan_dir: str = "/noteplan"

    # Embeddings
    embedding_provider: str = "proxy"  # "proxy" or "openai"
    litellm_proxy_host: str = "llm-proxy"
    litellm_proxy_port: int = 4000
    litellm_proxy_api_key: str = "sk-1234"  # LiteLLM virtual key
    litellm_proxy_embedding_model: str = "lm_studio/text-embedding-qwen3-embedding-8b"

    # Tidy MCP
    tidy_mcp_url: str = "http://tidy-mcp:8000"

    # Claude Agent SDK
    claude_model: str | None = None
    max_turns: int = 50
    session_idle_timeout: int = 600  # 10 min

    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = {"env_prefix": "CLAUDE_AGENT_"}
