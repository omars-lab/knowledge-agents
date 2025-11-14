"""
Proxy client configuration for LiteLLM proxy server.

This module provides clients that connect to the LiteLLM proxy server
instead of directly to OpenAI/LM Studio.
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Optional

from openai import AsyncOpenAI, OpenAI

if TYPE_CHECKING:
    from ..config.api_config import Settings

logger = logging.getLogger(__name__)


class ProxyClientManager:
    """
    Manages OpenAI client instances configured to use LiteLLM proxy.

    Uses explicit dependency injection - Settings must be provided at initialization.
    This eliminates global state, lazy loading, and the need for monkey-patching.
    """

    def __init__(self, settings: "Settings", api_key: Optional[str] = None):
        """
        Initialize the proxy client manager.

        Args:
            settings: Application settings instance (must be provided explicitly)
            api_key: Optional API key. If provided, overrides settings.openai_api_key
        """
        self.settings = settings
        self.api_key = api_key or settings.openai_api_key
        self._client: Optional[OpenAI] = None
        self._async_client: Optional[AsyncOpenAI] = None
        self._last_base_url: Optional[str] = None
        self._last_api_key: Optional[str] = None

    def _get_proxy_base_url(self) -> str:
        """
        Get the LiteLLM proxy base URL from settings.

        Returns:
            Proxy server base URL (e.g., "http://llm-proxy:4000")
        """
        host = os.getenv("LITELLM_PROXY_HOST", self.settings.litellm_proxy_host)
        port = os.getenv("LITELLM_PROXY_PORT", str(self.settings.litellm_proxy_port))
        return f"http://{host}:{port}"

    def get_client(self) -> OpenAI:
        """
        Get or create synchronous OpenAI client configured for proxy.

        Returns:
            OpenAI client instance pointing to proxy
        """
        proxy_url = self._get_proxy_base_url()
        current_base_url = f"{proxy_url}/v1"

        # Get API key from parameter or settings
        api_key = self.api_key
        if not api_key:
            raise ValueError(
                "OpenAI API key is required for proxy client. "
                "Provide it via Settings at initialization."
            )

        # Reset client if base_url or API key changed
        current_api_key = api_key
        if self._client is not None:
            if self._last_base_url != current_base_url:
                logger.info(
                    f"Proxy URL changed from {self._last_base_url} to {current_base_url}, resetting client"
                )
                self._client = None
            elif self._last_api_key != current_api_key:
                logger.info(f"API key changed, resetting client")
                self._client = None

        if self._client is None:
            # Store current values for change detection
            self._last_api_key = current_api_key
            self._last_base_url = current_base_url

            # Log warning if API key doesn't start with "sk-"
            if api_key and not api_key.startswith("sk-"):
                logger.warning(
                    f"API key does not start with 'sk-': {api_key[:20]}... "
                    f"(length: {len(api_key)}). This may be a non-standard key format."
                )

            logger.info(
                f"Creating proxy client pointing to: {current_base_url} with API key: {api_key[:10]}..."
            )

            # Create OpenAI client with explicit base_url pointing to LiteLLM proxy
            self._client = OpenAI(
                api_key=api_key,
                base_url=current_base_url,
                timeout=300.0,
            )

            # Verify base_url was set correctly
            if hasattr(self._client, "base_url"):
                actual_base_url = str(self._client.base_url)
                if not actual_base_url.startswith(proxy_url):
                    logger.error(
                        f"WARNING: base_url mismatch! Expected {proxy_url}, got {actual_base_url}"
                    )
                    self._client = None
                    raise ValueError(
                        f"Proxy client base_url mismatch: expected {proxy_url}, got {actual_base_url}"
                    )

        return self._client

    def get_async_client(self) -> AsyncOpenAI:
        """
        Get or create asynchronous OpenAI client configured for proxy.

        Returns:
            AsyncOpenAI client instance pointing to proxy
        """
        proxy_url = self._get_proxy_base_url()
        current_base_url = f"{proxy_url}/v1"

        # Get API key from parameter or settings
        api_key = self.api_key
        if not api_key:
            raise ValueError(
                "OpenAI API key is required for proxy client. "
                "Provide it via Settings at initialization."
            )

        # Reset if base_url or API key changed
        current_api_key = api_key
        if self._async_client is not None:
            if self._last_base_url != current_base_url:
                logger.info(f"Proxy URL changed, resetting async client")
                self._async_client = None
            elif self._last_api_key != current_api_key:
                logger.info(f"API key changed, resetting async client")
                self._async_client = None

        if self._async_client is None:
            # Store current values for change detection
            self._last_api_key = current_api_key
            self._last_base_url = current_base_url

            # Log warning if API key doesn't start with "sk-"
            if api_key and not api_key.startswith("sk-"):
                logger.warning(
                    f"API key does not start with 'sk-': {api_key[:20]}... "
                    f"(length: {len(api_key)}). This may be a non-standard key format."
                )

            logger.info(
                f"Creating async proxy client pointing to: {current_base_url} with API key: {api_key[:10]}..."
            )

            # Create AsyncOpenAI client
            self._async_client = AsyncOpenAI(
                api_key=api_key,
                base_url=current_base_url,
                timeout=300.0,
            )

        return self._async_client

    def reset_client(self):
        """Reset the clients (useful for testing or reconfiguration)"""
        self._client = None
        self._async_client = None
        self._last_base_url = None
        self._last_api_key = None


# NO global instances - created via Dependencies container!
# NO get_proxy_client() function - use Dependencies.proxy_client_manager.get_client()
