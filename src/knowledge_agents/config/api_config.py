"""Infrastructure configuration management."""

import logging
import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings

from .secrets_config import get_openai_api_key

logger = logging.getLogger(__name__)


def is_running_in_container() -> bool:
    """
    Detect if running in a container environment.
    
    Checks multiple indicators in order of reliability:
    - /.dockerenv file (Docker) - most reliable
    - DOCKER_CONTAINER environment variable - explicit indicator
    - /noteplan mount point (project-specific indicator) - only if it's a mount
    
    Returns:
        True if running in container, False if running locally
    """
    # Primary indicators (most reliable)
    if os.path.exists("/.dockerenv"):
        return True
    if os.environ.get("DOCKER_CONTAINER") == "true":
        return True
    
    # Secondary indicator: /noteplan mount point
    # Only consider it if it exists AND is likely a mount (not just a regular directory)
    # Check if it's a mount by seeing if it's different from parent filesystem
    noteplan_path = Path("/noteplan")
    if noteplan_path.exists():
        try:
            # On macOS/Linux, check if it's a mount point
            # A mount point will have a different device/st_dev than its parent
            noteplan_stat = noteplan_path.stat()
            parent_stat = noteplan_path.parent.stat()
            # If device numbers differ, it's likely a mount point
            if noteplan_stat.st_dev != parent_stat.st_dev:
                return True
        except (OSError, AttributeError):
            # If stat fails or st_dev not available, fall back to existence check
            # but only if we're sure it's not just a regular directory
            pass
    
    return False


class Settings(BaseSettings):
    """
    Infrastructure settings with runtime-aware defaults.
    
    **Precedence Order:**
    1. Manual overrides (kwargs to Settings() or get_settings()) - HIGHEST PRIORITY
    2. Environment variables (NEO4J_URI, NEO4J_PASSWORD, LITELLM_PROXY_HOST, etc.)
    3. Runtime-aware defaults (based on runtime_env or auto-detection)
    
    **Runtime Environment:**
    The `runtime_env` parameter controls default values for `neo4j_uri` and `litellm_proxy_host`:
    - `'container'`: Uses Docker service names (neo4j_uri="bolt://host.docker.internal:7687", litellm_proxy_host="llm-proxy")
    - `'local'`: Uses localhost (neo4j_uri="bolt://localhost:7687", litellm_proxy_host="localhost")
    - `None`: Auto-detects using is_running_in_container()
    
    **Environment Variables:**
    All settings can be overridden via environment variables. Pydantic automatically reads them.
    Common examples:
    - `NEO4J_URI`: Override Neo4j connection URI
    - `NEO4J_PASSWORD`: Override Neo4j password
    - `LITELLM_PROXY_HOST`: Override LiteLLM proxy host
    - `NEO4J_USERNAME`: Override Neo4j username
    
    **Usage Examples:**
    ```python
    # Auto-detect runtime (default)
    settings = Settings()
    
    # Force container defaults
    settings = Settings(runtime_env='container')
    
    # Override specific settings
    settings = Settings(neo4j_password='admin123', neo4j_uri='bolt://custom:7687')
    
    # Combine runtime_env with overrides
    settings = Settings(runtime_env='container', neo4j_password='admin123')
    ```
    
    **Note:** Use `get_settings()` for lazy loading and caching. Direct instantiation
    creates a new instance each time.
    """

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
    # Default will be set based on runtime environment in __init__
    litellm_proxy_host: str = Field(
        default="localhost",  # Base default, adjusted in __init__
        description="LiteLLM proxy server host",
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

    # Neo4j Configuration
    # Default will be set based on runtime environment in __init__
    neo4j_uri: str = Field(
        default="bolt://localhost:7687",  # Base default, adjusted in __init__
        description="Neo4j database URI (for Neo4j Desktop, typically bolt://localhost:7687)",
    )
    neo4j_username: str = Field(
        default="neo4j", description="Neo4j username"
    )
    neo4j_password: str = Field(
        default="admin123", description="Neo4j password"
    )
    neo4j_database: str = Field(
        default="knowledge", description="Neo4j database name"
    )
    neo4j_vector_index_name: str = Field(
        default="note_embeddings",
        description="Neo4j vector index name for note embeddings",
    )

    @staticmethod
    def get_runtime_aware_defaults(
        runtime_env: Optional[str] = None,
        **existing_kwargs
    ) -> dict:
        """
        Get runtime-aware default values for settings that weren't explicitly provided.
        
        This method applies defaults based on the runtime environment:
        - Container: Uses Docker service names and host.docker.internal
        - Local: Uses localhost
        
        **Precedence:** Only applies defaults if the setting wasn't provided in kwargs.
        This ensures manual overrides always take precedence.
        
        Args:
            runtime_env: Explicit runtime environment override ('container' or 'local').
                        If None, auto-detects using is_running_in_container().
            **existing_kwargs: Already provided kwargs (won't override these)
            
        Returns:
            Dictionary of default values to apply. Only includes settings that weren't
            already provided in existing_kwargs.
            
        Examples:
            ```python
            # Auto-detect
            defaults = Settings.get_runtime_aware_defaults()
            
            # Force container
            defaults = Settings.get_runtime_aware_defaults(runtime_env='container')
            
            # Won't override neo4j_uri if already provided
            defaults = Settings.get_runtime_aware_defaults(neo4j_uri='custom')
            # Result: defaults won't include neo4j_uri
            ```
        """
        defaults = {}
        
        # Determine runtime environment: explicit override > auto-detection
        if runtime_env is not None:
            is_container = runtime_env.lower() == 'container'
        else:
            is_container = is_running_in_container()
        
        # Neo4j URI defaults
        if "neo4j_uri" not in existing_kwargs:
            defaults["neo4j_uri"] = (
                "bolt://host.docker.internal:7687" if is_container
                else "bolt://localhost:7687"
            )
        
        # LiteLLM Proxy Host defaults
        if "litellm_proxy_host" not in existing_kwargs:
            defaults["litellm_proxy_host"] = (
                "llm-proxy" if is_container
                else "localhost"
            )
        
        return defaults

    def __init__(self, runtime_env: Optional[str] = None, **kwargs):
        """
        Initialize Settings with clear precedence order.
        
        See class docstring for detailed precedence order and usage examples.
        
        Args:
            runtime_env: Explicit runtime environment override ('container' or 'local').
                        If None, auto-detects using is_running_in_container().
                        This affects default values for neo4j_uri and litellm_proxy_host.
            **kwargs: Settings to override (e.g., neo4j_password='admin123', neo4j_uri='bolt://...')
        """
        # Store which values were manually overridden (highest priority)
        self._manual_overrides = set(kwargs.keys())
        
        # Apply runtime-aware defaults BEFORE Pydantic initialization
        # These will be used only if not provided via kwargs or env vars
        runtime_defaults = self.get_runtime_aware_defaults(
            runtime_env=runtime_env,
            **kwargs
        )
        kwargs.update(runtime_defaults)

        # Allow overriding openai_api_key via kwargs (useful for tests)
        openai_api_key_override = kwargs.pop("openai_api_key", None)

        # Initialize with Pydantic
        # Pydantic will: 1) Use kwargs (manual overrides), 2) Check env vars, 3) Use Field defaults
        # Our runtime-aware defaults are in kwargs, so they'll be used if no env var is set
        super().__init__(**kwargs)

        # Load OpenAI API key using shared secrets configuration
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
        
        # Log runtime environment detection
        # Use provided runtime_env or auto-detect
        if runtime_env is not None:
            detected_runtime = runtime_env.lower()
        else:
            detected_runtime = "container" if is_running_in_container() else "local"
        logger.debug(
            f"Settings initialized for {detected_runtime} runtime "
            f"(Neo4j: {self.neo4j_uri}, LiteLLM: {self.litellm_proxy_host})"
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


def get_settings(runtime_env: Optional[str] = None, **overrides) -> Settings:
    """
    Get the global settings instance (lazy loading with caching).
    
    **Precedence Order:** See Settings class docstring for full details.
    1. Manual overrides (kwargs) - HIGHEST PRIORITY
    2. Environment variables - handled automatically by Pydantic
    3. Runtime-aware defaults - based on runtime_env or auto-detection
    
    **Caching:** If no overrides or runtime_env provided, returns cached instance.
    Otherwise, creates a new instance (useful for tests or temporary overrides).

    Args:
        runtime_env: Explicit runtime environment override ('container' or 'local').
                    If None, auto-detects using is_running_in_container().
                    This affects default values for neo4j_uri and litellm_proxy_host.
        **overrides: Settings to override (e.g., neo4j_password="admin123", neo4j_uri="bolt://...")
                    If provided, creates a new Settings instance with overrides.
                    If not provided and instance exists, returns cached instance.

    Returns:
        Settings instance

    Examples:
        ```python
        # Auto-detect runtime (default behavior, uses cache)
        settings = get_settings()

        # Force container defaults even when running locally
        settings = get_settings(runtime_env='container')

        # Force local defaults even when running in container
        settings = get_settings(runtime_env='local')

        # Override specific settings (creates new instance)
        settings = get_settings(neo4j_password='admin123', neo4j_uri='bolt://custom:7687')

        # Combine runtime_env with overrides
        settings = get_settings(
            runtime_env='container',
            neo4j_password='admin123',
            neo4j_uri='bolt://custom:7687'
        )
        ```
    """
    global _settings
    if overrides or runtime_env is not None:
        # If overrides or runtime_env provided, create a new instance
        # This is useful for tests or when you want to override runtime detection
        override_keys = list(overrides.keys())
        if runtime_env is not None:
            override_keys.append('runtime_env')
        logger.debug(
            f"Creating Settings instance with overrides: {override_keys}"
        )
        return Settings(runtime_env=runtime_env, **overrides)
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
