"""
Unit tests for ProxyClientManager.

Tests verify that:
1. ProxyClientManager accepts Settings in constructor
2. Clients are created with correct configuration
3. API key validation works
4. Client caching and reset works
"""
import os
from unittest.mock import MagicMock, Mock, patch

import pytest

from knowledge_agents.clients.proxy_client import ProxyClientManager
from knowledge_agents.config.api_config import Settings


class TestProxyClientManager:
    """Test ProxyClientManager with dependency injection."""

    def test_initialization_with_settings(self):
        """Test that ProxyClientManager accepts Settings in constructor."""
        settings = Settings(
            openai_api_key="sk-test-key-123",
            environment="test",
            litellm_proxy_host="test-host",
            litellm_proxy_port=4000,
        )

        manager = ProxyClientManager(settings=settings)

        assert manager.settings is settings
        assert manager._client is None  # Not created yet
        assert manager._async_client is None

    def test_get_proxy_base_url(self):
        """Test that _get_proxy_base_url uses settings correctly."""
        settings = Settings(
            openai_api_key="sk-test-key",
            litellm_proxy_host="proxy-host",
            litellm_proxy_port=9999,
        )

        manager = ProxyClientManager(settings=settings)
        base_url = manager._get_proxy_base_url()

        assert base_url == "http://proxy-host:9999"

    def test_get_proxy_base_url_with_env_override(self):
        """Test that environment variables override settings."""
        settings = Settings(
            openai_api_key="sk-test-key",
            litellm_proxy_host="settings-host",
            litellm_proxy_port=4000,
        )

        manager = ProxyClientManager(settings=settings)

        with patch.dict(
            os.environ, {"LITELLM_PROXY_HOST": "env-host", "LITELLM_PROXY_PORT": "8888"}
        ):
            base_url = manager._get_proxy_base_url()
            assert base_url == "http://env-host:8888"

    @patch("knowledge_agents.clients.proxy_client.OpenAI")
    def test_get_client_creates_client_with_correct_config(self, MockOpenAI):
        """Test that get_client creates OpenAI client with correct configuration."""
        settings = Settings(
            openai_api_key="sk-test-key-123",
            litellm_proxy_host="test-host",
            litellm_proxy_port=4000,
        )

        mock_client = Mock()
        mock_client.base_url = "http://test-host:4000/v1"  # Set base_url attribute
        MockOpenAI.return_value = mock_client

        manager = ProxyClientManager(settings=settings)
        client = manager.get_client()

        # Verify OpenAI was called with correct parameters
        MockOpenAI.assert_called_once()
        call_kwargs = MockOpenAI.call_args[1]
        assert call_kwargs["api_key"] == "sk-test-key-123"
        assert call_kwargs["base_url"] == "http://test-host:4000/v1"
        assert call_kwargs["timeout"] == 300.0

        # Verify client is cached
        assert manager._client is mock_client
        assert client is mock_client

        # Second call should return cached client
        client2 = manager.get_client()
        assert client2 is client
        assert MockOpenAI.call_count == 1  # Not called again

    def test_get_client_raises_without_api_key(self):
        """Test that get_client raises ValueError if API key is missing."""
        # Create settings without API key - Settings.__init__ might set a default
        # So we need to explicitly set it to None after creation
        settings = Settings(
            environment="test",
        )
        # Explicitly set to None to test error handling
        settings.openai_api_key = None

        manager = ProxyClientManager(settings=settings)

        with pytest.raises(ValueError, match="OpenAI API key is required"):
            manager.get_client()

    @patch("knowledge_agents.clients.proxy_client.OpenAI")
    def test_get_client_resets_on_api_key_change(self, MockOpenAI):
        """Test that client is reset when API key changes."""
        settings = Settings(
            openai_api_key="sk-key-1",
            litellm_proxy_host="host",
            litellm_proxy_port=4000,
        )

        mock_client1 = Mock()
        mock_client1.base_url = "http://host:4000/v1"
        mock_client2 = Mock()
        mock_client2.base_url = "http://host:4000/v1"
        MockOpenAI.side_effect = [mock_client1, mock_client2]

        manager = ProxyClientManager(settings=settings)
        client1 = manager.get_client()

        # Change API key in settings
        settings.openai_api_key = "sk-key-2"

        # Get client again - should create new client
        client2 = manager.get_client()

        assert MockOpenAI.call_count == 2  # Called twice
        assert client1 is not client2

    @patch("knowledge_agents.clients.proxy_client.AsyncOpenAI")
    def test_get_async_client_creates_client_with_correct_config(self, MockAsyncOpenAI):
        """Test that get_async_client creates AsyncOpenAI client correctly."""
        settings = Settings(
            openai_api_key="sk-test-key-123",
            litellm_proxy_host="test-host",
            litellm_proxy_port=4000,
        )

        mock_client = Mock()
        MockAsyncOpenAI.return_value = mock_client

        manager = ProxyClientManager(settings=settings)
        client = manager.get_async_client()

        # Verify AsyncOpenAI was called with correct parameters
        MockAsyncOpenAI.assert_called_once()
        call_kwargs = MockAsyncOpenAI.call_args[1]
        assert call_kwargs["api_key"] == "sk-test-key-123"
        assert call_kwargs["base_url"] == "http://test-host:4000/v1"
        assert call_kwargs["timeout"] == 300.0

        assert manager._async_client is mock_client
        assert client is mock_client

    def test_reset_client(self):
        """Test that reset_client clears cached clients."""
        settings = Settings(
            openai_api_key="sk-test-key",
            litellm_proxy_host="host",
            litellm_proxy_port=4000,
        )

        manager = ProxyClientManager(settings=settings)

        mock_client = Mock()
        mock_client.base_url = "http://host:4000/v1"
        with patch(
            "knowledge_agents.clients.proxy_client.OpenAI", return_value=mock_client
        ):
            manager.get_client()
            assert manager._client is not None

        manager.reset_client()

        assert manager._client is None
        assert manager._async_client is None
        assert manager._last_base_url is None
        assert manager._last_api_key is None

    def test_independent_managers(self):
        """Test that multiple ProxyClientManager instances are independent."""
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

        manager1 = ProxyClientManager(settings=settings1)
        manager2 = ProxyClientManager(settings=settings2)

        assert manager1.settings is settings1
        assert manager2.settings is settings2
        assert manager1 is not manager2
