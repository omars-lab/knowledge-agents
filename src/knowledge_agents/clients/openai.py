"""
OpenAI client configuration and management
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from openai import AsyncOpenAI

if TYPE_CHECKING:
    from ..config.api_config import Settings

logger = logging.getLogger(__name__)


class OpenAIClientManager:
    """
    Manages OpenAI client instances with proper configuration.

    Uses explicit dependency injection - Settings must be provided at initialization.
    This eliminates global state, lazy loading, and the need for monkey-patching.
    """

    def __init__(self, settings: "Settings", api_key: Optional[str] = None):
        """
        Initialize the OpenAI client manager.

        Args:
            settings: Application settings instance (must be provided explicitly)
            api_key: Optional API key. If provided, overrides settings.openai_api_key
        """
        self.settings = settings
        self.api_key = api_key or settings.openai_api_key
        self._client: Optional[AsyncOpenAI] = None

    def get_client(self) -> AsyncOpenAI:
        """Get or create OpenAI client with proper configuration"""
        if self._client is None:
            # Get API key from parameter or settings
            api_key = self.api_key
            if not api_key:
                raise ValueError(
                    "OpenAI API key is required - must be provided via Settings at initialization"
                )

            # Configure AsyncOpenAI to use LiteLLM proxy
            # The proxy exposes an OpenAI-compatible API at http://llm-proxy:4000
            proxy_base_url = f"http://{self.settings.litellm_proxy_host}:{self.settings.litellm_proxy_port}"

            logger.info(
                f"Creating OpenAI client pointing to: {proxy_base_url} with API key: {api_key[:10]}..."
            )

            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=proxy_base_url,
                timeout=30.0,  # 30 second timeout
            )

        return self._client

    def reset_client(self):
        """Reset the client (useful for testing or reconfiguration)"""
        self._client = None


# NO global instances - created via Dependencies container!
# NO get_openai_client() function - use Dependencies.openai_client
