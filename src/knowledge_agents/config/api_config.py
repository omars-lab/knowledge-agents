"""Infrastructure configuration management."""

import logging
import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings

from .secrets_config import get_openai_api_key

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Infrastructure settings."""

    # Environment
    environment: str = Field(default="development", description="Environment name")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # API Configuration
    api_title: str = Field(
        default="Omar's Knowledge Workflow API", description="API title"
    )
    api_version: str = Field(default="1.0.0", description="API version")
    api_description: str = Field(
        default="AI-powered workflow analysis API", description="API description"
    )

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@postgres:5432/knowledge_workflow",
        description="Database connection URL",
    )
    db_pool_size: int = Field(default=10, description="Database pool size")
    db_max_overflow: int = Field(default=20, description="Database max overflow")
    db_pool_timeout: int = Field(default=30, description="Database pool timeout")
    database_timeout: int = Field(default=10, description="Database timeout in seconds")

    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    openai_model: str = Field(default="gpt-4.1", description="OpenAI model to use")
    openai_temperature: float = Field(default=0.1, description="OpenAI temperature")
    openai_max_tokens: int = Field(default=1000, description="OpenAI max tokens")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", description="OpenAI embedding model to use"
    )
    # https://platform.openai.com/docs/guides/embeddings/what-are-embeddings
    openai_embedding_size: int = Field(
        default=1536, description="OpenAI embedding vector size"
    )

    # Service Configuration
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")

    # Metrics Configuration
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    metrics_retention_days: int = Field(
        default=30, description="Metrics retention period in days"
    )

    # Timeout Configuration
    request_timeout: int = Field(default=30, description="Request timeout in seconds")

    # Health Check Configuration
    health_check_interval: int = Field(
        default=30, description="Health check interval in seconds"
    )

    # Vector Store Configuration (Qdrant)
    qdrant_host: str = Field(
        default="qdrant", description="Qdrant vector database host"
    )
    qdrant_port: int = Field(default=6333, description="Qdrant vector database port")
    qdrant_collection_name: str = Field(
        default="app_actions_collection",
        description="Qdrant collection name for NotePlan files",
    )
    semantic_search_limit: int = Field(
        default=5,
        description="Default number of top semantic search results to return for NotePlan files",
    )

    # LiteLLM Proxy Configuration
    litellm_proxy_host: str = Field(
        default="llm-proxy", description="LiteLLM proxy server host"
    )
    litellm_proxy_port: int = Field(
        default=4000, description="LiteLLM proxy server port"
    )
    litellm_proxy_embedding_model: str = Field(
        default="lm_studio/text-embedding-qwen3-embedding-8b",
        description="Embedding model to use via proxy",
    )
    litellm_proxy_embedding_size: int = Field(
        default=4096, description="Proxy embedding model vector size"
    )
    litellm_proxy_completion_model: str = Field(
        default="lm_studio/qwen3-coder-30b",
        description="Completion model to use via proxy",
    )
    litellm_proxy_responses_model: str = Field(
        default="lm_studio/gpt-oss-20b",
        description="Responses model to use via proxy",
    )

    # LM Studio Configuration (for local model hosting)
    lm_studio_host: str = Field(
        default="192.168.1.168",
        description="LM Studio host address for local model hosting",
    )
    lm_studio_port: int = Field(
        default=1234,
        description="LM Studio port for local model hosting",
    )

    # Tidy MCP Configuration
    tidy_mcp_url: str = Field(
        default="http://tidy-mcp:8000",
        description="URL for tidy-mcp HTTP service",
    )
    use_responses_api_for_mcp_tools: bool = Field(
        default=True,
        description="Use OpenAI Responses API instead of ChatCompletions API. "
        "Required for HostedMCPTool support. Note: Upgraded to openai-agents 0.5.1 which may have fixed usage handling.",
    )
    enable_usage_reporting: bool = Field(
        default=True,
        description="Enable usage reporting (token counts) in agent responses. "
        "When enabled, includes input/output/total tokens in response headers and enables include_usage in ModelSettings.",
    )

    def __init__(self, **kwargs):
        # Allow overriding openai_api_key via kwargs (useful for tests)
        openai_api_key_override = kwargs.pop("openai_api_key", None)

        super().__init__(**kwargs)

        # Load OpenAI API key using shared secrets configuration
        # If explicitly provided via kwargs, use that; otherwise load from secrets
        if openai_api_key_override is not None:
            self.openai_api_key = openai_api_key_override
            logger.debug(
                f"Using provided OpenAI API key override (first 10 chars: {openai_api_key_override[:10]}...)"
            )
        else:
            required = self.environment == "production"
            self.openai_api_key = get_openai_api_key(
                required=required,
                allow_test_key=True,
                environment=self.environment,
            )

    def validate_required(self) -> None:
        """Validate required configuration."""
        if not self.openai_api_key and self.environment == "production":
            raise ValueError(
                "API key is required - must be provided via Docker secret at /run/secrets/openai_api_key or secrets/openai_api_key.txt"
            )

    # Mapping of embedding model names to their vector dimensions
    # This allows us to dynamically determine embedding size based on the model being used
    EMBEDDING_MODEL_SIZES: dict[str, int] = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
        "text-embedding-qwen3-embedding-8b": 4096,
        "text-embedding-nomic-embed-text-v1.5": 768,  # Nomic Embed typically uses 768
    }

    def get_embedding_size(self, model_name: Optional[str] = None) -> int:
        """
        Get the embedding vector size for a given model.

        Args:
            model_name: Name of the embedding model. If None, uses the configured default.

        Returns:
            Vector dimension size for the model
        """
        if model_name is None:
            # Determine which model is being used based on configuration
            # Check if we're using proxy embedding model
            if hasattr(self, "litellm_proxy_embedding_model"):
                model_name = self.litellm_proxy_embedding_model
            else:
                model_name = self.openai_embedding_model

        # Check mapping first
        if model_name in self.EMBEDDING_MODEL_SIZES:
            return self.EMBEDDING_MODEL_SIZES[model_name]

        # Fallback to configured sizes based on model type
        if (
            "qwen3" in model_name.lower()
            or model_name == self.litellm_proxy_embedding_model
        ):
            return self.litellm_proxy_embedding_size
        elif model_name == self.openai_embedding_model:
            return self.openai_embedding_size

        # Default fallback
        logger.warning(
            f"Unknown embedding model '{model_name}', using default size 1536. "
            f"Please add it to EMBEDDING_MODEL_SIZES mapping."
        )
        return 1536

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Global settings instance - lazy loading
_settings = None


def get_settings(**overrides) -> Settings:
    """
    Get the global settings instance (lazy loading).

    Args:
        **overrides: Settings to override (e.g., openai_api_key="sk-...")
                    If provided, creates a new Settings instance with overrides.
                    If not provided and instance exists, returns cached instance.

    Returns:
        Settings instance
    """
    global _settings
    if overrides:
        # If overrides provided, create a new instance with overrides
        # This is useful for tests that need to inject specific values
        logger.debug(
            f"Creating Settings instance with overrides: {list(overrides.keys())}"
        )
        return Settings(**overrides)
    # If no overrides, check cache first (for performance)
    # NOTE: Test fixtures may monkey-patch this function to bypass cache
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """
    Reset the global settings instance (useful for testing).

    This clears the cached settings instance, forcing a reload on next get_settings() call.
    """
    global _settings
    _settings = None
    logger.debug("Settings cache reset")


# For backward compatibility - this will be loaded when first accessed
class LazySettings:
    def __getattr__(self, name):
        return getattr(get_settings(), name)


settings = LazySettings()
