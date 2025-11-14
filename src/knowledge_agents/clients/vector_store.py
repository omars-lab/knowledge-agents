"""
Qdrant vector store client configuration and management.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import qdrant_client
from qdrant_client.models import Distance, VectorParams

if TYPE_CHECKING:
    from ..config.api_config import Settings

logger = logging.getLogger(__name__)


class VectorStoreClientManager:
    """
    Manages Qdrant vector store client instances with proper configuration.

    Uses explicit dependency injection - Settings must be provided at initialization.
    This eliminates global state, lazy loading, and the need for monkey-patching.
    """

    def __init__(self, settings: "Settings"):
        """
        Initialize the vector store client manager.

        Args:
            settings: Application settings instance (must be provided explicitly)
        """
        self.settings = settings
        self._client: Optional[qdrant_client.QdrantClient] = None

    def get_client(self) -> qdrant_client.QdrantClient:
        """Get or create Qdrant client with proper configuration"""
        if self._client is None:
            # Get Qdrant connection settings from settings (explicitly provided at initialization)
            host = self.settings.qdrant_host
            port = self.settings.qdrant_port

            logger.info(f"Creating Qdrant client connecting to: {host}:{port}")

            # Create client with configuration
            self._client = qdrant_client.QdrantClient(
                host=host,
                port=port,
            )

        return self._client

    def reset_client(self):
        """Reset the client (useful for testing or reconfiguration)"""
        self._client = None

    def ensure_collection(
        self,
        collection_name: Optional[str] = None,
        vector_size: Optional[int] = None,
        recreate: bool = False,
    ) -> None:
        """
        Ensure a collection exists, create if it doesn't.

        Args:
            collection_name: Name of the collection (defaults to config value)
            vector_size: Size of vectors (defaults to config value)
            recreate: If True, delete and recreate existing collection
        """
        client = self.get_client()

        collection_name = collection_name or self.settings.qdrant_collection_name
        # Use dynamic embedding size based on configured model
        if vector_size is None:
            vector_size = self.settings.get_embedding_size()

        try:
            # Check if collection exists
            collections = client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if collection_name in collection_names:
                if recreate:
                    client.delete_collection(collection_name)
                else:
                    return  # Collection already exists

            logger.info(
                f"Creating Qdrant collection '{collection_name}' with vector size {vector_size}"
            )

            # Create collection
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )
        except Exception as e:
            raise ValueError(
                f"Failed to ensure collection '{collection_name}': {e}"
            ) from e


# NO global instances - created via Dependencies container!
# NO get_vector_store_client() function - use Dependencies.vector_store_client_manager.get_client()
