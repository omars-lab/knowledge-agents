"""
Unit tests for dependency injection container.

Tests verify that:
1. Dependencies are initialized correctly
2. Client managers are created with proper settings
3. Lazy initialization works correctly
4. Test instances can be created independently
"""
from unittest.mock import MagicMock, Mock, patch

import pytest

from knowledge_agents.config.api_config import Settings
from knowledge_agents.dependencies import (
    Dependencies,
    get_dependencies,
    initialize_dependencies,
    reset_dependencies,
)


class TestDependencies:
    """Test the Dependencies container class."""

    def test_dependencies_initialization(self):
        """Test that Dependencies can be initialized with Settings."""
        settings = Settings(
            openai_api_key="sk-test-key-123",
            environment="test",
        )

        deps = Dependencies(settings=settings)

        assert deps.settings is settings
        assert deps.settings.openai_api_key == "sk-test-key-123"
        assert deps._proxy_client_manager is None  # Lazy initialization
        assert deps._vector_store_client_manager is None
        assert deps._openai_client_manager is None

    def test_proxy_client_manager_lazy_initialization(self):
        """Test that proxy_client_manager is created lazily with correct settings."""
        settings = Settings(
            openai_api_key="sk-test-key-123",
            environment="test",
        )

        deps = Dependencies(settings=settings)

        # Access property to trigger lazy initialization
        # Patch where the import happens (inside the property)
        with patch(
            "knowledge_agents.clients.proxy_client.ProxyClientManager"
        ) as MockProxyManager:
            mock_manager = Mock()
            MockProxyManager.return_value = mock_manager

            manager = deps.proxy_client_manager

            # Verify ProxyClientManager was instantiated with correct settings
            MockProxyManager.assert_called_once_with(settings=settings)
            assert manager is mock_manager
            assert deps._proxy_client_manager is mock_manager

            # Second access should return cached instance
            manager2 = deps.proxy_client_manager
            assert manager2 is manager
            MockProxyManager.assert_called_once()  # Not called again

    def test_vector_store_client_manager_lazy_initialization(self):
        """Test that vector_store_client_manager is created lazily with correct settings."""
        settings = Settings(
            openai_api_key="sk-test-key-123",
            environment="test",
        )

        deps = Dependencies(settings=settings)

        with patch(
            "knowledge_agents.clients.vector_store.VectorStoreClientManager"
        ) as MockVectorManager:
            mock_manager = Mock()
            MockVectorManager.return_value = mock_manager

            manager = deps.vector_store_client_manager

            # Verify VectorStoreClientManager was instantiated with correct settings
            MockVectorManager.assert_called_once_with(settings=settings)
            assert manager is mock_manager
            assert deps._vector_store_client_manager is mock_manager

    def test_openai_client_lazy_initialization(self):
        """Test that openai_client is created lazily with correct settings."""
        settings = Settings(
            openai_api_key="sk-test-key-123",
            environment="test",
        )

        deps = Dependencies(settings=settings)

        with patch(
            "knowledge_agents.clients.openai.OpenAIClientManager"
        ) as MockOpenAIManager:
            mock_client = Mock()
            mock_manager = Mock()
            mock_manager.get_client.return_value = mock_client
            MockOpenAIManager.return_value = mock_manager

            client = deps.openai_client

            # Verify OpenAIClientManager was instantiated with correct settings
            MockOpenAIManager.assert_called_once_with(settings=settings)
            mock_manager.get_client.assert_called_once()
            assert client is mock_client
            assert deps._openai_client_manager is mock_manager

    def test_dependencies_use_settings_from_initialization(self):
        """Test that all client managers use the settings from initialization."""
        settings = Settings(
            openai_api_key="sk-test-key-123",
            environment="test",
            litellm_proxy_host="test-host",
            litellm_proxy_port=9999,
        )

        deps = Dependencies(settings=settings)

        # Verify settings are stored correctly
        assert deps.settings.openai_api_key == "sk-test-key-123"
        assert deps.settings.litellm_proxy_host == "test-host"
        assert deps.settings.litellm_proxy_port == 9999

    def test_independent_dependencies_instances(self):
        """Test that multiple Dependencies instances are independent."""
        settings1 = Settings(
            openai_api_key="sk-test-key-1",
            environment="test",
        )
        settings2 = Settings(
            openai_api_key="sk-test-key-2",
            environment="test",
        )

        deps1 = Dependencies(settings=settings1)
        deps2 = Dependencies(settings=settings2)

        assert deps1.settings is settings1
        assert deps2.settings is settings2
        assert deps1.settings.openai_api_key == "sk-test-key-1"
        assert deps2.settings.openai_api_key == "sk-test-key-2"
        assert deps1 is not deps2


class TestGlobalDependenciesFunctions:
    """Test global dependency management functions."""

    def test_initialize_dependencies(self):
        """Test that initialize_dependencies creates global instance."""
        reset_dependencies()  # Ensure clean state

        settings = Settings(
            openai_api_key="sk-test-key-123",
            environment="test",
        )

        deps = initialize_dependencies(settings)

        assert deps.settings is settings
        assert get_dependencies() is deps

        reset_dependencies()  # Cleanup

    def test_get_dependencies_before_initialization_raises(self):
        """Test that get_dependencies raises RuntimeError if not initialized."""
        reset_dependencies()  # Ensure clean state

        with pytest.raises(RuntimeError, match="Dependencies not initialized"):
            get_dependencies()

    def test_get_dependencies_after_initialization(self):
        """Test that get_dependencies returns initialized instance."""
        reset_dependencies()  # Ensure clean state

        settings = Settings(
            openai_api_key="sk-test-key-123",
            environment="test",
        )

        deps = initialize_dependencies(settings)
        retrieved_deps = get_dependencies()

        assert retrieved_deps is deps

        reset_dependencies()  # Cleanup

    def test_reset_dependencies(self):
        """Test that reset_dependencies clears global state."""
        settings = Settings(
            openai_api_key="sk-test-key-123",
            environment="test",
        )

        initialize_dependencies(settings)
        assert get_dependencies() is not None

        reset_dependencies()

        with pytest.raises(RuntimeError, match="Dependencies not initialized"):
            get_dependencies()

    def test_multiple_initializations_override(self):
        """Test that multiple calls to initialize_dependencies override previous instance."""
        reset_dependencies()  # Ensure clean state

        settings1 = Settings(
            openai_api_key="sk-test-key-1",
            environment="test",
        )
        settings2 = Settings(
            openai_api_key="sk-test-key-2",
            environment="test",
        )

        deps1 = initialize_dependencies(settings1)
        assert get_dependencies().settings.openai_api_key == "sk-test-key-1"

        deps2 = initialize_dependencies(settings2)
        assert get_dependencies().settings.openai_api_key == "sk-test-key-2"
        assert deps1 is not deps2  # New instance created

        reset_dependencies()  # Cleanup


class TestDependenciesWithMockClients:
    """Test Dependencies with mocked client managers to verify integration."""

    @patch("knowledge_agents.clients.openai.OpenAIClientManager")
    @patch("knowledge_agents.clients.vector_store.VectorStoreClientManager")
    @patch("knowledge_agents.clients.proxy_client.ProxyClientManager")
    def test_all_clients_initialized_with_settings(
        self,
        MockProxyManager,
        MockVectorManager,
        MockOpenAIManager,
    ):
        """Test that all client managers receive the correct settings."""
        settings = Settings(
            openai_api_key="sk-test-key-123",
            environment="test",
        )

        mock_proxy = Mock()
        MockProxyManager.return_value = mock_proxy

        mock_vector = Mock()
        MockVectorManager.return_value = mock_vector

        mock_openai_manager = Mock()
        mock_openai_client = Mock()
        mock_openai_manager.get_client.return_value = mock_openai_client
        MockOpenAIManager.return_value = mock_openai_manager

        deps = Dependencies(settings=settings)

        # Access all properties to trigger initialization
        proxy_manager = deps.proxy_client_manager
        vector_manager = deps.vector_store_client_manager
        openai_client = deps.openai_client

        # Verify all were called with correct settings
        MockProxyManager.assert_called_once_with(settings=settings)
        MockVectorManager.assert_called_once_with(settings=settings)
        MockOpenAIManager.assert_called_once_with(settings=settings)

        # Verify instances are correct
        assert proxy_manager is mock_proxy
        assert vector_manager is mock_vector
        assert openai_client is mock_openai_client
