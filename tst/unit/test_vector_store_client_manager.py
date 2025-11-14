"""
Unit tests for VectorStoreClientManager.

Tests verify that:
1. VectorStoreClientManager accepts Settings in constructor
2. Qdrant client is created with correct configuration
3. Collection management works
4. Client caching works
"""
from unittest.mock import MagicMock, Mock, patch

import pytest

from knowledge_agents.clients.vector_store import VectorStoreClientManager
from knowledge_agents.config.api_config import Settings


class TestVectorStoreClientManager:
    """Test VectorStoreClientManager with dependency injection."""

    def test_initialization_with_settings(self):
        """Test that VectorStoreClientManager accepts Settings in constructor."""
        settings = Settings(
            qdrant_host="test-host",
            qdrant_port=6333,
            qdrant_collection_name="test-collection",
        )

        manager = VectorStoreClientManager(settings=settings)

        assert manager.settings is settings
        assert manager._client is None  # Not created yet

    @patch("knowledge_agents.clients.vector_store.qdrant_client.QdrantClient")
    def test_get_client_creates_client_with_correct_config(self, MockQdrantClient):
        """Test that get_client creates QdrantClient with correct configuration."""
        settings = Settings(
            qdrant_host="test-host",
            qdrant_port=6333,
        )

        mock_client = Mock()
        MockQdrantClient.return_value = mock_client

        manager = VectorStoreClientManager(settings=settings)
        client = manager.get_client()

        # Verify QdrantClient was called with correct parameters
        MockQdrantClient.assert_called_once_with(
            host="test-host",
            port=6333,
        )

        # Verify client is cached
        assert manager._client is mock_client
        assert client is mock_client

        # Second call should return cached client
        client2 = manager.get_client()
        assert client2 is client
        assert MockQdrantClient.call_count == 1  # Not called again

    def test_reset_client(self):
        """Test that reset_client clears cached client."""
        settings = Settings(
            qdrant_host="host",
            qdrant_port=6333,
        )

        manager = VectorStoreClientManager(settings=settings)

        with patch("knowledge_agents.clients.vector_store.qdrant_client.QdrantClient"):
            manager.get_client()
            assert manager._client is not None

        manager.reset_client()
        assert manager._client is None

    @patch("knowledge_agents.clients.vector_store.qdrant_client.QdrantClient")
    @patch.object(Settings, "get_embedding_size")
    def test_ensure_collection_creates_collection(
        self, mock_get_embedding_size, MockQdrantClient
    ):
        """Test that ensure_collection creates collection if it doesn't exist."""
        settings = Settings(
            qdrant_host="host",
            qdrant_port=6333,
            qdrant_collection_name="default-collection",
        )
        mock_get_embedding_size.return_value = 1536

        mock_client = Mock()
        mock_collections = Mock()
        mock_collections.collections = []  # No collections exist
        mock_client.get_collections.return_value = mock_collections
        mock_client.create_collection = Mock()
        MockQdrantClient.return_value = mock_client

        manager = VectorStoreClientManager(settings=settings)
        manager.ensure_collection()

        # Verify collection was created
        mock_client.create_collection.assert_called_once()
        call_kwargs = mock_client.create_collection.call_args[1]
        assert call_kwargs["collection_name"] == "default-collection"
        assert call_kwargs["vectors_config"].size == 1536

    @patch("knowledge_agents.clients.vector_store.qdrant_client.QdrantClient")
    def test_ensure_collection_uses_custom_name_and_size(self, MockQdrantClient):
        """Test that ensure_collection uses custom collection name and vector size."""
        settings = Settings(
            qdrant_host="host",
            qdrant_port=6333,
            qdrant_collection_name="default-collection",
        )

        mock_client = Mock()
        mock_collections = Mock()
        mock_collections.collections = []
        mock_client.get_collections.return_value = mock_collections
        mock_client.create_collection = Mock()
        MockQdrantClient.return_value = mock_client

        manager = VectorStoreClientManager(settings=settings)
        manager.ensure_collection(collection_name="custom-collection", vector_size=4096)

        # Verify collection was created with custom parameters
        mock_client.create_collection.assert_called_once()
        call_kwargs = mock_client.create_collection.call_args[1]
        assert call_kwargs["collection_name"] == "custom-collection"
        assert call_kwargs["vectors_config"].size == 4096

    @patch("knowledge_agents.clients.vector_store.qdrant_client.QdrantClient")
    def test_ensure_collection_skips_existing_collection(self, MockQdrantClient):
        """Test that ensure_collection skips creation if collection exists."""
        settings = Settings(
            qdrant_host="host",
            qdrant_port=6333,
            qdrant_collection_name="existing-collection",
        )

        mock_client = Mock()
        mock_collection = Mock()
        mock_collection.name = "existing-collection"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]  # Collection exists
        mock_client.get_collections.return_value = mock_collections
        mock_client.create_collection = Mock()
        MockQdrantClient.return_value = mock_client

        manager = VectorStoreClientManager(settings=settings)
        manager.ensure_collection()

        # Verify collection was NOT created
        mock_client.create_collection.assert_not_called()

    @patch("knowledge_agents.clients.vector_store.qdrant_client.QdrantClient")
    @patch.object(Settings, "get_embedding_size")
    def test_ensure_collection_recreates_with_recreate_flag(
        self, mock_get_embedding_size, MockQdrantClient
    ):
        """Test that ensure_collection recreates collection when recreate=True."""
        settings = Settings(
            qdrant_host="host",
            qdrant_port=6333,
            qdrant_collection_name="existing-collection",
        )
        mock_get_embedding_size.return_value = 1536

        mock_client = Mock()
        mock_collection = Mock()
        mock_collection.name = "existing-collection"
        mock_collections = Mock()
        mock_collections.collections = [mock_collection]
        mock_client.get_collections.return_value = mock_collections
        mock_client.delete_collection = Mock()
        mock_client.create_collection = Mock()
        MockQdrantClient.return_value = mock_client

        manager = VectorStoreClientManager(settings=settings)
        manager.ensure_collection(recreate=True)

        # Verify collection was deleted and recreated
        mock_client.delete_collection.assert_called_once_with("existing-collection")
        mock_client.create_collection.assert_called_once()

    def test_independent_managers(self):
        """Test that multiple VectorStoreClientManager instances are independent."""
        settings1 = Settings(
            qdrant_host="host1",
            qdrant_port=6333,
        )
        settings2 = Settings(
            qdrant_host="host2",
            qdrant_port=6334,
        )

        manager1 = VectorStoreClientManager(settings=settings1)
        manager2 = VectorStoreClientManager(settings=settings2)

        assert manager1.settings is settings1
        assert manager2.settings is settings2
        assert manager1 is not manager2
