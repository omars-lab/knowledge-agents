"""
Unit tests for OpenAIClientManager.

Tests verify that:
1. OpenAIClientManager accepts Settings in constructor
2. AsyncOpenAI client is created with correct configuration
3. API key validation works
4. Client caching works
"""
from unittest.mock import Mock, patch

import pytest

from knowledge_agents.clients.openai import OpenAIClientManager
from knowledge_agents.config.api_config import Settings


class TestOpenAIClientManager:
    """Test OpenAIClientManager with dependency injection."""

    def test_initialization_with_settings(self):
        """Test that OpenAIClientManager accepts Settings in constructor."""
        settings = Settings(
            openai_api_key="sk-test-key-123",
            environment="test",
            litellm_proxy_host="test-host",
            litellm_proxy_port=4000,
        )

        manager = OpenAIClientManager(settings=settings)

        assert manager.settings is settings
        assert manager._client is None  # Not created yet

    @patch("knowledge_agents.clients.openai.AsyncOpenAI")
    def test_get_client_creates_client_with_correct_config(self, MockAsyncOpenAI):
        """Test that get_client creates AsyncOpenAI client with correct configuration."""
        settings = Settings(
            openai_api_key="sk-test-key-123",
            litellm_proxy_host="test-host",
            litellm_proxy_port=4000,
        )

        mock_client = Mock()
        MockAsyncOpenAI.return_value = mock_client

        manager = OpenAIClientManager(settings=settings)
        client = manager.get_client()

        # Verify AsyncOpenAI was called with correct parameters
        MockAsyncOpenAI.assert_called_once()
        call_kwargs = MockAsyncOpenAI.call_args[1]
        assert call_kwargs["api_key"] == "sk-test-key-123"
        assert call_kwargs["base_url"] == "http://test-host:4000"
        assert call_kwargs["timeout"] == 30.0

        # Verify client is cached
        assert manager._client is mock_client
        assert client is mock_client

        # Second call should return cached client
        client2 = manager.get_client()
        assert client2 is client
        assert MockAsyncOpenAI.call_count == 1  # Not called again

    def test_get_client_raises_without_api_key(self):
        """Test that get_client raises ValueError if API key is missing."""
        settings = Settings(
            environment="test",
        )
        # Explicitly set to None to test error handling
        settings.openai_api_key = None

        manager = OpenAIClientManager(settings=settings)

        with pytest.raises(ValueError, match="OpenAI API key is required"):
            manager.get_client()

    def test_reset_client(self):
        """Test that reset_client clears cached client."""
        settings = Settings(
            openai_api_key="sk-test-key",
            litellm_proxy_host="host",
            litellm_proxy_port=4000,
        )

        manager = OpenAIClientManager(settings=settings)

        with patch("knowledge_agents.clients.openai.AsyncOpenAI"):
            manager.get_client()
            assert manager._client is not None

        manager.reset_client()
        assert manager._client is None

    def test_independent_managers(self):
        """Test that multiple OpenAIClientManager instances are independent."""
        settings1 = Settings(
            openai_api_key="sk-key-1",
            litellm_proxy_host="host1",
            litellm_proxy_port=4000,
        )
        settings2 = Settings(
            openai_api_key="sk-key-2",
            litellm_proxy_host="host2",
            litellm_proxy_port=5000,
        )

        manager1 = OpenAIClientManager(settings=settings1)
        manager2 = OpenAIClientManager(settings=settings2)

        assert manager1.settings is settings1
        assert manager2.settings is settings2
        assert manager1 is not manager2
