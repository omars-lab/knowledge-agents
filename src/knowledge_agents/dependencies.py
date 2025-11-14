"""
Dependency injection container for the application.

This module provides a clean way to manage and inject dependencies throughout
the application without global state, lazy loading, or monkey-patching.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from openai import AsyncOpenAI, OpenAI

if TYPE_CHECKING:
    from .clients.openai import OpenAIClientManager
    from .clients.proxy_client import ProxyClientManager
    from .clients.vector_store import VectorStoreClientManager
    from .config.api_config import Settings

logger = logging.getLogger(__name__)


class Dependencies:
    """
    Dependency injection container.

    All dependencies are initialized once at app startup and passed explicitly
    to components that need them. This eliminates global state, lazy loading,
    and the need for monkey-patching in tests.
    """

    def __init__(self, settings: Settings, api_key: Optional[str] = None):
        """
        Initialize dependencies with the given settings and optional API key.

        All client managers are eagerly initialized to avoid lazy loading
        and eliminate circular dependency risks. Client managers only depend
        on Settings, so there's no circular dependency risk.

        Args:
            settings: Application settings instance
            api_key: Optional API key from request header. If provided, overrides
                    settings.openai_api_key for client managers.
        """
        self.settings = settings
        self.api_key = api_key or settings.openai_api_key

        # Eagerly initialize all client managers
        # Using late imports here is safe because:
        # 1. __init__ is called at runtime, not import time
        # 2. Client managers only depend on Settings (no cycle)
        # 3. This eliminates the need for lazy loading in properties
        from .clients.openai import OpenAIClientManager
        from .clients.proxy_client import ProxyClientManager
        from .clients.vector_store import VectorStoreClientManager

        self._proxy_client_manager: ProxyClientManager = ProxyClientManager(
            settings=settings, api_key=self.api_key
        )
        self._vector_store_client_manager: VectorStoreClientManager = (
            VectorStoreClientManager(settings=settings)
        )
        self._openai_client_manager: OpenAIClientManager = OpenAIClientManager(
            settings=settings, api_key=self.api_key
        )

    @property
    def proxy_client_manager(self) -> ProxyClientManager:
        """Get the proxy client manager."""
        return self._proxy_client_manager

    @property
    def vector_store_client_manager(self) -> VectorStoreClientManager:
        """Get the vector store client manager."""
        return self._vector_store_client_manager

    @property
    def openai_client_manager(self) -> OpenAIClientManager:
        """Get the OpenAI client manager."""
        return self._openai_client_manager

    @property
    def openai_client(self) -> AsyncOpenAI:
        """Get the OpenAI async client."""
        return self.openai_client_manager.get_client()


# Global dependency container - initialized at app startup
_dependencies: Optional[Dependencies] = None


def get_dependencies() -> Dependencies:
    """
    Get the global dependency container.

    This should only be called after initialize_dependencies() has been called.
    In production code, dependencies should be passed explicitly rather than
    using this global accessor.

    Returns:
        Dependencies instance

    Raises:
        RuntimeError: If dependencies haven't been initialized
    """
    global _dependencies
    if _dependencies is None:
        raise RuntimeError(
            "Dependencies not initialized. Call initialize_dependencies() first, "
            "or pass dependencies explicitly to components."
        )
    return _dependencies


def initialize_dependencies(settings: Settings, api_key: Optional[str] = None) -> Dependencies:
    """
    Initialize the global dependency container.

    This should be called once at application startup.

    Args:
        settings: Application settings instance
        api_key: Optional API key from request header. If provided, overrides
                settings.openai_api_key for client managers.

    Returns:
        Initialized Dependencies instance
    """
    global _dependencies
    _dependencies = Dependencies(settings=settings, api_key=api_key)
    logger.info("Dependencies initialized")
    return _dependencies


def reset_dependencies() -> None:
    """
    Reset the global dependency container (useful for testing).

    This clears the global state, allowing tests to create fresh instances.
    """
    global _dependencies
    _dependencies = None
    logger.debug("Dependencies reset")
